#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一条命令：Markdown 中间稿 → 成品 docx（含 4 个 XML 补丁 + 自检）。

## 为什么要有这个脚本

`edsdk.py` 是个 **CLI**，每次调用都要**重启一个 Python 进程** —— 实测启动 **1.0 秒**、
真正通信只有 **0.15 秒**。原来整条流程拆成 30+ 次调用（光 26 次插空段就 31 秒），
而且**每一步都要主 Agent 参与一轮决策**（读上下文 → 想 → 写），往返成本远大于计算成本。

本脚本把「建文档 → 写内容 → 插空段 → 页码 → 保存 → 4 个补丁」**串在同一个进程里**：
进程只启一次、端点只发现一次、Agent 只参与一次。

## 用法

    python build_docx.py 中间稿.md "E:/.../2026-09-24 标题.docx"
    python build_docx.py 中间稿.md 输出.docx --no-patch     # 只生成，不打补丁
    python build_docx.py 中间稿.md 输出.docx --keep-open    # 不关编辑器实例
    python build_docx.py 中间稿.md 输出.docx --skip-check   # 跳过中间稿自检
    python build_docx.py 中间稿.md 输出.docx -v             # 打印重试/清理细节

## 健壮性

- **自检先行**：中间稿不合格（引号 / 字数 / 区块数 / 相邻加粗）直接停，**不碰 SDK**。
- **吞掉 `SystemExit`**：`edsdk._rpc()` 一遇错就 `_die()` → `sys.exit(1)`，
  不捕的话进程直接死、兜底分支变死代码（见 `references/docx-pitfalls.md` A18）。
- **自动重试**：`document is not opened` / timeout / 连接失败 这类瞬时错误重试 3 次
  （实测 `create_doc` 后紧接着设样式**第 1 次必失败、第 2 次成功**，见 A19）。
- **清残留实例**：开工前把前次失败留下的 `new_doc_*` 关掉，避免加重竞态。

## 中间稿要求

- 第 1 行必须是 `# 视频标题`（大标题）
- 头部标签行写成 `**整理日期：**2026-09-24`（有链接时在它上面再加一行
  `**原视频链接：**https://…`）。🚫 **不要写「频道」「视频时长」**（2026-09-24 起废弃）
- `## 一、分段精读` / `## 二、重点词汇` 两个二级标题**必须存在**（脚本靠它们定位区块）
- 🚫 **没有 `## 三、重点句子`**（2026-09-24 整节删除）。文档到「二、重点词汇」就结束。
  词表 **3 组 × 7–8 条 = 20–22 条**，每条 2 行（`**N. term**　词性　释义` + `例：… — 中文`），
  **只有 6–8 条有坑的**才加第 3 行 `提示：`。
- 每个区块 = `**[MM:SS]**` + 英文段 + 中文段

## 前置

`editor_sdk` 需在运行中（由 WorkBuddy 的 tencent-local-office-edit 技能提供）。
"""
import argparse
import contextlib
import io
import json
import os
import re
import subprocess
import sys
import time

# ---- 定位 editor SDK（edsdk.py）----
DEFAULT_SDK_DIR = (r'<WorkBuddy 安装目录>/resources/app.asar.unpacked'
                   r'/resources/plugins/workbuddy-builtin/skills/tencent-local-office-edit')
PATCH_DIR = os.path.dirname(os.path.abspath(__file__))

TS = re.compile(r'^\[\d\d:\d\d\]$')
CJK = re.compile(r'[\u4e00-\u9fff]')
H1 = re.compile(r'^#\s+(.+)$')
SECT1 = '一、分段精读'
SECT2 = '二、重点词汇'


# ======================= 中间稿自检 =======================
def check_markdown(path):
    """返回 (ok, [问题...], 统计dict)。"""
    src = open(path, encoding='utf-8').read()
    lines = src.split('\n')
    bad, stat = [], {}

    m = H1.match(lines[0]) if lines else None
    if not m:
        bad.append('第 1 行不是 `# 大标题`')
    stat['标题'] = m.group(1).strip() if m else '?'

    blocks = [l for l in lines if TS.match(l.strip().replace('**', ''))]
    stat['区块数'] = len(blocks)

    i1 = next((i for i, l in enumerate(lines) if l.startswith('## ') and SECT1 in l), None)
    i2 = next((i for i, l in enumerate(lines) if l.startswith('## ') and SECT2 in l), None)
    if i1 is None or i2 is None:
        bad.append(f'找不到 `## {SECT1}` 或 `## {SECT2}`（脚本靠它们定位区块）')
    elif i2 <= i1:
        bad.append(f'`## {SECT2}` 出现在 `## {SECT1}` 之前')

    # 全篇大意 = 头部之后、SECT1 之前最长的一段中文
    if i1 is not None:
        best = ''
        for l in lines[:i1]:
            if len(CJK.findall(l)) > len(CJK.findall(best)):
                best = l
        n = len(CJK.findall(best))
        stat['全篇大意中文字数'] = n
        if not (200 <= n <= 250):
            bad.append(f'全篇大意 {n} 字，规范要求 200–250')

    stat['中文弯引号'] = src.count('\u201c') + src.count('\u201d')
    if stat['中文弯引号']:
        bad.append(f'有 {stat["中文弯引号"]} 个中文弯引号，规范要求用 ASCII 直引号')

    adj = re.findall(r'\*\*[^*\n]+?\*\*\s+\*\*[^*\n]+?\*\*', src)
    stat['相邻加粗'] = len(adj)
    if adj:
        bad.append(f'有 {len(adj)} 处相邻加粗（会吞空格）：{adj[:2]}')

    # ---- 2026-09-24 提速改版：不许再出现「三、重点句子」----
    i3 = next((i for i, l in enumerate(lines) if l.startswith('## ') and '三、' in l), None)
    if i3 is not None:
        bad.append(f'出现了 `{lines[i3].strip()}` —— 「三、重点句子」2026-09-24 已整节删除，'
                   f'有价值的"看点"请并进词条的 `提示：`')

    # 词表体量（统计用，不拦人 —— 短素材允许少几条）
    if i2 is not None:
        tail = lines[i2:]
        stat['词条数'] = len([l for l in tail if re.match(r'^\*\*\d+\.\s', l.strip())])
        stat['提示条数'] = len([l for l in tail
                                if l.strip().lstrip('*').startswith('提示：')])
        # 组标题在 markdown 里写作 `### ① …`，所以前缀要允许 # 和空白
        stat['分组数'] = len([l for l in tail
                              if re.match(r'^#*\s*[①②③④⑤⑥⑦⑧⑨]', l.strip())])

    odd = [i + 1 for i, l in enumerate(lines) if l.count('**') % 2]
    if odd:
        bad.append(f'第 {odd[:5]} 行 `**` 个数为奇数（markdown 语法坏了）')

    return (not bad), bad, stat


# ======================= SDK 封装（同进程复用） =======================
# 🔴 edsdk._rpc() 一遇错就 _die() → sys.exit(1)，会直接杀掉本进程，
#    让所有 `if 'error' in r: return 1` 的兜底分支变成死代码。
#    所以这里必须用 redirect_stdout 兜住它的输出 + 捕 SystemExit，把失败降级成字符串。
RETRY_HINTS = ('document is not opened', 'not opened', 'timeout', '连接失败',
               '连接超时', 'Connection', 'ECONNRESET', 'busy')
# 「文档还没装载完」这种是**稳定复现**的（每次 create_doc 后第一次必失败），
# 属于「再等一下就好」，用短间隔快速连试；其他瞬时错误用常规退避。
NOT_READY_HINTS = ('not opened', 'document is not opened')


def make_caller(sdk_dir, retries=4, delay=0.9, verbose=False):
    sys.path.insert(0, sdk_dir)
    import edsdk                                   # noqa: E402

    def call(tool, args):
        """调一个 SDK 工具。失败不退出进程，返回以 'error:' 开头的字符串。"""
        last = 'error: 未执行'
        for attempt in range(retries + 1):
            buf = io.StringIO()
            err = io.StringIO()
            try:
                # edsdk._die() 同时往 stdout / stderr 打两行，两个都要收，
                # 否则流水线日志里会混进它自己的 "error: ..." 噪音
                with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(err):
                    r = edsdk._rpc('tools/call', {'name': tool, 'arguments': args})
            except SystemExit:
                last = buf.getvalue().strip().split('\n')[0] or 'error: unknown'
                if verbose:
                    print(f'    ↻ {tool} 第 {attempt + 1} 次失败：{last[:120]}', flush=True)
                # 只对「疑似竞态/瞬时」的错误重试；逻辑错误重试也没用
                if attempt < retries and any(h in last for h in RETRY_HINTS):
                    wait = 0.3 if any(h in last for h in NOT_READY_HINTS) else delay * (attempt + 1)
                    time.sleep(wait)
                    continue
                return last
            texts = [c.get('text', '') for c in (r.get('content') or [])
                     if isinstance(c, dict) and c.get('type') == 'text']
            return '\n'.join(texts) if texts else json.dumps(r, ensure_ascii=False)
        return last

    return call


def clean_pool(call, verbose=False):
    """清掉残留的 new_doc_* 编辑器实例（前次失败留下的会引发 create 后竞态）。"""
    out = call('get_pool_status', {})
    if out.startswith('error:'):
        return 0
    try:
        pool = json.loads(out)
    except (ValueError, TypeError):
        return 0
    n = 0
    for ed in (pool.get('open_editors') or []):
        fid = ed.get('file_id') or ''
        if fid.startswith('new_doc_'):
            call('close_file', {'file_id': fid, 'force': True})
            n += 1
            if verbose:
                print(f'    🧹 关闭残留实例 {fid}', flush=True)
    return n


def resolve_nodes(call, fid):
    """拿全部段落节点。limit=0 = 不分页，一次拿全。"""
    out = call('doc_resolve_document_structure',
               {'file_id': fid, 'limit': 0, 'text_preview_length': 60})
    return json.loads(out).get('nodes') or []


def cn_end_indexes(nodes):
    """分段精读区里每个「中文翻译段」的 end_index（插空段的位置）。

    区块结构固定为 时间戳 / 英文段 / 中文段 —— 用时间戳当锚点最稳。
    """
    i1 = i2 = None
    for i, n in enumerate(nodes):
        t = (n.get('text_preview') or '').strip()
        if i1 is None and t.startswith(SECT1):
            i1 = i
        elif t.startswith(SECT2):
            i2 = i
            break
    if i1 is None:
        return [], '未找到「一、分段精读」'
    if i2 is None:
        i2 = len(nodes)
    pts = []
    for i in range(i1 + 1, i2):
        if TS.match((nodes[i].get('text_preview') or '').strip()):
            if i + 2 < i2:
                pts.append(nodes[i + 2]['end_index'])
    return pts, None


# ======================= 主流程 =======================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('markdown')
    ap.add_argument('out')
    ap.add_argument('--sdk-dir', default=DEFAULT_SDK_DIR)
    ap.add_argument('--keep-open', action='store_true', help='不 close_file')
    ap.add_argument('--no-patch', action='store_true', help='跳过 4 个 XML 补丁')
    ap.add_argument('--skip-check', action='store_true', help='跳过中间稿自检')
    ap.add_argument('-v', '--verbose', action='store_true', help='打印重试/清理细节')
    args = ap.parse_args()

    md = os.path.abspath(args.markdown)
    out = os.path.abspath(args.out)
    if not os.path.isfile(md):
        print('❌ 找不到中间稿：' + md)
        return 1
    if not os.path.isdir(args.sdk_dir):
        print('❌ 找不到 editor SDK 目录：' + args.sdk_dir)
        return 1

    T0 = time.time()
    step = [0]

    def say(name, extra='', t=None):
        step[0] += 1
        dt = f'  {time.time() - t:.2f}s' if t else ''
        print(f'[{step[0]}] {name:<22} {extra}{dt}', flush=True)

    # ---- 0. 中间稿自检 ----
    if not args.skip_check:
        t = time.time()
        ok, bad, stat = check_markdown(md)
        if not ok:
            print('❌ 中间稿自检没过：')
            for b in bad:
                print('   - ' + b)
            return 1
        say('check_markdown', f'{stat["区块数"]} 区块 / 大意 {stat["全篇大意中文字数"]} 字', t)
        if '词条数' in stat:
            print(f'   · 词表：{stat["分组数"]} 组 / {stat["词条数"]} 条 / '
                  f'{stat["提示条数"]} 条带提示'
                  f'（目标 3 组 / 20–22 条 / 提示 6–8 条）')

    call = make_caller(args.sdk_dir, verbose=args.verbose)
    say('connect_edsdk', '')

    # ---- 0.5 清残留实例（前次失败留下的 new_doc_* 会引发竞态）----
    t = time.time()
    n_clean = clean_pool(call, verbose=args.verbose)
    say('clean_pool', f'清掉 {n_clean} 个残留' if n_clean else '无残留', t)

    # ---- 1. 新建 ----
    t = time.time()
    r = call('create_doc', {})
    m = re.search(r'file_id=(\S+?),', r)
    if not m:
        print(f'❌ create_doc 失败：{r[:300]}')
        return 1
    fid = m.group(1)
    say('create_doc', fid, t)

    # ---- 2. 文档级样式 ----
    t = time.time()
    r = call('doc_set_document_style', {
        'file_id': fid,
        'default_text_style': {'font_family': 'Calibri', 'font_size': 12},
        'default_paragraph_style': {'line_spacing': 1.4, 'line_spacing_rule': 1,
                                    'spacing_before': 0, 'spacing_after': 6},
    })
    if r.startswith('error:'):
        print(f'❌ set_document_style 失败：{r[:300]}')
        return 1
    say('set_document_style', 'Calibri/12pt/1.4/段后6pt', t)

    # ---- 3. 写入全文 ----
    t = time.time()
    r = call('doc_insert_markdown', {'file_id': fid, 'idx': 0,
                                     'markdown': 'file://' + md.replace('\\', '/')})
    if r.startswith('error:'):
        print(f'❌ insert_markdown 失败：{r[:300]}')
        return 1
    say('insert_markdown', os.path.basename(md), t)

    # ---- 4. 拿结构 → 定位中文段 ----
    t = time.time()
    try:
        nodes = resolve_nodes(call, fid)
    except ValueError as e:
        print(f'❌ resolve_document_structure 返回不是 JSON：{e}')
        return 1
    pts, err = cn_end_indexes(nodes)
    if err or not pts:
        print(f'❌ 定位中文段失败：{err or "没找到时间戳区块"}')
        return 1
    say('resolve_structure', f'{len(nodes)} 段 / {len(pts)} 个区块', t)

    # ---- 5. 插区块间空段（降序，前面坐标不漂移）----
    t = time.time()
    for k, idx in enumerate(sorted(pts, reverse=True)):
        r = call('doc_insert_paragraph_with_text',
                 {'file_id': fid, 'idx': idx, 'text': '', 'type': 0})
        if r.startswith('error:') or 'ok' not in r:
            print(f'❌ 第 {k + 1} 个空段插入失败：{r[:200]}')
            return 1
    say('insert_blank_paras', f'{len(pts)} 个', t)

    # ---- 6. 页码（覆盖式写页脚，必须放最后）----
    t = time.time()
    r = call('doc_set_page_number', {'file_id': fid, 'position': 'center'})
    if r.startswith('error:'):
        print(f'❌ set_page_number 失败：{r[:300]}')
        return 1
    say('set_page_number', '居中', t)

    # ---- 7. 保存 ----
    t = time.time()
    r = call('save_file', {'file_id': fid, 'file_path': out})
    if r.startswith('error:'):
        print(f'❌ save_file 失败：{r[:300]}')
        return 1
    say('save_file', os.path.basename(out), t)

    if not args.keep_open:
        call('close_file', {'file_id': fid, 'force': True})

    # ---- 8. 四个 XML 补丁（顺序固定）----
    if not args.no_patch:
        for s in ('apply_fonts.py', 'fix_title_and_labels.py',
                  'fix_paraid.py', 'set_indent.py'):
            t = time.time()
            p = subprocess.run([sys.executable, '-B', os.path.join(PATCH_DIR, s), out],
                               capture_output=True)
            log = (p.stdout or b'').decode('utf-8', 'ignore')
            hits = [l.strip() for l in log.split('\n')
                    if l.strip().startswith(('❌', '⚠️', '大标题', '缺 ind', '段落分类'))]
            say(s.replace('.py', ''), (' | '.join(hits))[:110] or 'ok', t)
            if p.returncode != 0:
                print(f'❌ {s} 返回码 {p.returncode}')
                return 1

    print(f'\n✅ 完成：{out}\n   总耗时 {time.time() - T0:.1f}s')
    return 0


if __name__ == '__main__':
    sys.exit(main())

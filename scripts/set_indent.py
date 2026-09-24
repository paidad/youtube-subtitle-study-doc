#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""逐段显式设首行缩进（纯 XML，不依赖编辑器 SDK）。

为什么需要这个脚本：
  1. **WPS 不认 `docDefaults` / `Normal` 样式里的 `<w:ind>`**，首行缩进必须逐段写死。
  2. `doc_resolve_document_structure` **有分页**（实测 `limit:150, total_nodes:203, has_more:true`），
     长文档拿不到全部段落坐标；而 XML 层一次就能遍历所有段落。
  3. **`doc_insert_paragraph_with_text(text="")` 建出的空段是自闭合 `<w:p .../>`**，
     用 `<w:p[ >].*?</w:p>` 这种正则**匹配不到**（会把空段漏掉，还会误伤文档末尾的段落）。
     本脚本统一用 `<w:p\\b[^>]*/>|<w:p[ >].*?</w:p>`，自闭合的先展开再处理。

段落分类 → 缩进（判据全部基于段落自身，不依赖外部坐标）：

| 类型 | 判据 | 缩进 |
|---|---|---|
| HEAD  | 段落里含 `<w:outlineLvl>`（大标题 / 一、二、三 / ①②③④） | 0 |
| HDR   | 文本匹配 `^(原视频链接|整理日期)\\s*[：:]`（「频道」「视频时长」已废弃，留在模式里兼容老稿） | 0 |
| TS    | 文本匹配 `^\\[\\d\\d:\\d\\d\\]$` | 0 |
| EMPTY | 无文本（含自闭合空段） | 0 |
| P     | 其余（英文段 / 中文段 / 词汇 / 句子 / 全篇大意） | `--size`（默认 2 字符） |

用法：
    python set_indent.py "2026-09-24 xxx.docx"
    python set_indent.py "xxx.docx" --size 2 --no-backup

⚠️ 幂等：重复跑结果一致（已实测「改写段数 0」）。
⚠️ 若配合编辑器 SDK 用，**务必在所有 SDK 操作（含 save_file）之后**再跑本脚本 ——
   `save_file` 会让 WPS 重写 `styles.xml` 并规范化段落，先跑会被冲掉。
"""
import argparse
import collections
import os
import re
import shutil
import sys
import time
import zipfile
from xml.etree import ElementTree as ET

TS = re.compile(r'^\[\d\d:\d\d\]$')
# 头部标签行。正式口径只有「原视频链接 / 整理日期」；
# 「频道」「视频时长」已废弃（2026-09-24），留在模式里只为兼容老稿的缩进归零。
HDR = re.compile(r'^(频道|原视频链接|视频时长|整理日期)\s*[：:]')
IND = re.compile(r'<w:ind\b[^>]*/>')
# 自闭合空段 **或** 正常配对段落 —— 少了前半段就会漏掉 SDK 建的空段
PAT = re.compile(r'<w:p\b[^>]*/>|<w:p[ >].*?</w:p>', re.S)


def read_parts(path):
    z = zipfile.ZipFile(path)
    items = z.infolist()
    data = {i.filename: z.read(i.filename) for i in items}
    z.close()
    return items, data


def write_parts(path, items, data):
    tmp = path + '.tmp'
    with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as zout:
        for i in items:
            zout.writestr(i, data[i.filename])
    for a in range(6):
        try:
            with open(path, 'wb') as f:
                f.write(open(tmp, 'rb').read())
            os.remove(tmp)
            return True
        except PermissionError as e:
            print(f'  写回被占用，重试 {a + 1}: {e}')
            time.sleep(1.2)
    return False


def kind_of(p, txt):
    t = txt(p).strip()
    if p.endswith('/>') or not t:
        return 'EMPTY'
    if '<w:outlineLvl' in p:
        return 'HEAD'
    if HDR.match(t):
        return 'HDR'
    if TS.match(t):
        return 'TS'
    return 'P'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('path')
    ap.add_argument('--size', type=int, default=2,
                    help='正文首行缩进字符数（默认 2 → firstLineChars="200"）')
    ap.add_argument('--no-backup', action='store_true')
    args = ap.parse_args()

    path = args.path
    if not os.path.isfile(path):
        print('❌ 找不到文件：' + path)
        return 1
    if not args.no_backup:
        shutil.copy2(path, path + '.pre-indent.bak')
        print('备份 → ' + path + '.pre-indent.bak')

    items, data = read_parts(path)
    doc = data['word/document.xml'].decode('utf-8')
    txt = lambda x: ''.join(re.findall(r'<w:t[^>]*>(.*?)</w:t>', x, re.S))

    stat = collections.Counter()
    changed = [0]
    want_body = str(args.size * 100)

    def fix(m):
        p = m.group(0)
        kind = kind_of(p, txt)
        stat[kind] += 1
        ind = f'<w:ind w:firstLineChars="{"0" if kind != "P" else want_body}"/>'
        if p.endswith('/>'):                       # 自闭合空段 → 展开并补 pPr
            changed[0] += 1
            return p[:-2] + '><w:pPr>' + ind + '</w:pPr></w:p>'
        if IND.search(p):
            new = IND.sub(ind, p, count=1)
        elif '</w:pPr>' in p:
            new = p.replace('</w:pPr>', ind + '</w:pPr>', 1)
        else:
            mo = re.match(r'(<w:p[^>]*>)', p)
            new = p[:mo.end()] + '<w:pPr>' + ind + '</w:pPr>' + p[mo.end():]
        if new != p:
            changed[0] += 1
        return new

    doc = PAT.sub(fix, doc)
    data['word/document.xml'] = doc.encode('utf-8')
    if not write_parts(path, items, data):
        print('❌ 写回失败：文件被占用（WPS 是不是开着？见 docx-pitfalls B4）')
        return 1

    print('段落分类 :', dict(sorted(stat.items())))
    print('改写段数 :', changed[0], '（幂等：重跑应为 0）')

    # ---------- 校验 ----------
    z = zipfile.ZipFile(path)
    d = z.read('word/document.xml').decode('utf-8')
    print('zip 完整性 :', z.testzip())
    toks = PAT.findall(d)
    left = len(re.findall(r'<w:p\b[^>]*/>', d))
    print('段落 token 总数 :', len(toks), f'（残留自闭合 {left}，应为 0）')
    c = collections.Counter()
    for q in toks:
        k = kind_of(q, txt)
        m = IND.search(q)
        c[(k, m.group(0) if m else 'NONE')] += 1
    for kk, v in sorted(c.items()):
        print(f'  {str(kk[0]):<6} {kk[1]:<38} {v}')
    miss = sum(v for kk, v in c.items() if kk[1] == 'NONE')
    print('缺 ind 的段 :', miss)
    ET.fromstring(d)
    print('document.xml 良构 : ok')
    return 1 if (miss or left) else 0


if __name__ == '__main__':
    sys.exit(main())

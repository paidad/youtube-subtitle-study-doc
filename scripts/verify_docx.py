#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""交付前全项校验 docx。

用法：
    python verify_docx.py 2026-09-23.docx
    python verify_docx.py 2026-09-23.docx --en Calibri --cn 仿宋 --size 12
    python verify_docx.py 2026-09-23.docx --expect-blocks 74

输出全部为「实际值」，逐项和预期对照即可。发现 ❌ 就先修再交付。
"""
import argparse
import re
import sys
import zipfile
from collections import Counter
from xml.etree import ElementTree as ET

TS = re.compile(r'^\[\d\d:\d\d\]$')
CJK = re.compile(r'[\u4e00-\u9fff]')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('path')
    ap.add_argument('--en', default='Calibri')
    ap.add_argument('--cn', default='仿宋')
    ap.add_argument('--size', type=float, default=12.0)
    ap.add_argument('--expect-blocks', type=int, default=None,
                    help='分段精读区预期区块数（= 时间戳数）')
    ap.add_argument('--header-lines', type=int, default=4,
                    help='头部标签行段数（标题 + 频道/链接/时长 等），默认 4')
    args = ap.parse_args()

    p = args.path
    z = zipfile.ZipFile(p)
    problems = []

    def check(label, ok, detail=''):
        mark = '✅' if ok else '❌'
        if not ok:
            problems.append(label)
        print(f'  {mark} {label}{("  " + detail) if detail else ""}')

    # ---------- 1. 包完整性 ----------
    print('=== 包完整性 ===')
    check('zip 无损', z.testzip() is None, str(z.testzip()))
    bad = []
    for n in z.namelist():
        if n.endswith('.xml') or n.endswith('.rels'):
            try:
                ET.fromstring(z.read(n))
            except Exception as e:
                bad.append(n)
    check('XML 全部良构', not bad, str(bad) if bad else '')

    doc = z.read('word/document.xml').decode('utf-8')
    sty = z.read('word/styles.xml').decode('utf-8')
    paras = re.findall(r'<w:p[ >].*?</w:p>', doc, re.S)
    txt = lambda x: ''.join(re.findall(r'<w:t[^>]*>(.*?)</w:t>', x, re.S))
    kind = lambda q: ('HEAD' if '<w:outlineLvl' in q
                      else ('TS' if TS.match(txt(q).strip())
                            else ('EMPTY' if not txt(q).strip() else 'P')))

    # ---------- 2. 结构 ----------
    print(f'\n=== 结构（段落总数 {len(paras)}）===')
    heads = [(i, txt(q), set(re.findall(r'<w:sz w:val="(\d+)"', q)))
             for i, q in enumerate(paras) if '<w:outlineLvl' in q]
    print('  标题段：')
    for i, t, sz in heads:
        print(f'    [{i:>3}] {t[:34]!r:<38} sz={sz or "继承"}')
    check('标题段存在', bool(heads))
    title = paras[0]
    check('大标题居中', 'w:val="center"' in title, re.findall(r'<w:jc w:val="(\w+)"', title).__str__())
    check('大标题 sz=44 (22pt)', 'w:val="44"' in title)
    check('大标题字体=黑体', '黑体' in title)

    n_ts = sum(1 for q in paras if kind(q) == 'TS')
    check('时间戳数 = 区块数', args.expect_blocks is None or n_ts == args.expect_blocks,
          f'实际 {n_ts}' + (f' / 预期 {args.expect_blocks}' if args.expect_blocks else ''))

    # ---------- 3. 区块模式 ----------
    i0 = next((i for i, q in enumerate(paras) if txt(q).strip().startswith('一、分段精读')), None)
    i1 = next((i for i, q in enumerate(paras) if txt(q).strip().startswith('二、重点词汇')), None)
    if i0 is not None and i1 is not None:
        body = paras[i0 + 1:i1]
        pats, i = [], 0
        while i < len(body):
            if kind(body[i]) == 'TS':
                pats.append(tuple(kind(m) for m in body[i:i + 4]))
                i += 4
            else:
                i += 1
        dist = Counter(pats)
        check('区块模式统一为 时间戳/英文/中文/空段',
              set(dist) == {('TS', 'P', 'P', 'EMPTY')}, str(dict(dist)))

    # ---------- 4. 关键内容 ----------
    print('\n=== 关键内容 ===')
    check('超链接域存在', 'HYPERLINK' in doc,
          str(re.findall(r'HYPERLINK &quot;([^&]+)&quot;', doc)))
    check('无版权行残留', not any('版权' in txt(q) for q in paras))
    n_off = len(re.findall(r'<w:b w:val="0"/>', doc))
    check('头部标签显式不加粗', n_off >= 3, f'<w:b w:val="0"/> 出现 {n_off} 次')

    # ---------- 5. 缩进 ----------
    print('\n=== 首行缩进 ===')
    tab = {}
    for q in paras:
        m = re.search(r'<w:ind [^>]*/>', q)
        tab.setdefault(kind(q), Counter())[m.group(0) if m else '（无 ind）'] += 1
    for k in ('P', 'TS', 'EMPTY', 'HEAD'):
        if k in tab:
            print(f'  {k:<6} {dict(tab[k])}')
    # 头部标签行（标题后、正文前的几段）本来就该顶格，从正文检查里排除
    hdr = args.header_lines
    body_p = [q for q in paras[hdr:] if kind(q) == 'P']
    body_ok = all('firstLineChars="200"' in q for q in body_p)
    check(f'正文段（跳过头部 {hdr} 段）全部 2 字符缩进', body_ok,
          f'检查 {len(body_p)} 段，不合规 '
          f'{sum(1 for q in body_p if "firstLineChars=" + chr(34) + "200" + chr(34) not in q)} 段'
          if not body_ok else f'检查 {len(body_p)} 段')
    zero_ok = all(all('firstLineChars="0"' in ind for ind in v)
                  for k, v in tab.items() if k in ('TS', 'EMPTY'))
    check('时间戳/空段缩进归零', zero_ok)

    # ---------- 6. 字体 ----------
    print('\n=== 字体 ===')
    names = Counter()
    for n in z.namelist():
        if n.endswith('.xml'):
            s = z.read(n).decode('utf-8', 'ignore')
            for mm in re.findall(r'w:(?:ascii|hAnsi|eastAsia|cs)="([^"]+)"', s):
                names[mm] += 1
    print('  全包字体名统计:', dict(names))
    dd = re.search(r'<w:docDefaults><w:rPrDefault><w:rPr>(.*?)</w:rPr>', sty, re.S)
    check('docDefaults 含英文字体', bool(dd) and args.en in dd.group(1), dd.group(1) if dd else '')
    check('docDefaults 含中文字体', bool(dd) and args.cn in dd.group(1))
    half = int(round(args.size * 2))
    check(f'docDefaults 字号={half} (={args.size}pt)',
          bool(dd) and f'<w:sz w:val="{half}"/>' in dd.group(1))
    nrm = re.search(r'w:default="1"[^>]*>.*?<w:rPr>(.*?)</w:rPr></w:style>', sty, re.S)
    check('Normal 样式含中文字体', bool(nrm) and args.cn in nrm.group(1),
          nrm.group(1) if nrm else '未找到')
    stray = {k for k in names if k not in (args.en, args.cn, '黑体', 'zh-CN')}
    check('无多余字体（Times New Roman / 微软雅黑 等）', not stray, str(stray))

    # ---------- 7. 加粗 / paraId / 页脚 ----------
    print('\n=== 其它 ===')
    nb = len(re.findall(r'<w:b/>', doc)) + len(re.findall(r'<w:b w:val="1"/>', doc))
    print(f'  加粗 run 数 : {nb}')
    print(f'  sz 取值     : {sorted(set(re.findall(r"<w:sz w:val=.(\d+).", doc)))}')
    dup = [k for k, v in Counter(re.findall(r'w14:paraId="([0-9A-Fa-f]{8})"', doc)).items() if v > 1]
    check('无重复 paraId', not dup, str(dup))
    foot = []
    for n in z.namelist():
        if re.match(r'word/footer\d*\.xml', n):
            f = z.read(n).decode('utf-8')
            if 'PAGE' in f:
                foot.append((n, re.findall(r'w:xAlign="(\w+)"', f)))
    check('页脚含 PAGE 域', bool(foot), str(foot))

    # ---------- 结论 ----------
    print()
    if problems:
        print('❌ 有 ' + str(len(problems)) + ' 项未通过：')
        for x in problems:
            print('   -', x)
        return 1
    print('✅ 全部通过，可以交付。')
    return 0


if __name__ == '__main__':
    sys.exit(main())

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按词表给 Markdown 正文里的单词/词组批量加 **加粗**。

规则：
  - 只处理**不含中文**的行（避免动到中文译文）
  - 已在 **...** 里的内容跳过，不重复加粗
  - 匹配用 \\b(...)\\b，不区分大小写

用法：
    python bold_terms.py 2026-09-23.md            # 就地覆盖（自动备份 .bak）
    python bold_terms.py 2026-09-23.md -o out.md  # 另存
    python bold_terms.py 2026-09-23.md --terms my_terms.txt
"""
import argparse
import io
import re
import shutil
import sys

# 默认词表：与《The Reality of Change》那份词汇表对应，可按需替换
TERMS = [
    r'glamorize', r'romanticiz\w*', r'gearing up for', r'take the leap', r'humbling',
    r'willed', r'bring to fruition', r'baby steps', r'redeem', r'vulnerable',
    r'authentic', r'out of whack', r'fight or flight', r'PMDD', r'curate',
    r'dissociated', r'stagnant', r'stifled', r'cut out for', r'ground you',
    r'hydrangea\w*', r'Lace caps', r'star jasmine', r"St\. John's Wort",
    r'golden hour', r'geode', r'rainbows and butterflies', r'a good chunk',
    r'a trigger warning', r'a heads-up', r'go through the motions',
    r'ups and the downs', r'get by', r'letting her down', r'push through', r'take in',
]

CJK = re.compile(r'[\u4e00-\u9fff]')


def load_terms(path):
    if not path:
        return TERMS
    return [l.strip() for l in io.open(path, encoding='utf-8')
            if l.strip() and not l.startswith('#')]


def inside_bold(line, pos):
    """判断 pos 是否落在已有的 **...** 区间内。"""
    return line.count('**', 0, pos) % 2 == 1


def bold_line(line, pattern):
    """返回 (新行, 本次新增的加粗个数)。"""
    out, pos, added = [], 0, 0
    for m in pattern.finditer(line):
        s, e = m.span()
        if s < pos or inside_bold(line, s):
            continue
        out.append(line[pos:s])
        out.append('**' + m.group(0) + '**')
        pos = e
        added += 1
    out.append(line[pos:])
    return ''.join(out), added


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('path')
    ap.add_argument('-o', '--out')
    ap.add_argument('--terms', help='自定义词表文件（一行一个正则片段，# 开头为注释）')
    ap.add_argument('--no-backup', action='store_true')
    args = ap.parse_args()

    terms = load_terms(args.terms)
    pattern = re.compile(r'\b(' + '|'.join(terms) + r')\b', re.IGNORECASE)

    src = io.open(args.path, encoding='utf-8').read()
    total = 0
    out_lines = []
    for ln in src.split('\n'):
        if CJK.search(ln):            # 含中文的行不动
            out_lines.append(ln)
            continue
        new, added = bold_line(ln, pattern)
        total += added
        out_lines.append(new)

    dst = args.out or args.path
    if dst == args.path and not args.no_backup:
        shutil.copy2(args.path, args.path + '.bak')
        print('备份 → ' + args.path + '.bak')

    io.open(dst, 'w', encoding='utf-8').write('\n'.join(out_lines))
    print(f'词表条数      : {len(terms)}')
    print(f'新增加粗处数  : {total}')
    print(f'输出          : {dst}')


if __name__ == '__main__':
    sys.exit(main())

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""给 docx 设全文基准字体，并剥离非标题段落的直设字体/字号。

为什么需要这个脚本：
  editor SDK 的 doc_set_document_style / doc_update_named_style 的 font_family
  只能写一个字体名，会同时落到 ascii / hAnsi / eastAsia，
  做不到「英文 Calibri + 中文仿宋」。所以必须直接改 XML。

本脚本做三件事：
  1. 把基准字体写进 styles.xml 的 docDefaults/rPrDefault
  2. 同时写进 Normal 样式（WPS 保存会把 docDefaults 的内容搬进 Normal，两边都要有）
  3. 把**非标题段落**里带字体名的 <w:rFonts> 和 <w:sz>/<w:szCs> 剥掉，让它们回落基准
     —— 标题段的判据是段落里含 <w:outlineLvl>，必须跳过，否则标题字号会被抹掉

用法：
    python apply_fonts.py 2026-09-23.docx
    python apply_fonts.py 2026-09-23.docx --en Calibri --cn 仿宋 --size 12
    python apply_fonts.py 2026-09-23.docx --keep-overrides   # 只改基准，不剥离

⚠️ 运行前先 close_file 关掉编辑器实例，否则文件被占用 / 内存副本会覆盖回去。
"""
import argparse
import os
import re
import shutil
import sys
import time
import zipfile


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('path')
    ap.add_argument('--en', default='Calibri', help='英文字体（ascii/hAnsi/cs）')
    ap.add_argument('--cn', default='仿宋', help='中文字体（eastAsia）')
    ap.add_argument('--size', type=float, default=12.0, help='正文字号（pt）')
    ap.add_argument('--keep-overrides', action='store_true',
                    help='不剥离非标题段落的直设字体（只改基准）')
    ap.add_argument('--no-backup', action='store_true')
    args = ap.parse_args()

    if not args.no_backup:
        bak = args.path + '.bak'
        shutil.copy2(args.path, bak)
        print('备份 → ' + bak)

    items, data = read_parts(args.path)
    half = int(round(args.size * 2))          # pt → 半磅

    rfonts = (f'<w:rFonts w:ascii="{args.en}" w:hAnsi="{args.en}" '
              f'w:eastAsia="{args.cn}" w:cs="{args.en}"/>')
    sz = f'<w:sz w:val="{half}"/><w:szCs w:val="{half}"/>'

    # ---------- styles.xml ----------
    sty = data['word/styles.xml'].decode('utf-8')

    m = re.search(r'(<w:docDefaults><w:rPrDefault><w:rPr>)(.*?)(</w:rPr></w:rPrDefault>)',
                  sty, re.S)
    if m:
        print('docDefaults 原 rPr : ' + m.group(2))
        sty = sty[:m.start(2)] + rfonts + sz + sty[m.end(2):]
    else:
        print('⚠️ 未找到 docDefaults/rPrDefault，跳过')

    m2 = re.search(r'(<w:style [^>]*w:default="1"[^>]*>.*?<w:rPr>)(.*?)(</w:rPr></w:style>)',
                   sty, re.S)
    if m2:
        print('Normal 样式 原 rPr : ' + m2.group(2))
        sty = sty[:m2.start(2)] + rfonts + sz + sty[m2.end(2):]
    else:
        print('⚠️ 未找到默认段落样式（Normal），跳过')

    data['word/styles.xml'] = sty.encode('utf-8')
    print(f'基准字体已写入：en={args.en}  cn={args.cn}  size={args.size}pt (sz={half})')

    # ---------- document.xml ----------
    doc = data['word/document.xml'].decode('utf-8')
    if args.keep_overrides:
        print('按 --keep-overrides 跳过剥离直设格式')
    else:
        strip_rf = re.compile(
            r'<w:rFonts\b[^>]*\b(?:w:ascii|w:hAnsi|w:eastAsia|w:cs)="[^"]*"[^>]*/>')
        strip_sz = re.compile(r'<w:sz w:val="\d+"/>')
        strip_szcs = re.compile(r'<w:szCs w:val="\d+"/>')

        parts = re.split(r'(<w:p[ >].*?</w:p>)', doc, flags=re.S)
        total, changed, skipped_head = 0, 0, 0
        for k, part in enumerate(parts):
            if not part.startswith('<w:p'):
                continue
            total += 1
            if '<w:outlineLvl' in part:          # 标题段 → 跳过
                skipped_head += 1
                continue
            before = part
            part = strip_rf.sub('', part)
            part = strip_sz.sub('', part)
            part = strip_szcs.sub('', part)
            if part != before:
                changed += 1
                parts[k] = part
        doc = ''.join(parts)
        data['word/document.xml'] = doc.encode('utf-8')
        print(f'段落总数 {total}｜跳过标题段 {skipped_head}｜剥离直设格式 {changed} 段')

    if not write_parts(args.path, items, data):
        print('❌ 写回失败：文件被占用')
        return 1

    # ---------- 校验 ----------
    z = zipfile.ZipFile(args.path)
    print('zip 完整性 :', z.testzip())
    s = z.read('word/styles.xml').decode('utf-8')
    print('ascii      :', set(re.findall(r'w:ascii="([^"]+)"', s)))
    print('eastAsia   :', set(re.findall(r'w:eastAsia="([^"]+)"', s)))
    print('sz         :', set(re.findall(r'<w:sz w:val="(\d+)"/>', s)))
    from xml.etree import ElementTree as ET
    bad = []
    for n in z.namelist():
        if n.endswith('.xml') or n.endswith('.rels'):
            try:
                ET.fromstring(z.read(n))
            except Exception as e:
                bad.append((n, str(e)))
    print('XML 良构   :', bad if bad else '全部通过')
    return 0


if __name__ == '__main__':
    sys.exit(main())

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""收尾修补：大标题黑体 + 大标题居中 + 头部标签取消加粗。

为什么需要这个脚本（三件事 markdown 都表达不出来）：
  1. `doc_insert_markdown` 的 `# 标题` 只给了 **44 半磅（22pt）**，**不会**给中文字体名，
     所以大标题会回落成「仿宋」，不符合规范要求的「黑体」。
  2. 同一个 `# 标题` 也**不会**给 `<w:jc>` —— 大标题默认左对齐。
     （2026-09-24 第三份才暴露：第二份成品里有 `w:jc="center"`，是当时用
     `doc_modify_paragraph` 额外设的，不是 markdown 自带的。）
  3. 头部标签写成 `**原视频链接：**` 会落成 `<w:b w:val="1"/>`（加粗），
     而规范要求标签**不加粗** —— 需要改成 `<w:b w:val="0"/>`。

做三件事：
  1. 第 1 个段落（大标题）：在 pPr/rPr 和 run/rPr 里补 `<w:rFonts ... 黑体 .../>`
  2. 第 1 个段落（大标题）：补 `<w:jc w:val="center"/>`（插在 `<w:ind>` 之后、
     `<w:outlineLvl>` 之前 —— OOXML 对 pPr 子元素顺序有要求）
  3. 头部标签行：把 `<w:b w:val="1"/>` 改成 `val="0"`

头部标签行数**自动探测**（2026-09-24 二次改口径后）：
  给了原视频链接 → 2 行（原视频链接 / 整理日期）
  没给链接       → 1 行（整理日期）
  🚫「频道」「视频时长」已废弃，新稿不写

段落正则用 `<w:p\\b[^>]*/>|<w:p[ >].*?</w:p>` —— 前半段是为了覆盖
`doc_insert_paragraph_with_text(text="")` 建出的**自闭合空段**，
少了它会漏段落（见 docx-pitfalls A16）。

用法：
    python fix_title_and_labels.py 2026-09-24 xxx.docx
    python fix_title_and_labels.py xxx.docx --cn 黑体 --labels 3 --no-center

⚠️ 运行前先 close_file 关掉编辑器实例。
⚠️ 应在 `apply_fonts.py` 之后、`fix_paraid.py` 之前跑。
"""
import argparse
import os
import re
import shutil
import sys
import time
import zipfile
from xml.etree import ElementTree as ET

# 头部标签行。2026-09-24 起正式口径只有「原视频链接 / 整理日期」；
# 「频道」「视频时长」已废弃，仍留在模式里是为了老稿子也能被正确识别头部。
HDR = re.compile(r'^(频道|原视频链接|视频时长|整理日期)\s*[：:]')
# 自闭合空段 **或** 正常配对段落
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('path')
    ap.add_argument('--cn', default='黑体', help='大标题中文字体名')
    ap.add_argument('--labels', type=int, default=None,
                    help='头部标签行数（标题之后、正文之前）。默认自动探测：有链接 3 / 无链接 1')
    ap.add_argument('--no-center', action='store_true', help='不给大标题补居中')
    ap.add_argument('--no-backup', action='store_true')
    args = ap.parse_args()

    if not args.no_backup:
        shutil.copy2(args.path, args.path + '.bak')
        print('备份 → ' + args.path + '.bak')

    items, data = read_parts(args.path)
    doc = data['word/document.xml'].decode('utf-8')
    txt = lambda x: ''.join(re.findall(r'<w:t[^>]*>(.*?)</w:t>', x, re.S))
    rfonts = ('<w:rFonts w:hint="eastAsia" w:ascii="%s" w:hAnsi="%s" '
              'w:eastAsia="%s" w:cs="%s"/>' % (args.cn, args.cn, args.cn, args.cn))

    parts = re.split(r'(<w:p\b[^>]*/>|<w:p[ >].*?</w:p>)', doc, flags=re.S)

    # 头部标签行数自动探测：从第 2 段起，连续匹配「原视频链接/整理日期：」
    if args.labels is None:
        ptexts = [txt(p) for p in PAT.findall(doc)]
        n = 0
        while 1 + n < len(ptexts) and HDR.match(ptexts[1 + n].strip()):
            n += 1
        args.labels = n
        shape = ('含链接：原视频链接 / 整理日期' if n >= 2
                 else '无链接：仅整理日期')
        if n >= 3:
            shape += '  ⚠️ 疑似残留「频道」/「视频时长」行 —— 2026-09-24 起不该写'
        print(f'自动探测头部标签行数：{n}（{shape}）')

    pi = -1
    title_font = 0
    title_center = 0
    label_ok = 0
    for k, part in enumerate(parts):
        if not part.startswith('<w:p'):
            continue
        pi += 1
        if pi == 0:
            if part.endswith('/>'):          # 保险：首段不该是自闭合
                continue
            before = part
            # 段落级 rPr（大标题的 pPr 里通常带 <w:kern>）
            part = re.sub(r'<w:rPr>(?!<w:rFonts)', '<w:rPr>' + rfonts, part, count=1)
            # run 级 rPr（带 sz 的那个）
            part = re.sub(r'<w:rPr>(?=<w:b)', '<w:rPr>' + rfonts, part, count=1)
            title_font = part.count(args.cn) // 4
            # 居中：markdown 的 `# 标题` 不给 <w:jc>，要自己补
            if not args.no_center and '<w:jc ' not in part:
                part = re.sub(r'(<w:ind\b[^>]*/>)', r'\1<w:jc w:val="center"/>',
                              part, count=1)
                if '<w:jc ' not in part:     # 没有 <w:ind> 就插在 outlineLvl 前
                    part = re.sub(r'(<w:outlineLvl\b[^>]*/>)',
                                  r'<w:jc w:val="center"/>\1', part, count=1)
            title_center = 1 if '<w:jc w:val="center"/>' in part else 0
            if part != before:
                parts[k] = part
        elif 1 <= pi <= args.labels:
            n = part.count('<w:b w:val="1"/>')
            if n:
                label_ok += n
                parts[k] = part.replace('<w:b w:val="1"/>', '<w:b w:val="0"/>')
    doc = ''.join(parts)
    data['word/document.xml'] = doc.encode('utf-8')

    if not write_parts(args.path, items, data):
        print('❌ 写回失败：文件被占用')
        return 1

    z = zipfile.ZipFile(args.path)
    d = z.read('word/document.xml').decode('utf-8')
    print('zip 完整性        :', z.testzip())
    print(f'大标题 {args.cn} 处数 :', d.count(args.cn), '（8 = pPr/rPr + run/rPr 各 4 个属性）')
    print('大标题居中        :', '是' if title_center else '❌ 否')
    print('<w:b w:val="0"/>  :', len(re.findall(r'<w:b w:val="0"/>', d)),
          f'（应 ≥ {args.labels}）')
    ET.fromstring(d)
    print('document.xml 良构 : ok')
    if d.count(args.cn) == 0:
        print('⚠️ 大标题字体没写进去，检查模板的 pPr/rPr 结构是否变了')
        return 1
    if not title_center and not args.no_center:
        print('⚠️ 大标题居中没写进去（段落里可能既没有 <w:ind> 也没有 <w:outlineLvl>）')
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())

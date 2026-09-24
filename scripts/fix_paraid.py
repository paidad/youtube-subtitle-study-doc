#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""去掉 docx 里重复的 w14:paraId（WPS 保存后的常见副作用）。

重复的 paraId 属无效 OOXML，Word 打开可能弹「修复文档」。
做法：保留首次出现，其余重编号为未占用的 8 位十六进制。

用法：
    python fix_paraid.py 2026-09-23.docx
"""
import os
import random
import re
import shutil
import sys
import time
import zipfile
from collections import Counter


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    path = sys.argv[1]

    shutil.copy2(path, path + '.bak')
    print('备份 → ' + path + '.bak')

    z = zipfile.ZipFile(path)
    items = z.infolist()
    data = {i.filename: z.read(i.filename) for i in items}
    z.close()

    doc = data['word/document.xml'].decode('utf-8')
    ids = re.findall(r'w14:paraId="([0-9A-Fa-f]{8})"', doc)
    dup = [k for k, v in Counter(ids).items() if v > 1]
    print('paraId 总数 :', len(ids))
    print('重复的      :', dup if dup else '无')

    if not dup:
        print('无需处理')
        return 0

    used = {x.upper() for x in ids}
    fixed = 0
    for d in dup:
        state = {'seen': 0}

        def repl(m):
            nonlocal fixed
            if m.group(1).upper() != d.upper():
                return m.group(0)
            state['seen'] += 1
            if state['seen'] == 1:
                return m.group(0)
            while True:
                new = '%08X' % random.randint(0x10000000, 0x7FFFFFFF)
                if new not in used:
                    used.add(new)
                    break
            fixed += 1
            return f'w14:paraId="{new}"'

        doc = re.sub(r'w14:paraId="([0-9A-Fa-f]{8})"', repl, doc)

    data['word/document.xml'] = doc.encode('utf-8')
    print('重编号处数  :', fixed)

    tmp = path + '.tmp'
    with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as zout:
        for i in items:
            zout.writestr(i, data[i.filename])
    for a in range(6):
        try:
            with open(path, 'wb') as f:
                f.write(open(tmp, 'rb').read())
            os.remove(tmp)
            break
        except PermissionError as e:
            print('  写回被占用，重试', a + 1, e)
            time.sleep(1.2)
    else:
        print('❌ 写回失败：文件被占用')
        return 1

    z = zipfile.ZipFile(path)
    ids2 = re.findall(r'w14:paraId="([0-9A-Fa-f]{8})"', z.read('word/document.xml').decode('utf-8'))
    print('校验重复    :', [k for k, v in Counter(ids2).items() if v > 1] or '无')
    print('zip 完整性  :', z.testzip())
    return 0


if __name__ == '__main__':
    sys.exit(main())

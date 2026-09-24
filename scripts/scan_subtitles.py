#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""扫描 YouTube 自动字幕 txt，给出规模与分段建议。

用法：
    python scan_subtitles.py <字幕.txt> [--per-seg 110]

典型字幕格式（每 4 行一块）：
    00:00
    英文 ASR 文本
    中文机翻文本
    (空行)
"""
import argparse
import io
import re
import sys

TS = re.compile(r'^\s*\[?(\d{1,2}):(\d{2})(?::(\d{2}))?\]?\s*$')
CJK = re.compile(r'[\u4e00-\u9fff]')


def norm_ts(line):
    m = TS.match(line)
    if not m:
        return None
    a, b, c = m.group(1), m.group(2), m.group(3)
    if c is None:                       # MM:SS
        return f'[{int(a):02d}:{b}]'
    return f'[{int(a)}:{b}:{c}]'        # H:MM:SS


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('path')
    ap.add_argument('--per-seg', type=int, default=110, help='目标每段词数（默认 110）')
    ap.add_argument('--min-words', type=int, default=80,
                    help='段落词数下限（默认 80；常规目标 90–130，短素材允许 80–90）')
    ap.add_argument('--max-words', type=int, default=130,
                    help='段落词数上限（默认 130）')
    args = ap.parse_args()

    raw = io.open(args.path, encoding='utf-8', errors='replace').read()
    lines = raw.split('\n')

    blocks = []          # [(ts, en, cn)]
    i = 0
    anomalies = []
    while i < len(lines):
        ln = lines[i].strip()
        if not ln:
            i += 1
            continue
        ts = norm_ts(ln)
        if ts is None:
            anomalies.append((i + 1, ln[:60]))
            i += 1
            continue
        en = lines[i + 1].strip() if i + 1 < len(lines) else ''
        cn = lines[i + 2].strip() if i + 2 < len(lines) else ''
        blocks.append((ts, en, cn))
        i += 3

    total_words = sum(len(b[1].split()) for b in blocks)
    total_cjk = sum(len(CJK.findall(b[2])) for b in blocks)
    en_only = [b for b in blocks if b[1] and not CJK.search(b[1])]

    print(f'文件            : {args.path}')
    print(f'总行数          : {len(lines)}')
    print(f'识别到的字幕块  : {len(blocks)}')
    print(f'英文总词数      : {total_words}')
    print(f'中文总字数      : {total_cjk}')
    print(f'时长            : {blocks[0][0] if blocks else "-"} → {blocks[-1][0] if blocks else "-"}')
    print()
    print(f'按每段 {args.min_words}-{args.max_words} 词切分，建议约 '
          f'{max(1, round(total_words / args.per_seg))} 段')
    print()

    # 噪声信号（英文行和中文行都要看：标记常被机翻成中文混进中文行）
    NOISE = ('[music]', '[applause]', '[laughter]', '（音乐）', '（掌声）', '（笑声）')
    music = [b for b in blocks
             if any(k in b[1].lower() or k in b[2] for k in NOISE)]
    empty_en = [b for b in blocks if not b[1].strip()]
    empty_cn = [b for b in blocks if not b[2].strip()]
    print('=== 需要留意的块 ===')
    print(f'  含 [music]/[applause] 等标记 : {len(music)}')
    for b in music[:8]:
        print(f'      {b[0]}  EN={b[1][:40]!r}  CN={b[2][:24]!r}')
    print(f'  英文为空的块               : {len(empty_en)}')
    print(f'  中文为空的块               : {len(empty_cn)}')
    print(f'  英文块里混入中文的         : {len(blocks) - len(en_only) - len(empty_en)}')

    if anomalies:
        print()
        print('=== 不符合"时间戳/英文/中文"三段式的行（前 10）===')
        for ln, t in anomalies[:10]:
            print(f'  行 {ln}: {t!r}')

    print()
    print('提示：分段按语义走，不要按时间戳机械切；只保留每段起始时间戳。')


if __name__ == '__main__':
    sys.exit(main())

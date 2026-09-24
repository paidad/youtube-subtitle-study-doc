# YouTube 字幕 → 中英对照精读稿

一个 [WorkBuddy](https://www.workbuddy.cn) 技能（Agent Skill）：把 YouTube 自动生成的字幕 txt（时间戳 / 英文 ASR / 中文机翻）整理成一份可直接打印、也能对着视频精读的**中英对照 Word 稿**。

核心价值在两件事：**修掉 ASR 与机翻的错误**，以及**按固定规范产出排版统一的成品**。

---

## 它产出什么

```
The Reality of Change                        ← 居中，黑体 22pt
频道：Flowering Philosophies
原视频链接：https://www.youtube.com/watch?v=xxxx     ← 可点超链接
视频时长：41:10　｜　整理日期：2026-09-23

（全篇大意，200–250 字，不写小标题）

一、分段精读
[00:00]
I didn't think this would be the reality of change. ……

我从没想过，"改变"的真面目会是这样。……

[00:19]
……

二、重点词汇
① 改变与成长
1. glamorize　v.　美化、把……理想化
例：We glamorize change. — 我们把改变想得太美。
提示：贬义，常指"把痛苦包装得浪漫"。

三、重点句子
1. Change is so easy to glamorize when we've been asking for it for so long.
译：当我们渴望改变太久，就很容易把它想得过于美好。
看点：sth is easy to + v. 的被动式主动表达；when 引导时间状语。
```

排版规范（固定，不自由发挥）：

| 对象 | 英文 | 中文 | 字号 |
|---|---|---|---|
| 正文（英文段 / 中文段 / 词汇 / 句子 / 时间戳） | Calibri | 仿宋 | 12pt（小四） |
| 文档大标题 | 黑体 | 黑体 | 22pt 加粗居中 |
| 各级小标题（一、/ ②…） | Calibri | 仿宋 | 16pt 加粗 |

行距 1.4、段后 6pt；正文段首行缩进 2 字符；区块之间空一行；**词汇表收录过的词在正文里加粗**；页脚居中页码。

---

## 安装

把整个目录放到 WorkBuddy 的技能目录下：

```bash
git clone https://github.com/paidad/youtube-subtitle-study-doc.git \
  ~/.workbuddy-ai/skills/youtube-subtitle-study-doc
```

Windows 下是 `%USERPROFILE%\.workbuddy-ai\skills\youtube-subtitle-study-doc\`。
技能是用户级（user-level）的，装一次所有项目都能用。

---

## 使用

不用报技能名，直接说就行：

> 把这个字幕整理成精读稿：`~/Downloads/xxx.txt`
> 帮我整理一下这个 YouTube 字幕，做成中英对照的 Word

技能会自动触发。它一般不反问，只在两种情况下先确认：**你的描述和文件实际对不上**（比如你说"宋体"、文件里其实是仿宋），或**规范里有多个合理选项**。

产出文件名 = `当天日期 + 空格 + 视频标题`（如 `2026-09-23 The Reality of Change.docx`），标题里的 `\ / : * ? " < > |` 自动换成 `-`。

---

## 目录结构

```
youtube-subtitle-study-doc/
├── SKILL.md                    主流程（技能被触发时读这个）
├── 使用说明书.md                给使用者看的操作说明
├── references/
│   ├── spec.md                 成品规范全字段（结构/字体/字号/缩进/间距/词表）
│   ├── proofreading.md         ASR / 机翻错误速查信号（9 类，带真实例子）
│   ├── docx-pipeline.md        生成 docx 的命令序列与参数模板
│   └── docx-pitfalls.md        踩坑清单（editor SDK + WPS）
└── scripts/
    ├── scan_subtitles.py       扫字幕：块数、词数、建议段数、噪声块
    ├── bold_terms.py           按词表给正文词条批量加粗
    ├── apply_fonts.py          设基准字体 + 剥离段落直设字体
    ├── fix_paraid.py           去重复 paraId（WPS 副作用）
    └── verify_docx.py          交付前全项校验
```

脚本可单独使用：

```bash
# 先看字幕规模
python scripts/scan_subtitles.py ~/Downloads/xxx.txt

# 成品自检
python scripts/verify_docx.py "out.docx" --en Calibri --cn 仿宋 --size 12 --expect-blocks 74

# 只换字体，不动内容
python scripts/apply_fonts.py out.docx --en Calibri --cn 宋体 --size 12
```

---

## 依赖

- **WorkBuddy** 平台，且装有内置技能 `tencent-local-office-edit`（生成 docx 走它的 `edsdk.py`，**不要用 python-docx**）
- Python 3.11+（只用标准库：`zipfile` / `re` / `xml.etree`）
- 处理中文路径前先设 `PYTHONIOENCODING=utf-8`

---

## 几个已规避的坑

1. **WPS 不认文档默认样式里的缩进** —— 首行缩进必须逐段写死，只靠 `docDefaults` 会失效。
2. **中英字体没法用接口一次设好** —— SDK 的 `font_family` 只能写一个名字，会同时落到 ascii/hAnsi/eastAsia，所以直接改文档 XML。
3. **WPS 保存会重写样式表** —— 基准字体要同时写进 `docDefaults` 和 `Normal` 样式。
4. **插空行会把上一段的格式"搬走"** —— 所以顺序是：先插完所有空行，最后再统一设缩进。
5. **WPS 会留下重复的段落 ID** —— Word 打开会提示"修复文档"，需要清掉。

完整清单见 `references/docx-pitfalls.md`。

---

## 说明

示例中出现的视频《The Reality of Change》与频道 Flowering Philosophies 仅作校对实例引用，原视频版权归原作者所有。

---

## License

[MIT](LICENSE)


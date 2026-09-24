---
name: youtube-subtitle-study-doc
description: 把 YouTube 自动字幕 txt（时间戳 / 英文 ASR / 中文机翻）整理成中英对照的英语精读 Word 稿。含语义分段、ASR 与机翻错误校对、全篇大意、重点词汇（按主题分组、带例句精讲）、重点句子，以及固定的排版规范（英文 Calibri / 中文仿宋 / 12pt、首行缩进 2 字符、区块间空行、词汇在正文加粗、可点超链接、居中页码）。当用户提供 YouTube 字幕 txt、提到"字幕整理""精读稿""中英对照""学习稿""校对机翻""ASR 错误"，或要把字幕做成 Word 学习材料时使用。
agent_created: true
---

# YouTube 字幕 → 中英对照精读 Word 稿

## 用途

把 YouTube 自动生成的字幕 txt（典型 4 行一块：时间戳 / 英文 ASR / 中文机翻 / 空行）
整理成一份可直接打印或对着视频精读的中英对照 Word 稿。

核心价值在两件事：**修掉 ASR 与机翻的错误**，以及**按固定规范产出排版统一的成品**。
规范是用户逐轮打磨定下来的，**不要自由发挥**。

## 触发场景

- 用户给一个字幕 txt，说要"整理成学习材料 / 精读稿 / 中英对照"
- 用户说"机翻哪里错了""帮我改改 ASR 识别错误"
- 用户要把之前做好的稿子按新规范重排（改字体、改缩进、改结构）

## 输入与输出

- **输入**：YouTube 自动字幕 txt（可能来自 `Downloads`，或用户直接粘贴）
- **输出**：单个 `.docx`，**文件名 = `当天日期 + 空格 + 视频标题`**
  （如 `2026-09-23 The Reality of Change.docx`），存到用户指定目录
  （本项目惯例：`E:\EnglishStudy\YouTube英语字幕\`）
  - 日期取**生成当天**，格式 `YYYY-MM-DD`
  - 标题取**视频原标题**，与文档里的大标题**逐字一致**
  - ⚠️ 标题里若含 Windows 非法字符 `\ / : * ? " < > |`，**替换成 `-`**（如
    `Why It's Hard: A Story` → `Why It's Hard- A Story`）；结尾的 `.` 和空格也去掉
  - 标题过长时**不截断**（保留完整标题便于辨认），若用户嫌长再改

## 成品规范（摘要）

详细字段、字号、缩进值见 `references/spec.md`，开工前读一遍。

**结构顺序**
1. 标题行：视频标题（居中）/ `频道：` / `原视频链接：`（独立成行 + 超链接）/ `视频时长：… ｜ 整理日期：…`
2. 全篇大意正文（**不写小标题**，200–250 字）
3. `一、分段精读`：`[起始时间戳]` + 英文段 + 中文段 + **空段**
4. `二、重点词汇`：按主题分组（3–4 组），每条 = 中文释义 + 原文例句 + 一句用法提示
5. `三、重点句子`：译文 + 看点
6. 页脚居中页码

**排版**
- 正文：英文 `Calibri` / 中文 `仿宋` / `12pt`（小四）
- 大标题：黑体 22pt 加粗居中；各级小标题：16pt 加粗
- 行距 1.4，段后 6pt
- 正文段（英文 + 中文）首行缩进 2 字符；标题 / 时间戳 / 头部行 / 空段显式归零
- 词汇表里出现过的词和词组，**在正文中加粗**

**明确不要的**：处理说明、「全篇大意」小标题、「怎么用这份稿子」、末尾版权行、Excel 复习版。

## 工作流

### 阶段 1 · 读素材、定切分

1. 读完整 txt，统计字数与字幕块数（`scripts/scan_subtitles.py` 可先跑一遍看规模）
2. 按**语义**切分，不按时间戳切。目标 **每段 90–130 词**（41 分钟 / 7000 词 → 约 70 段）
3. 只保留**每段起始**的时间戳，格式 `[MM:SS]`

### 阶段 2 · 校对

对照 `references/proofreading.md` 里的速查信号逐类扫。原则：

- **只修识别错误，不"提升"说话人的英语**：保留口语原貌（you know / like / 自我修正 / 修辞性重复），
  只删无意义结巴（"I I"、"for for"）
- 拿不准的残缺句**不瞎补**，标 `[听不清]`
- 中文以"读得懂"为准，长句按中文习惯拆开
- **中文只保留修正后的版本，不留改动痕迹**（不写"原文/修正后"）
- 涉及抑郁、焦虑、亲人离世等内容如实翻译，不淡化也不加戏

### 阶段 3 · 写 Markdown 中间稿

先产出纯 Markdown（后续喂给编辑器导入），包含：头部 → 全篇大意 → 分段精读 → 重点词汇 → 重点句子。

- 词汇/句子条目里的词条用 `**加粗**`
- 正文中**凡是词汇表收录过的词和词组，也用 `**加粗**`**（用 `scripts/bold_terms.py` 批量处理）
- 超链接写 `[文字](url)`
- **不要用引用块 `> `**（导入后每行会被拆成独立段落，见 pitfalls）

### 阶段 4 · 生成 docx

走 `tencent-local-office-edit` 技能的 `edsdk.py`，**不要用 python-docx**。
命令序列与参数模板见 `references/docx-pipeline.md`。要点：

1. `close_file` 旧实例 → `create_doc`
2. `doc_set_document_style` 设字体/字号/行距/段间距
3. `doc_insert_markdown` 写入全文（`markdown` 传 `file://<绝对路径>`）
4. `doc_modify_paragraph` 批量设首行缩进（**一次可传上百个 ranges**）
5. `doc_insert_paragraph_with_text` 插区块间空段（**从后往前**）
6. `doc_set_page_number` → `save_file`
7. **`close_file` 后**用 zipfile 改 XML：中文字体（eastAsia）、去重复 paraId

**顺序铁律**：缩进必须在**所有插段动作之后**再设。插空段会把源段落的直接格式搬走。

### 阶段 5 · 校验与交付

跑 `scripts/verify_docx.py`，逐项核对：段落数 / 标题 / 超链接 / 版权行 / 各类缩进计数 /
加粗计数 / 字体名统计 / 字号 / paraId 重复 / zip 完整性 / XML 良构。全绿再 `present_files`。

**交付文件名 = `当天日期 + 空格 + 视频标题`**（如 `2026-09-23 The Reality of Change.docx`）：
- 日期用生成当天的 `YYYY-MM-DD`，标题与文档大标题**逐字一致**
- 标题含 `\ / : * ? " < > |` 时替换为 `-`；结尾 `.` 与空格去掉
- 若同名文件已存在（同一天做了两个视频），**先确认再覆盖**，不要静默覆盖用户的文件

## 铁律（违反会导致返工）

1. **缩进在插段之后设**。`doc_insert_paragraph_with_text` 会把源段落的直接段落格式搬给新空段。
2. **中英分设字体必须改 XML**。SDK 的 `font_family` 只能写一个名字，会同时落到 ascii/hAnsi/eastAsia。
3. **基准字体要同时写 `docDefaults` 和 `Normal` 样式**。WPS 保存会把 docDefaults 的内容搬进 Normal。
4. **WPS 不认 `docDefaults` 里的 `<w:ind>`**。首行缩进必须逐段显式设。
5. **剥离直设格式时跳过标题段**（判据：段落里有没有 `<w:outlineLvl>`），否则会把标题字号抹掉。
6. **校验脚本写成 `.py` 文件再跑**。`python -c "..."` 里 bash 双引号会吃掉反斜杠，正则匹配数会变成 0。
7. **用户手改过的文档，以 XML 实际值为准**。用户的文字描述可能与文件不符（本技能就踩过一次：
   用户说"宋体"，文件里实际是"仿宋"）。**发现差异先问，别照话面猜。**

完整坑清单见 `references/docx-pitfalls.md`。

## 脚本

| 脚本 | 用途 |
|---|---|
| `scripts/scan_subtitles.py` | 扫字幕 txt：块数、词数、建议分段数、异常块 |
| `scripts/bold_terms.py` | 按词表给正文里的词条批量加 `**加粗**` |
| `scripts/apply_fonts.py` | 改 docx 基准字体（英文/中文/字号）+ 剥离非标题段落的直设字体 |
| `scripts/fix_paraid.py` | 去掉重复的 `w14:paraId`（WPS 保存后的常见副作用） |
| `scripts/verify_docx.py` | 成品全项校验 |

脚本都用托管 Python 跑：
`%USERPROFILE%\.workbuddy-ai\binaries\python\versions\3.13.12\python.exe`，
中文路径下先设 `PYTHONIOENCODING=utf-8`。

## 参考文档

| 文档 | 内容 |
|---|---|
| `references/spec.md` | 成品规范全字段（结构、字体、字号、缩进、间距、词表写法） |
| `references/proofreading.md` | ASR / 机翻错误速查信号与实例 |
| `references/docx-pipeline.md` | edsdk.py 命令序列与参数模板 |
| `references/docx-pitfalls.md` | editor SDK + WPS 的完整踩坑清单 |
| `使用说明书.md` | 给用户看的操作说明 |

## 维护本技能

用户改完规范说"更新到技能里"时，**要同步改这几处**（漏一处下次就按旧规范跑）：

1. `references/spec.md` —— 规范的全字段，这是源头
2. `SKILL.md` 的「成品规范（摘要）」+「输入与输出」
3. `使用说明书.md` —— 给用户看的那份
4. 涉及的脚本默认值（如 `verify_docx.py` 的 `--en/--cn/--size`）

改完校验 + 打包：

```bash
PY="$HOME/.workbuddy-ai/binaries/python/versions/3.13.12/python.exe"
SC="$HOME/.workbuddy-ai/plugins/cache/workbuddy-builtin/skill-skill-creator/<版本号>"
S="$HOME/.workbuddy-ai/skills/youtube-subtitle-study-doc"
export PYTHONIOENCODING=utf-8
"$PY" "$SC/scripts/quick_validate.py" "$S"
"$PY" "$SC/scripts/package_skill.py" "$S" "<输出目录>"
```

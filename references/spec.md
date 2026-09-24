# 成品规范（全字段）

> 2026-09-23 定稿。这是用户逐轮打磨的结果，**照做，不要自由发挥**。

## 一、文件

- 格式：`.docx`（只要 Word，**不做 Excel 复习版**）
- 文件名：**`当天日期 + 空格 + 视频标题`**，如 `2026-09-23 The Reality of Change.docx`
  - 日期 = 生成当天，格式 `YYYY-MM-DD`（补零）
  - 标题 = 视频原标题，与文档大标题**逐字一致**
  - **非法字符替换**：`\ / : * ? " < > |` → `-`；去掉结尾的 `.` 与空格
    - 例：`Why It's Hard: A Story` → `2026-09-23 Why It's Hard- A Story.docx`
  - 标题过长**不截断**（便于辨认是哪期）
- 存放：用户指定目录；本项目惯例 `E:\EnglishStudy\YouTube英语字幕\`

## 二、结构（固定顺序）

### 1. 标题行（4 段）

```
The Reality of Change                      ← 视频标题，居中，黑体 22pt 加粗
频道：Flowering Philosophies
原视频链接：https://www.youtube.com/watch?v=xxxx
视频时长：41:10　｜　整理日期：2026-09-23
```

- 标签（频道 / 原视频链接 / 视频时长 / 整理日期）一律**不加粗**，用**全角冒号 `：`**
- 「原视频链接」**独立成行**，放在「频道」下方，URL 做成**可点超链接**
- 分隔符用全角空格 `　` + 竖线 `｜`

### 2. 全篇大意

- **不写「全篇大意」小标题**，直接上正文
- 200–250 字，简短精炼，讲清视频讲了什么、核心观点是什么

### 3. 一、分段精读

每个区块固定 4 段：

```
[00:00]                     ← 时间戳，加粗，首行缩进归零
I didn't think this ...     ← 英文段，首行缩进 2 字符
我从没想过，……              ← 中文段，首行缩进 2 字符
                            ← 空段（做区块隔离）
```

- 时间戳只保留**每段起始**，格式 `[MM:SS]`
- 每段 90–130 词
- 区块之间用**真空段**隔离，**不是**靠段间距

### 4. 二、重点词汇

- 按主题分组，**3–4 组**，如：① 改变与成长 ② 情绪与心理 ③ 自然与意象 ④ 口语高频表达
- 每组 8–10 条，全文 30–40 条
- 每条 3 行：

```
**1. glamorize**　v.　美化、把……理想化
例：We glamorize change. — 我们把改变想得太美。
提示：贬义，常指"把痛苦包装得浪漫"。
```

### 5. 三、重点句子

- 5–8 句，每句 3 行：

```
**1. Change is so easy to glamorize when we've been asking for it for so long.**
译：当我们渴望改变太久，就很容易把它想得过于美好。
看点：sth is easy to + v. 的被动式主动表达；when 引导时间状语。
```

### 6. 页脚

- 居中页码（`doc_set_page_number` → `position: center`）

## 三、字体字号

| 对象 | 英文（ascii/hAnsi） | 中文（eastAsia） | 字号 |
|---|---|---|---|
| 正文（英文段 / 中文段 / 词汇 / 句子 / 时间戳 / 空段） | `Calibri` | `仿宋` | `12pt`（小四） |
| 文档大标题 | `黑体` | `黑体` | `22pt`，加粗，居中 |
| 各级小标题（一、/ 二、/ ①…） | 继承 Calibri | 继承 仿宋 | `16pt`，加粗 |

落盘写法：
- 基准写进 `styles.xml` 的 `docDefaults/rPrDefault` **和** `Normal` 样式：
  `<w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:eastAsia="仿宋" w:cs="Calibri"/>` + `<w:sz w:val="24"/><w:szCs w:val="24"/>`
  （`24` 是半磅值，`24/2 = 12pt`）
- 大标题：`<w:rFonts ... 黑体 .../>` + `<w:sz w:val="44"/>`（22pt）+ `<w:jc w:val="center"/>`
- 小标题：`<w:sz w:val="32"/>`（16pt）

## 四、段落格式

| 项 | 值 | 落盘写法 |
|---|---|---|
| 行距 | 1.4 | `<w:spacing w:line="336" w:lineRule="auto"/>`（336/240 = 1.4） |
| 段前间距 | 0 | `w:before="0"` |
| 段后间距 | 6pt | `w:after="120"`（120 twips = 6pt） |
| 正文首行缩进 | 2 字符 | `<w:ind w:firstLineChars="200"/>` |
| 标题 / 时间戳 / 头部行 / 空段首行缩进 | 0 | `<w:ind w:firstLine="0" w:firstLineChars="0"/>` |

**为什么用 `firstLineChars` 而不是 `firstLine`（磅值）**：字符数缩进会随字号自动换算，
字号改了不用重算。用户手工改的也是 `firstLineChars="200"`。

**首行缩进必须逐段显式设**，不能只靠 `docDefaults` / `Normal` —— **WPS 不认文档默认样式里的 `<w:ind>`**。

## 五、正文加粗规则

**词汇表收录过的单词和词组，在分段精读的正文中要加粗**。

- 加粗落盘：`<w:b/>`（WPS 保存后）或 `<w:b w:val="1"/>`（编辑器写入时）
- 显式取消加粗：`<w:b w:val="0"/>`（头部标签用这个）
- 用 `scripts/bold_terms.py` 按词表批量处理

词表写法（正则片段，不区分大小写，整体套 `\b(...)\b`）：

```python
TERMS = [r'glamorize', r'romanticiz\w*', r'gearing up for', r'take the leap', r'humbling',
         r'willed', r'bring to fruition', r'baby steps', r'redeem', r'vulnerable',
         r'authentic', r'out of whack', r'fight or flight', r'PMDD', r'curate',
         r'dissociated', r'stagnant', r'stifled', r'cut out for', r'ground you',
         r'hydrangea\w*', r'Lace caps', r'star jasmine', r"St\. John's Wort",
         r'golden hour', r'geode', r'rainbows and butterflies', r'a good chunk',
         r'a trigger warning', r'a heads-up', r'go through the motions',
         r'ups and the downs', r'get by', r'letting her down', r'push through', r'take in']
```

处理时**只对不含中文的行**做替换，避免动到中文译文。

## 六、明确否掉的（不要再加回来）

- ❌ 「处理说明」整块
- ❌ 「全篇大意」小标题（正文保留）
- ❌ 「四、怎么用这份稿子 / 复习路径」整节
- ❌ 末尾版权行（"原视频版权归作者所有…"）
- ❌ Excel 复习版（只要 Word）
- ❌ 中文标注"原文/修正后"痕迹（只留修正后的版本）

# YouTube 字幕 → 中英对照精读稿

一个 [WorkBuddy](https://www.workbuddy.cn) 技能（Agent Skill）：把 YouTube 自动生成的字幕 txt（时间戳 / 英文 ASR / 中文机翻）整理成一份可直接打印、也能对着视频精读的**中英对照 Word 稿**。

核心价值在三件事：**修掉 ASR 与机翻的错误**、**按固定规范产出排版统一的成品**、**几秒钟出稿**。

---

## 它产出什么

```
The Reality of Change                        ← 居中，黑体 22pt
原视频链接：https://www.youtube.com/watch?v=xxxx     ← 可点超链接（给了链接才写）
整理日期：2026-09-23

（全篇大意，200–250 字，不写小标题）

一、分段精读
[00:00]
I didn't think this would be the reality of change. ……

我从没想过，"改变"的真面目会是这样。……

[00:19]
……

二、重点词汇
① 择偶与关系
1. soulmate　n.　灵魂伴侣
例：I don't believe there's such thing as soulmate. — 我不相信有"灵魂伴侣"这回事。

2. compatible　adj.　合得来的、兼容的
例：I need to find a partner who I'm truly compatible with. — 我想找一个真正合得来的人。
提示：搭配介词 with；强调"各方面都合得上"，比 fit 正式。

② 情绪与心态
……

③ 句式与搭配
……
```

排版规范（固定，不自由发挥）：

| 对象 | 英文 | 中文 | 字号 |
|---|---|---|---|
| 正文（英文段 / 中文段 / 词汇 / 时间戳） | Calibri | 仿宋 | 12pt（小四） |
| 文档大标题 | 黑体 | 黑体 | 22pt 加粗居中 |
| 各级小标题（一、/ ②…） | Calibri | 仿宋 | 16pt 加粗 |

行距 1.4、段后 6pt；正文段首行缩进 2 字符；区块之间空一行；**词汇表收录过的词在正文里加粗**；页脚居中页码。

### 体量（2026-09-24 提速改版）

- **头部 3 行**：标题 / `原视频链接：`（给了链接才写）/ `整理日期：`
  —— **不写「频道」「视频时长」**（查这两样纯属浪费时间，已废弃）
- **文档只有两节**：`一、分段精读` + `二、重点词汇`（**没有「三、重点句子」**）
- **词表 3 组 × 7–8 条 = 20–22 条**；每条固定 2 行（词条 + 例句）；
  **只有 6–8 条"有坑"的**才加第 3 行 `提示：`

**为什么这么砍** —— 拿一份 15 分钟稿子（223 段）量过：

| 章节 | 段数 | 占段落量 | 贡献的中文字 |
|---|---|---|---|
| 头部 + 全篇大意 | 4 | 2% | 252 |
| 一、分段精读 | 89 | 40% | 2879 |
| **二、重点词汇** | 104 | **47%** | 874 |
| **三、重点句子**（已删） | 26 | **12%** | 469 |

**58% 的段落来自"词汇 + 句子"，却只贡献 17% 的内容量** —— 所以提速只能从这里下刀。
「分段精读」是中英对照的命根子，动不了。
（顺带一提：`build_docx.py` 那套管道只占整体耗时 **不到 1%**，优化它等于白忙。）


---

## ⚡ 一条命令出成品

生成 docx 的整条链子已经封装成 `scripts/build_docx.py`：

```bash
python scripts/build_docx.py 中间稿.md "2026-09-24 视频标题.docx"
```

它在一个进程里跑完：**自检中间稿 → 清残留编辑器实例 → 建文档 → 写内容 → 插区块空行 → 页码 → 保存 → 4 个 XML 补丁**。

为什么值得封装：底层的 `edsdk.py` 是个 CLI，**每次调用都要重启一个 Python 进程**（实测启动 1.0 秒，真正通信只有 0.15 秒）。手工一步步调要 30+ 次，光插 26 个空行就 31 秒，再叠加每一步的推理往返，**一份稿子实测 12 分钟**。串成一个脚本后 **实测 5–6 秒**，产出与手工流程逐字一致。

参数：

| 参数 | 作用 |
|---|---|
| `--no-patch` | 只生成，不打 4 个 XML 补丁 |
| `--keep-open` | 不关闭编辑器实例（要手工接着改时用） |
| `--skip-check` | 跳过中间稿自检 |
| `-v` | 打印重试 / 清理细节 |

脚本自带**中间稿自检**，不合格直接停、**不碰编辑器**：`# 大标题` 存在、区块数、两个二级标题存在且顺序对、全篇大意 200–250 中文字、无中文弯引号、无相邻加粗、每行 `**` 成对。

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

技能会自动触发。它只在两种情况下先确认：**没有原视频链接**（问一句"要提供吗"，答"没有"就做只有标题 + 日期的精简头部），或**你的描述和文件实际对不上**（比如你说"宋体"、文件里其实是仿宋）。

产出文件名 = `当天日期 + 空格 + 视频标题`（如 `2026-09-23 The Reality of Change.docx`），标题里的 `\ / : * ? " < > |` 自动换成 `-`。

---

## 目录结构

```
youtube-subtitle-study-doc/
├── SKILL.md                      主流程（技能被触发时读这个）
├── 使用说明书.md                  给使用者看的操作说明
├── references/
│   ├── spec.md                   成品规范全字段（结构/字体/字号/缩进/间距/词表/引号）
│   ├── proofreading.md           ASR / 机翻错误速查信号（11 类，带真实例子）
│   ├── docx-pipeline.md          生成 docx 的命令序列与参数模板
│   └── docx-pitfalls.md          踩坑清单（editor SDK + WPS，A1–A21）
└── scripts/
    ├── scan_subtitles.py         扫字幕：块数、词数、建议段数、噪声块
    ├── bold_terms.py             按词表给正文词条批量加粗（自动合并相邻加粗）
    ├── build_docx.py             ⚡ 一键流水线：中间稿 → 成品 docx
    ├── apply_fonts.py            设基准字体 + 剥离段落直设字体
    ├── fix_title_and_labels.py   补大标题黑体与居中、去掉头部标签的加粗
    ├── fix_paraid.py             去重复 paraId（WPS 副作用）
    ├── set_indent.py             逐段设首行缩进（顺带修好"自闭合空段"）
    └── verify_docx.py            交付前全项校验
```

脚本也能单独用：

```bash
# 一条命令出成品（最常用）
python scripts/build_docx.py 中间稿.md "out.docx"

# 先看字幕规模
python scripts/scan_subtitles.py ~/Downloads/xxx.txt

# 成品自检
python scripts/verify_docx.py "out.docx" --en Calibri --cn 仿宋 --size 12 --expect-blocks 74

# 只换字体，不动内容
python scripts/apply_fonts.py out.docx --en Calibri --cn 仿宋 --size 12

# 逐段设首行缩进（正文 2 字符，标题/时间戳/空段顶格）
python scripts/set_indent.py out.docx
```

---

## 依赖

- **WorkBuddy** 平台，且装有内置技能 `tencent-local-office-edit`（生成 docx 走它的 `edsdk.py`，**不要用 python-docx**）
- Python 3.11+（只用标准库：`zipfile` / `re` / `xml.etree` / `subprocess`）
- 处理中文路径前先设 `PYTHONIOENCODING=utf-8`

---

## 几个已规避的坑

1. **WPS 不认文档默认样式里的缩进** —— 首行缩进必须逐段写死，只靠 `docDefaults` 会失效。
2. **中英字体没法用接口一次设好** —— SDK 的 `font_family` 只能写一个名字，会同时落到 ascii/hAnsi/eastAsia，所以直接改文档 XML。
3. **WPS 保存会重写样式表** —— 基准字体要同时写进 `docDefaults` 和 `Normal` 样式。
4. **插空行会把上一段的格式"搬走"** —— 所以顺序是：先插完所有空行，最后再统一设缩进。
5. **WPS 会留下重复的段落 ID** —— Word 打开会提示"修复文档"，需要清掉。
6. **markdown 导入有四个"静默坑"** —— `# 大标题` 不给中文字体（回落成仿宋）、也不给居中（变成左对齐）、`**标签：**` 会落成加粗、相邻加粗 `**a** **b**` 会吞掉中间空格。四个都不报错但结果不对，所以最后专门跑脚本补掉。
7. **插空行建出来的段落是"自闭合"的** —— 它没有段落属性容器，用常规正则数不到它，直接往上写缩进还会把文档写坏。
8. **底层 SDK 出错时会 `sys.exit(1)`** —— 直接杀掉调用它的脚本，让"检查返回值再兜底"的代码变成死代码。必须捕获 `SystemExit` 并重定向输出。
9. **新建文档后立刻设样式会撞瞬时竞态** —— 报"document is not opened"，但文档其实建好了。重试即可。
10. **用 SDK 插段落会"破坏源段落"** —— 在标题后插一行，标题的 Heading 属性会丢、还凭空多出一个空段。所以头部这种精确插入**直接改文档 XML**，不走插入接口。
11. **编辑器会自动保存** —— 脚本明明没调 `save_file`，原文件的 mtime 和段落数还是变了。**动 SDK 之前先备份**，回滚用 `close_file force=true` + 覆盖。

完整清单见 `references/docx-pitfalls.md`。

---

## 说明

示例中出现的视频《The Reality of Change》与频道 Flowering Philosophies 仅作校对实例引用，原视频版权归原作者所有。

---

## License

[MIT](LICENSE)

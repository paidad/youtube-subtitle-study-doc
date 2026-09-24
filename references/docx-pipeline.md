# 生成 docx 的命令序列（edsdk.py）

> 走 `tencent-local-office-edit` 技能。**不要用 python-docx。**
> 调用任何工具前先 `python3 edsdk.py schema <工具名>` 确认参数。

## ⚡ 一键入口（首选，2026-09-24 起）

**别手敲下面这一长串。** 用 `scripts/build_docx.py`，一条命令跑完全流程：

```bash
PY="$HOME/.workbuddy-ai/binaries/python/versions/3.13.12/python.exe"
S="$HOME/.workbuddy-ai/skills/youtube-subtitle-study-doc/scripts"
export PYTHONIOENCODING=utf-8
"$PY" -B "$S/build_docx.py" "<中间稿.md>" "<输出.docx>"
```

为什么快：`edsdk.py` 是 **CLI**，每次调用都要**重启 Python 进程**（实测启动 **1.0 秒**，
真正通信只有 **0.15 秒**）。手工走一遍是 30+ 次调用 —— 光 26 次插空段就 31 秒；
再叠加主 Agent 每一步的推理往返，一份稿子实测能到 **12 分钟**。

`build_docx.py` 把整条链子**串进同一个进程**：进程只启一次、端点只发现一次、
Agent 只参与一次，**实测 5–6 秒**。

参数：`--no-patch` / `--keep-open` / `--skip-check` / `-v`。

它内置两件手工做容易忘的事：

- **中间稿自检**（不合格直接停、不碰 SDK）：`# 大标题` 存在、区块数、两个二级标题
  存在且顺序对、全篇大意 200–250 中文字、无中文弯引号、无相邻加粗、每行 `**` 成对。
- **失败重试**：`edsdk._rpc()` 一遇错就 `_die()` → `sys.exit(1)`（**会直接杀进程**，
  让所有兜底分支变死代码），所以必须用 `redirect_stdout`/`redirect_stderr` 包住 + 捕
  `SystemExit`，把失败降级成字符串再判断。对 `document is not opened` 这类
  **瞬时竞态**错误自动重试（实测 3 次里 2 次第 1 发就失败，隔 0.3 秒再发必成功）。

## 前置

```bash
SKILL="<WorkBuddy 安装目录>/resources/app.asar.unpacked/resources/plugins/workbuddy-builtin/skills/tencent-local-office-edit"
PY="$HOME/.workbuddy-ai/binaries/python/versions/3.13.12/python.exe"
cd "$SKILL"
export PYTHONIOENCODING=utf-8      # 中文路径必备

"$PY" edsdk.py list                # 验通
"$PY" edsdk.py call get_pool_status
```

## 完整序列（= `build_docx.py` 内部做的事）

### 0. 清残留实例 + 释放旧实例

```bash
"$PY" edsdk.py call get_pool_status            # 看有没有残留 new_doc_*
"$PY" edsdk.py call close_file file_id=<旧 file_id>
```

同路径留着两个实例会导致保存互相覆盖。
**前一次跑失败留下的 `new_doc_*`（`version: 0`）也会引发 `create_doc` 后的竞态**，
跑之前清掉更稳（`build_docx.py` 的 `clean_pool()` 会自动做）。

### 1. 新建

```bash
"$PY" edsdk.py call create_doc
# → 纯文本：Created blank doc from embedded template. file_id=new_doc_xxxxxxxx_e720, file_path=...
# ⚠️ 不是 JSON！要正则抠 file_id=(\S+?),
```

### 2. 设文档级样式

```bash
"$PY" edsdk.py call doc_set_document_style --json '{
  "file_id": "<FID>",
  "default_text_style": {"font_family": "Calibri", "font_size": 12},
  "default_paragraph_style": {"line_spacing": 1.4, "line_spacing_rule": 1,
                              "spacing_before": 0, "spacing_after": 6}
}'
```

**注意**：`font_family` 会**同时**写 ascii/hAnsi/eastAsia，中英分设必须事后改 XML（见 `apply_fonts.py`）。
`font_size` 是 **pt**；`line_spacing_rule` 1=auto（倍数）。

> 🔴 **紧接着 `create_doc` 调它，可能报 `SetDocDefaults failed: document is not opened`**，
> 而 `create_doc` 明明成功了、`get_pool_status` 里实例也在（`version: 0`）。
> 这是**瞬时竞态**，**重试即可**（实测第 1 次失败、第 2 次成功）。别去改参数。

### 3. 写入全文

```bash
"$PY" edsdk.py call doc_insert_markdown --json '{
  "file_id": "<FID>",
  "idx": 0,
  "markdown": "file://E:/path/to/2026-09-23.md"
}'
# → last_edit_index / position
```

- `markdown` 支持 `"file://<绝对路径>"` 直接读文件，**长正文用这个**，免 shell 转义
- 也支持 `--json-file args.json`
- ⚠️ 引用块 `> ` 会被拆成独立段落，别用

### 4. 设首行缩进 → 推荐放到第 7 步用 `set_indent.py` 做

**别在这一步用 `doc_modify_paragraph` 设缩进**，两个原因（2026-09-24 第三份踩到）：

1. `doc_resolve_document_structure` **有分页** —— 实测返回
   `pagination: {limit: 150, has_more: true, total_nodes: 203}`，
   长文档一次拿不到全部段落坐标，得翻页才能凑齐 ranges。
2. 这一步之后还要插空段（第 5 步），而**插段会把源段落的直接格式搬走**，
   缩进会跑到新空段上 —— 还得再设一次。

所以**缩进统一挪到第 7 步**，用 `scripts/set_indent.py` 在 XML 层一次做完
（一次遍历全部段落，还能顺手把自闭合空段展开）。

<details>
<summary>备选：一定要走 SDK 的话</summary>

```bash
"$PY" edsdk.py call doc_resolve_document_structure --json '{
  "file_id":"<FID>", "mode":"compact", "limit":150, "text_preview_length":40
}' > struct.json
# has_more=true 时要带 offset 继续翻页，把全部段落凑齐

# 正文段 → 2 字符
"$PY" edsdk.py call doc_modify_paragraph --json-file args_indent2.json
#   {"file_id":"<FID>", "ranges":[{...},...], "first_line_indent_chars": 2}

# 标题 / 时间戳 / 头部行 / 空段 → 0
"$PY" edsdk.py call doc_modify_paragraph --json-file args_indent0.json
```

**互斥约束**：`first_line_indent_chars` 不能与 `jc` / `spacing_*` / `line_spacing*` /
`heading_lvl` / `indent` / `block_quote` / `numbering` / `highlight_block` 同包。
</details>

### 5. 插区块间空段

`doc_insert_paragraph` 是拆段底层接口，**建独立空段要用**：

```bash
"$PY" edsdk.py call doc_insert_paragraph_with_text --json '{
  "file_id":"<FID>", "idx": <目标段落的 end_index>, "text": "", "type": 0
}'
```

**顺序**：把所有插入点 `end_index` **降序**排好，从后往前逐个插（前面坐标不漂移）。

> 🔴 **建出来的空段是自闭合 `<w:p w14:paraId="..."/>`** —— 它**没有 `<w:pPr>`**。
> 后果：
> - 用 `<w:p[ >].*?</w:p>` 这种正则**数不到它**（段落总数会莫名少一截）；
> - 用 `re.match(r'(<w:p[^>]*>)')` 往它后面插 `<w:pPr>`，会写出
>   `<w:p .../><w:pPr>…</w:pPr><w:sectPr/>` 这种**畸形结构**（文档末尾那段尤其容易中招）。
>
> **别手写 XML 处理它** —— 交给第 7 步的 `set_indent.py`，它认得自闭合段落。

返回值里有 `next_index` / `position`（**没有** `end_index`，判成功别只看 `end_index`）。
**驱动写法直接用 `scripts/build_docx.py`** —— 它把循环放在同一个进程里，
26 次插空段 0.2 秒；手工 subprocess 循环调 edsdk.py 的话，光进程启动就 26 秒。

### 6. 页码 + 保存

```bash
"$PY" edsdk.py call doc_set_page_number --json '{
  "file_id":"<FID>", "position":"center", "format":"decimal",
  "scope":"whole_doc", "continue_from_prev": true
}'

"$PY" edsdk.py call save_file --json '{
  "file_id":"<FID>", "file_path":"E:/EnglishStudy/YouTube英语字幕/2026-09-23 The Reality of Change.docx"
}'
```

⚠️ `doc_set_page_number` 是**覆盖式**写页脚（与 `doc_insert_footer` 互斥），
**必须放在最后设**，否则会把自己或用户已有的页脚文本清掉。

⚠️ `save_file` 会让 WPS 引擎重写 `styles.xml`（把 `docDefaults` 搬进 `Normal`）。
**所以 SDK 操作必须全部做完，再进第 7 步打 XML 补丁** —— 先打补丁会被冲掉。

### 7. 关闭后改 XML

```bash
"$PY" edsdk.py call close_file --json '{"file_id":"<FID>","force":true}'
```

（有未保存改动时 `close_file` 会拒绝，测试文档直接传 `force: true`。）

然后用 zipfile 打补丁（见 `scripts/`），**顺序固定，别换**：

1. `apply_fonts.py` —— 基准字体写进 `docDefaults` **和** `Normal` 样式；
   `Normal` 里没有 `<w:rPr>` 时会自动插入（新生成的 docx 就是这种，见 pitfalls B5）
2. `fix_title_and_labels.py` —— 大标题补 `黑体` + **补 `<w:jc w:val="center"/>`（居中）**；
   头部标签 `<w:b w:val="1"/>` → `val="0"`
3. `fix_paraid.py` —— 去重复 `w14:paraId`
4. `set_indent.py` —— **逐段设首行缩进**（正文 2 字符、标题/时间戳/头部行/空段归零），
   同时把自闭合空段展开。放最后，因为它要看到全部段落

要点：
- 中文字体：`w:eastAsia` → `仿宋`
- 标题段（含 `<w:outlineLvl>`）**不要**被剥离字体，否则 22pt / 16pt 会被抹掉
- 这四个脚本**幂等** —— 在成品上重跑一遍，`set_indent.py` 应报「改写段数 : 0」，
  `verify_docx.py` 应仍全绿。改动脚本后务必这样回归一次。

改完必须 `zipfile.testzip()` + `ElementTree` 良构检查。

## 常用工具速查

| 工具 | 用途 |
|---|---|
| `get_pool_status` | 查已打开实例，拿真实 `file_id` |
| `doc_resolve_document_structure` | 拿所有段落的 `start_index`/`end_index`/`type` |
| `doc_get_outline` | 拿标题树与坐标 |
| `doc_get_paragraph_property` | 读某段落的对齐/缩进/间距/行距 |
| `doc_get_text_property` | 读某位置**直设**的字体字号（继承的不返回） |
| `doc_modify_paragraph` | 批量改段落属性（支持上百 ranges） |
| `doc_insert_paragraph_with_text` | 插带文本段落 / 独立空段 |
| `doc_delete_paragraph` | 删整段（多段要从后往前，每次重查） |
| `doc_find` | 查文本位置，返回字段是 **`locations`** |

## 校验

```bash
"$PY" scripts/verify_docx.py "E:/path/2026-09-23 The Reality of Change.docx"
```

## 命名

交付文件名为 **`YYYY-MM-DD + 空格 + 视频标题`**（如 `2026-09-23 The Reality of Change.docx`）。
标题里含 `\ / : * ? " < > |` 时替换为 `-`；`save_file` 的 `file_path` 直接按这个拼。

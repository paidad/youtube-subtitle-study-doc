# 生成 docx 的命令序列（edsdk.py）

> 走 `tencent-local-office-edit` 技能。**不要用 python-docx。**
> 调用任何工具前先 `python3 edsdk.py schema <工具名>` 确认参数。

## 前置

```bash
SKILL="<WorkBuddy 安装目录>/resources/app.asar.unpacked/resources/plugins/workbuddy-builtin/skills/tencent-local-office-edit"
PY="$HOME/.workbuddy-ai/binaries/python/versions/3.13.12/python.exe"
cd "$SKILL"
export PYTHONIOENCODING=utf-8      # 中文路径必备

"$PY" edsdk.py list                # 验通
"$PY" edsdk.py call get_pool_status
```

## 完整序列

### 0. 释放旧实例

```bash
"$PY" edsdk.py call close_file file_id=<旧 file_id>
```

同路径留着两个实例会导致保存互相覆盖。

### 1. 新建

```bash
"$PY" edsdk.py call create_doc
# → file_id=new_doc_xxxxxxxx_e720
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

### 4. 批量设首行缩进

先拿结构：

```bash
"$PY" edsdk.py call doc_resolve_document_structure --json '{
  "file_id":"<FID>", "mode":"compact", "limit":0, "text_preview_length":40
}' > struct.json
```

再按段落分类生成两组 ranges，各一次调用（**ranges 支持一次传上百个**）：

```bash
# 正文段 → 2 字符
"$PY" edsdk.py call doc_modify_paragraph --json-file args_indent2.json
#   {"file_id":"<FID>", "ranges":[{...},...], "first_line_indent_chars": 2}

# 标题 / 时间戳 / 头部行 / 空段 → 0
"$PY" edsdk.py call doc_modify_paragraph --json-file args_indent0.json
#   {"file_id":"<FID>", "ranges":[{...},...], "first_line_indent_chars": 0}
```

**互斥约束**：`first_line_indent_chars` 不能与 `jc` / `spacing_*` / `line_spacing*` /
`heading_lvl` / `indent` / `block_quote` / `numbering` / `highlight_block` 同包。

### 5. 插区块间空段

`doc_insert_paragraph` 是拆段底层接口，**建独立空段要用**：

```bash
"$PY" edsdk.py call doc_insert_paragraph_with_text --json '{
  "file_id":"<FID>", "idx": <目标段落的 end_index>, "text": "", "type": 0
}'
```

**顺序**：把所有插入点 `end_index` **降序**排好，从后往前逐个插（前面坐标不漂移）。
插完 **再回头设一次缩进**（插段会把源段落的直接格式搬走）。

驱动写法见 `scripts/`（python subprocess 循环调 edsdk.py，70 次约 1 分钟）。

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

### 7. 关闭后改 XML

```bash
"$PY" edsdk.py call close_file file_id=<FID>
```

然后用 zipfile 打补丁（见 `scripts/apply_fonts.py`、`scripts/fix_paraid.py`）：

- 中文字体：`w:eastAsia` → `仿宋`
- 基准字体同时写 `docDefaults` **和** `Normal` 样式
- 去重复 `w14:paraId`
- 必要时剥离非标题段落的直设字体

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

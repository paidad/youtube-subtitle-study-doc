# 踩坑清单（editor SDK + WPS）

> 全部在 2026-09-23 那次整理里真实踩过。按此处理可省几小时返工。

## A. 编辑器 SDK（edsdk.py）

### A1. 插段会把源段落的直接格式搬走 🔴

`doc_insert_paragraph_with_text(idx=<某段的 end_index>, text="")` 在段末插空段时，
**会把源段落的直接段落格式"搬"到新空段上，源段落退回继承**。

实测：先给 74 个中文段设好 `firstLineChars="200"`，再逐个插空段 →
**72 个中文段的缩进跑到了新空段上**，中文段自己变成"无 `<w:ind>`"。

**处理**：**所有插段动作做完之后，最后再统一设缩进。**

### A2. 建独立空段要用 `doc_insert_paragraph_with_text`

`doc_insert_paragraph` 是"拆当前段落"的底层接口，官方说明明确写了
**不要用它创建独立空段**，要用
`doc_insert_paragraph_with_text(idx=段落 end_index, text="", type=0)`。

### A3. 批量插段从后往前

插入会让后面的坐标漂移。把所有插入点的 `end_index` **降序**排列，从后往前逐个插，
前面段落的坐标就始终有效。

### A4. `doc_modify_paragraph` 的 ranges 可以一次传上百个

实测一次传 271 个 range 正常返回。比逐段调用快两个数量级。
但注意 `first_line_indent_chars` 与 `jc`/`spacing_*`/`line_spacing*`/`heading_lvl` **互斥**，
不能同包传。

### A5. 中英分设字体做不到

`doc_set_document_style` / `doc_update_named_style` 的 `font_family`
**只接受一个字体名，会同时写 ascii / hAnsi / eastAsia**。

要"英文 Calibri + 中文仿宋"，**必须 zipfile 改 XML**。SDK 只用来 open / close / save。

### A6. `doc_update_named_style` 传 `HEADING_1` 会报 style not found

模板里没有这些 styleId。要改标题的段落属性，改用
`doc_get_outline` 拿坐标 + `doc_modify_paragraph` 传 ranges。

### A7. `doc_insert_markdown` 会把引用块拆段

`> ` 引用块的**每一行**会变成独立段落，不是一段。别用引用块做"说明块"。
删多段时要用 `doc_find` 逐个定位锚点，**从后往前**逐次 `doc_delete_paragraph`
（每次重新 find，不要沿用旧 idx）。

### A8. `doc_find` 返回字段是 `locations`

不是 `matches` / `results` / `data`。每项含 `begin` / `end` / `paragraph_id` / `related_text`。

### A9. `doc_get_text_property` 只返回直设属性

继承来的字体字号**不会**返回（只给 `{"idx":N,"version":M}`）。想确认生效字体要看 XML。

### A10. `edsdk.py schema <工具名> --raw`

`--raw` 属于 **schema 子命令**的参数。写成 `edsdk.py schema <工具名> --json`
会报 `unrecognized arguments`。

## B. WPS 相关

### B1. WPS 不认 `docDefaults` 里的 `<w:ind>` 🔴

`<w:docDefaults><w:pPrDefault><w:pPr><w:ind w:firstLine="460"/>` 在 **Word 里生效、
在 WPS 里完全不生效**。所以**首行缩进必须逐段显式设**，不能只靠文档默认样式。

### B2. WPS 保存会重写 `styles.xml`

用户在 WPS 里保存一次后：

- `docDefaults/pPrDefault` 里的行距 / 段距 / 首行缩进被**搬进 `Normal` 样式**（`w:styleId="1"`），
  `<w:pPrDefault/>` 变空
- `docDefaults` 里的 `<w:sz>` 被**删掉**，字号只留在 `Normal` 样式里
- `<w:b w:val="1"/>` 被规范化成 `<w:b/>`
- `"Microsoft YaHei"` 被改成 `"微软雅黑"`

**处理**：设全文基准字体 / 字号时，**必须同时改 `docDefaults/rPrDefault` 和 `Normal` 样式**。
校验加粗要同时认 `<w:b/>` 和 `<w:b w:val="1"/>`。

### B3. WPS 会留下重复的 `w14:paraId`

Word 打开可能弹「修复文档」。用 `scripts/fix_paraid.py` 给重复项重编号为未占用的 8 位十六进制。

### B4. WPS 占用文件

用户正开着某个文件时该文件被独占：Python 写入报 `PermissionError`。
改文件前先看同目录有没有 `~$xxx.docx`。

## C. Python / shell

### C1. `os.replace()` 会报 WinError 5

该目录下覆盖写入用 `os.replace()` 报 `WinError 5`（文件被占），
但 **`open(path, 'wb')` 直接覆盖写入可以成功**。配 5~6 次重试兜底。

### C2. `python -c "..."` 里的正则会被 bash 吃掉反斜杠 🔴

用 `python -c "..."` 时，bash 双引号会把 `\*` `\[` 之类处理掉，
导致 `re.findall` 返回 0，**误判成"功能没生效"**。

**处理**：**校验脚本一律写成 `.py` 文件再跑。**

### C3. 中文路径乱码

处理中文路径文件前先设 `PYTHONIOENCODING=utf-8`。

## D. 内容层面

### D1. 用户描述可能与文件实际不符 🔴

用户说"中文改成了宋体"，XML 里实际是"仿宋"（84 处，全文无一处宋体）。
用户说"字号改好了"，实测一个区块里三个不同的字号（英文 12pt / 中文 11.5pt / 时间戳 11pt）。

**处理**：**以 XML 实际值为准，并把差异明确提出来让用户确认**。
猜错要重做几百段，问一句成本极低。

### D2. 剥离直设格式时要跳过标题段

把"样板段字体"推广到全文时，要剥掉非标题段落里的 `<w:rFonts>`（带字体名的）和 `<w:sz>`。

**判据**：段落里**有没有 `<w:outlineLvl`**。
有 → 是标题段，**必须跳过**，否则大标题的 22pt、小标题的 16pt 会被一起抹掉。

另外：**只剥带字体名的 `rFonts`**，纯 `<w:rFonts w:hint="eastAsia"/>` 要留着
（它影响歧义字符走哪个字体）。

## E. 校验清单（交付前必跑）

- `zipfile.testzip()` → `None`
- 所有 `.xml` / `.rels` 过一遍 `ElementTree.fromstring`
- 段落总数与预期一致
- 标题段落列表 + 各自字号（大标题 44 / 小标题 32）
- `HYPERLINK` 域存在且目标正确
- 版权行残留 = False
- 各类缩进计数（正文 `firstLineChars="200"` / 其余 `="0"`）
- 加粗计数（`<w:b/>` + `<w:b w:val="1"/>`）
- 字体名统计（只应出现 Calibri / 仿宋 / 黑体）
- `w:sz` 取值集合
- `w14:paraId` 无重复

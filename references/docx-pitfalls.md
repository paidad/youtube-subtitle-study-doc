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

⚠️ **但「首行缩进」别走这条路** —— 它要先 `doc_resolve_document_structure` 拿坐标，
而那个接口**有分页**（实测 `limit:150 / total_nodes:203`），长文档一次拿不全，
得翻页凑 ranges。改用 `scripts/set_indent.py`（XML 层，一次遍历全部段落）。

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

### A11. `create_doc` 返回的是**纯文本**，不是 JSON 🔴

```
Created blank doc from embedded template. file_id=new_doc_146483423712100_e3eb, file_path=...
```

用 `json.loads()` 会抛异常 / 拿不到 `file_id`。要正则抠：
`re.search(r'file_id=(\S+?),', out)`。
（`save_file`、`close_file` 也是纯文本；`get_pool_status`、`doc_resolve_document_structure`
等查询类工具才是 JSON。）

### A12. `close_file` 有未保存改动时会报错

`close_file: file_id=xxx has unsaved changes. Call save_file first, or set force=true`。
测试用的临时文档直接传 `{"file_id": ..., "force": true}`。

### A13. markdown 的 `# 大标题` **不会**给中文字体 🔴

`doc_insert_markdown` 的 `# 标题` 只落 `<w:sz w:val="44"/>`（22pt）+ `<w:b/>`，
**不写 `<w:rFonts>`**，中文字符会回落成基准的「仿宋」——不符合规范的「黑体」。
（另外它**也不给居中**，见 A17。）
必须事后改 XML（`scripts/fix_title_and_labels.py`）。
判据：段落里 `<w:rFonts>` 出现在 **pPr 的 rPr** 和 **run 的 rPr** 两处。

### A14. markdown 的 `**标签：**` 落成的是**加粗**，不是取消加粗 🔴

规范要求头部标签（原视频链接 / 整理日期；「频道」「视频时长」2026-09-24 起已废弃）**不加粗**，
但 markdown 没有"取消加粗"的写法，`**原视频链接：**` 会落成 `<w:b w:val="1"/>`。
上一份成品里是 `<w:b w:val="0"/>` —— 那是事后改的。
**处理**：导入后把头部标签段的 `<w:b w:val="1"/>` 全部换成 `val="0"`。
`verify_docx.py` 会检查 `<w:b w:val="0"/>` 出现次数 ≥ 头部标签行数。

### A15. 相邻加粗会**吞掉空格** 🔴

markdown 里写 `**self-doubt** **trickles in**`，导入后变成**一个 run**，
中间的空格被吃掉 → 正文里出现 `self-doubttrickles in`。
**处理**：词表加粗时就把相邻的 `**a** **b**` 合并成 `**a b**`
（`scripts/bold_terms.py` 已内置这一步）。
校验：搜 `****`、`** **`，以及读回 XML 看有没有两个单词粘在一起。

### A16. `doc_insert_paragraph_with_text(text="")` 建出的空段是**自闭合** `<w:p .../>` 🔴

2026-09-24 第三份才暴露。26 次调用全部返回 `"insert_paragraph_with_text ok"`、
位置也对（每个中文段之后一个），但**段落统计正则 `<w:p[ >].*?</w:p>` 匹配不到自闭合标签** ——
229 个段落只数到 202。

更坑的是：文档**末尾模板自带**的那个 `<w:p w14:paraId="19D4ED60"/>` 会被
`re.match(r'(<w:p[^>]*>)')` 命中，往它后面插一个孤立的 `<w:pPr>`，把文档写成

```xml
<w:p w14:paraId="19D4ED60"/><w:pPr><w:ind w:firstLineChars="0"/></w:pPr><w:sectPr/>
```

这种**畸形结构**（段落开标签已经自闭合了，后面又跟一个 pPr）。

**处理**：
- 段落正则一律写 **`<w:p\b[^>]*/>|<w:p[ >].*?</w:p>`** —— 前半段不能少。
- 自闭合空段先**展开**成 `<w:p ...><w:pPr><w:ind w:firstLineChars="0"/></w:pPr></w:p>` 再处理。
- 别自己手写这段逻辑，用 `scripts/set_indent.py`（已内置）。
- **自查信号：`fix_paraid.py` 报的 paraId 数 ≠ 段落正则数到的段数时，差的就是自闭合空段。**
  （那次 229 vs 202。）
- `verify_docx.py` 现在会打印「⚠️ 有 N 个自闭合空段」，并且因为空段没有 `<w:ind>`，
  「时间戳/空段缩进归零」会直接判 ❌ —— 能兜住。

### A17. markdown 的 `# 标题` **不给 `<w:jc>`** 🔴

`doc_insert_markdown` 的 `# 标题` 落的是
`<w:ind .../><w:outlineLvl w:val="0"/>`，**没有 `<w:jc w:val="center"/>`** ——
大标题默认**左对齐**，不符合「居中」规范。

第二份成品里有 `w:jc="center"`，是当时用 `doc_modify_paragraph` 额外设的，
**不是 markdown 自带的**，所以这个坑一直没暴露，到第三份才被 `verify_docx.py` 抓到
（❌ 大标题居中）。

**处理**：`scripts/fix_title_and_labels.py` 现在会补 `<w:jc w:val="center"/>`，
位置插在 `<w:ind>` 之后、`<w:outlineLvl>` 之前 ——
**OOXML 对 `pPr` 子元素顺序有要求**（pStyle → … → spacing → ind → jc → … → outlineLvl），
顺序错了 Word 可能不认。

### A18. `edsdk._rpc()` 出错会 `sys.exit(1)`，直接杀掉你的脚本 🔴

`edsdk.py` 的 `_die()` 一遇 JSON-RPC 错误就 `_emit_error()` → **`sys.exit(1)`**
（同时往 stdout / stderr 各打两行 `error: ...` 和一行 JSON）。
所以如果你写自动化脚本时这样包：

```python
r = edsdk._rpc('tools/call', {...})     # 出错时进程直接没了
if 'error' in r:                        # ← 死代码，永远走不到
    return 1
```

**正确写法**（`scripts/build_docx.py` 的 `make_caller()` 就是这么干的）：

```python
import contextlib, io
buf, err = io.StringIO(), io.StringIO()
try:
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(err):
        r = edsdk._rpc('tools/call', {'name': tool, 'arguments': args})
except SystemExit:
    return buf.getvalue().strip().split('\n')[0] or 'error: unknown'   # 降级成字符串
```

两个 `redirect` 都要加：`_die()` 往**两个流**都写，只收 stdout 的话流水线日志里
还会混进它自己的 `error: ...` 噪音。

### A19. `create_doc` 之后立刻设样式会撞**瞬时竞态** 🔴

现象：`create_doc` 明明成功（返回了 `file_id`），紧接着
`doc_set_document_style` 报

```
JSON-RPC 错误 -32603: doc_set_document_style: SetDocDefaults failed:
[-1]SetDocDefaults failed: document is not opened.
```

`get_pool_status` 里实例是在的，但 `version: 0` —— 说明 create 之后再没成功操作过。

**这是瞬时错误，重试就好**（实测 3 次里 2 次第 1 发就失败；隔 0.3 秒再发就成功）。
**别去改参数、别以为是 `file_id` 抠错了。**

另：前一次跑失败会留下 `new_doc_*` 残留实例，**它会加重这个竞态** ——
开工前先 `get_pool_status` + `close_file --force` 清一遍
（`build_docx.py` 的 `clean_pool()` 自动做）。

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

### B4. WPS 占用文件 🔴

用户正开着某个文件时该文件被独占：Python 写入报 `PermissionError`，
`os.rename()` 报 `WinError 32`（另一个程序正在使用此文件）。

**探测**：看同目录有没有 WPS 属主文件（形如 `~$xxx.docx`）。

⚠️ **属主文件名的规则是 `~$` + 原文件名去掉前 2 个字符**，不是 `~$` + 完整名：

- `2026-09-24 get up and keep going.docx` → `~$26-09-24 get up and keep going.docx`
- 按完整名拼 `~$2026-09-24 …` 去探会**漏判**（2026-09-24 就这么踩了一次，
  脚本报告"属主文件不存在"，实际文件正被锁着）

**查是谁占着**：`tasklist | grep -i wps`

- ⚠️ 本机 **PowerShell 工具的输出会被吞**（`Get-Process | Where-Object {...}` 跑完 exit 0 但零输出），
  查进程改用 bash 的 `tasklist` 更可靠。
- 编辑器 SDK 的 `get_pool_status` 若返回 `open_editors: []`，说明**不是** WorkBuddy 编辑器占的，
  基本就是 WPS（实测有 8~10 个 `wps.exe` 进程在跑）。

**处理**：让用户关掉 WPS 里的该文件。改好的版本先存成 `.new` 放旁边，
等文件释放后再覆盖回去。

⚠️ **要提醒用户关的时候选「不保存」** —— 他 WPS 里显示的是旧内容，
一旦保存就会把我们改好的内容盖掉。

### B5. 新生成的 docx 里 `Normal` 样式**没有 `<w:rPr>`** 🔴

`create_doc` 出来的模板，默认样式长这样：

```xml
<w:style w:type="paragraph" w:styleId="xgyoku" w:default="1">
  <w:name w:val="Normal"/><w:pPr><w:widowControl w:val="0"/><w:jc w:val="left"/></w:pPr>
</w:style>
```

**没有 `<w:rPr>`**。`apply_fonts.py` 早期版本的正则要求 rPr 存在，
于是直接跳过并打印「未找到默认段落样式（Normal）」—— 结果只有 `docDefaults` 有基准字体，
一旦用户在 WPS 里保存（WPS 会把 docDefaults 搬进 Normal），字号/字体就丢了。
**现已修正**：`apply_fonts.py` 找不到 rPr 时会**插入**一份。
（注意 styleId 每次生成都不一样，可能是 `c3lag8`、`xgyoku`…，**不能写死**，
判据只能用 `w:default="1"`。）

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

### D3. 「全篇大意 200–250 字」指的是**中文字数** 🔴

不要把拉丁字母、数字、标点都算进去。上一份成品实测：
非空白字符 **316**，中文字符 **214** —— 规范要的是后者。

**量法**：`len(re.findall(r'[\u4e00-\u9fff]', text))`。

### D4. 字幕 txt 可能**只有英文 ASR、没有中文机翻**

用户下载的 txt 不一定是「时间戳 / 英文 / 中文」四行一块。
2026-09-24 那份《get up and keep going》就是**只有英文**（`scan_subtitles.py`
会报「中文总字数 0 / 中文为空的块 = 全部」）。
**处理**：中文全部自己译，反而少了一层机翻坑；分段仍按 90–130 词走。

### A20. `doc_insert_paragraph_with_text` 会**破坏源段落** 🔴

2026-09-24 补头部链接时踩到。拿 `idx = 标题段.end_index` 插一行，结果：

- **标题丢了 Heading 属性**（`type` 从 `Heading` 变 `Paragraph`，`<w:outlineLvl>` 没了）
- **凭空多出一个空段**，而且是**空 Heading**，带着原标题的 `paragraph_id`
- 返回字段是 **`range.end` / `next_index` / `position` / `paragraph_id`**，
  **不是 `end_index`** —— 按 `end_index` 解析会「假失败」，但插入其实已经生效，
  照原样重试就会插两遍

**处理**：头部这种「精确结构插入」**不要用 SDK 的插入接口**，直接改 `word/document.xml`：
定位第 1 段 → 在它后面拼两段 `<w:p>`（标签 run 带 `<w:b w:val="0"/>`；
链接用 `HYPERLINK` 域 + `<w:color w:val="0563c1"/>` + `<w:u w:val="single"/>`）
→ `paraId` 取未占用的 8 位十六进制 → `ET.fromstring` 良构校验 → 重打包写盘。

### A21. 编辑器会**自动保存**，改了内存就等于改了磁盘 🔴

同一次踩到：脚本两次都在 `save_file` 之前就中止了（只存到预览路径），
但**原文件的 mtime 和段落数还是变了**（222 → 224）。引擎自己有自动保存。

**处理**：**动 SDK 之前先 `cp` 一份备份**。回滚流程：

```bash
close_file <file_id> force=true   # 丢弃内存改动，释放实例
cp <备份> <原文件>                 # 再覆盖回来
```

⚠️ `close_file` 不带 `force` 时，有未保存改动会**拒绝关闭**（见 A12）。

## E. 校验清单（交付前必跑）

- `zipfile.testzip()` → `None`
- 所有 `.xml` / `.rels` 过一遍 `ElementTree.fromstring`
- 段落总数与预期一致
- 标题段落列表 + 各自字号（大标题 44 / 小标题 32）
- `HYPERLINK` 域存在且目标正确（**只在头部有「原视频链接」行时才查**）
- 版权行残留 = False
- **头部无「频道」/「视频时长」行**（2026-09-24 起废弃，见 `spec.md`）
- **无「三、重点句子」节**（2026-09-24 整节删除，见 `spec.md`）
- 各类缩进计数（正文 `firstLineChars="200"` / 其余 `="0"`）
- 加粗计数（`<w:b/>` + `<w:b w:val="1"/>`）
- `<w:b w:val="0"/>` ≥ 头部标签行数（头部标签显式不加粗；2026-09-24 起头部只有「原视频链接 / 整理日期」，所以是 ≥ 2）
- 字体名统计（只应出现 Calibri / 仿宋 / 黑体）
- `w:sz` 取值集合（正文继承 24；标题 32 / 44）
- `w14:paraId` 无重复
- **没有两个单词粘在一起**（相邻加粗吞空格的副作用，见 A15）：
  抽查正文里有没有 `[a-z][A-Z]` 之外的可疑粘连，或直接对比原文字符串
- **`Normal` 样式里确实有 `<w:rPr>`**（见 B5）
- **大标题段里有 `<w:jc w:val="center"/>`**（见 A17）——
  markdown 不会给，漏了就是左对齐
- **没有残留的自闭合 `<w:p .../>`**（见 A16）——
  段落正则要写成 `<w:p\b[^>]*/>|<w:p[ >].*?</w:p>` 才数得准；
  跑过 `set_indent.py` 后应为 0
- **「段落数」和「paraId 数」应该相等** —— 差一截就是漏了自闭合空段（见 A16）

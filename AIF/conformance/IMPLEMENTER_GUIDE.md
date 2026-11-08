# AIF/0.9 Implementer's Guide（语言无关）

**给谁看**：拿到本文件 + `specification/AIF-0.9.md` + `conformance/vectors.json`、
准备从零写一个 AIF/0.9 实现的开发者。

**本文件的约束**：描述的是**线上的字节与文法**，不引用任何语言的标准库、
不引用任何现有实现的函数名、模块路径或内部数据结构。若某个行为只能靠
"看参考实现怎么写的"才能确定，那是规范的缺陷，请报告，不要猜。

配套正式规范：`specification/AIF-0.9.md`（ normative ）。
本文件是它的实现者视角展开；两者冲突时**以正式规范为准，并报告该冲突**。

---

## 1. 词法层

| 项目 | 规则 |
|---|---|
| 编码 | UTF-8 |
| 行分隔符 | 仅 LF (`0A`)、CRLF (`0D 0A`)、CR (`0D`)。**不得**把 VT/FF/FS/GS/RS/NEL/U+2028/U+2029 当换行 |
| 值 | 一个值恰好占一整行；值行内允许出现未转义空格 |
| 空行 | 只有两种合法位置：header 之后恰好一个分隔空行；记录之间的装饰空行（decoder 可跳过）。**schema 行本身可以是空行**（空 schema），必须按位置读取，不得"跳过所有空行" |
| 尾随空行 | 允许，decoder 忽略末尾空行 |
| 大小写 | 所有标记、类型、布尔字面量均区分大小写 |

## 2. 文档结构

```ebnf
document   = header , LF , blank_line , [ "@single" , LF ] , schema_line , LF ,
             { blank_line } , { record_block } ;
header     = "AIF/0.9" ;
record_blk = "@record" , LF , { slot } ;
```

- `header` 必须是第 1 行，逐字等于 `AIF/0.9`。
- 第 2 行是空分隔行。
- `@single` 可选：出现时顶层是**单个对象**且必须恰好有 1 个 `@record`；
  不出现时顶层是**对象数组**（可以是空数组）。
- 空数组 `[]` 编码为 `AIF/0.9` + 一个空行（无 schema 行、无 `@record`）。
- schema 行之后按位置读取 `@record` 块，直到文本结束。

**关键**：schema 行按**位置**取，不是"找第一个非空行"。空 schema 是合法的
（例如 `[{}]`），跳过空行会导致把 `@record` 误当 schema 解析。

## 3. Schema 行

schema 行由空格分隔的 token 组成，可为空。

```ebnf
token     = path , [ "[]" ] , [ "?" ] , ":" , type ;
path      = segment , { "." , segment } ;
type      = "s" | "i" | "f" | "b" | "n" | "object" ;
segment   = 不含 " . : ? [ ] { } / \\ \" ' @ - 空白" 的非空字符串，且首字符不是 '@' 或 '-' ；
```

- `?` 表示该字段 optional，位置在 `[]` 之后、`:` 之前：如 `tools[]?:object`。
- `[]` 表示数组字段：标量数组 `tags[]:s`、对象数组 `tools[]:object`。
  类型 `object` **只能**用于带 `[]` 的 token。
- `.` 是嵌套路径分隔符，`profile.age:i` 解码后重建为
  `{"profile": {"age": <int>}}`。
- 字段顺序由**全体记录**推断：按字段首次出现顺序排列；
  **所有 optional 字段必须排在 schema 尾部**（先全部 required，再全部 optional，
  各自保持首次出现顺序）。
- 同一字段在所有记录中的非 null 值类型必须一致，否则编码器必须报错。

## 4. 记录与槽位

**每个 schema 字段在每个 `@record` 中恰好占一个"槽位"**，顺序与 schema 一致。
槽位可以是 1 行，也可以是一个多行块（数组 / 对象数组）。
这条"固定槽位"规则是游标不漂移的唯一保证，不得用"看下一行是不是 `@record`"
来猜测 optional 字段是否存在。

槽位取值：

| 行 | 含义 |
|---|---|
| `-` | 该字段在此记录中**缺失**（不写入解码结果的键） |
| `@null` | 该字段值为 `null`（**要**写入键） |
| `\e` | 空字符串 `""` |
| `@onull:<path>` | 某个祖先嵌套对象显式为 `null`；见 §6 |
| `@array` + 后续块 | 标量数组，见 §7 |
| `@objects` + 后续块 | 对象数组，见 §7 |
| 其他 | 标量字面量，见 §5 |

## 5. 标量类型与字面量

| 类型 | 字面量 | 解码结果 |
|---|---|---|
| `s` | 转义后的字符串 | 字符串 |
| `i` | `[+-]?[0-9]+`，且绝对值 ≤ 2^53−1 | 整数 |
| `f` | 有限十进制数（可含指数），不得为 NaN/Infinity | 浮点数 |
| `b` | `true` / `false`（仅这两个） | 布尔 |
| `n` | `@null` | `null` |

`i` 超出 IEEE-754 安全范围、非有限浮点、非法布尔字面量都必须**报错**，
不得静默接受或截断。

### 转义表（字符串值）

| 序列 | 还原 |
|---|---|
| `\\` | 反斜杠 |
| `\s` | 空格（Structured Mode 产出；Text Mode 直接写裸空格，两者 decoder 都必须接受） |
| `\n` `\r` `\t` | LF、CR、TAB |
| `\uXXXX` | 码位 `U+XXXX`（4 位十六进制，大小写均可） |
| `\@` | 字面 `@` |
| `\-` | 字面 `-` |
| `\e` | 仅当**整个值行**恰好是 `\e` 时表示空字符串 |

规则：

1. 任何 C0 控制字符（`U+0000`–`U+001F`，`\n`/`\r`/`\t` 除外）、
   C1（`U+007F`–`U+009F`）、`U+2028`、`U+2029` **必须**写成 `\uXXXX`。
   否则某些语言的行切分会把一个值拆成两行。
2. 原始标记判断发生在**反转义之前**：整行 `-` 是缺失、整行 `@null` 是 null、
   整行 `\e` 是空串。字符串值 `@null` 必须编码成 `\@null`，
   值 `-dash` 必须编码成 `\-dash`，值 `@missing` 编码成 `\@missing`。
3. 未知转义序列（如 `\q`）必须报错。
4. 逗号 `,` 在值中**无需转义**（值按整行读取，不是逗号分隔）。

## 6. 嵌套路径与显式 null 对象

解码时把 `a.b.c` 逐层构造为嵌套对象。若父层已存在且不是对象，重建之。

**难点**：`{"result": null}` 与「`result` 字段完全不存在」在扁平路径模型里
都会表现为所有 `result.*` 子字段缺失，二者必须可区分。

规则：当某记录中祖先路径 `<p>` 存在且值为 `null`：

- 属于 `<p>.*` 的第一个 schema 槽位写 `@onull:<p>`；
- 属于 `<p>.*` 的其余槽位写 `-`；
- decoder 读到 `@onull:<p>` 时，把路径 `<p>` 设为 `null`，
  并忽略该组其余槽位。

`@onull` 的路径必须是该槽位字段名的祖先（以 `<p>.` 开头），否则报错。

## 7. 数组

### 标量数组 `tags[]:s`

```
@array
3
AI
technology
agents
```

- 第 1 行 `@array`，第 2 行是非负整数元素个数，随后恰好 count 行元素。
- 元素按声明的 item 类型解码；`@null` 表示单个元素为 null。
- 空数组：count = 0，无元素行。

### 对象数组 `tools[]:object`

```
@objects
name:s arguments.query?:s result.success?:b
2
web_search
AI\stechnology
true
calculator
1+1
-
```

- 第 1 行 `@objects`，第 2 行是**该对象数组自己的 schema 行**（同样 grammar），
  第 3 行是对象个数。
- 随后每个对象按该 schema 逐字段占一个槽位，规则与顶层记录完全相同
  （含 `-`、`@null`、`@onull`、嵌套路径、optional 尾部排序）。
- 数组内元素若又是数组（嵌套数组）：AIF/0.9 **不支持**，必须报错。

## 8. 编码器必须拒绝的情形

| 情形 | 要求 |
|---|---|
| 顶层不是对象 / 对象数组 | 报错 |
| 同一字段出现冲突的非 null 类型 | 报错，消息含字段名 |
| 数组内元素类型不一致 / 元素是数组 | 报错 |
| 字段名含空白或 `.:?[]{}/\"'` 等语法字符、以 `@`/`-` 开头 | 报错 |
| 整数超出 ±(2^53−1)、NaN、Infinity | 报错 |
| 对象为空 `{}` | 合法（空 schema 行），**不得**报错 |

原则：**宁可明确报错，也不静默产出会被别的实现解成不同结果的数据**。

## 9. 解码器必须拒绝的情形

- header 不匹配、缺少 schema 行（注意空 schema 合法）。
- 未知 schema token、未知类型、非法类型组合（如 `x:object`）。
- 槽位数与 schema 不符、`@array` / `@objects` count 非数字或为负、块被截断。
- 非法布尔 / 整数 / 浮点字面量、超出安全范围整数。
- 未知转义序列、悬空转义、`@onull` 路径不是祖先。
- `@single` 但记录数不为 1。
- 传入的不是 AIF 文本（例如一个文件路径）当作文本解析 —— 报类型错误，
  **不要**尝试打开文件。

错误消息应带字段名与行号/块号，便于定位；但这属于质量建议，不是一致性硬要求。

## 10. 跨语言互操作约束（必须用同一套）

1. 整数范围 ±(2^53−1)。Python `int` 无界，编码器必须主动拒绝更大的值。
2. 只认 LF / CRLF / CR 为行分隔符；其余控制字符在字符串中必须 `\uXXXX`。
3. 布尔不能当 0/1，整数不能当布尔。
4. `@single` 决定解码返回**对象**还是**数组**，实现必须保留这个形态。
5. **JSON 数字的固有歧义**：字面量 `3.0` 在 Python 解析为 float、在
   JavaScript 的 `JSON.parse` 解析为整数 3，AIF 类型 `i`/`f` 因此可能不同。
   生产者应保证同一字段不混用整数与非整数；测试向量刻意只用非整数浮点。
   这是 JSON 数字模型的限制，不是 AIF 缺陷，但实现者必须知道。
6. 解码结果的键顺序不影响语义相等；一致性测试比较**结构**，不比较键顺序。

## 11. 语言无关的 decoder 骨架

```
lines = split_on_LF_CRLF_CR(text)
drop trailing empty lines
require lines[0] == "AIF/0.9"
p = 1
if p < len and lines[p] == "": p += 1        # exactly one separator
if p >= len: return []                       # empty document
single = (lines[p] == "@single"); if single: p += 1
schema = parse_schema(lines[p]); p += 1      # may be an EMPTY line
records = []
while p < len:
    if lines[p] == "": p += 1; continue
    require lines[p] == "@record"; p += 1
    obj = {}
    for field in schema:
        p, slot = read_slot(lines, p, field) # consumes exactly one slot
        apply(obj, field, slot)              # path rebuild / onull / skip
    records.append(obj)
if single: require len(records) == 1; return records[0]
return records
```

`read_slot` 是唯一推进游标的地方；它返回新的 `p`。任何"看下一行猜字段是否
存在"的写法都会在多行块 / optional / 带空格字符串处漂移。

## 12. 一致性验收

1. 读 `conformance/vectors.json`（严格合法 JSON，42 个向量）。
2. `kind = "positive"`（33 个）：把 `expected_aif_structured` 与
   `expected_aif_text_mode` 分别解码，两者都必须**结构相等**于
   `expected_decoded`。
3. `kind = "negative"`（9 个）：编码器必须拒绝；注意 N002/N003 的
   `not_valid_json = true`，其 `input_json` 是占位 `null`，
   按 `construct_hint` 在宿主语言里构造非有限数值。
4. 双向兼容性（若实现了 encoder）：
   - 你的 encoder 输出 → 参考实现 A 的 decoder → 必须还原 `input_json`；
   - 参考实现 A 的 encoder 输出 → 你的 decoder → 必须还原 `input_json`。
5. 逐字节相等**不是**要求：schema 推断顺序等实现自由度允许文本不同，
   语义一致才算通过。

自动化框架：`conformance/bidirectional.py`（演示 A↔B 双向）；
第三方实现接入方式见 `conformance/THIRD_PARTY_CHECKLIST.md`。

## 13. 报告规范缺陷

若你发现某行为只能靠阅读现有实现才能确定，**不要照抄实现**。
把它记录下来（哪一条、期望的确定性规则是什么），反馈给规范维护者。
这类发现的价值高于多写一个实现版本。

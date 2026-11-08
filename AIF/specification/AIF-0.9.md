# AIF/0.9 Specification

状态：**AIF/0.9 定稿（冻结候选）**。已由两个**作者自写的参考实现**（Python、JavaScript）交叉验证：单元测试 104/104、双实现一致性 78/78、随机 fuzz 639/639、V8 benchmark 17/17 round-trip PASS、双向兼容性 A→B 33/33 与 B→A 33/33。

> 这两个实现**都不是第三方独立实现**。发布门槛 #6（未参与原始实现的开发者照规范独立实现并通过一致性测试）尚未达成，见 `conformance/THIRD_PARTY_CHECKLIST.md` 与 `RELEASE_GATES.md`。在此之前不得标记 1.0 Stable。

AIF（AI-Native Format）是面向 AI Agent / LLM 之间结构化数据交换的面向行的文本格式。它把 schema 与数据分离，让字段名和类型只声明一次，从而减少大量重复的结构性 token。

> AIF 不是「更短的 JSON」。它是一种结构化交换格式。在长自然语言文本上它可能比 JSON 更耗 token，这是设计事实，不是 bug。

---

## 1. 文档结构

```
AIF/0.9
<空行>
[@single]                ← 仅当顶层是单个对象时出现
<schema 行>
@record
<值 1>
<值 2>
...
@record
<值 1>
...
```

- 第一行必须是 `AIF/0.9`。
- 第二行是**恰好一个**空行（分隔行）。
- **schema 行按位置读取，它本身可以是空行**：当所有记录都没有字段（`{}` / `[{}]`）时，schema 为空，该行就是空字符串。解析器**不得**用「跳过所有空行」来定位 schema —— 那会吃掉空 schema 行，把随后的 `@record` 误当成 schema token（这是 fuzz 实测发现过的真实缺陷）。
- `@single` 之后**不插入**空行，紧跟 schema 行。
- 记录区（schema 行之后）允许空行，解析器跳过。
- 顶层是 list 时**不写** `@single`；顶层是 dict 时写 `@single`，且必须恰好有一个 `@record`。
- 空 list 编码为 `AIF/0.9` 加一个空行，解码回 `[]`。
- 空对象 dict `{}` 的 schema 行为空，仍必须有一个 `@record`，解码回 `{}`（`[{}]` 同理回 `[{}]`）。

## 2. Schema 行

由空格分隔的 token 组成，格式 `path[:修饰符]:type`：

| 写法 | 含义 |
|---|---|
| `name:s` | string |
| `age:i` | integer |
| `score:f` | float |
| `active:b` | boolean（`true` / `false`） |
| `empty:n` | 恒为 null |
| `profile.age:i` | 嵌套对象，路径用 `.` |
| `tags[]:s` | scalar 数组 |
| `tools[]:object` | 对象数组 |
| `field?:s` | optional 字段 |
| `tools[]?:object` | optional 对象数组 |

规则：

1. 字段名必须是非空字符串，且不得包含任意空白字符（空格、Tab、换行等）、`.`（与嵌套路径冲突）、`:`（与类型分隔冲突）、`?`（与 optional 标记冲突）、`[]`、`{}`、`/`、`\`、`"`、`'`。首字符不得是 `@` 或 `-`（与保留标记冲突）。encoder 在推断 schema 时逐层校验，违反即抛 `TypeError`，**不允许静默产生有歧义的 token**。
2. optional 字段必须排在 schema 的**尾部**。encoder 自动把 required 排前、optional 排后，并保持各自原有相对顺序。
3. 每个 schema 字段在每条记录中占据**恰好一个值槽位**，顺序严格对应。这是解析器游标不会漂移的根本保证。
4. 嵌套对象被完全扁平化为路径；AIF/0.9 不为嵌套对象单独保留容器行。

## 3. 值与标记

| 标记 | 含义 |
|---|---|
| `-` | 字段缺失（decoder 不创建该键） |
| `@null` | 显式 null（decoder 创建该键并置 `None`） |
| `\e` | 空字符串 |
| `@onull:<path>` | 某个祖先对象显式为 null，见 §6 |
| `@array` | scalar 数组开始，下一行是元素个数，随后每行一个值 |
| `@objects` | 对象数组开始，见 §5 |
| `@record` | 一条记录开始 |
| `@single` | 顶层是单个对象 |

「缺失」与「null」是不同语义，必须用不同标记，不能省略槽位。

## 4. 字符串转义

| 转义 | 含义 |
|---|---|
| `\s` | 空格（Structured Mode） |
| `\n` `\r` `\t` | 换行、回车、制表 |
| `\e` | 空字符串（只能单独占一整行） |
| `\uXXXX` | 码位 U+XXXX（4 位十六进制，大小写均可） |
| `\\` | 反斜杠 |
| `\@` | 字面 `@` |
| `\-` | 字面 `-` |

- 任何以 `@` 或 `-` 开头的字符串值必须转义首字符，否则会与保留标记冲突。
- **控制字符必须转义**：所有 C0（U+0000–U+001F）、C1（U+007F–U+009F）以及 U+2028 / U+2029 一律编码为 `\uXXXX`。Python 的 `str.splitlines()` 会把 `\v`、`\f`、`\x1c`、`\x85`、`\u2028` 等也当作行分隔符；不转义时一个值会被拆成两行，导致游标错位与静默数据丢失。
- 行分隔符**只有 LF / CRLF / CR**。实现不得使用 `str.splitlines()` 这类会额外识别 Unicode 行分隔符的切分方式。
- 未知转义序列是错误，decoder 抛 `ValueError`。
- 值按**整行**读取，因此未转义的空格在值行中也是合法的（见 §8 Text Mode）。

## 5. 数组

### 5.1 Scalar 数组

```
@array
3
AI
technology
agents
```

下一行必须是非负整数 count，随后恰好 count 行。元素可以是 `-` 以外的任意标量；`@null` 表示 null 元素。AIF/0.9 **不支持嵌套数组**。

### 5.2 对象数组

```
@objects
<object schema 行>
<count>
<object 1 的值...>
<object 2 的值...>
```

- object schema 使用与 §2 完全相同的语法。
- 每个对象按 schema 顺序消耗固定数量的槽位。
- 对象数组可以嵌套（对象里的字段本身是对象数组）。
- 空数组写作 `@objects` / `<schema>` / `0`。

## 6. 显式 null 的嵌套对象

扁平路径无法区分「父对象不存在」与「父对象为 null」。为此规定：

- 若某 nested 组的某个祖先路径存在且值为 `null`，该组**第一个**槽位写 `@onull:<祖先路径>`，其余槽位写 `-`。
- decoder 遇到 `@onull:<path>` 时，把该路径设为 `None`，并忽略该组后续的 `-` 槽位。
- `@onull` 的 path 必须是当前字段名的祖先，否则报错。

例：

```json
{"items":[{"name":"A","result":{"success":true}},{"name":"B","result":null}]}
```

```
AIF/0.9

@single
items[]:object
@record
@objects
name:s result.success?:b
2
A
true
B
@onull:result
```

## 7. 类型冲突与错误处理

encoder 在推断 schema 时检测冲突，遇到以下情况抛 `TypeError`（错误消息含字段名）：

- 同一字段在不同记录中出现不同的非 null 类型（如 `1` 与 `"x"`）。
- 同一数组中出现不同类型的元素。
- 数组中出现数组（嵌套数组不支持）。
- 顶层不是 dict 或 list of dict。
- 字段名违反 §2 规则 1（含空格 / 语法字符 / 为空 / 以 `@` 或 `-` 开头）。
- 整数超出 IEEE-754 安全范围 ±(2^53−1)。
- `NaN` / `Infinity`（不是合法 JSON 数字）。

**原则**：encoder 宁可明确拒绝，也绝不产出「自己能解、别的语言解不了」或「解码后数据变了」的 AIF。静默数据损坏比报错严重得多。

decoder 遇到以下情况抛 `ValueError`（消息含字段名或行号）：

- header 不是 `AIF/0.9`；输入不是字符串（防止历史上把 AIF 文本当文件名 `open()` 的错误）。
- schema token 非法或类型未知。
- 记录被截断、槽位不足、数组/对象数量与实际行数不符。
- count 不是非负整数。
- boolean 不是 `true` / `false`；整数、浮点解析失败。
- 未知转义序列；非法 `@onull` 标记。
- `@single` 但记录数不等于 1。
- 期望 `@record` / `@array` / `@objects` 却出现别的行。

## 8. Text Mode（编码器选项）

`json_to_aif(data, text_mode=True)` 不转义字符串值中的空格。

- 因为 AIF 值按整行读取，未转义空格不破坏结构。
- 输出仍是合法 AIF/0.9，**同一个 decoder 无需任何改动或版本区分**。
- 适合长自然语言文本；Structured Mode 保持默认以兼容历史文本。

V8 实测：Text Mode 让 Long Text 从 −109.60% 变为 +4.10%，Messages 从 −29.76% 变为 +8.08%，且 17/17 round-trip 仍 PASS。它不能让所有数据集变正（scalar 数组场景仍为 −37.99%），这是格式的真实边界。

四个 tokenizer（`cl100k_base` / `o200k_base` / `p50k_base` / `r50k_base`）的交叉验证与 crossover 扫描见 `research/FINDINGS.md`；该研究为只读实验，**不改变本规范定义的语法**。

## 9. 完整示例

原始 JSON：

```json
{
  "agent_id": "agent_001",
  "tools": [
    {
      "name": "web_search",
      "arguments": {"query": "AI technology", "limit": 10},
      "result": {"success": true, "count": 10}
    },
    {
      "name": "calculator",
      "arguments": {"query": "1+1", "limit": 1}
    }
  ]
}
```

AIF/0.9：

```
AIF/0.9

@single
agent_id:s tools[]:object
@record
agent_001
@objects
name:s arguments.query:s arguments.limit:i result.success?:b result.count?:i
2
web_search
AI\stechnology
10
true
10
calculator
1+1
1
-
-
```

## 10. 与早期 0.9 草案的差异（定稿说明）

| 项目 | 早期草案 | AIF/0.9 定稿 | 理由 |
|---|---|---|---|
| 缺失字段 | 直接省略 optional 值 | `-` 固定槽位 | 省略会让游标漂移，是 V7 四个 FAIL 的根因 |
| 缺失标记 | `@missing`（恢复包重建版） | `-` | 单字符，V8 实测省 17,930 tokens |
| optional 标记 | `field?:s` | `field?:s` | **沿用草案** |
| 数组写法 | `tools[]:object` | `tools[]:object` | **沿用草案**（重建版的 `tools:array_object` 已废弃） |
| 字符串转义 | `\s` | `\s` + `\@` + `\-` | 防止保留标记歧义导致数据丢失 |
| 顶层单/多记录 | 未定义 | `@single` | 让 `[{...}]` 与 `{...}` round-trip 类型无损 |
| 嵌套对象为 null | 未定义 | `@onull:<path>` | 保留「缺失 vs null」语义 |
| 长文本 | 无方案 | Text Mode 编码器选项 | 阶段 5 结论，未牺牲格式设计 |
| 控制字符 | 无定义 | `\uXXXX` 强制转义 | fuzz 发现 `splitlines()` 隐式换行会静默损坏数据 |
| 数值范围 | 无定义 | 整数限 ±(2^53−1)、拒绝非有限浮点 | 独立 JS 实现无法无损解码越界值 |
| 空 schema | 无定义 | 按位置读取，允许空 schema 行 | fuzz 发现 `[{}]` 会把 `@record` 误当 schema token |

## 11. 明确不支持

- 嵌套数组（数组的元素还是数组）。
- 字段名含空白或 §2 列出的语法字符；字段名以 `@` / `-` 开头。
- 顶层为非对象（标量、数组）。
- 同一 schema 字段出现混合类型。
- 超出 ±(2^53−1) 的整数（需要精确大整数请改用 string）。
- `NaN` / `Infinity`（JSON 本身不支持）。
- 流式 / 增量解析（schema 必须由全体记录预先推断）。
- 多语言 SDK、HTTP / WebSocket 传输层（属于后续路线，按计划不做）。`implementations/js/` 是**规范一致性验证用的参考实现**，不是 SDK。

## 12. 跨语言互操作约束

这些是写第二个独立实现时暴露、随后写入规范并在两边同时修复的约束：

| 项目 | 规则 | 原因 |
|---|---|---|
| 整数 | −(2^53−1) … 2^53−1 | Python `int` 无界、JS `Number` 仅 53 位精度；不限制就会产出别的语言无法无损解码的文本 |
| 浮点 | 必须有限 | `NaN` / `±Inf` 不是合法 JSON 数字 |
| `-0.0` | 解码后可能是 `0.0` | 数值等价，JSON 字面量可不同 |
| 行分隔 | 仅 LF / CRLF / CR | `splitlines()` 的隐式行为会让不同实现互相分歧 |
| 控制字符 | 一律 `\uXXXX` | 保证一个值恰好占一行 |
| 空 schema | 合法，按位置读取 | `{}` / `[{}]` 的 schema 行本身是空行 |
| 对象键 | 允许 `__proto__` / `constructor` | JS 实现用 null-prototype 对象避免原型污染 |

## 13. 一致性验证状态

| 验证 | 命令 | 结果 |
|---|---|---|
| 单元测试 | `python AIF/tests/run_all.py` | 104/104 PASS |
| 规范示例与实现一致 | `python AIF/tests/test_spec_examples.py` | 2/2 MATCH |
| 双实现一致性 | `python AIF/tests/cross_validate.py` | 78/78 AGREE |
| 随机 fuzz | `python AIF/tests/fuzz_roundtrip.py` | 639/639，0 静默损坏、0 分歧 |
| V8 benchmark round-trip | `python AIF/benchmarks/benchmark_v8.py` | 17/17 PASS |
| 示例校验 | `python AIF/examples/make_examples.py` | 5/5 PASS |
| 历史 V7 重跑 | `python test_token_benchmark_v7_rerun.py` | 8/8 PASS |
| 公开测试向量 | `python AIF/conformance/build_vectors.py --verify` | 42 vectors VERIFIED |
| 双向兼容性 A↔B | `python AIF/conformance/bidirectional.py` | A→B 33/33、B→A 33/33 |

一键运行全部：`python AIF/tests/verify_all.py` → **9/9 CHECKS PASSED**。

fuzz 报告见 `tests/FUZZ_REPORT.md`（固定 seed `20261108`，可完全复现）。
公开测试向量见 `conformance/vectors.json`（42 个，严格合法 JSON），
语言无关的实现者指南见 `conformance/IMPLEMENTER_GUIDE.md`。
两套实现都从本规范出发编写，但均由本项目作者完成；任何一次分歧都被视为
**规范 bug**，必须同时修规范与双方实现。第三方实现者若发现只能靠阅读参考
实现才能确定的行为，应作为规范歧义上报，而不是照抄实现。

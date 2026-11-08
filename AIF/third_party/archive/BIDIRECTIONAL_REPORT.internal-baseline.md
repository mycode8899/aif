# AIF/0.9 双向兼容性验证报告

- 生成时间：2026-11-08 13:07:28
- 实现 A：Python 参考实现（`AIF/aif/`）
- 实现 B：**JS reference B (author-written, NOT third-party)**
- 测试向量：`conformance/vectors.json`（42 个）

> ⚠️ **本次运行不满足 1.0 发布门槛 #6**。实现 B 是本项目作者自写的
> 参考实现，不是「未参与原始实现的第三方开发者」的独立实现。
> 本报告只证明**验收框架可用**；要真正满足门槛，必须用
> `--adapter third_party_adapter.json` 由第三方实现重跑。

## 判定口径

- `A→B`：实现 A 产出的 AIF（Structured 与 Text Mode 两种）由 B 解码，必须结构相等于 `expected_decoded`。
- `B→A`：实现 B 从 `input_json` 产出的 AIF 由 A 解码，必须结构相等于 `input_json`。
- 逐字节相等**不是**通过条件，只作信息性记录（schema 推断顺序等实现自由度允许文本不同）。
- negative 向量必须被两个编码器都拒绝。

## 汇总

| 检查 | 结果 |
|---|---:|
| A→B（A 编码 / B 解码） | **33/33** |
| B→A（B 编码 / A 解码） | **33/33** |
| A→A（自检基线） | 33/33 |
| 逐字节相等（信息性） | 33/33 |
| negative 拒绝 | PASS 7 / SKIP 2 / FAIL 0 |
| **双向兼容性** | **PASS** |

## 逐向量明细

| ID | 名称 | A→B | B→A | A→A | 逐字节 |
|---|---|:---:|:---:|:---:|:---:|
| V001 | flat object, 3 scalar types | PASS | PASS | PASS | 是 |
| V002 | flat list with 3 records | PASS | PASS | PASS | 是 |
| V003 | single-element list (not @single) | PASS | PASS | PASS | 是 |
| V004 | empty list | PASS | PASS | PASS | 是 |
| V005 | chinese values | PASS | PASS | PASS | 是 |
| V006 | nested object depth 1 | PASS | PASS | PASS | 是 |
| V007 | nested object depth 3 | PASS | PASS | PASS | 是 |
| V008 | optional field missing in some records | PASS | PASS | PASS | 是 |
| V009 | top-level null value | PASS | PASS | PASS | 是 |
| V010 | explicitly null nested object | PASS | PASS | PASS | 是 |
| V011 | scalar string array | PASS | PASS | PASS | 是 |
| V012 | scalar integer array | PASS | PASS | PASS | 是 |
| V013 | scalar boolean array | PASS | PASS | PASS | 是 |
| V014 | empty scalar array | PASS | PASS | PASS | 是 |
| V015 | array of objects, two fields | PASS | PASS | PASS | 是 |
| V016 | array of objects, optional fields | PASS | PASS | PASS | 是 |
| V017 | empty array of objects | PASS | PASS | PASS | 是 |
| V018 | object array with result = null | PASS | PASS | PASS | 是 |
| V019 | marker-like strings | PASS | PASS | PASS | 是 |
| V020 | leading dash and empty string | PASS | PASS | PASS | 是 |
| V021 | spaces and commas in strings | PASS | PASS | PASS | 是 |
| V022 | backslash, newline, tab, CR | PASS | PASS | PASS | 是 |
| V023 | control chars and Unicode separators | PASS | PASS | PASS | 是 |
| V024 | integer safe-range boundaries | PASS | PASS | PASS | 是 |
| V025 | floats | PASS | PASS | PASS | 是 |
| V026 | booleans false / true | PASS | PASS | PASS | 是 |
| V027 | mixed realistic agent state | PASS | PASS | PASS | 是 |
| V028 | all-null field | PASS | PASS | PASS | 是 |
| E001 | published example: 01_flat | PASS | PASS | PASS | 是 |
| E002 | published example: 02_nested | PASS | PASS | PASS | 是 |
| E003 | published example: 03_tool_calls | PASS | PASS | PASS | 是 |
| E004 | published example: 04_messages_text_mode | PASS | PASS | PASS | 是 |
| E005 | published example: 05_null_and_optional | PASS | PASS | PASS | 是 |

## Negative 向量

| ID | 名称 | 结果 | 说明 |
|---|---|:---:|---|
| N001 | integer beyond IEEE-754 safe range | PASS | A_reject=True, B_reject=True |
| N002 | NaN | SKIP | 值不是合法 JSON，公共向量只存占位 null；请按 construct_hint 在宿主语言内构造 |
| N003 | Infinity | SKIP | 值不是合法 JSON，公共向量只存占位 null；请按 construct_hint 在宿主语言内构造 |
| N004 | conflicting field types | PASS | A_reject=True, B_reject=True |
| N005 | nested array (unsupported) | PASS | A_reject=True, B_reject=True |
| N006 | field name with a space | PASS | A_reject=True, B_reject=True |
| N007 | field name with a dot | PASS | A_reject=True, B_reject=True |
| N008 | field name starting with @ | PASS | A_reject=True, B_reject=True |
| N009 | top-level scalar | PASS | A_reject=True, B_reject=True |

## 已知互操作边界（不隐藏）

- JSON numeric literals such as 3.0 lose their int/float distinction in JavaScript (JSON.parse returns 3). Test vectors deliberately use non-integral floats only. A JS encoder cannot infer the original AIF type from a JSON number literal; this is a JSON model limitation, not an AIF defect.
- Python decodes @single documents to a dict and list documents to a list; implementations must preserve that shape.

## 复现

```bash
python AIF/conformance/build_vectors.py --verify
python AIF/conformance/bidirectional.py
python AIF/conformance/bidirectional.py --adapter path/to/third_party_adapter.json
```

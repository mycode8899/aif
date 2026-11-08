# AIF Benchmark

AI-Native Interchange Format

---

## 1. Benchmark Purpose

AIF is designed as a schema-driven, multilingual, token-efficient data interchange format for AI agents.

The benchmark measures:

- Token count
- Token reduction
- JSON → AIF → JSON round-trip correctness
- Schema reuse efficiency
- Nested data handling
- Optional field handling
- Type inference and type validation
- Edge-case behavior

The benchmark results below are experiment-specific and should not be interpreted as universal compression or token-saving guarantees.

---

## 2. Tokenizer

Token counts are measured with:

```python
import tiktoken
enc = tiktoken.get_encoding("cl100k_base")
```

Token reduction is calculated as:

```text
Token Reduction = 1 - (AIF Tokens / JSON Tokens)
```

---

# 3. AIF 0.1 Benchmark

AIF 0.1 introduced a schema-first, positional representation for structured data.

### 2-item order

| Format | Tokens |
|---|---:|
| JSON | 93 |
| AIF | 45 |
| Reduction | 51.61% |

### 10-item order

| Format | Tokens |
|---|---:|
| JSON | 331 |
| AIF | 131 |
| Reduction | 60.42% |

These results demonstrate that defining field names once can substantially reduce repeated structural tokens.

---

# 4. AIF 0.2 Benchmark

AIF 0.2 added:

- Automatic basic type representation
- String escaping
- Generic flat JSON object support

Type codes:

```text
s = string
 i = integer
 f = float
 b = boolean
 n = null
```

### Single record

| Format | Tokens |
|---|---:|
| JSON | 47 |
| AIF | 34 |
| Reduction | 27.66% |

### 100 records with schema repeated for every record

| Format | Tokens |
|---|---:|
| JSON | 4802 |
| AIF | 3399 |
| Reduction | 29.22% |

This benchmark exposed an important design issue: repeating the schema for every record significantly reduces AIF's efficiency.

---

# 5. AIF 0.3 Benchmark

AIF 0.3 defined the schema once and reused it across multiple flat records.

### 100 records

| Format | Tokens |
|---|---:|
| JSON | 4802 |
| AIF | 1419 |
| Reduction | 70.45% |

### 1000 records

| Format | Tokens |
|---|---:|
| JSON | 48003 |
| AIF | 14020 |
| Reduction | 70.79% |

The results show that schema reuse can greatly improve token efficiency for repetitive fixed-schema data.

These percentages apply to the tested dataset and tokenizer, not to arbitrary JSON data.

---

# 6. AIF 0.4 Benchmark

AIF 0.4 extended the format to nested objects and arrays.

### Single nested record

| Format | Tokens |
|---|---:|
| JSON | 128 |
| AIF | 79 |
| Reduction | 38.28% |

### 100 nested records

| Format | Tokens |
|---|---:|
| JSON | 12902 |
| AIF | 4140 |
| Reduction | 67.91% |

### 1000 nested records

| Format | Tokens |
|---|---:|
| JSON | 129004 |
| AIF | 41042 |
| Reduction | 68.19% |

### Scale test

| Records | JSON Tokens | AIF Tokens | Reduction |
|---:|---:|---:|---:|
| 10 | 1292 | 450 | 65.17% |
| 100 | 12902 | 4140 | 67.91% |
| 1000 | 129004 | 41042 | 68.19% |

### Realistic mixed dataset

| Dataset | JSON Tokens | AIF Tokens | Reduction |
|---|---:|---:|---:|
| Mixed 4-record dataset | 457 | 186 | 59.30% |

---

# 7. AIF 0.5 Benchmark

AIF 0.5 introduced a more general JSON → AIF conversion approach with automatic type detection, nested objects, arrays, and arrays of objects.

## 7.1 Array of Objects

### Single array-object record

| Format | Tokens |
|---|---:|
| JSON | 49 |
| AIF | 57 |
| Reduction | -16.33% |

A negative reduction means AIF used more tokens than JSON for this small dataset.

### 100 independently encoded array-object records

| Format | Tokens |
|---|---:|
| JSON | 4703 |
| AIF | 5699 |
| Reduction | -21.18% |

### Batch 100 records

| Format | Tokens |
|---|---:|
| JSON | 4703 |
| AIF | 3425 |
| Reduction | 27.17% |

### Batch 1000 records

| Format | Tokens |
|---|---:|
| JSON | 47003 |
| AIF | 34025 |
| Reduction | 27.61% |

## 7.2 Realistic datasets

### Realistic nested 1000-record dataset

| Format | Tokens |
|---|---:|
| JSON | 63503 |
| AIF | 42534 |
| Reduction | 33.02% |

### Variable array 1000-record dataset

| Format | Tokens |
|---|---:|
| JSON | 73753 |
| AIF | 49784 |
| Reduction | 32.50% |

These results show that arrays of objects can reduce AIF's advantage when schemas are not sufficiently repetitive, while batching and schema reuse improve efficiency.

---

# 8. AIF 0.5 Round-trip Tests

AIF 0.5 round-trip tests covered:

- Flat objects
- Nested objects
- Basic arrays
- Arrays of objects
- Batch records

The tested cases successfully reconstructed the original JSON structures.

The AIF 0.5 array-of-object syntax used a temporary `|` delimiter inside rows. This was an experimental syntax and had known escaping limitations for strings containing `|`.

---

# 9. AIF 0.6 Optional Fields

AIF 0.6 introduced Optional Fields.

Syntax:

```text
field?:type
```

Example:

```text
name:s city:s coupon?:s
```

The `?` indicates that a field may be absent from a record.

## 9.1 Optional Field Rule

Optional fields must appear at the end of the schema.

Valid:

```text
name:s city:s coupon?:s age?:i
```

Invalid:

```text
name:s city:s coupon?:s age:i
```

This rule prevents ambiguity when decoding records with omitted trailing fields.

## 9.2 Schema Construction

AIF 0.6 collects fields across all records instead of using only the first record.

Therefore a field can first appear in a later record and still be included in the schema.

---

# 10. AIF 0.6 Token Benchmark

Benchmark configuration:

- 1000 records
- Optional `coupon` field
- Some records omit `coupon`
- Tokenizer: `cl100k_base`

| Format | Tokens |
|---|---:|
| JSON | 12833 |
| AIF 0.6 | 8511 |
| Reduction | 33.68% |

This demonstrates the token benefit of schema reuse even when records contain optional fields.

---

# 11. AIF 0.6 Round-trip Test

Base test records:

```python
[
    {"name": "张伟", "city": "上海", "coupon": "SAVE10"},
    {"name": "李娜", "city": "北京"},
    {"name": "王强", "city": "深圳", "coupon": "VIP20"}
]
```

Result:

```text
PASS
JSON → AIF → JSON
数据完全一致
```

---

# 12. AIF 0.6 Optional Field Edge Cases

## Edge Case 01 — All Records Omit Optional Field

Input:

```python
[
    {"name": "张伟", "city": "上海"},
    {"name": "李娜", "city": "北京"},
    {"name": "王强", "city": "深圳"}
]
```

Result: **PASS**

---

## Edge Case 02 — Optional Field Appears Only in Last Record

Input:

```python
[
    {"name": "张伟", "city": "上海"},
    {"name": "李娜", "city": "北京"},
    {"name": "王强", "city": "深圳", "coupon": "VIP20"}
]
```

Result: **PASS**

This verifies that schema construction considers fields across all records.

---

## Edge Case 03 — Optional Field Appears Only in Middle Record

Input:

```python
[
    {"name": "张伟", "city": "上海"},
    {"name": "李娜", "city": "北京", "coupon": "VIP20"},
    {"name": "王强", "city": "深圳"}
]
```

Result: **PASS**

---

## Edge Case 04 — Optional Field Followed by Required Field

Example:

```python
[
    {
        "name": "张伟",
        "city": "上海",
        "coupon": "SAVE10",
        "age": 18
    },
    {
        "name": "李娜",
        "city": "北京",
        "age": 20
    }
]
```

Result:

```text
PASS
Optional fields must appear at the end of the schema
```

The encoder correctly rejects the ambiguous schema.

---

## Edge Case 05 — Optional Field with Null Value

Input:

```python
[
    {"name": "张伟", "city": "上海", "coupon": "SAVE10"},
    {"name": "李娜", "city": "北京"},
    {"name": "王强", "city": "深圳", "coupon": None}
]
```

Result: **PASS**

The implementation correctly distinguishes:

- Optional field absent
- Optional field present with `null`

---

## Edge Case 06 — First Value Is Null, Later Value Has a Type

Input:

```python
[
    {"name": "张伟", "city": "上海", "coupon": None},
    {"name": "李娜", "city": "北京", "coupon": "VIP20"},
    {"name": "王强", "city": "深圳"}
]
```

Correct schema:

```text
name:s city:s coupon?:s
```

Result: **PASS**

Rule validated:

> `None` does not determine the field's type when a real value exists elsewhere.

---

## Edge Case 07 — Mixed Field Types

Input:

```python
[
    {"name": "张伟", "age": 18},
    {"name": "李娜", "age": "18"},
    {"name": "王强", "age": 20}
]
```

The same field contains both integer and string values.

Result:

```text
PASS
Mixed field types not supported: age
```

The encoder correctly rejects the inconsistent schema.

---

## Edge Case 08 — Field Contains Only Null Values

Input:

```python
[
    {"name": "张伟", "coupon": None},
    {"name": "李娜", "coupon": None},
    {"name": "王强"}
]
```

Correct schema:

```text
name:s coupon?:n
```

Result: **PASS**

Rule validated:

> If a field has no non-null value anywhere, its type is `n`.

---

## Edge Case 09 — String "null"

Input:

```python
[
    {"name": "张伟", "value": "null"}
]
```

The encoded representation is:

```text
name:s value:s

@record
张伟
null
```

The decoder must preserve the string because the schema says `value:s`.

Result: **PASS**

Decoded value:

```python
"null"
```

Rule validated:

> A string value of `"null"` is different from the null value `null`.

---

## Edge Case 10 — Strings "true" and "false"

Input:

```python
[
    {
        "name": "张伟",
        "value1": "true",
        "value2": "false"
    }
]
```

Result: **PASS**

Decoded values remain:

```python
{
    "value1": "true",
    "value2": "false"
}
```

Rule validated:

> String values are interpreted according to their schema type and are not automatically converted to Boolean values.

---

# 13. Current AIF Limitations

The current implementation is experimental and should not yet be considered a finalized interchange standard.

Known limitations include:

1. AIF 0.6 Optional Fields do not currently support arrays.
2. Robust escaping for all control characters is not finalized.
3. Some experimental AIF 0.5 array syntax used temporary delimiters.
4. Literal reserved tokens and delimiter characters require a formally specified escaping strategy.
5. Multiple schemas and schema references are not implemented.
6. Schema Registry functionality is not implemented.
7. Compression is not implemented.
8. Network protocol behavior is not defined.
9. Encryption and authentication are outside the current format implementation.
10. Agent discovery is outside the current format implementation.
11. Benchmarks currently use `cl100k_base`; different tokenizers may produce different results.
12. Token reduction depends heavily on schema repetition, data shape, field names, language, and record count.

---

# 14. Interpretation of Benchmark Results

The benchmarks demonstrate several consistent design observations.

## 14.1 Schema reuse is important

AIF becomes substantially more token-efficient when a schema is defined once and reused across many records.

This is visible in the difference between AIF 0.2 and AIF 0.3.

## 14.2 Small datasets may not benefit

For small or irregular structures, AIF can use as many or more tokens than JSON.

For example, the tested single array-object record in AIF 0.5 produced a negative reduction.

Therefore AIF should not claim a universal token-saving percentage.

## 14.3 Repetition improves efficiency

As the number of records increases under a fixed schema, schema overhead is amortized over more data.

## 14.4 Structured semantics are part of the design

AIF is not intended to be only a punctuation-removal technique. Its main design idea is to move repeated structural information into a schema and represent records positionally.

## 14.5 Round-trip correctness is required

Token reduction is not useful if the original data cannot be reconstructed correctly.

Therefore JSON → AIF → JSON correctness remains a primary benchmark requirement.

---

# 15. Future Benchmark Plan

Future versions should benchmark AIF against additional structured formats where appropriate, including:

- JSON
- MessagePack
- CBOR
- Protocol Buffers

Future benchmark dimensions should include:

- Small records
- Large batches
- Highly repetitive data
- Irregular data
- Nested objects
- Arrays
- Arrays of objects
- Optional fields
- Null-heavy data
- Multilingual text
- Long strings
- Different tokenizers
- Persistent schema scenarios
- Encode/decode speed
- Memory usage
- Semantic accuracy
- Round-trip equivalence

A future benchmark should also report both:

```text
one-shot token cost
```

and:

```text
amortized token cost with persistent schema
```

because these represent different real-world communication scenarios.

---

# 16. Conclusion

AIF 0.1–0.6 demonstrates a progressive development path:

```text
AIF 0.1
Schema-first positional structure
        ↓
AIF 0.2
Type system + escaping
        ↓
AIF 0.3
Schema reuse across records
        ↓
AIF 0.4
Nested structures
        ↓
AIF 0.5
General conversion + arrays
        ↓
AIF 0.6
Optional fields + type inference + null handling
```

The current benchmark results support the hypothesis that schema reuse can substantially reduce token usage for repetitive structured data while maintaining round-trip correctness in the tested cases.

However, these results are experimental. AIF still requires broader benchmarks, a finalized grammar, robust escaping, broader data-type support, and interoperability testing before it can be considered a mature interchange format.

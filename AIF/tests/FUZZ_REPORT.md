# AIF/0.9 fuzz report

- Seed: `20261108` (deterministic, rerun reproduces exactly)
- Cases: 720 (600 normal + 120 adversarial)
- Encoder accepted: 639
- Encoder clearly rejected: 81
- Clean Python round-trip **and** JS agreement: 639/639
- Silent corruptions: 0
- Cross-language disagreements: 0

## Encoder rejections (documented limitations, not failures)

| Count | Error |
|---:|---|
| 27 | `TypeError: Unsupported array item type for 'v': array. Nested arrays are not supp` |
| 11 | `TypeError: NaN / Infinity are not valid JSON numbers: -inf` |
| 10 | `TypeError: Integer out of IEEE-754 safe range (±9007199254740991): 90071992547409` |
| 6 | `TypeError: Integer out of IEEE-754 safe range (±9007199254740991): 10000000000000` |
| 5 | `TypeError: Integer out of IEEE-754 safe range (±9007199254740991): -9223372036854` |
| 5 | `TypeError: NaN / Infinity are not valid JSON numbers: nan` |
| 4 | `TypeError: NaN / Infinity are not valid JSON numbers: inf` |
| 4 | `TypeError: AIF/0.9 field names cannot contain ['?']: 'q?'` |
| 3 | `TypeError: AIF/0.9 field names cannot start with '@' or '-': '@lead'` |
| 2 | `TypeError: AIF/0.9 field names cannot contain [' ']: 'has space'` |
| 2 | `TypeError: AIF/0.9 field names must be non-empty strings` |
| 1 | `TypeError: AIF/0.9 field names cannot start with '@' or '-': '-lead'` |
| 1 | `TypeError: AIF/0.9 field names cannot contain ['\t']: 'a\tb'` |

## Silent corruptions (real bugs)

(none)

## Cross-language disagreements (specification bugs)

(none)

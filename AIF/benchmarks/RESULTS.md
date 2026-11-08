# AIF TOKEN BENCHMARK V8 — RESULTS

- Generated: 2026-11-08 13:07:26
- Tokenizer: `cl100k_base` (tiktoken 0.14.0)
- Python: 3.13.14
- Records per dataset: 1,000; all 17 datasets use the same N
- JSON: `json.dumps(..., ensure_ascii=False, separators=(',', ':'))`
- AIF-S: AIF/0.9 structured mode (spaces escaped as `\s`)
- AIF-T: AIF/0.9 Text Mode (spaces left unescaped; same decoder)
- Every row is actually decoded and compared to the original structure

## Full results

| Dataset | JSON | AIF-S | Reduction S | AIF-T | Reduction T | RT-S | RT-T |
|---|---:|---:|---:|---:|---:|:---:|:---:|
| 01 Flat | 33,003 | 22,021 | +33.28% | 22,021 | +33.28% | PASS | PASS |
| 02 Chinese | 39,002 | 32,017 | +17.91% | 32,017 | +17.91% | PASS | PASS |
| 03 English | 28,002 | 29,017 | -3.62% | 21,017 | +24.94% | PASS | PASS |
| 04 Mixed language | 36,002 | 36,017 | -0.04% | 29,017 | +19.40% | PASS | PASS |
| 05 Nested | 28,002 | 16,021 | +42.79% | 16,021 | +42.79% | PASS | PASS |
| 06 Deep nested | 24,002 | 11,021 | +54.08% | 11,021 | +54.08% | PASS | PASS |
| 07 Array | 29,002 | 40,021 | -37.99% | 40,021 | -37.99% | PASS | PASS |
| 08 Array of Objects | 41,003 | 37,013 | +9.73% | 37,013 | +9.73% | PASS | PASS |
| 09 Tool Calls | 36,002 | 22,029 | +38.81% | 19,029 | +47.14% | PASS | PASS |
| 10 Multiple Tool Calls | 69,002 | 62,015 | +10.13% | 59,015 | +14.47% | PASS | PASS |
| 11 Agent State | 43,002 | 32,028 | +25.52% | 32,028 | +25.52% | PASS | PASS |
| 12 Memory | 36,002 | 27,028 | +24.93% | 27,028 | +24.93% | PASS | PASS |
| 13 Messages | 37,003 | 48,015 | -29.76% | 34,015 | +8.08% | PASS | PASS |
| 14 Long Text | 73,003 | 153,013 | -109.60% | 70,013 | +4.10% | PASS | PASS |
| 15 Optional fields | 24,772 | 18,064 | +27.08% | 18,064 | +27.08% | PASS | PASS |
| 16 Null | 26,002 | 20,019 | +23.01% | 20,019 | +23.01% | PASS | PASS |
| 17 Mixed realistic | 78,002 | 70,031 | +10.22% | 67,031 | +14.07% | PASS | PASS |

**Round-trip: 17/17 PASS.** Negative reductions are kept in the table on purpose.

## Where AIF loses

AIF structured mode uses MORE tokens than JSON on:

- 03 English: -3.62%
- 04 Mixed language: -0.04%
- 07 Array: -37.99%
- 13 Messages: -29.76%
- 14 Long Text: -109.60%

AIF Text Mode uses MORE tokens than JSON on:

- 07 Array: -37.99%

## Token Efficiency findings (stage 5)

1. **Text Mode helps text-heavy data.** It reduced AIF tokens on 7/17 datasets relative to structured mode. The largest gains are on datasets whose strings contain many spaces.

   - 14 Long Text: 153,013 → 70,013 tokens (83,000 saved)
   - 13 Messages: 48,015 → 34,015 tokens (14,000 saved)
   - 03 English: 29,017 → 21,017 tokens (8,000 saved)

2. **Text Mode needs no decoder change and no version bump.** AIF reads one line as one value, so an unescaped space is structurally harmless. Escaping it was historical overhead. The decoder accepts both forms.

3. **'-' instead of '@missing' saves 17,930 tokens** across the 17 datasets (counterfactual: replacing every standalone '-' line with '@missing' and re-counting; used for token counting only, not decoded).

4. **AIF's advantage is structural repetition.** Best structured result: 06 Deep nested +54.08%. Worst: 14 Long Text -109.60%. Nested / tool / high-record-count data wins; long natural-language text does not.

5. **Recommendation.** Keep AIF as a structured interchange format and offer Text Mode as an encoder option for text-heavy payloads. Do NOT claim AIF is always smaller than JSON, and do not sacrifice the format design to chase a positive number on every dataset.

## Honesty notes

- No dataset was tuned to favour AIF. All 17 are defined in `benchmark_v8.py`.
- AIF 0.8 and Compact columns are absent because their source files were never recovered; no numbers were estimated for them.
- Results depend on tokenizer, dataset shape, schema repetition and encoder implementation. They are not a universal claim about AIF vs JSON.
- Re-run with `python AIF/benchmarks/benchmark_v8.py` to regenerate this file.

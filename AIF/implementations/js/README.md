# JavaScript reference implementation (Implementation B)

This is **Reference Implementation B** for AIF/0.9: a decoder and an encoder
written from `../../specification/AIF-0.9.md` without reusing the Python
code structure. It exists for one reason: **conformance verification**.

> **Important correction (do not skip):** this is **NOT a third-party
> independent implementation**. It was written by the same author / session
> that produced the Python implementation. Two author-written implementations
> can prove the specification is self-consistent; they cannot rule out
> "author's tacit knowledge". Release gate #6 requires a developer who did
> **not** take part in the original work — see
> `../../conformance/THIRD_PARTY_CHECKLIST.md`. Earlier wording calling this
> an "independent implementation" was misleading and is hereby corrected.

It is **not** an SDK, has no build step, no dependencies, and no publishing
plan. Per the project roadmap, multi-language SDKs and transport layers are
explicitly out of scope for now.

## Files

| File | Purpose |
|---|---|
| `decoder.js` | `aifToJson(text)` — full AIF/0.9 decoder |
| `encoder.js` | `jsonToAif(data, textMode)` — independent AIF/0.9 encoder (B→A direction) |
| `cli.js` | single-document stdin → JSON bridge |
| `batch_cli.js` | batch AIF-text → JSON bridge (fuzz / cross validation) |
| `encode_cli.js` | single + batch JSON → AIF bridge, `--self-test` included |

Node.js >= 18. No npm install needed.

## Run it

```bash
node cli.js --self-test
node encode_cli.js --self-test
node cli.js < ../../examples/01_flat.aif
```

## Cross-language conformance

```bash
# from the AIF/ delivery root
python tests/cross_validate.py
```

`cross_validate.py` feeds the same AIF text to both the Python decoder and
this JavaScript decoder and compares the decoded structures. It also reports
any case where the two implementations disagree — that is a **specification
bug**, not simply an implementation bug, and must be fixed in the spec plus
both implementations.

## Known interop constraints discovered while writing this

These are places where the spec had to be made explicit so that a second
implementation could agree. See the specification for the authoritative text.

- Integers are limited to IEEE-754 safe integers (±2^53−1). Python's `int` is
  unbounded, so the Python encoder now rejects larger values rather than emit
  text another language cannot decode.
- `NaN` / `Infinity` are rejected (they are not valid JSON numbers).
- Only LF, CRLF and CR are line separators. Other control characters inside
  string values must be escaped as `\uXXXX`, otherwise Python's
  `str.splitlines()` would silently split one value into two lines.
- The schema line is read **by position** and may itself be empty (`{}`).
  Skipping "all blank lines" to find it eats the empty schema and misreads
  `@record` as a schema token.
- All objects are `Object.create(null)` so keys such as `__proto__` and
  `constructor` survive intact.

## Verification results

- `cross_validate.py`: **78/78** Python/JS agreements
- `fuzz_roundtrip.py`: **639/639** clean round-trips, 0 silent corruptions,
  0 cross-language disagreements (seed `20261108`)
- `conformance/bidirectional.py` (default, A=Python / B=this JS):
  **A→B 33/33, B→A 33/33**, byte-identical 33/33, negative FAIL 0 —
  see `../../conformance/BIDIRECTIONAL_REPORT.md`

The bidirectional run proves the **harness works**, not that gate #6 is met.
A third party must re-run it with `--adapter`.

See `../../tests/FUZZ_REPORT.md`, specification §12–§13, and
`../../conformance/IMPLEMENTER_GUIDE.md`.

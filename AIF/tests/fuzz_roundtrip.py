"""Randomised round-trip conformance fuzz for AIF/0.9.

For every generated document:
    data -> Python encoder -> AIF text -> Python decoder
                                       -> JavaScript decoder
and all three must agree with the original data.

A document that the encoder *clearly rejects* is fine (a documented
limitation). A document that the encoder accepts but that decodes to
something else is a REAL BUG: silent data corruption. That is what this
fuzz is designed to find.

Run:  python AIF/tests/fuzz_roundtrip.py
Writes: AIF/tests/FUZZ_REPORT.md
"""

import json
import math
import random
import subprocess
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
DELIVERY = HERE.parent
BATCH_CLI = DELIVERY / "implementations" / "js" / "batch_cli.js"
REPORT = HERE / "FUZZ_REPORT.md"

sys.path.insert(0, str(DELIVERY))
from aif import json_to_aif, aif_to_json  # noqa: E402

SEED = 20261108
N_NORMAL = 600
N_ADVERSARIAL = 120

SAFE_KEYS = ["id", "name", "age", "score", "active", "city", "note",
             "meta", "tags", "tools", "result", "x", "y", "delta"]

WEIRD_KEYS = ["has space", "a:b", "q?", "arr[]", "dot.name", "__proto__",
              "constructor", "中文键", "", "@lead", "-lead", "a\tb"]

STRINGS = [
    "Alice", "张伟", "AI technology", "", "@null", "@missing", "-", "-dash",
    "@record", "@objects", "a\\b", "a\nb", "a\rb", "tab\there", "a  b",
    " leading", "trailing ", "emoji 🚀", "100% done", "quote'\"double",
    r"\s", r"\e", "\\", "line\vseparator", "form\ffeed", "\x1c", "\x1d",
    "\x85", "\u2028", "\u2029", "x" * 60, "0", "true",
]

# Normal cases use values that are valid JSON, so the fuzz spends its budget
# exercising successful round-trips instead of tripping over documented
# limitations. Out-of-range values get their own adversarial cases below.
INTS = [0, 1, -1, 42, -999, 2 ** 31, 2 ** 53 - 1]
BIG_INTS = [2 ** 53, 2 ** 53 + 1, -(2 ** 63), 10 ** 30]

FLOATS = [0.0, -0.0, 3.14, -2.5, 1e-9, 1e300]
NONFINITE = [float("nan"), float("inf"), -float("inf")]


def normalize(obj):
    """Make float corner cases comparable across Python / JS / JSON."""
    if isinstance(obj, float):
        if math.isnan(obj):
            return "<NaN>"
        if math.isinf(obj):
            return "<+Inf>" if obj > 0 else "<-Inf>"
        if obj == 0.0:
            return 0.0  # JSON serialises -0 as 0; numerically identical
        return obj
    if isinstance(obj, dict):
        return {k: normalize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [normalize(v) for v in obj]
    return obj


def scalar(rng, kind):
    if kind == "s":
        return rng.choice(STRINGS)
    if kind == "i":
        return rng.choice(INTS)
    if kind == "f":
        return rng.choice(FLOATS)
    if kind == "b":
        return rng.choice([True, False])
    return None  # kind "n"


def value_for(rng, kind):
    if kind in ("s", "i", "f", "b", "n"):
        return scalar(rng, kind)
    if kind == "nested":
        return {"city": rng.choice(STRINGS), "age": rng.choice([0, 1, 30, -7])}
    if kind == "nullnested":
        return None if rng.random() < 0.4 else {"ok": rng.choice([True, False])}
    if isinstance(kind, tuple) and kind[0] == "array":
        base = kind[1]  # fixed per field, so records never conflict in type
        return [scalar(rng, base) for _ in range(rng.randint(0, 4))]
    if kind == "objarray":
        return [
            {"name": rng.choice(["a", "b", "中文", "@x"]),
             "v": rng.choice([1, 2, 3])}
            for _ in range(rng.randint(0, 3))
        ]
    if kind == "nested_array":  # intentionally unsupported
        return [[1, 2], [3]]
    raise AssertionError(kind)


KINDS = ["s", "i", "f", "b", "n", "nested", "nullnested",
         "array", "objarray"]


def make_normal_case(rng):
    keys = rng.sample(SAFE_KEYS, rng.randint(1, 6))
    spec = []
    for key in keys:
        kind = rng.choice(KINDS)
        if kind == "array":
            kind = ("array", rng.choice(["s", "i", "f", "b"]))
        spec.append((key, kind))
    records = []
    for _ in range(rng.randint(1, 4)):
        rec = {}
        for key, kind in spec:
            if rng.random() < 0.22:  # optional absent in this record
                continue
            rec[key] = value_for(rng, kind)
        records.append(rec)
    if rng.random() < 0.15:
        records = records[0]  # exercise @single
    return records, rng.random() < 0.5


def make_adversarial_case(rng):
    mode = rng.randrange(5)
    if mode == 0:
        return {rng.choice(WEIRD_KEYS): 1}, rng.random() < 0.5
    if mode == 1:
        return [{"v": [[1], [2]]}], False  # nested arrays
    if mode == 2:
        return [{"n": rng.choice(BIG_INTS)}], False  # out-of-range integer
    if mode == 3:
        return [{"f": rng.choice(NONFINITE)}], False
    return [{"s": rng.choice(["\v", "\f", "\x1c", "\x85", "\u2028", "\u2029"])}], False


def js_batch_decode(texts):
    payload = json.dumps(texts, ensure_ascii=True)
    proc = subprocess.run(
        ["node", str(BATCH_CLI)],
        input=payload, capture_output=True, text=True, encoding="utf-8",
    )
    if proc.returncode != 0:
        raise RuntimeError("batch_cli failed: " + (proc.stderr or "").strip())
    return json.loads(proc.stdout)


def main():
    rng = random.Random(SEED)
    cases = [("normal", make_normal_case(rng)) for _ in range(N_NORMAL)]
    cases += [("adversarial", make_adversarial_case(rng)) for _ in range(N_ADVERSARIAL)]

    encoded = []       # (index, aif_text, expected, text_mode)
    rejections = Counter()
    reject_samples = {}

    for idx, (group, (data, text_mode)) in enumerate(cases):
        try:
            aif_text = json_to_aif(data, text_mode=text_mode)
        except Exception as exc:  # noqa: BLE001
            key = f"{type(exc).__name__}: {str(exc)[:70]}"
            rejections[key] += 1
            reject_samples.setdefault(key, (group, data))
            continue
        encoded.append((idx, aif_text, data, group, text_mode))

    print(f"# AIF/0.9 FUZZ  seed={SEED}  total={len(cases)}  "
          f"encoded={len(encoded)}  rejected={len(cases) - len(encoded)}")

    js_results = js_batch_decode([e[1] for e in encoded])

    passed = 0
    corruptions = []
    disagreements = []

    for (idx, aif_text, original, group, text_mode), js in zip(encoded, js_results):
        expected = normalize(original)
        try:
            py = normalize(aif_to_json(aif_text))
        except Exception as exc:  # noqa: BLE001
            corruptions.append((idx, group, "Python decoder raised", str(exc),
                                original, None))
            continue

        if not js["ok"]:
            disagreements.append((idx, group, "JS decoder rejected",
                                  js["error"], original, py))
            continue

        js_val = normalize(js["value"])
        if py != expected:
            corruptions.append((idx, group, "Python decode != original",
                                "", original, py))
        elif js_val != expected:
            disagreements.append((idx, group, "JS decode != original",
                                  "", original, js_val))
        elif py != js_val:
            disagreements.append((idx, group, "Python != JS", "", py, js_val))
        else:
            passed += 1

    print(f"# clean round-trip + cross-language agreement: {passed}/{len(encoded)}")
    print(f"# silent corruptions : {len(corruptions)}")
    print(f"# cross-language disagreements: {len(disagreements)}")

    lines = [
        "# AIF/0.9 fuzz report",
        "",
        f"- Seed: `{SEED}` (deterministic, rerun reproduces exactly)",
        f"- Cases: {len(cases)} ({N_NORMAL} normal + {N_ADVERSARIAL} adversarial)",
        f"- Encoder accepted: {len(encoded)}",
        f"- Encoder clearly rejected: {len(cases) - len(encoded)}",
        f"- Clean Python round-trip **and** JS agreement: {passed}/{len(encoded)}",
        f"- Silent corruptions: {len(corruptions)}",
        f"- Cross-language disagreements: {len(disagreements)}",
        "",
        "## Encoder rejections (documented limitations, not failures)",
        "",
    ]
    if rejections:
        lines.append("| Count | Error |")
        lines.append("|---:|---|")
        for key, count in rejections.most_common():
            lines.append(f"| {count} | `{key.replace('|', '\\|')}` |")
    else:
        lines.append("(none)")

    lines += ["", "## Silent corruptions (real bugs)", ""]
    if corruptions:
        for idx, group, why, detail, original, got in corruptions[:20]:
            lines += [
                f"- case #{idx} [{group}] **{why}** {detail}",
                f"  - original: `{json.dumps(original, ensure_ascii=False)[:200]}`",
                f"  - decoded : `{json.dumps(got, ensure_ascii=False)[:200]}`",
            ]
        if len(corruptions) > 20:
            lines.append(f"- ... and {len(corruptions) - 20} more")
    else:
        lines.append("(none)")

    lines += ["", "## Cross-language disagreements (specification bugs)", ""]
    if disagreements:
        for idx, group, why, detail, a, b in disagreements[:20]:
            lines += [
                f"- case #{idx} [{group}] **{why}** {detail}",
                f"  - A: `{json.dumps(a, ensure_ascii=False)[:200]}`",
                f"  - B: `{json.dumps(b, ensure_ascii=False)[:200]}`",
            ]
        if len(disagreements) > 20:
            lines.append(f"- ... and {len(disagreements) - 20} more")
    else:
        lines.append("(none)")

    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"# Report written to {REPORT}")

    return 0 if not corruptions and not disagreements else 1


if __name__ == "__main__":
    sys.exit(main())

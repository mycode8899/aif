"""Cross-language conformance test: Python decoder vs JavaScript decoder.

A format is only a format if a second implementation can read it from the
specification alone. This script feeds the SAME AIF text to both decoders and
compares the decoded structures. Any disagreement is a specification bug.

Run from anywhere:  python AIF/tests/cross_validate.py
Requires: Node.js >= 18 (no npm packages), tiktoken installed.
"""

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DELIVERY = HERE.parent
ROOT = DELIVERY.parent
CLI = DELIVERY / "implementations" / "js" / "cli.js"

for p in (str(DELIVERY), str(HERE), str(DELIVERY / "benchmarks"), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from aif import json_to_aif, aif_to_json  # noqa: E402
import _v7_data  # noqa: E402
import benchmark_v8 as v8  # noqa: E402


def js_decode(aif_text):
    proc = subprocess.run(
        ["node", str(CLI)],
        input=aif_text,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or "").strip())
    return json.loads(proc.stdout)


def collect_cases():
    cases = []  # (name, aif_text, expected_python_object_or_None)

    # 1. Shipped examples (04 is Text Mode on purpose).
    for aif_path in sorted((DELIVERY / "examples").glob("*.aif")):
        json_path = aif_path.with_suffix(".json")
        expected = json.loads(json_path.read_text(encoding="utf-8")) if json_path.exists() else None
        cases.append(("example " + aif_path.name,
                      aif_path.read_text(encoding="utf-8"), expected))

    # 2. Historical V7 datasets, verbatim generators, 20 records each.
    for name, make in _v7_data.DATASETS:
        records = make(20)
        cases.append(("V7 " + name, json_to_aif(records), records))
        cases.append(("V7 " + name + " [text mode]",
                      json_to_aif(records, text_mode=True), records))

    # 3. All 17 V8 dataset families, both encoding modes.
    for name, make in v8.DATASETS:
        records = make(20)
        cases.append(("V8 " + name, json_to_aif(records), records))
        cases.append(("V8 " + name + " [text mode]",
                      json_to_aif(records, text_mode=True), records))

    # 4. Hand-picked structural edge cases.
    edges = {
        "single dict": {"a": 1, "b": "two words"},
        "single-element list": [{"a": 1}],
        "empty list": [],
        "empty object array": [{"tools": []}],
        "nested null ancestor": {"items": [
            {"name": "A", "result": {"ok": True}},
            {"name": "B", "result": None},
        ]},
        "marker-like strings": {"id": "@missing", "n": "@null", "d": "-", "e": ""},
        "escapes": {"s": "a\\b\nc\td", "at": "@record", "dash": "-x"},
        "deep nesting": {"a": {"b": {"c": {"d": 42}}}},
        "scalar array": {"tags": ["AI", "tech", "agents"]},
        "bool/int/float": {"t": True, "f": False, "z": 0, "neg": -1, "pi": 3.14},
        "optional across records": [{"id": "A", "x": 1}, {"id": "B"}],
    }
    for name, data in edges.items():
        cases.append(("edge " + name, json_to_aif(data), data))
        cases.append(("edge " + name + " [text mode]",
                      json_to_aif(data, text_mode=True), data))

    # 5. One full-scale case (1000 records) to exercise the cursor at scale.
    big = _v7_data.DATASETS[7][1](1000)
    cases.append(("V7 Mixed Agent State [1000 records]", json_to_aif(big), big))

    return cases


def shorten(obj, limit=260):
    text = json.dumps(obj, ensure_ascii=False)
    return text if len(text) <= limit else text[:limit] + "..."


def main():
    print("# AIF/0.9 CROSS-LANGUAGE CONFORMANCE")
    print(f"# Python decoder : {DELIVERY / 'aif' / 'decoder.py'}")
    print(f"# JS decoder     : {CLI}")
    print("#" * 70)

    try:
        self_test = subprocess.run(
            ["node", str(CLI), "--self-test"],
            capture_output=True, text=True, encoding="utf-8",
        )
        if self_test.returncode != 0 or "JS_DECODER_OK" not in self_test.stdout:
            print("FATAL: JS decoder self-test failed:", self_test.stderr.strip())
            return 1
    except FileNotFoundError:
        print("FATAL: Node.js not found. Install Node >= 18 and retry.")
        return 1

    cases = collect_cases()
    passed = 0
    failures = []

    for name, aif_text, expected in cases:
        try:
            py = aif_to_json(aif_text)
            js = js_decode(aif_text)
            agree = py == js
            correct = (expected is None) or (py == expected)
            ok = agree and correct
            if ok:
                passed += 1
                print(f"  {name:<52} PASS")
            else:
                failures.append(name)
                print(f"  {name:<52} FAIL")
                if not agree:
                    print("      PY:", shorten(py))
                    print("      JS:", shorten(js))
                if not correct:
                    print("      EXPECTED:", shorten(expected))
                    print("      PY GOT  :", shorten(py))
        except Exception as exc:  # noqa: BLE001
            failures.append(name)
            print(f"  {name:<52} ERROR {type(exc).__name__}: {exc}")

    print("#" * 70)
    print(f"# RESULT: {passed}/{len(cases)} AGREE")
    if failures:
        print("# DISAGREEMENTS (these are specification bugs):")
        for name in failures:
            print("#   -", name)
        return 1
    print("# Two independent implementations agree on every case.")
    print("#" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())

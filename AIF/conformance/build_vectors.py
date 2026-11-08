"""
Generate the PUBLIC AIF/0.9 conformance test vectors.

    python AIF/conformance/build_vectors.py            # (re)generate vectors.json
    python AIF/conformance/build_vectors.py --verify   # assert file is unmodified

A third-party implementer needs ONLY:
    specification/AIF-0.9.md
    conformance/IMPLEMENTER_GUIDE.md
    conformance/vectors.json

No Python source is required. `expected_aif` is a golden reference produced by
implementation A; a third-party DECODER must decode it to `expected_decoded`.
A third-party ENCODER is judged by semantic compatibility (its AIF must decode
to the same JSON in implementation A), byte-for-byte equality is informative
but NOT required.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
AIF_ROOT = HERE.parent
sys.path.insert(0, str(AIF_ROOT))
from aif import json_to_aif, aif_to_json  # noqa: E402

OUT = HERE / "vectors.json"


def positive_cases():
    """(id, title, category, data, notes)"""
    cases = [
        ("V001", "flat object, 3 scalar types", "flat",
         {"name": "Alice", "age": 30, "active": True},
         "baseline; @single must be emitted for a top-level dict"),
        ("V002", "flat list with 3 records", "flat",
         [{"name": "Alice", "age": 30, "active": True},
          {"name": "Bob", "age": 25, "active": False},
          {"name": "Carol", "age": 41, "active": True}],
         "no @single for a list"),
        ("V003", "single-element list (not @single)", "shape",
         [{"id": "A1", "v": 1}],
         "distinguishes [ {...} ] from {...}"),
        ("V004", "empty list", "shape", [],
         "encodes as header + blank line; decodes back to []"),
        ("V005", "chinese values", "flat",
         [{"name": "张伟", "city": "上海", "age": 30},
          {"name": "李娜", "city": "北京", "age": 28}],
         "UTF-8, ensure_ascii=False"),
        ("V006", "nested object depth 1", "nested",
         {"name": "张伟", "profile": {"age": 30, "city": "上海"}},
         "flattened field paths profile.age / profile.city"),
        ("V007", "nested object depth 3", "nested",
         [{"id": "a", "p": {"q": {"r": {"v": 42}}}},
          {"id": "b", "p": {"q": {"r": {"v": 7}}}}],
         "multi-level path reconstruction"),
        ("V008", "optional field missing in some records", "optional",
         [{"id": "A1", "v": 1}, {"id": "A2"}, {"id": "A3", "v": 3}],
         "missing slot is exactly one '-' line; optional fields sort to tail"),
        ("V009", "top-level null value", "null",
         [{"id": "A1", "score": None}, {"id": "A2", "score": 5}],
         "@null vs '-' must remain distinguishable"),
        ("V010", "explicitly null nested object", "null",
         [{"id": "A1", "result": {"ok": True, "n": 1}},
          {"id": "A2", "result": None}],
         "@onull:<path> distinguishes 'object is null' from 'field absent'"),
        ("V011", "scalar string array", "array",
         {"id": "A1", "tags": ["AI", "technology", "agents"]},
         "@array + count + one line per element"),
        ("V012", "scalar integer array", "array",
         {"id": "A1", "scores": [1, 20, 300]}, "array_i"),
        ("V013", "scalar boolean array", "array",
         {"id": "A1", "flags": [True, False, True]}, "array_b"),
        ("V014", "empty scalar array", "array",
         {"id": "A1", "tags": []}, "count = 0, no element lines"),
        ("V015", "array of objects, two fields", "object_array",
         {"users": [{"name": "A", "age": 20}, {"name": "B", "age": 30}]},
         "@objects block with its own schema"),
        ("V016", "array of objects, optional fields", "object_array",
         {"tools": [
             {"name": "web_search", "arguments": {"query": "AI technology",
                                                  "limit": 10},
              "result": {"success": True, "count": 10}},
             {"name": "calculator", "arguments": {"query": "1+1", "limit": 1}},
         ]},
         "canonical AIF/0.9 example from the specification §9"),
        ("V017", "empty array of objects", "object_array",
         {"tools": []}, "@objects with count 0"),
        ("V018", "object array with result = null", "object_array",
         {"items": [{"name": "A", "result": {"success": True}},
                    {"name": "B", "result": None}]},
         "@onull inside an @objects block"),
        ("V019", "marker-like strings", "escaping",
         [{"id": "@null", "note": "@missing", "extra": "@onull:x", "v": 1}],
         "literal marker strings must survive as strings"),
        ("V020", "leading dash and empty string", "escaping",
         [{"id": "-", "note": "-dash", "body": "", "v": 2}],
         "'\\-' escapes a leading dash; '\\e' is the empty string"),
        ("V021", "spaces and commas in strings", "escaping",
         [{"id": "a b c", "note": "x,y,z", "v": 3}],
         "Structured Mode escapes spaces as \\s; commas are harmless in values"),
        ("V022", "backslash, newline, tab, CR", "escaping",
         [{"id": "a\\b", "note": "line\nbreak", "tab": "x\ty",
           "cr": "a\rb", "v": 4}],
         "\\\\ \\n \\t \\r"),
        ("V023", "control chars and Unicode separators", "escaping",
         [{"id": "v\x0bf\x0cf\x1cg", "note": "a\u2028b\u2029c", "v": 5}],
         "MUST be \\uXXXX; raw ones would split a value into two lines"),
        ("V024", "integer safe-range boundaries", "numeric",
         [{"id": "max", "v": 2 ** 53 - 1},
          {"id": "min", "v": -(2 ** 53 - 1)},
          {"id": "zero", "v": 0}],
         "IEEE-754 safe integers; larger values must be rejected"),
        ("V025", "floats", "numeric",
         [{"id": "a", "v": 3.14}, {"id": "b", "v": -0.5},
          {"id": "c", "v": 2.5}],
         "all values are non-integral floats to avoid the int/float ambiguity "
         "documented in IMPLEMENTER_GUIDE.md"),
        ("V026", "booleans false / true", "numeric",
         [{"id": "a", "v": False}, {"id": "b", "v": True}],
         "bool must not be treated as int 0/1"),
        ("V027", "mixed realistic agent state", "mixed",
         [{"agent_id": "a000001",
           "session": {"id": "s000001", "status": "active"},
           "tools": [{"name": "web_search", "ok": True}],
           "tags": ["AI", "agent"], "score": 3.5},
          {"agent_id": "a000002",
           "session": {"id": "s000002", "status": "queued"},
           "tools": [], "tags": [], "score": 1.25}],
         "nested + array + object array + float in one record"),
        ("V028", "all-null field", "null",
         [{"id": "a", "v": None}, {"id": "b", "v": None}],
         "type n, every value is @null"),
    ]

    # Reuse the published examples as vectors too (they are part of the bundle).
    ex_dir = AIF_ROOT / "examples"
    for i, path in enumerate(sorted(ex_dir.glob("*.json")), start=1):
        data = json.loads(path.read_text(encoding="utf-8"))
        cases.append((f"E{i:03d}", f"published example: {path.stem}", "example",
                      data, f"source: examples/{path.name}"))
    return cases


def negative_cases():
    """(id, title, data, reason, hint) — encoder MUST reject these.

    `hint` is non-None when the offending value is NOT representable in strict
    JSON. Such cases must never be written into the public vectors file as
    NaN/Infinity literals, or a third party's JSON.parse would fail before it
    even reaches the AIF encoder.
    """
    return [
        ("N001", "integer beyond IEEE-754 safe range",
         [{"id": "a", "v": 2 ** 53}],
         "JS/Go/Rust cannot represent this integer exactly", None),
        ("N002", "NaN", [{"id": "a", "v": float("nan")}],
         "not a valid JSON number",
         'Python: [{"id":"a","v":float("nan")}] — non-finite numbers are not '
         'valid JSON, so the public vector stores null as a placeholder.'),
        ("N003", "Infinity", [{"id": "a", "v": float("inf")}],
         "not a valid JSON number",
         'Python: [{"id":"a","v":float("inf")}] — non-finite numbers are not '
         'valid JSON, so the public vector stores null as a placeholder.'),
        ("N004", "conflicting field types",
         [{"id": "a", "v": 1}, {"id": "b", "v": "x"}],
         "same field cannot be both i and s", None),
        ("N005", "nested array (unsupported)",
         [{"id": "a", "v": [[1, 2], [3]]}],
         "arrays of arrays are outside AIF/0.9", None),
        ("N006", "field name with a space",
         [{"bad name": "x"}], "schema line is space-separated", None),
        ("N007", "field name with a dot",
         [{"a.b": "x"}], "'.' is the nested-path separator", None),
        ("N008", "field name starting with @",
         [{"@id": "x"}], "would collide with reserved markers", None),
        ("N009", "top-level scalar",
         [1, 2, 3], "top level must be a dict or list of dicts", None),
    ]


def build():
    vectors = []
    for vid, title, cat, data, notes in positive_cases():
        s = json_to_aif(data)
        t = json_to_aif(data, text_mode=True)
        if aif_to_json(s) != data or aif_to_json(t) != data:
            raise AssertionError(f"{vid}: generator produced a bad vector")
        vectors.append({
            "id": vid, "title": title, "category": cat,
            "kind": "positive",
            "input_json": data,
            "expected_aif_structured": s,
            "expected_aif_text_mode": t,
            "expected_decoded": data,
            "notes": notes,
        })

    for nid, title, data, reason, hint in negative_cases():
        try:
            json_to_aif(data)
        except (TypeError, ValueError) as exc:
            err_type = type(exc).__name__
            err_msg = str(exc)
        else:
            raise AssertionError(f"{nid}: encoder should have rejected this")
        entry = {
            "id": nid, "title": title, "category": "error",
            "kind": "negative",
            # Never emit NaN / Infinity into the public JSON file.
            "input_json": None if hint else data,
            "expected_error_type": err_type,
            "expected_error_message_contains": err_msg[:60],
            "notes": reason,
        }
        if hint:
            entry["not_valid_json"] = True
            entry["construct_hint"] = hint
        vectors.append(entry)

    doc = {
        "format": "AIF/0.9 conformance test vectors",
        "specification": "specification/AIF-0.9.md",
        "implementer_guide": "conformance/IMPLEMENTER_GUIDE.md",
        "generated_by": "conformance/build_vectors.py",
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "count": len(vectors),
        "positive": len([v for v in vectors if v["kind"] == "positive"]),
        "negative": len([v for v in vectors if v["kind"] == "negative"]),
        "how_to_use": [
            "A DECODER must decode expected_aif_structured AND "
            "expected_aif_text_mode to expected_decoded.",
            "An ENCODER's output must decode to input_json in the reference "
            "implementation; byte equality with expected_aif_* is informative, "
            "not required.",
            "Every negative vector must be REJECTED, never silently encoded.",
        ],
        "known_interop_limits": [
            "JSON numeric literals such as 3.0 lose their int/float distinction "
            "in JavaScript (JSON.parse returns 3). Test vectors deliberately "
            "use non-integral floats only. A JS encoder cannot infer the "
            "original AIF type from a JSON number literal; this is a JSON "
            "model limitation, not an AIF defect.",
            "Python decodes @single documents to a dict and list documents to "
            "a list; implementations must preserve that shape.",
        ],
        "vectors": vectors,
    }
    return doc


def main():
    doc = build()
    if "--verify" in sys.argv:
        if not OUT.exists():
            print(f"MISSING: {OUT}")
            return 1
        old = json.loads(OUT.read_text(encoding="utf-8"))
        old.pop("generated_at", None)
        new = dict(doc)
        new.pop("generated_at", None)
        # Compare serialised text, not Python objects: float('nan') and -0.0
        # make object equality unreliable.
        if json.dumps(old, sort_keys=True) != json.dumps(new, sort_keys=True):
            print("MISMATCH: vectors.json differs from a fresh regeneration. "
                  "Do not hand-edit golden vectors.")
            return 1
        print(f"vectors.json VERIFIED ({doc['count']} vectors, unmodified)")
        return 0
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    print(f"已生成 {OUT.relative_to(AIF_ROOT.parent)}")
    print(f"  {doc['positive']} positive + {doc['negative']} negative "
          f"= {doc['count']} vectors")
    for v in doc["vectors"]:
        if v["kind"] == "negative":
            print(f"  {v['id']} REJECTED as expected: {v['expected_error_type']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

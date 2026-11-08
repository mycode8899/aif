"""Edge cases and error handling for AIF/0.9."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from aif import json_to_aif, aif_to_json  # noqa: E402


CASES = {
    "single record list": [{"id": "A1", "v": 1}],
    "single dict": {"id": "A1", "v": 1},
    "empty list": [],
    "top-level null": [{"id": "A1", "score": None}],
    "nested object null": [{"id": "A1", "result": None}],
    "all-null field": [{"id": "A1", "a": None}, {"id": "A2", "a": None}],
    "empty string": [{"id": "", "v": 1}],
    "space and Chinese": [{"id": "张 伟", "v": 1}],
    "backslash newline tab CR": [{"id": "a\\b\nc\td\re", "v": 1}],
    "literal backslash-s": [{"id": r"a\sb", "v": 1}],
    "value @missing": [{"id": "@missing", "v": 1}],
    "value @null": [{"id": "@null", "v": 1}],
    "value @record": [{"id": "@record", "v": 1}],
    "value @objects": [{"id": "@objects", "v": 1}],
    "value @array": [{"id": "@array", "v": 1}],
    "value @single": [{"id": "@single", "v": 1}],
    "value bare dash": [{"id": "-", "v": 1}],
    "value dash prefix": [{"id": "-foo", "v": 1}],
    "empty scalar array": [{"id": "A1", "tags": []}],
    "empty object array": [{"id": "A1", "tools": []}],
    "array containing null": [{"id": "A1", "tags": [None, "AI"]}],
    "three level nesting": [{"id": "A1", "a": {"b": {"c": 42}}}],
    "top-level optional": [{"id": "A1", "v": 1}, {"id": "A2"}],
    "nested object optional": [
        {"id": "A1", "profile": {"age": 30}},
        {"id": "A2"},
    ],
    "numeric boundaries": [
        {"id": "A1", "a": 0, "b": -1, "c": 3.14, "d": 1e-5, "e": False, "f": True}
    ],
    "mixed languages": [
        {"id": "A1", "text": "AI Agent 数据交换 テスト"},
        {"id": "A2", "text": "café naïve"},
    ],
    "unicode symbols": [{"id": "A1", "text": "→ ± × §"}],
    # Regressions found by cross-language fuzz (seed 20261108).
    "empty dict": {},
    "list of empty dicts": [{}, {}],
    "C0 control characters": [{"id": "a\vb\fc\x1cd\x1de\x1fe\x00g"}],
    "Unicode line separators": [{"id": "a\u2028b\u2029c\u0085d"}],
    "safe max integer": [{"n": 2 ** 53 - 1}],
    "negative zero float": [{"f": -0.0}],
    "literal backslash-u": [{"id": r"\u000b"}],
}

# Hand-written AIF text (not produced by the encoder) -> expected object.
RAW_DECODE_CASES = {
    "handwritten \\u000b": ("AIF/0.9\n\nname:s\n@record\na\\u000bb",
                            [{"name": "a\vb"}]),
}


def _expect_error(fn, exception_type):
    try:
        fn()
    except exception_type:
        return True, ""
    except Exception as exc:
        return False, f"raised {type(exc).__name__} instead of {exception_type.__name__}: {exc}"
    return False, f"did not raise {exception_type.__name__}"


ERROR_CASES = [
    ("type conflict int/str", lambda: json_to_aif([{"a": 1}, {"a": "x"}]), TypeError),
    ("array item type conflict", lambda: json_to_aif({"a": [1, "x"]}), TypeError),
    ("nested array unsupported", lambda: json_to_aif({"a": [[1]]}), TypeError),
    ("non-object top level", lambda: json_to_aif([1, 2]), TypeError),
    ("decoder given non-text", lambda: aif_to_json(123), TypeError),
    ("wrong header", lambda: aif_to_json("AIF/0.8\n\nname:s\n@record\nx"), ValueError),
    ("invalid schema type", lambda: aif_to_json("AIF/0.9\n\nname:z\n@record\nx"), ValueError),
    ("schema without colon", lambda: aif_to_json("AIF/0.9\n\nname\n@record\nx"), ValueError),
    ("truncated record", lambda: aif_to_json("AIF/0.9\n\nname:s age:i\n@record\nx"), ValueError),
    ("invalid boolean", lambda: aif_to_json("AIF/0.9\n\nflag:b\n@record\nmaybe"), ValueError),
    ("unknown escape", lambda: aif_to_json("AIF/0.9\n\nname:s\n@record\n\\q"), ValueError),
    ("missing @objects", lambda: aif_to_json("AIF/0.9\n\ntools[]:object\n@record\n2"), ValueError),
    ("@single with 2 records", lambda: aif_to_json(
        "AIF/0.9\n\n@single\nname:s\n@record\na\n@record\nb"), ValueError),
    # Regressions: values that are not valid JSON numbers must be rejected
    # instead of producing AIF another language cannot decode.
    ("integer over 2^53", lambda: json_to_aif({"n": 2 ** 53}), TypeError),
    ("negative huge integer", lambda: json_to_aif({"n": -(2 ** 63)}), TypeError),
    ("NaN rejected", lambda: json_to_aif({"f": float("nan")}), TypeError),
    ("Infinity rejected", lambda: json_to_aif({"f": float("inf")}), TypeError),
    ("field name with space", lambda: json_to_aif({"a b": 1}), TypeError),
    ("field name with colon", lambda: json_to_aif({"a:b": 1}), TypeError),
    ("field name with dot", lambda: json_to_aif({"a.b": 1}), TypeError),
    ("field name with question mark", lambda: json_to_aif({"a?": 1}), TypeError),
    ("empty field name", lambda: json_to_aif({"": 1}), TypeError),
    ("field name starts with @", lambda: json_to_aif({"@x": 1}), TypeError),
    ("invalid \\u escape", lambda: aif_to_json(
        "AIF/0.9\n\nname:s\n@record\n\\uZZZZ"), ValueError),
]


def run():
    print("=" * 70)
    print("TEST 2/3  Edge cases and error handling")
    print("=" * 70)

    passed = 0
    total = 0

    for name, data in CASES.items():
        try:
            text = json_to_aif(data)
            decoded = aif_to_json(text)
            ok = decoded == data and type(decoded) is type(data)
            detail = ""
            if not ok:
                detail = ("in =" + json.dumps(data, ensure_ascii=False)[:90]
                          + " out=" + json.dumps(decoded, ensure_ascii=False)[:90])
        except Exception as exc:
            ok = False
            detail = f"{type(exc).__name__}: {exc}"
        total += 1
        passed += int(ok)
        print(f"  {name:<30} {'PASS' if ok else 'FAIL'}")
        if detail:
            print(f"    {detail[:170]}")

    for name, (text, expected) in RAW_DECODE_CASES.items():
        try:
            decoded = aif_to_json(text)
            ok = decoded == expected
            detail = "" if ok else "got " + json.dumps(decoded, ensure_ascii=False)[:90]
        except Exception as exc:
            ok = False
            detail = f"{type(exc).__name__}: {exc}"
        total += 1
        passed += int(ok)
        print(f"  {name:<30} {'PASS' if ok else 'FAIL'}")
        if detail:
            print(f"    {detail[:170]}")

    for name, fn, exc_type in ERROR_CASES:
        ok, detail = _expect_error(fn, exc_type)
        total += 1
        passed += int(ok)
        print(f"  {name:<30} {'PASS' if ok else 'FAIL'}")
        if detail:
            print(f"    {detail[:170]}")

    print("-" * 70)
    print(f"  subtotal: {passed}/{total} PASS")
    return passed, total


if __name__ == "__main__":
    ok, total = run()
    raise SystemExit(0 if ok == total else 1)

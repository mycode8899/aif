"""Stage 3: systematic Array of Objects coverage."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from aif import json_to_aif, aif_to_json  # noqa: E402


CASES = {
    "simple object array": {
        "items": [{"name": "A"}, {"name": "B"}],
    },
    "multi-field objects": {
        "items": [
            {"name": "A", "age": 20, "active": True},
            {"name": "B", "age": 30, "active": False},
        ],
    },
    "nested object in array": {
        "items": [
            {"name": "A", "profile": {"city": "Shanghai"}},
            {"name": "B", "profile": {"city": "Beijing"}},
        ],
    },
    "optional nested object": {
        "items": [
            {"name": "A", "result": {"success": True}},
            {"name": "B", "result": None},
        ],
    },
    "optional nested object absent": {
        "items": [
            {"name": "A", "result": {"success": True}},
            {"name": "B"},
        ],
    },
    "complex tool calls": {
        "tools": [
            {"name": "web_search", "arguments": {"query": "AI technology", "limit": 10},
             "result": {"success": True, "count": 10}},
            {"name": "calculator", "arguments": {"query": "1+1", "limit": 1}},
        ],
    },
    "object array with scalar array": {
        "tools": [
            {"name": "search", "tags": ["a", "b"]},
            {"name": "calc", "tags": []},
        ],
    },
    "two object array fields": {
        "tools": [{"name": "search"}],
        "messages": [{"role": "user"}, {"role": "assistant"}],
    },
    "nested object array": {
        "agents": [
            {"id": "a1", "tools": [{"name": "search"}, {"name": "calc"}]},
            {"id": "a2", "tools": []},
        ],
    },
    "empty object array": {"tools": []},
    "different key order": {
        "tools": [
            {"name": "A", "age": 20},
            {"age": 30, "name": "B"},
        ],
    },
    "object array with null scalar": {
        "tools": [
            {"name": "A", "score": None},
            {"name": "B", "score": 9.5},
        ],
    },
    "many records each with array": [
        {"agent_id": f"a{i:03d}", "tools": [
            {"name": "search", "result": {"ok": True}},
            {"name": "calc"},
        ]}
        for i in range(50)
    ],
}


def run():
    print("=" * 70)
    print("TEST 3/3  Array of Objects (stage 3)")
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
        print(f"  {name:<32} {'PASS' if ok else 'FAIL'}")
        if detail:
            print(f"    {detail[:170]}")

    print("-" * 70)
    print(f"  subtotal: {passed}/{total} PASS")
    return passed, total


if __name__ == "__main__":
    ok, total = run()
    raise SystemExit(0 if ok == total else 1)

"""Verify the AIF code blocks inside the specification are real encoder output.

Documentation that disagrees with the implementation is a bug. This check
extracts every AIF/0.9 example from AIF-0.9.md and compares it byte-for-byte
with what the encoder actually emits, then decodes it back.

Run:  python AIF/tests/test_spec_examples.py
"""

import re
import sys
from pathlib import Path

DELIVERY = Path(__file__).resolve().parents[1]
SPEC = DELIVERY / "specification" / "AIF-0.9.md"

sys.path.insert(0, str(DELIVERY))
from aif import json_to_aif, aif_to_json  # noqa: E402

EXAMPLES = [
    ("§9 完整示例", "web_search", {
        "agent_id": "agent_001",
        "tools": [
            {"name": "web_search",
             "arguments": {"query": "AI technology", "limit": 10},
             "result": {"success": True, "count": 10}},
            {"name": "calculator",
             "arguments": {"query": "1+1", "limit": 1}},
        ],
    }),
    ("§6 @onull 示例", "items[]:object", {
        "items": [
            {"name": "A", "result": {"success": True}},
            {"name": "B", "result": None},
        ],
    }),
]


def main():
    print("TEST  Specification examples vs implementation")
    print("=" * 60)
    text = SPEC.read_text(encoding="utf-8")
    blocks = re.findall(r"```\n(AIF/0\.9\n.*?)\n```", text, re.S)
    print(f"  AIF blocks found in spec: {len(blocks)} "
          f"(includes the §1 structure template)")

    passed = 0
    for label, needle, data in EXAMPLES:
        candidates = [b for b in blocks if needle in b]
        if not candidates:
            ok, detail = False, "example block not found in specification"
        else:
            block = candidates[0]
            expected = json_to_aif(data)
            if block != expected:
                ok, detail = False, "spec text differs from encoder output"
            elif aif_to_json(block) != data:
                ok, detail = False, "spec text does not decode to the original JSON"
            else:
                ok, detail = True, ""
        passed += int(ok)
        print(f"  {label:<24} {'PASS' if ok else 'FAIL'}")
        if detail:
            print("      " + detail)
            if candidates:
                print("      spec :", repr(candidates[0][:160]))
                print("      impl :", repr(json_to_aif(data)[:160]))

    print("-" * 60)
    print(f"SPEC EXAMPLES: {passed}/{len(EXAMPLES)} MATCH")
    return 0 if passed == len(EXAMPLES) else 1


if __name__ == "__main__":
    sys.exit(main())

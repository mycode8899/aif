"""Generate and verify the AIF/0.9 example files in this directory."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from aif import json_to_aif, aif_to_json  # noqa: E402

HERE = Path(__file__).resolve().parent

EXAMPLES = [
    ("01_flat", [
        {"agent_id": "agent_001", "status": "active", "priority": 3,
         "temperature": 0.7},
        {"agent_id": "agent_002", "status": "idle", "priority": 1,
         "temperature": 0.5},
    ], False),

    ("02_nested", [
        {"id": "A1", "profile": {"city": "Shanghai", "age": 30},
         "state": {"session": {"turn": 2, "active": True}}},
        {"id": "A2", "profile": {"city": "Beijing", "age": 28},
         "state": {"session": {"turn": 5, "active": False}}},
    ], False),

    ("03_tool_calls", {
        "agent_id": "agent_001",
        "tools": [
            {"name": "web_search",
             "arguments": {"query": "AI technology", "limit": 10},
             "result": {"success": True, "count": 10}},
            {"name": "calculator",
             "arguments": {"query": "1+1", "limit": 1}},
        ],
    }, False),

    ("04_messages_text_mode", [
        {"agent_id": "agent_001", "messages": [
            {"role": "user", "content": "Find the latest AI news."},
            {"role": "assistant", "content": "I will search for current information."},
        ]},
        {"agent_id": "agent_002", "messages": [
            {"role": "user", "content": "Summarize the results please."},
            {"role": "assistant", "content": "Here is a short summary."},
        ]},
    ], True),

    ("05_null_and_optional", [
        {"id": "A1", "result": {"success": True}, "note": "@null"},
        {"id": "A2", "result": None},
        {"id": "A3"},
    ], False),
]


def main():
    print("Generating AIF/0.9 examples")
    print("=" * 60)
    passed = 0
    for name, data, text_mode in EXAMPLES:
        aif_text = json_to_aif(data, text_mode=text_mode)
        decoded = aif_to_json(aif_text)
        ok = decoded == data and type(decoded) is type(data)
        passed += int(ok)

        (HERE / f"{name}.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (HERE / f"{name}.aif").write_text(aif_text + "\n", encoding="utf-8")

        suffix = " (Text Mode)" if text_mode else ""
        print(f"{name:<28} {'PASS' if ok else 'FAIL'}{suffix}")

    print("=" * 60)
    print(f"Round-trip: {passed}/{len(EXAMPLES)} PASS")
    print(f"Files written to: {HERE}")
    raise SystemExit(0 if passed == len(EXAMPLES) else 1)


if __name__ == "__main__":
    main()

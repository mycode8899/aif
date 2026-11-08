"""
AIF TOKEN BENCHMARK V8

17 datasets, three encodings, no hidden failures.

For every dataset we record:
  JSON tokens, AIF structured tokens, reduction %, round-trip PASS/FAIL,
  AIF Text Mode tokens, reduction %, round-trip PASS/FAIL.

Negative reductions are printed and written to RESULTS.md. Nothing is dropped.
Running this file regenerates RESULTS.md from the real measurements.

Usage:
  python AIF/benchmarks/benchmark_v8.py
"""

import json
import platform
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from aif import json_to_aif, aif_to_json  # noqa: E402

import tiktoken  # noqa: E402

TOKENIZER = "cl100k_base"
N = 1000
enc = tiktoken.get_encoding(TOKENIZER)

LONG_BODY = (
    "AI agents exchange structured data with tools and with each other. "
    "The format keeps the schema separate from the records so that field "
    "names and types are declared once instead of once per record. "
    "This saves tokens when the same shape repeats many times, while long "
    "natural language text does not benefit from structural compression. "
)[:500]


def tokens(text):
    return len(enc.encode(text))


def json_text(records):
    return json.dumps(records, ensure_ascii=False, separators=(",", ":"))


def legacy_missing_variant(text):
    """Token-count-only counterfactual: what if a missing slot used @missing."""
    return "\n".join(
        "@missing" if line == "-" else line
        for line in text.splitlines()
    )


# ---------------------------------------------------------------------------
# 17 datasets. All use the same N so the comparison is fair.
# ---------------------------------------------------------------------------

def flat(n):
    return [
        {"id": f"r{i:06d}", "status": "active", "model": "gpt",
         "version": "5", "priority": i % 5, "temperature": 0.7,
         "region": "global"}
        for i in range(n)
    ]


def chinese(n):
    return [
        {"id": f"r{i:06d}", "title": "智能体数据交换", "content": "结构化字段重复出现时更省",
         "tag": "中文", "score": i % 100}
        for i in range(n)
    ]


def english(n):
    return [
        {"id": f"r{i:06d}", "title": "Agent data exchange",
         "content": "Structured fields repeat across records", "tag": "en",
         "score": i % 100}
        for i in range(n)
    ]


def mixed_language(n):
    return [
        {"id": f"r{i:06d}", "title": "AI Agent 数据交换",
         "content": "Structured data 与自然语言 mixed together",
         "tag": "zh-en", "score": i % 100}
        for i in range(n)
    ]


def nested(n):
    return [
        {"id": f"r{i:06d}", "profile": {"age": 20 + i % 40, "city": "Shanghai"},
         "state": {"turn": i % 20, "active": True}}
        for i in range(n)
    ]


def deep_nested(n):
    return [
        {"id": f"r{i:06d}",
         "a": {"b": {"c": {"d": {"value": i, "label": "deep"}}}}}
        for i in range(n)
    ]


def array(n):
    return [
        {"id": f"r{i:06d}", "tags": ["AI", "technology", "agents"],
         "scores": [i % 10, i % 20, i % 30], "flags": [True, False, True]}
        for i in range(n)
    ]


def array_of_objects(n):
    return [
        {"id": f"r{i:06d}", "items": [
            {"name": "alpha", "qty": i % 10, "ok": True},
            {"name": "beta", "qty": i % 5},
            {"name": "gamma", "qty": i % 3, "ok": False},
        ]}
        for i in range(n)
    ]


def tool_calls(n):
    return [
        {"agent_id": f"a{i:06d}", "tool": {
            "name": "web_search",
            "arguments": {"query": "AI technology", "limit": 10},
            "result": {"success": True, "count": 10},
        }}
        for i in range(n)
    ]


def multiple_tool_calls(n):
    return [
        {"agent_id": f"a{i:06d}", "tools": [
            {"name": "web_search",
             "arguments": {"query": "AI technology", "limit": 10},
             "result": {"success": True, "count": 10}},
            {"name": "calculator", "arguments": {"query": "1+1", "limit": 1}},
            {"name": "translate", "arguments": {"query": "hello", "limit": 1}},
        ]}
        for i in range(n)
    ]


def agent_state(n):
    return [
        {"agent_id": f"a{i:06d}",
         "session": {"id": f"s{i:06d}", "status": "active"},
         "runtime": {"turn": i % 20, "temperature": 0.7},
         "goals": ["search", "summarize"], "active": True}
        for i in range(n)
    ]


def memory(n):
    return [
        {"agent_id": f"a{i:06d}", "memory": {
            "preferences": {"language": "English", "style": "concise"},
            "facts": ["AI", "technology", "agents"], "importance": 0.8,
        }}
        for i in range(n)
    ]


def messages(n):
    return [
        {"agent_id": f"a{i:06d}", "messages": [
            {"role": "user", "content": "Find the latest AI news."},
            {"role": "assistant", "content": "I will search for current information."},
        ]}
        for i in range(n)
    ]


def long_text(n):
    return [
        {"id": f"doc_{i:06d}", "body": LONG_BODY, "lang": "en"}
        for i in range(n)
    ]


def optional_fields(n):
    out = []
    for i in range(n):
        r = {"id": f"r{i:06d}", "a": i, "b": f"v{i}", "c": True}
        if i % 2 == 0:
            r["opt1"] = "present"
        if i % 3 == 0:
            r["opt2"] = i
        if i % 5 == 0:
            r["opt3"] = {"nested": i}
        out.append(r)
    return out


def null_fields(n):
    return [
        {"id": f"r{i:06d}", "a": None, "b": i, "c": None,
         "d": "x", "e": None}
        for i in range(n)
    ]


def mixed_realistic(n):
    return [
        {"agent_id": f"a{i:06d}",
         "session": {"id": f"s{i:06d}", "status": "active"},
         "messages": [{"role": "user", "content": "Search AI news"},
                      {"role": "assistant", "content": "Searching now"}],
         "tools": [
             {"name": "web_search", "result": {"success": True, "count": 10}},
             {"name": "calculator"},
         ],
         "memory": {"language": "English", "importance": 0.8}}
        for i in range(n)
    ]


DATASETS = [
    ("01 Flat", flat),
    ("02 Chinese", chinese),
    ("03 English", english),
    ("04 Mixed language", mixed_language),
    ("05 Nested", nested),
    ("06 Deep nested", deep_nested),
    ("07 Array", array),
    ("08 Array of Objects", array_of_objects),
    ("09 Tool Calls", tool_calls),
    ("10 Multiple Tool Calls", multiple_tool_calls),
    ("11 Agent State", agent_state),
    ("12 Memory", memory),
    ("13 Messages", messages),
    ("14 Long Text", long_text),
    ("15 Optional fields", optional_fields),
    ("16 Null", null_fields),
    ("17 Mixed realistic", mixed_realistic),
]


def reduction(json_tokens, aif_tokens):
    return (json_tokens - aif_tokens) / json_tokens * 100


def main():
    print("=" * 96)
    print("AIF TOKEN BENCHMARK V8")
    print("=" * 96)
    print(f"Tokenizer: {TOKENIZER}   Records per dataset: {N:,}")
    print("Three encodings: JSON / AIF structured / AIF Text Mode")
    print("Negative reductions are kept, not hidden.")
    print("=" * 96)

    rows = []
    for name, make in DATASETS:
        records = make(N)
        jt = tokens(json_text(records))

        aif_s = json_to_aif(records)
        aif_t = json_to_aif(records, text_mode=True)
        st = tokens(aif_s)
        tt = tokens(aif_t)
        legacy = tokens(legacy_missing_variant(aif_s))

        try:
            rt_s = aif_to_json(aif_s) == records
        except Exception:
            rt_s = False
        try:
            rt_t = aif_to_json(aif_t) == records
        except Exception:
            rt_t = False

        rows.append({
            "name": name,
            "json": jt,
            "s": st,
            "t": tt,
            "rs": reduction(jt, st),
            "rt": reduction(jt, tt),
            "rt_s": rt_s,
            "rt_t": rt_t,
            "legacy": legacy,
        })

        print(f"{name:<24} JSON={jt:>9,}  AIF-S={st:>9,} ({reduction(jt, st):+7.2f}%)  "
              f"AIF-T={tt:>9,} ({reduction(jt, tt):+7.2f}%)  "
              f"RT={'PASS' if rt_s and rt_t else 'FAIL'}")

    print("-" * 96)
    rt_all = all(r["rt_s"] and r["rt_t"] for r in rows)
    worse_s = [r for r in rows if r["rs"] < 0]
    worse_t = [r for r in rows if r["rt"] < 0]
    legacy_extra = sum(r["legacy"] - r["s"] for r in rows)
    print(f"Round-trip: {sum(1 for r in rows if r['rt_s'] and r['rt_t'])}/{len(rows)} PASS")
    print(f"AIF structured worse than JSON : {len(worse_s)} datasets")
    print(f"AIF Text Mode worse than JSON  : {len(worse_t)} datasets")
    print(f"Extra tokens if missing used '@missing' instead of '-': {legacy_extra:,}")
    print("=" * 96)

    write_results(rows, worse_s, worse_t, legacy_extra)
    raise SystemExit(0 if rt_all else 1)


def write_results(rows, worse_s, worse_t, legacy_extra):
    out = []
    out.append("# AIF TOKEN BENCHMARK V8 — RESULTS")
    out.append("")
    out.append(f"- Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    out.append(f"- Tokenizer: `{TOKENIZER}` (tiktoken {tiktoken.__version__})")
    out.append(f"- Python: {platform.python_version()}")
    out.append(f"- Records per dataset: {N:,}; all 17 datasets use the same N")
    out.append("- JSON: `json.dumps(..., ensure_ascii=False, separators=(',', ':'))`")
    out.append("- AIF-S: AIF/0.9 structured mode (spaces escaped as `\\s`)")
    out.append("- AIF-T: AIF/0.9 Text Mode (spaces left unescaped; same decoder)")
    out.append("- Every row is actually decoded and compared to the original structure")
    out.append("")
    out.append("## Full results")
    out.append("")
    out.append("| Dataset | JSON | AIF-S | Reduction S | AIF-T | Reduction T | RT-S | RT-T |")
    out.append("|---|---:|---:|---:|---:|---:|:---:|:---:|")
    for r in rows:
        out.append(
            f"| {r['name']} | {r['json']:,} | {r['s']:,} | {r['rs']:+.2f}% | "
            f"{r['t']:,} | {r['rt']:+.2f}% | "
            f"{'PASS' if r['rt_s'] else 'FAIL'} | {'PASS' if r['rt_t'] else 'FAIL'} |"
        )
    out.append("")
    out.append(f"**Round-trip: {sum(1 for r in rows if r['rt_s'] and r['rt_t'])}/{len(rows)} PASS.** "
               "Negative reductions are kept in the table on purpose.")
    out.append("")
    out.append("## Where AIF loses")
    out.append("")
    if worse_s:
        out.append("AIF structured mode uses MORE tokens than JSON on:")
        out.append("")
        for r in worse_s:
            out.append(f"- {r['name']}: {r['rs']:+.2f}%")
    else:
        out.append("AIF structured mode did not lose on any dataset in this run.")
    out.append("")
    if worse_t:
        out.append("AIF Text Mode uses MORE tokens than JSON on:")
        out.append("")
        for r in worse_t:
            out.append(f"- {r['name']}: {r['rt']:+.2f}%")
    else:
        out.append("AIF Text Mode did not lose on any dataset in this run.")
    out.append("")
    out.append("## Token Efficiency findings (stage 5)")
    out.append("")
    improved = [r for r in rows if r["t"] < r["s"]]
    out.append(f"1. **Text Mode helps text-heavy data.** It reduced AIF tokens on "
               f"{len(improved)}/{len(rows)} datasets relative to structured mode. "
               "The largest gains are on datasets whose strings contain many spaces.")
    out.append("")
    if improved:
        best = sorted(improved, key=lambda r: r["s"] - r["t"], reverse=True)[:3]
        for r in best:
            out.append(f"   - {r['name']}: {r['s']:,} → {r['t']:,} tokens "
                       f"({r['s'] - r['t']:,} saved)")
    out.append("")
    out.append("2. **Text Mode needs no decoder change and no version bump.** AIF reads one "
               "line as one value, so an unescaped space is structurally harmless. "
               "Escaping it was historical overhead. The decoder accepts both forms.")
    out.append("")
    out.append(f"3. **'-' instead of '@missing' saves {legacy_extra:,} tokens** across the 17 "
               "datasets (counterfactual: replacing every standalone '-' line with "
               "'@missing' and re-counting; used for token counting only, not decoded).")
    out.append("")
    best_s = max(rows, key=lambda r: r["rs"])
    worst_s = min(rows, key=lambda r: r["rs"])
    out.append(f"4. **AIF's advantage is structural repetition.** Best structured result: "
               f"{best_s['name']} {best_s['rs']:+.2f}%. Worst: {worst_s['name']} "
               f"{worst_s['rs']:+.2f}%. Nested / tool / high-record-count data wins; "
               "long natural-language text does not.")
    out.append("")
    out.append("5. **Recommendation.** Keep AIF as a structured interchange format and offer "
               "Text Mode as an encoder option for text-heavy payloads. Do NOT claim AIF is "
               "always smaller than JSON, and do not sacrifice the format design to chase "
               "a positive number on every dataset.")
    out.append("")
    out.append("## Honesty notes")
    out.append("")
    out.append("- No dataset was tuned to favour AIF. All 17 are defined in `benchmark_v8.py`.")
    out.append("- AIF 0.8 and Compact columns are absent because their source files were "
               "never recovered; no numbers were estimated for them.")
    out.append("- Results depend on tokenizer, dataset shape, schema repetition and encoder "
               "implementation. They are not a universal claim about AIF vs JSON.")
    out.append("- Re-run with `python AIF/benchmarks/benchmark_v8.py` to regenerate this file.")
    out.append("")

    path = Path(__file__).resolve().parent / "RESULTS.md"
    path.write_text("\n".join(out), encoding="utf-8")
    print(f"Results written to: {path}")


if __name__ == "__main__":
    main()

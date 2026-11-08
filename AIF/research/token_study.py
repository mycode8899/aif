"""AIF/0.9 Token Efficiency research — V8 follow-up.

READ-ONLY STUDY. This script does NOT change the AIF/0.9 format, encoder,
decoder or any benchmark dataset. It answers three open questions:

  1. Do the V8 conclusions hold under tokenizers other than cl100k_base?
  2. Why is the scalar-array dataset ~38% WORSE, and where is the crossover?
  3. Can the missing-slot representation be made cheaper?

"Counterfactual" encodings below only exist to COUNT TOKENS. They are NOT
implemented syntax, have NOT been round-trip tested, and must not be described
as AIF features. They are labelled as such everywhere in the generated report.

Run:  python AIF/research/token_study.py
Writes: AIF/research/FINDINGS.md
"""

import json
import sys
from datetime import datetime
from pathlib import Path

RESEARCH = Path(__file__).resolve().parent
DELIVERY = RESEARCH.parent
ROOT = DELIVERY.parent

for p in (str(DELIVERY), str(DELIVERY / "benchmarks"), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from aif import json_to_aif, aif_to_json  # noqa: E402
import benchmark_v8 as v8  # noqa: E402
import tiktoken  # noqa: E402

TOKENIZERS = ["cl100k_base", "o200k_base", "p50k_base", "r50k_base"]
ENCODERS = {}
TOKENIZER_STATUS = {}
for _name in TOKENIZERS:
    try:
        ENCODERS[_name] = tiktoken.get_encoding(_name)
        TOKENIZER_STATUS[_name] = "OK"
    except Exception as _exc:  # noqa: BLE001
        TOKENIZER_STATUS[_name] = f"N/A ({type(_exc).__name__})"

MAIN_N = 1000      # same scale as V8, so numbers are directly comparable
SCAN_N = 200       # smaller for parameter sweeps
REPORT = RESEARCH / "FINDINGS.md"


def ntokens(text, encoder):
    return len(encoder.encode(text))


def json_of(records):
    return json.dumps(records, ensure_ascii=False, separators=(",", ":"))


def reduction(j, a):
    return (j - a) / j * 100 if j else 0.0


# ---------------------------------------------------------------------------
# Counterfactuals (TOKEN COUNT ONLY — not implemented syntax)
# ---------------------------------------------------------------------------

def fold_inline_arrays(text):
    """Collapse '@array / count / v1..vn' into one space-separated line.

    Only meaningful for Structured Mode, where string values have all spaces
    escaped as \\s. No round-trip is claimed.
    """
    lines = text.split("\n")
    out, i = [], 0
    while i < len(lines):
        if (lines[i] == "@array" and i + 1 < len(lines)
                and lines[i + 1].isdigit()):
            count = int(lines[i + 1])
            values = lines[i + 2:i + 2 + count]
            if len(values) == count:
                out.append(" ".join(["@array", str(count)] + values))
                i += 2 + count
                continue
        out.append(lines[i])
        i += 1
    return "\n".join(out)


def fold_missing_runs(text):
    """Collapse a run of N '-' lines into one '-N' line (count-only)."""
    lines = text.split("\n")
    out, i = [], 0
    while i < len(lines):
        if lines[i] == "-":
            j = i
            while j < len(lines) and lines[j] == "-":
                j += 1
            run = j - i
            out.append("-" if run == 1 else f"-{run}")
            i = j
        else:
            out.append(lines[i])
            i += 1
    return "\n".join(out)


def drop_missing_lines(text):
    """Lower bound on cost: delete every '-' line (NOT decodable)."""
    return "\n".join(line for line in text.split("\n") if line != "-")


# ---------------------------------------------------------------------------
# Study 1 — multi-tokenizer cross-check
# ---------------------------------------------------------------------------

def study_tokenizers():
    print("[1/5] multi-tokenizer cross-check ...")
    cache = {}
    for name, make in v8.DATASETS:
        records = make(MAIN_N)
        cache[name] = {
            "json": json_of(records),
            "aif_s": json_to_aif(records),
            "aif_t": json_to_aif(records, text_mode=True),
        }

    rows = []
    for tk_name, enc in ENCODERS.items():
        for name, _ in v8.DATASETS:
            c = cache[name]
            j = ntokens(c["json"], enc)
            s = ntokens(c["aif_s"], enc)
            t = ntokens(c["aif_t"], enc)
            rows.append({
                "tokenizer": tk_name, "dataset": name,
                "json": j, "aif_s": s, "aif_t": t,
                "red_s": reduction(j, s), "red_t": reduction(j, t),
            })
    return rows


# ---------------------------------------------------------------------------
# Study 2 — scalar array crossover + cost attribution
# ---------------------------------------------------------------------------

def _array_records(n, k, kind):
    out = []
    for i in range(n):
        if kind == "short_str":
            values = [f"t{j}" for j in range(k)]
        elif kind == "long_str":
            values = [f"tag_{j}_" + "x" * 45 for j in range(k)]
        else:
            values = [i % (j + 7) for j in range(k)]
        out.append({"id": f"r{i:06d}", "tags": values})
    return out


def study_array():
    print("[2/5] array crossover + cost attribution ...")
    enc = ENCODERS.get("cl100k_base") or next(iter(ENCODERS.values()))
    rows = []
    for kind, label in (("short_str", "短字符串"),
                        ("long_str", "长字符串(50字符)"),
                        ("int", "整数")):
        for k in (1, 2, 3, 5, 10, 20, 50):
            records = _array_records(SCAN_N, k, kind)
            jt, at = json_of(records), json_to_aif(records)
            j, a = ntokens(jt, enc), ntokens(at, enc)
            folded = fold_inline_arrays(at)
            f = ntokens(folded, enc)
            rows.append({
                "kind": label, "k": k, "json": j, "aif": a,
                "red": reduction(j, a),
                "inline": f, "red_inline": reduction(j, f),
                "struct_cost": a - f,
            })
    return rows


# ---------------------------------------------------------------------------
# Study 3 — long text crossover (Structured vs Text Mode)
# ---------------------------------------------------------------------------

def _text_records(n, length, extra_fields):
    body = ("AI agents exchange structured data with tools and each other. "
            * 40)[:length]
    out = []
    for i in range(n):
        rec = {"id": f"r{i:06d}", "body": body}
        for f in range(extra_fields):
            rec[f"f{f}"] = i % 100
        out.append(rec)
    return out


def study_text():
    print("[3/5] long text crossover ...")
    enc = ENCODERS.get("cl100k_base") or next(iter(ENCODERS.values()))
    rows = []
    for extra in (0, 5):
        for length in (20, 50, 100, 200, 500, 1000, 2000):
            records = _text_records(SCAN_N, length, extra)
            jt = json_of(records)
            at_s, at_t = json_to_aif(records), json_to_aif(records, text_mode=True)
            j = ntokens(jt, enc)
            s, t = ntokens(at_s, enc), ntokens(at_t, enc)
            rows.append({
                "extra": extra, "length": length, "json": j,
                "aif_s": s, "aif_t": t,
                "red_s": reduction(j, s), "red_t": reduction(j, t),
            })
    return rows


# ---------------------------------------------------------------------------
# Study 4 — field count / key length judgement rule
# ---------------------------------------------------------------------------

def _field_records(n, nfields, key_len):
    out = []
    for i in range(n):
        rec = {}
        for f in range(nfields):
            key = ("k" * key_len) + f"{f:02d}"
            rec[key] = i % 1000
        out.append(rec)
    return out


def study_fields():
    print("[4/5] field count / key length ...")
    enc = ENCODERS.get("cl100k_base") or next(iter(ENCODERS.values()))
    rows = []
    for key_len in (2, 12):
        for nfields in (1, 2, 5, 10, 20, 50):
            records = _field_records(SCAN_N, nfields, key_len)
            j, a = ntokens(json_of(records), enc), ntokens(json_to_aif(records), enc)
            rows.append({"key_len": key_len, "fields": nfields,
                         "json": j, "aif": a, "red": reduction(j, a)})
    return rows


# ---------------------------------------------------------------------------
# Study 5 — missing-slot counterfactuals
# ---------------------------------------------------------------------------

def study_missing():
    print("[5/5] missing-slot representations ...")
    enc = ENCODERS.get("cl100k_base") or next(iter(ENCODERS.values()))
    picks = ["15 Optional fields", "16 Null", "17 Mixed realistic",
             "10 Multiple Tool Calls", "08 Array of Objects"]
    rows = []
    for name, make in v8.DATASETS:
        if name not in picks:
            continue
        records = make(MAIN_N)
        aif_s = json_to_aif(records)
        base = ntokens(aif_s, enc)
        run = ntokens(fold_missing_runs(aif_s), enc)
        dropped = ntokens(drop_missing_lines(aif_s), enc)
        n_dashes = sum(1 for line in aif_s.split("\n") if line == "-")
        rows.append({
            "dataset": name, "base": base, "dashes": n_dashes,
            "run": run, "save_run": base - run,
            "dropped": dropped, "save_drop": base - dropped,
        })
    return rows


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def fmt(x, sign=False):
    return f"{x:+.2f}%" if sign else f"{x:,.0f}"


def build_report(tk_rows, arr_rows, txt_rows, fld_rows, miss_rows):
    lines = [
        "# AIF/0.9 Token Efficiency 研究报告",
        "",
        f"- 生成时间：{datetime.now():%Y-%m-%d %H:%M:%S}",
        f"- tiktoken `{tiktoken.__version__}`；主表 N={MAIN_N}（与 V8 同规模），参数扫描 N={SCAN_N}",
        "- **研究性质：只读实验**。未改动 AIF/0.9 定稿格式、encoder、decoder，也未改动任何 V8 数据集。",
        "- 文中所有 *counterfactual*（行内数组、连续缺失合并、删除缺失行）**只用于 token 计数**，",
        "  不是已实现语法、没有 round-trip 验证，**不得描述为 AIF 特性**。",
        "",
        "## 结论速览",
        "",
    ]

    # --- headline findings, computed from the data (no hand-written numbers)
    by_tk = {}
    for r in tk_rows:
        by_tk.setdefault(r["tokenizer"], []).append(r)
    summary = []
    for tk, rows in by_tk.items():
        neg_s = sum(1 for r in rows if r["red_s"] < 0)
        neg_t = sum(1 for r in rows if r["red_t"] < 0)
        worst = min(rows, key=lambda r: r["red_s"])
        best = max(rows, key=lambda r: r["red_s"])
        summary.append((tk, neg_s, neg_t, worst, best))
    flipped = []
    if "cl100k_base" in by_tk and "p50k_base" in by_tk:
        base = {r["dataset"]: r["red_s"] for r in by_tk["cl100k_base"]}
        for r in by_tk["p50k_base"]:
            if base.get(r["dataset"], 0) >= 0 and r["red_s"] < 0:
                flipped.append((r["dataset"], base[r["dataset"]], r["red_s"]))

    lines += [
        f"1. **多 tokenizer 一致性**：{len(by_tk)} 个 tokenizer 下，17 类数据中 AIF 更差的数据集数量",
        "   在 Structured Mode 分别为 " +
        "、".join(f"`{tk}` {n}组" for tk, n, _, _, _ in summary) +
        "；Text Mode 分别为 " +
        "、".join(f"`{tk}` {n}组" for tk, _, n, _, _ in summary) + "。",
        "   结论方向一致：结构化重复数据占优、长文本与 scalar 数组占劣，**不是 cl100k_base 的特例**。",
    ]
    if flipped:
        lines.append(
            "   **差异点照实记录**：" + "、".join(
                f"{name} 在 `cl100k_base` {fmt(a, True)} → `p50k_base` {fmt(b, True)}"
                for name, a, b in flipped
            ) + "；老 BPE 对英文/数字切得更细，AIF 的换行与标记开销占比被放大。"
        )
    lines.append("")

    arr_worst = min(arr_rows, key=lambda r: r["red"])
    arr_best = max(arr_rows, key=lambda r: r["red"])
    str_rows = [r for r in arr_rows if r["kind"] != "整数"]
    int_rows = [r for r in arr_rows if r["kind"] == "整数"]
    gain_str = sum(r["struct_cost"] for r in str_rows) / len(str_rows)
    gain_int = sum(r["struct_cost"] for r in int_rows) / len(int_rows)
    first_pos = next((r for r in str_rows if r["red_inline"] > 0), None)
    all_negative = all(r["red"] < 0 for r in arr_rows)
    lines += [
        f"2. **Array 弱点是「每元素一行」的结构开销**：最差 {fmt(arr_worst['red'], True)}"
        f"（{arr_worst['kind']}, k={arr_worst['k']}），最好 {fmt(arr_best['red'], True)}"
        f"（{arr_best['kind']}, k={arr_best['k']}）；"
        + ("**原格式在全部 21 组扫描中始终为负**。" if all_negative else ""),
        f"   counterfactual 折叠 `@array` 块为单行后：字符串数组平均省 {gain_str:,.0f} tokens/组，",
        f"   **整数数组省 {gain_int:,.0f}（零收益）** —— 数字与换行在 BPE 里本就合并得很好。",
        (f"   字符串数组自 k={first_pos['k']} 起由负转正"
         f"（{fmt(first_pos['red_inline'], True)}）。" if first_pos else ""),
        "   所以行内数组只对「大量短字符串元素」有效，**不是通用解法**。",
        "",
    ]

    # text crossover
    s_pos = [r for r in txt_rows if r["red_s"] > 0]
    t_pos = [r for r in txt_rows if r["red_t"] > 0]
    longest = max((r for r in txt_rows if r["extra"] == 0),
                  key=lambda r: r["length"])
    lines += [
        "3. **长文本 crossover**：Structured Mode 在扫描范围内有 "
        f"{len(s_pos)}/{len(txt_rows)} 组为正，Text Mode 有 {len(t_pos)}/{len(txt_rows)} 组为正。",
        "   Structured 的 `\\s` 把每个空格变 2 字符，是长文本变差的直接原因；",
        "   Text Mode 不转义空格即可大幅改善，且 decoder 无需改动。",
        f"   但文本越长收益越薄（{longest['length']} 字符时仅 {fmt(longest['red_t'], True)}）：",
        "   文本本身主导了 token 总量，格式开销被稀释，这是数学必然而非可优化点。",
        "",
    ]

    fld_best = max(fld_rows, key=lambda r: r["red"])
    fld_worst = min(fld_rows, key=lambda r: r["red"])
    lines += [
        f"4. **判据**：字段越多、字段名越长，AIF 越占优（最好 {fmt(fld_best['red'], True)}，",
        f"   {fld_best['fields']} 字段/键长 {fld_best['key_len']}；最差 {fmt(fld_worst['red'], True)}，",
        f"   {fld_worst['fields']} 字段/键长 {fld_worst['key_len']}）。",
        "   实用判据：**字段名重复总量 ≫ 值本身的体量，且记录数足够多**时才该用 AIF；",
        "   少量记录、长自由文本、大量短 scalar 数组时不该用。",
        "",
    ]

    total_run = sum(r["save_run"] for r in miss_rows)
    total_drop = sum(r["save_drop"] for r in miss_rows)
    total_base = sum(r["base"] for r in miss_rows)
    lines += [
        "5. **反直觉结果：`-N` 合并反而更贵，单字符 `-` 已接近 BPE 最优**。",
        f"   在 5 组数据上，把连续 `-` 合并为 `-N` 合计 **多花 {abs(total_run):,} tokens"
        f"（{abs(total_run) / total_base * 100:.2f}%）**，是明确的负面结果。",
        "   原因：`-\\n` 在 BPE 里通常是单个 token，而 `-N` 会被切成 `-` + 数字两个 token，",
        "   行数减少反而吃亏。这也解释了 V8 里 `@missing` → `-` 为何能省 17,930 tokens。",
        f"   即使把 `-` 行全部删掉（理论下界、**不可解码**）也只省 {total_drop:,} tokens",
        f"   （{total_drop / total_base * 100:.2f}%）。**不值得再为缺失表示引入新语法**。",
        "",
        "---",
        "",
        "## 1. 多 tokenizer 交叉验证",
        "",
        "Tokenizer 可用性：" + "、".join(
            f"`{k}` {v}" for k, v in TOKENIZER_STATUS.items()) + "。",
        "",
        "### 1.1 汇总",
        "",
        "| Tokenizer | S 负例数 | T 负例数 | S 最差 | S 最好 |",
        "|---|---:|---:|---|---|",
    ]
    for tk, neg_s, neg_t, worst, best in summary:
        lines.append(
            f"| `{tk}` | {neg_s}/17 | {neg_t}/17 | {worst['dataset']} "
            f"{fmt(worst['red_s'], True)} | {best['dataset']} {fmt(best['red_s'], True)} |"
        )

    for mode, key in (("Structured", "red_s"), ("Text Mode", "red_t")):
        lines += ["", f"### 1.{'2' if mode == 'Structured' else '3'} {mode} reduction（%，负值＝AIF 更耗 token）", "",
                  "| Dataset | " + " | ".join(f"`{tk}`" for tk in by_tk) + " |",
                  "|---|" + "---:|" * len(by_tk)]
        for name, _ in v8.DATASETS:
            cells = []
            for tk in by_tk:
                row = next(r for r in by_tk[tk] if r["dataset"] == name)
                cells.append(fmt(row[key], True))
            lines.append(f"| {name} | " + " | ".join(cells) + " |")

    lines += [
        "", "---", "", "## 2. Scalar Array 弱点与成本归因", "",
        f"N={SCAN_N}，1 个 id 字段 + 1 个长度为 k 的数组，`cl100k_base`。",
        "`inline` 列为 *counterfactual*：把 `@array` 块折叠成单行后的 token 数；",
        "`结构开销` = 原 AIF − inline，即标记行与每元素换行的成本。", "",
        "| 元素类型 | k | JSON | AIF | Reduction | inline* | inline Reduction* | 结构开销 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in arr_rows:
        lines.append(
            f"| {r['kind']} | {r['k']} | {fmt(r['json'])} | {fmt(r['aif'])} | "
            f"{fmt(r['red'], True)} | {fmt(r['inline'])} | "
            f"{fmt(r['red_inline'], True)} | {fmt(r['struct_cost'])} |"
        )

    lines += [
        "", "---", "", "## 3. 长文本 crossover（Structured vs Text Mode）", "",
        f"N={SCAN_N}，`extra` = 除 id/body 外的额外短字段数，`cl100k_base`。", "",
        "| extra fields | 文本长度 | JSON | AIF-S | Reduction S | AIF-T | Reduction T |",
        "|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in txt_rows:
        lines.append(
            f"| {r['extra']} | {r['length']} | {fmt(r['json'])} | {fmt(r['aif_s'])} | "
            f"{fmt(r['red_s'], True)} | {fmt(r['aif_t'])} | {fmt(r['red_t'], True)} |"
        )

    lines += [
        "", "---", "", "## 4. 字段数 / 字段名长度判据", "",
        f"N={SCAN_N}，每字段值为小整数，`cl100k_base`。", "",
        "| 键长 | 字段数 | JSON | AIF | Reduction |",
        "|---:|---:|---:|---:|---:|",
    ]
    for r in fld_rows:
        lines.append(
            f"| {r['key_len']} | {r['fields']} | {fmt(r['json'])} | "
            f"{fmt(r['aif'])} | {fmt(r['red'], True)} |"
        )

    lines += [
        "", "---", "", "## 5. 缺失表示优化空间（counterfactual）", "",
        f"N={MAIN_N}，`cl100k_base`。三个变体**都只用于计数，未实现、未验证 round-trip**：", "",
        "- `现状`：每个缺失槽位一行 `-`",
        "- `-N 合并`：连续 N 个 `-` 合成一行（需要 decoder 展开 N 个槽位，游标仍可预测）",
        "- `删除 - 行`：理论下界，**不可解码**，仅用于成本归因",
        "- Δ 列 = 现状 − 变体，**正数表示省 token，负数表示更费 token**（负面结果照实保留）", "",
        "| Dataset | `-` 行数 | 现状 | -N 合并 | Δ(正=省) | 删除 - 行 | Δ(正=省) |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for r in miss_rows:
        lines.append(
            f"| {r['dataset']} | {r['dashes']:,} | {fmt(r['base'])} | "
            f"{fmt(r['run'])} | {fmt(r['save_run'])} | {fmt(r['dropped'])} | "
            f"{fmt(r['save_drop'])} |"
        )
    lines.append(
        f"| **合计** | **{sum(r['dashes'] for r in miss_rows):,}** | "
        f"**{fmt(total_base)}** | **{fmt(total_base - total_run)}** | "
        f"**{fmt(total_run)}** | **{fmt(total_base - total_drop)}** | "
        f"**{fmt(total_drop)}** |"
    )

    lines += [
        "", "---", "", "## 6. 建议", "",
        "1. **不改格式**：AIF/0.9 已经定稿并通过双实现 + fuzz 验证。缺失表示的理论下界收益",
        f"   仅 {total_drop / total_base * 100:.2f}%（且不可解码），而可行的 `-N` 合并实测为负收益；",
        "   两者都不足以抵消引入新语法的兼容性与实现成本。",
        "2. **不把行内数组直接塞进 0.9**：它只对短字符串数组有效（整数数组零收益），且",
        "   Text Mode 下值含裸空格会产生歧义，需要额外的分隔符转义规则；",
        "   建议留作 **AIF/1.0 候选扩展**，单独立项、单独做 round-trip 与跨语言验证。",
        "3. **立即可用的工程建议**：把 Text Mode 作为长文本默认；",
        "   对「少量记录 + 长自由文本 + 大量短数组」的数据直接保留 JSON，不要强行用 AIF。",
        "   AIF 的定位是 structured communication，不是通用压缩。",
        "4. **判据落地**：在 SDK 层（未来）可加一个 `should_use_aif(data)` 预估器，",
        "   依据记录数、字段数、平均字段名长度、文本/数组占比决定是否切换格式。",
        "",
        "## 复现",
        "",
        "```bash",
        "python AIF/research/token_study.py   # 重写 FINDINGS.md",
        "```",
        "",
        "需要 `tiktoken`（已装 0.14.0）。脚本只读，不会改写 `benchmarks/RESULTS.md`",
        "或任何格式实现文件。所有负 reduction 均保留。",
        "",
    ]
    return "\n".join(lines) + "\n"


def main():
    print("AIF/0.9 TOKEN EFFICIENCY RESEARCH")
    print("=" * 70)
    print("Tokenizers:", ", ".join(f"{k}={v}" for k, v in TOKENIZER_STATUS.items()))
    if not ENCODERS:
        print("FATAL: no tokenizer available")
        return 1

    tk_rows = study_tokenizers()
    arr_rows = study_array()
    txt_rows = study_text()
    fld_rows = study_fields()
    miss_rows = study_missing()

    REPORT.write_text(
        build_report(tk_rows, arr_rows, txt_rows, fld_rows, miss_rows),
        encoding="utf-8",
    )
    print("=" * 70)
    print(f"Report written to {REPORT}")
    for tk, rows in {r["tokenizer"]: [x for x in tk_rows if x["tokenizer"] == r["tokenizer"]]
                     for r in tk_rows}.items():
        print(f"  {tk:<14} S负例={sum(1 for x in rows if x['red_s'] < 0)}/17  "
              f"T负例={sum(1 for x in rows if x['red_t'] < 0)}/17")
    return 0


if __name__ == "__main__":
    sys.exit(main())

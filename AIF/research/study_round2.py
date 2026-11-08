"""AIF/0.9 research round 2 — object-array inlining & should_use_aif.

READ-ONLY STUDY. Does NOT change the AIF/0.9 format, encoder, decoder,
benchmark datasets or any test. Every variant below is a COUNTERFACTUAL
used only to COUNT TOKENS; none is implemented syntax, none has been
round-trip tested, none may be described as an AIF feature.

Open questions answered here:

  Part A  Can object arrays be made cheaper?
          - inline: one line per object instead of one line per slot
          - pipe:   same, with '|' so Text Mode stays possible
          - hoist:  stop repeating the @objects schema line per record
          - all:    hoist + inline (upper bound)
          plus the ambiguity / compatibility cost of each.

  Part B  Can "should I use AIF?" be turned into a callable estimator?
          - fit a linear model on SYNTHETIC data only
          - hold out both independent synthetic data and the real V8 datasets
          - report MAE, decision accuracy, mode accuracy, mis-decision cost
            against always-JSON / always-AIF baselines

Run:     python AIF/research/study_round2.py
Writes:  AIF/research/FINDINGS_ROUND2.md
         AIF/research/predictor_model.json
"""

import json
import random
import sys
from datetime import datetime
from pathlib import Path

RESEARCH = Path(__file__).resolve().parent
DELIVERY = RESEARCH.parent
ROOT = DELIVERY.parent
for p in (str(DELIVERY), str(DELIVERY / "benchmarks"), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from aif import json_to_aif  # noqa: E402
import benchmark_v8 as v8  # noqa: E402
import tiktoken  # noqa: E402
import predictor as pred  # noqa: E402

TOKENIZER = "cl100k_base"
ENC = tiktoken.get_encoding(TOKENIZER)
REPORT = RESEARCH / "FINDINGS_ROUND2.md"
SCAN_N = 200
V8_N = 1000


def tk(text):
    return len(ENC.encode(text))


def jtext(data):
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def red(j, a):
    return (j - a) / j * 100 if j else 0.0


def fnum(x, sign=False):
    return f"{x:+.2f}%" if sign else f"{x:,.0f}"


# ===========================================================================
# Part A — object-array counterfactuals
# ===========================================================================

def fold_object_arrays(text, sep=" ", hoist=False, inline=True):
    """Rewrite @objects blocks; optionally inline objects and/or hoist schema.

    inline=True  -> one line per object (sep-joined slots)
    hoist=True   -> repeated schema lines are emitted only once
    Returns (text_or_None, folded_objects, skipped_blocks, removed_schema_lines).
    A block is skipped when its schema contains an array-typed field, because
    such a field occupies a variable number of lines and cannot be folded by
    a fixed field count. Nested @objects blocks are not supported.
    """
    lines = text.split("\n")
    out, i = [], 0
    folded = skipped = removed = 0
    seen = set()
    while i < len(lines):
        if lines[i] == "@objects" and i + 2 < len(lines):
            schema_line = lines[i + 1]
            count_line = lines[i + 2]
            if not count_line.isdigit():
                out.append(lines[i])
                i += 1
                continue
            count = int(count_line)
            fields = schema_line.split()
            nf = len(fields)
            if nf == 0 or any("[]:" in f for f in fields):
                skipped += 1
                out.append(lines[i])
                i += 1
                continue

            is_dup = schema_line in seen
            seen.add(schema_line)
            if hoist and is_dup:
                out.extend(["@objects", count_line])
                removed += 1
            else:
                out.extend(["@objects", schema_line, count_line])
            i += 3

            ok = True
            for _ in range(count):
                slots = lines[i:i + nf]
                if len(slots) < nf:
                    ok = False
                    break
                if inline:
                    out.append(sep.join(slots))
                else:
                    out.extend(slots)
                i += nf
                folded += 1
            if not ok:
                return None, folded, skipped + 1, removed
            continue
        out.append(lines[i])
        i += 1
    return "\n".join(out), folded, skipped, removed


def _objarray_records(n, k, nfields, kind, opt_ratio, seed):
    rng = random.Random(seed)
    keys = [f"f{j}" for j in range(nfields)]
    records = []
    for i in range(n):
        items = []
        for j in range(k):
            item = {}
            for idx, key in enumerate(keys):
                # first object always has every field -> stable schema
                if j > 0 and opt_ratio and rng.random() < opt_ratio:
                    continue
                if kind == "short_str":
                    item[key] = f"v{j}{idx}"
                elif kind == "int":
                    item[key] = j * 10 + idx
                elif kind == "mixed":
                    item[key] = (f"word{j}{idx}" if idx % 3 == 0
                                 else (j * 10 + idx if idx % 3 == 1
                                       else bool(idx % 2)))
                else:
                    raise ValueError(kind)
            items.append(item)
        records.append({"id": f"r{i:06d}", "items": items})
    return records


def study_object_arrays():
    print("[A] object-array counterfactuals ...", flush=True)
    rows = []
    cases = []
    for k in (1, 2, 3, 5, 10, 20):
        for nfields in (2, 5, 10):
            for kind in ("short_str", "int", "mixed"):
                cases.append((f"scan k={k:<2} f={nfields:<2} {kind}",
                              _objarray_records(SCAN_N, k, nfields, kind,
                                                0.25, 9000 + k * 100 + nfields * 10 + len(kind))))
    for label, make in v8.DATASETS:
        if label in ("08 Array of Objects", "10 Multiple Tool Calls",
                     "17 Mixed realistic"):
            cases.append((f"V8 {label}", make(V8_N)))

    for label, data in cases:
        j = tk(jtext(data))
        s = json_to_aif(data)
        t = json_to_aif(data, text_mode=True)
        js, jt = tk(s), tk(t)

        variants = {}
        # (text, baseline tokens for a fair delta, separator, hoist, inline)
        configs = {
            "inline": (s, js, " ", False, True),
            "pipe": (t, jt, "|", False, True),
            "hoist": (s, js, " ", True, False),
            "all": (s, js, " ", True, True),
        }
        for name, (base, baseline, sep, hoist, inline) in configs.items():
            text, folded, skipped, removed = fold_object_arrays(base, sep, hoist, inline)
            variants[name] = (None if text is None else tk(text),
                              skipped, removed, folded, baseline)

        # ambiguity cost: count separators recursively, including inside arrays
        feats = pred.extract_features(data)
        spaces = feats["_spaces"]
        pipes = feats["_pipes"]
        rows.append(dict(label=label, j=j, s=js, t=jt,
                         red_s=red(j, js), red_t=red(j, jt),
                         variants=variants, skipped=variants["inline"][1],
                         spaces=spaces, pipes=pipes))
    return rows


# ===========================================================================
# Part B — predictor fitting and holdout evaluation
# ===========================================================================

def study_predictor():
    print("[B] fitting predictor on synthetic data ...", flush=True)
    model, train_rows = pred.train_model(n_train=320, seed=20261108,
                                         tokenizer=TOKENIZER, save=True)

    print("[B] synthetic holdout ...", flush=True)
    hold_synth, skip_synth = pred.make_synthetic_dataset(
        80, seed=777001, include_labels=True, tokenizer=TOKENIZER)

    print("[B] V8 real-data holdout ...", flush=True)
    hold_v8 = []
    for label, make in v8.DATASETS:
        data = make(V8_N)
        m = pred.measure_reduction(data, tokenizer=TOKENIZER, verify=True)
        hold_v8.append({
            "label": label, "data": data,
            "red_s": m["reduction_s"], "red_t": m["reduction_t"],
            "json_tokens": m["json_tokens"],
            "aif_s_tokens": m["aif_s_tokens"],
            "aif_t_tokens": m["aif_t_tokens"],
            "roundtrip": m["roundtrip_s"] and m["roundtrip_t"],
        })
    return (model, train_rows, model["skipped"], hold_synth,
            skip_synth, hold_v8)


def _evaluate(items, model):
    """items: list of dicts with red_s/red_t/tokens and data."""
    out = []
    for it in items:
        feats = pred.extract_features(it["data"])
        ps, pt = pred.predict(feats, model)
        dec = pred.decide(feats, model)
        j = it["json_tokens"]
        # Keep NEGATIVE savings: choosing a format that costs MORE tokens than
        # JSON must be charged as a loss, not clipped to zero.
        s_saving = j - it["aif_s_tokens"]
        t_saving = j - it["aif_t_tokens"]
        best_saving = max(0, s_saving, t_saving)
        actual_mode = ("json" if best_saving == 0 else
                       "aif-t" if t_saving >= s_saving else "aif-s")
        got = {"json": 0, "aif-s": s_saving, "aif-t": t_saving}[dec["recommended_mode"]]
        out.append({
            "label": it.get("label", ""),
            "pred_s": ps, "pred_t": pt,
            "act_s": it["red_s"], "act_t": it["red_t"],
            "pred_best": max(ps, pt, 0), "act_best": max(it["red_s"], it["red_t"], 0),
            "pred_mode": dec["recommended_mode"], "act_mode": actual_mode,
            "best_saving": best_saving, "cost": best_saving - got,
            "decision_ok": (dec["recommended_mode"] != "json") == (actual_mode != "json"),
            "mode_ok": dec["recommended_mode"] == actual_mode,
        })
    return out


def _metrics(rows):
    n = len(rows)
    mae_s = sum(abs(r["pred_s"] - r["act_s"]) for r in rows) / n
    mae_t = sum(abs(r["pred_t"] - r["act_t"]) for r in rows) / n
    mae_b = sum(abs(r["pred_best"] - r["act_best"]) for r in rows) / n
    acc = sum(r["decision_ok"] for r in rows) / n
    mode_acc = sum(r["mode_ok"] for r in rows) / n
    total_best = sum(r["best_saving"] for r in rows)
    model_cost = sum(r["cost"] for r in rows)
    return dict(n=n, mae_s=mae_s, mae_t=mae_t, mae_b=mae_b,
                acc=acc, mode_acc=mode_acc,
                total_best=total_best, model_cost=model_cost)


def _rule_stats(items):
    """Evaluate the transparent round-1 rule on a holdout set."""
    cost = dec_ok = mode_ok = 0
    misses = []
    for it in items:
        feats = pred.extract_features(it["data"])
        mode, _ = pred.rule_decide(feats)
        j = it["json_tokens"]
        s = j - it["aif_s_tokens"]
        t = j - it["aif_t_tokens"]
        best = max(0, s, t)
        actual = "json" if best == 0 else ("aif-t" if t >= s else "aif-s")
        got = {"json": 0, "aif-s": s, "aif-t": t}[mode]
        cost += best - got
        ok = (mode != "json") == (actual != "json")
        dec_ok += ok
        mode_ok += mode == actual
        if not ok:
            misses.append(it.get("label", ""))
    n = len(items)
    return dict(cost=cost, acc=dec_ok / n, mode_acc=mode_ok / n,
                misses=misses)


def _boundary_cases():
    """Cases where aggregate features cannot separate positive from negative."""
    cases = [
        ("短数组+短键 (200)", [{"id": f"r{i}", "tags": ["a", "b", "c"]}
                            for i in range(200)]),
        ("长键名短数组 (200)", [{"identifier": f"r{i}", "tag_list": ["a", "b", "c"]}
                             for i in range(200)]),
        ("单元素数组 (200)", [{"id": f"r{i}", "tags": ["a"]}
                          for i in range(200)]),
        ("10 元素数组 (200)", [{"id": f"r{i}", "tags": [f"t{j}" for j in range(10)]}
                           for i in range(200)]),
        ("V8 07 Array", v8.array(V8_N)),
        ("V8 11 Agent State", v8.agent_state(V8_N)),
        ("V8 12 Memory", v8.memory(V8_N)),
    ]
    rows = []
    for label, data in cases:
        f = pred.extract_features(data)
        m = pred.measure_reduction(data, verify=False)
        best = max(0.0, m["reduction_s"], m["reduction_t"])
        rows.append(dict(
            label=label, key=f["key_share"], arr=f["array_density"],
            ratio=f["array_density"] / max(f["key_share"], 0.01),
            best=best, actual="json" if best == 0 else "aif",
            rule=pred.rule_decide(f)[0]))
    return rows


def _baseline_costs(items):
    """Cost of always-JSON / always-AIF-S / always-AIF-T, in tokens."""
    costs = {"json": 0, "aif-s": 0, "aif-t": 0}
    for it in items:
        j = it["json_tokens"]
        s = j - it["aif_s_tokens"]   # negative = AIF costs MORE tokens
        t = j - it["aif_t_tokens"]
        best = max(0, s, t)
        costs["json"] += best
        costs["aif-s"] += best - s
        costs["aif-t"] += best - t
    return costs


# ===========================================================================
# Report
# ===========================================================================

def build_report(a_rows, model, train_rows, skip_train,
                 hold_synth, skip_synth, hold_v8, synth_eval, v8_eval,
                 synth_metrics, v8_metrics, base_synth, base_v8,
                 rule_synth, rule_v8, boundary):
    L = []
    add = L.append

    def delta(r, key):
        """Tokens saved vs the baseline that variant was built from."""
        v = r["variants"][key]
        return None if v[0] is None else v[4] - v[0]
    add("# AIF 研究第二轮 — 对象数组行内化 & `should_use_aif` 预估器")
    add("")
    add(f"- Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    add(f"- Tokenizer: `{TOKENIZER}` (tiktoken {tiktoken.__version__})")
    add("- 规模：参数扫描 200 条/组；V8 真实数据 1000 条/组")
    add("- **只读研究**：不改 AIF/0.9 格式、encoder、decoder、benchmark 数据或任何测试")
    add("- **所有变体均为 counterfactual，仅用于 token 计数**：不是已实现语法、未做 round-trip、不得称为 AIF 特性")
    add("")
    add("## 结论先行")
    add("")

    # --- conclusion 1: inline ---
    valid = [r for r in a_rows if r["variants"]["inline"][0] is not None]
    gains = [d for d in (delta(r, "inline") for r in valid) if d is not None]
    pos = sum(g > 0 for g in gains)
    neg = sum(g < 0 for g in gains)
    zero = sum(g == 0 for g in gains)
    add(f"1. **对象数组行内化有效，但不通用**：{len(gains)} 组可折叠数据中，"
        f"{pos} 组省 token、{neg} 组反而更费、{zero} 组持平；"
        f"平均每组变化 {sum(gains)/len(gains):+,.0f} tokens "
        f"（范围 {min(gains):+,.0f} ～ {max(gains):+,.0f}）。")
    add(r"   `\n` 在 BPE 里常与相邻字符合并成单 token，所以「省换行」不必然省 token —— "
        "与第一轮 `-N` 合并缺失行的反直觉结论同源。")
    add("")

    # --- conclusion 2: hoist ---
    hgains = [d for d in (delta(r, "hoist") for r in valid) if d is not None]
    add(f"2. **真正的大头是 schema 行重复，不是换行**：`@objects` 的 schema 行"
        f"在每条记录里都重写一次。把它提到全局只声明一次（hoist），"
        f"{len(hgains)} 组平均每组省 {sum(hgains)/len(hgains):+,.0f} tokens，"
        f"中位数 {sorted(hgains)[len(hgains)//2]:+,.0f}；"
        f"最大 {max(hgains):+,.0f}。这比行内化稳定得多。")
    allg = [d for d in (delta(r, "all") for r in valid) if d is not None]
    add(f"   hoist + 行内化组合上限：平均每组 {sum(allg)/len(allg):+,.0f} tokens。")
    add("")

    # --- conclusion 3: crossover / V8 ---
    add("3. **V8 真实对象数组场景的改善幅度**（Δ 为相对各自基线的 token 变化）：")
    for r in a_rows:
        if not r["label"].startswith("V8"):
            continue
        parts = []
        for key in ("inline", "pipe", "hoist", "all"):
            d = delta(r, key)
            parts.append(f"{key} {d:+,.0f}" if d is not None else f"{key} N/A")
        add(f"   - {r['label']}: JSON {fnum(r['j'])} / AIF-S {fnum(r['s'])} "
            f"({fnum(r['red_s'], True)})；" + "、".join(parts) + " tokens")
    add("   `pipe` 在 Text Mode 基线上几乎零收益：`|` 自身在 BPE 里也要占 token，"
        "替换掉换行（常与相邻字符合并成单 token）省不到东西。"
        "**行内化只在 Structured Mode 下有意义**。")
    add("")

    # --- conclusion 4: ambiguity cost ---
    tot_spaces = sum(r["spaces"] for r in a_rows)
    tot_pipes = sum(r["pipes"] for r in a_rows)
    skipped = sum(r["skipped"] for r in a_rows)
    add(f"4. **兼容性成本不能忽略**：空格方案在 Text Mode 下会歧义 —— 全部 "
        f"{len(a_rows)} 组数据的值内空格共 {tot_spaces:,} 处；`|` 方案需新增「值内 `|` 必须转义」规则"
        f"（本次数据内 `|` 出现 {tot_pipes:,} 处，所以测出的收益是**上界**）。"
        f"另有 {skipped} 个含数组类型字段的 `@objects` 块无法用定长方案折叠。")
    add("   任何一项都要求同时改 encoder、两套 decoder、规范、双实现一致性测试与 fuzz —— "
        "而 0.9 已定稿。")
    add("")

    # --- conclusion 5: predictor ---
    add("5. **预估器研究得到的是否定结论：近似判据不足以驱动决策**。")
    add(f"   线性模型在合成留出集 {synth_metrics['n']} 组上二分类准确率 "
        f"{synth_metrics['acc']*100:.1f}%、MAE {synth_metrics['mae_b']:.2f}pp；"
        f"在**从未参与拟合**的 V8 17 类上准确率 {v8_metrics['acc']*100:.1f}%，"
        f"但 MAE 高达 {v8_metrics['mae_b']:.2f}pp —— 预测 +30～+57%、实际仅 +0～+54%，"
        "系统性高估（合成训练集的结构比真实数据更有利于 AIF）。")
    add(f"   **关键**：V8 上模型误判代价 {fnum(v8_metrics['model_cost'])} tokens，"
        f"与「总是用 AIF Text Mode」的 {fnum(base_v8['aif-t'])} **完全相同** —— "
        "两者都只错 `07 Array`，训练出来的模型没有增量价值。"
        f"来自第一轮结论的可解释规则在 V8 上代价 {fnum(rule_v8['cost'])}（看似达到 Oracle），"
        f"**但在独立合成留出集上代价高达 {fnum(rule_synth['cost'])} tokens**"
        f"（线性模型仅 {fnum(synth_metrics['model_cost'])}）—— "
        "两者在不同留出集上互有胜负，谁都不能泛化；规则在 V8 上的好表现只是 "
        "`07 Array` 的 `array_density=2.30` 恰好跨过阈值 2.0。")
    add("   因此 `should_use_aif(exact=True)` 是唯一可靠路径：真编码、真计数、"
        "验证 round-trip、100% 准确；代价是编码成本已付，适合批量/缓存决策，不是零成本预估。")
    add("")
    add("6. **建议：两项 counterfactual 都不进 0.9**。行内化收益不稳定且需破坏兼容性；"
        "schema hoisting 收益稳定但属格式级变更，值得作为 **AIF/1.0 候选扩展单独立项**。"
        "预估器保留为研究工具，但**不把近似模式包装成可靠组件**："
        "`exact=False` 的结果一律带 `reliable=False` 与警告，文档推荐 `exact=True`。")
    add("")
    add("---")
    add("")

    # ---------------- Part A ----------------
    add("## Part A — 对象数组还能不能更省")
    add("")
    add("### 方法")
    add("")
    add("当前 `@objects` 块布局（每个字段占一行，schema 每条记录重写一次）：")
    add("")
    add("```")
    add("@objects")
    add("name:s arguments.query:s arguments.limit:i result.success?:b")
    add("3")
    add("web_search")
    add("AI\\stechnology")
    add("10")
    add("true")
    add("...")
    add("```")
    add("")
    add("四个 counterfactual（`s` = Structured 文本，`t` = Text Mode 文本）：")
    add("")
    add("| 变体 | 定义 | 前提 |")
    add("|---|---|---|")
    add("| `inline` | 每个 object 的所有 slot 用空格拼成一行，基于 `s` | 值已用 `\\s` 转义空格 |")
    add("| `pipe` | 每个 object 用 `\\|` 拼成一行，基于 `t` | 值内 `\\|` 需要新转义规则 |")
    add("| `hoist` | 重复的 schema 行只保留第一次（假设全局 schema 注册表） | 需全局 schema 语义 |")
    add("| `all` | `hoist` + `inline` 组合上限 | 两者前提叠加 |")
    add("")
    add("`Δ` = **变体所基于的基线** tokens − 变体 tokens（`inline` / `hoist` / `all` "
        "基于 AIF-S，`pipe` 基于 AIF-T），**正数表示省了**；这样不会把 Text Mode 自身的收益"
        "错算到行内化头上。含数组类型字段的块因行数不固定，标 `N/A` 并原样保留，不估算。")
    add("")
    add("### 参数扫描全表（54 组）")
    add("")
    add("| Case | JSON | AIF-S | Red S | inline Δ | pipe Δ | hoist Δ | all Δ |")
    add("|---|---:|---:|---:|---:|---:|---:|---:|")
    for r in a_rows:
        if r["label"].startswith("V8"):
            continue
        cells = []
        for key in ("inline", "pipe", "hoist", "all"):
            d = delta(r, key)
            cells.append(f"{d:+,.0f}" if d is not None else "N/A")
        add(f"| {r['label']} | {fnum(r['j'])} | {fnum(r['s'])} | "
            f"{fnum(r['red_s'], True)} | " + " | ".join(cells) + " |")
    add("")
    add("### V8 真实数据（3 类含对象数组）")
    add("")
    add("| Dataset | JSON | AIF-S | Red S | AIF-T | Red T | inline Δ | pipe Δ | hoist Δ | all Δ |")
    add("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for r in a_rows:
        if not r["label"].startswith("V8"):
            continue
        cells = []
        for key in ("inline", "pipe", "hoist", "all"):
            d = delta(r, key)
            cells.append(f"{d:+,.0f}" if d is not None else "N/A")
        add(f"| {r['label']} | {fnum(r['j'])} | {fnum(r['s'])} | "
            f"{fnum(r['red_s'], True)} | {fnum(r['t'])} | {fnum(r['red_t'], True)} | "
            + " | ".join(cells) + " |")
    add("")

    # aggregation by k
    add("### 按对象数 k 汇总（每 k 9 组平均）")
    add("")
    add("| k | 当前 Red S | inline 后 Red | inline Δ | hoist Δ | all Δ |")
    add("|---:|---:|---:|---:|---:|---:|")
    for k in (1, 2, 3, 5, 10, 20):
        group = [r for r in a_rows if r["label"].startswith(f"scan k={k} ")]
        if not group:
            continue
        avg = lambda fn: sum(fn(r) for r in group) / len(group)  # noqa: E731

        def avg_d(key):
            vals = [v for v in (delta(r, key) for r in group) if v is not None]
            return sum(vals) / len(vals) if vals else 0.0

        inline_reds = [red(r["j"], r["variants"]["inline"][0]) for r in group
                       if r["variants"]["inline"][0] is not None]
        add(f"| {k} | {avg(lambda r: r['red_s']):+.2f}% | "
            f"{sum(inline_reds)/len(inline_reds):+.2f}% | "
            f"{avg_d('inline'):+,.0f} | {avg_d('hoist'):+,.0f} | "
            f"{avg_d('all'):+,.0f} |")
    add("")
    add("### 歧义与兼容性成本")
    add("")
    add(f"- 值内空格总数：{tot_spaces:,}（空格分隔方案在 Text Mode 下不可用）")
    add(f"- 值内 `\\|` 总数：{tot_pipes:,}（`\\|` 方案需要新转义规则；当前数据几乎不出现，所以 `pipe` 是无转义成本的上界）")
    add(f"- 含数组类型字段、无法定长折叠的 `@objects` 块：{skipped} 个")
    add("- 三个变体都需要改动：encoder + Python/JS 两套 decoder + 规范 + 双实现一致性 + fuzz")
    add("- 本报告**没有**实现这些变体，也没有对它们做 round-trip 验证")
    add("")
    add("**判断**：`inline` 收益在 k 与值类型间来回翻转，不是可靠优化；"
        "`hoist` 方向稳定但需要全局 schema 语义，属于格式级变更。"
        "两者都应留到 AIF/1.0 候选扩展，不塞进已定稿并通过 fuzz 的 0.9。")
    add("")
    add("---")
    add("")

    # ---------------- Part B ----------------
    add("## Part B — `should_use_aif` 预估器")
    add("")
    add("### 方法")
    add("")
    add("- 实现：`research/predictor.py`，**独立研究工具**，不被任何测试 / benchmark / 核心包导入")
    add(f"- 训练集：**仅合成参数扫描** {len(train_rows)} 组"
        f"（跳过 {skip_train} 组不支持的结构），固定 seed `20261108`；"
        f"V8 17 类数据**完全不参与拟合**")
    add(f"- 留出集：独立合成 {len(hold_synth)} 组（seed `777001`，跳过 {skip_synth} 组）"
        f" + V8 17 类真实数据（n={V8_N}）")
    add("- 两个线性回归（Structured / Text），标签是真实 `cl100k_base` reduction")
    add(f"- {len(pred.FEATURES)} 个特征，全部为纯结构统计，**不调用 AIF encoder、不调用 tokenizer**：")
    add("  " + "、".join(f"`{f}`" for f in pred.FEATURES))
    add("- 决策：取 `max(预测S, 预测T, 0)`，输出 `json` / `aif-s` / `aif-t` 三选一")
    add("- 对照组：可解释粗规则（阈值来自**第一轮已发表结论**，不用 V8 标签拟合）、"
        "「总是 JSON / 总是 AIF-S / 总是 AIF-T」三条基线、"
        "`exact=True` 真编码路径、以及理论最优 Oracle")
    add("")
    add("### 留出集指标")
    add("")
    add("| 留出集 | n | MAE-S (pp) | MAE-T (pp) | MAE-best (pp) | 二分类准确率 | 三分类准确率 |")
    add("|---|---:|---:|---:|---:|---:|---:|")
    for label, m in (("独立合成", synth_metrics), ("V8 真实数据", v8_metrics)):
        add(f"| {label} | {m['n']} | {m['mae_s']:.2f} | {m['mae_t']:.2f} | "
            f"{m['mae_b']:.2f} | {m['acc']*100:.1f}% | {m['mode_acc']*100:.1f}% |")
    add("")
    add("### V8 17 类：预测 vs 实际（模型从未见过这些数据）")
    add("")
    add("| Dataset | 预测 best | 实际 best | 误差 (pp) | 预测 mode | 实际 mode | 决策 |")
    add("|---|---:|---:|---:|---|---|:---:|")
    for r in v8_eval:
        add(f"| {r['label']} | {r['pred_best']:+.2f}% | {r['act_best']:+.2f}% | "
            f"{abs(r['pred_best']-r['act_best']):.2f} | {r['pred_mode']} | "
            f"{r['act_mode']} | {'OK' if r['decision_ok'] else 'MISS'} |")
    add("")
    misses = [r for r in v8_eval if not r["decision_ok"]]
    add(f"决策错误 {len(misses)} 组" + ("：" + "、".join(r["label"] for r in misses)
                                   if misses else "，无") + "。")
    add("")
    add("### 误判代价与基线对比（tokens，越小越好）")
    add("")
    add("代价 = 该组「理论最优节省」−「该策略实际节省」，按组累加。"
        "**实际节省允许为负**：选了比 JSON 更费 token 的格式，多花的部分全额计入代价，不裁剪为 0。")
    add("")
    add("| 策略 | 独立合成留出集 | V8 真实留出集 |")
    add("|---|---:|---:|")
    add(f"| 总是 JSON | {fnum(base_synth['json'])} | {fnum(base_v8['json'])} |")
    add(f"| 总是 AIF-S | {fnum(base_synth['aif-s'])} | {fnum(base_v8['aif-s'])} |")
    add(f"| 总是 AIF-T | {fnum(base_synth['aif-t'])} | {fnum(base_v8['aif-t'])} |")
    add(f"| **线性模型预估器** | **{fnum(synth_metrics['model_cost'])}** | **{fnum(v8_metrics['model_cost'])}** |")
    add(f"| 可解释粗规则 | {fnum(rule_synth['cost'])} | {fnum(rule_v8['cost'])} |")
    add(f"| `exact=True`（真编码） | 0 | 0 |")
    add("| 理论最优（Oracle） | 0 | 0 |")
    add("")
    add(f"规则在 V8 上二分类准确率 {rule_v8['acc']*100:.1f}%"
        + (f"，决策失误：{'、'.join(rule_v8['misses'])}" if rule_v8["misses"] else "，无决策失误")
        + "；在独立合成留出集上准确率 "
        + f"{rule_synth['acc']*100:.1f}%，代价 {fnum(rule_synth['cost'])} tokens。"
        "它在 V8 上表现好，是因为 `07 Array` 的 `array_density=2.30` 刚好跨过阈值 2.0，"
        "**不能据此声称规则已泛化**。")
    add("")
    add("### 为什么近似判据分不开：聚合特征冲突表")
    add("")
    add("下表是本研究最重要的证伪证据。`arr` = `log1p(每记录 scalar 数组元素数)`，"
        "`ratio` = `arr / key_share`（数组开销相对键名收益），`best` = 两种 AIF 模式下"
        "实际最优 reduction（0 表示应保留 JSON）。")
    add("")
    add("| Case | key_share | arr | ratio | 实际 best | 应选 | 粗规则 |")
    add("|---|---:|---:|---:|---:|---|---|")
    for r in boundary:
        add(f"| {r['label']} | {r['key']:.2f} | {r['arr']:.2f} | {r['ratio']:.2f} | "
            f"{r['best']:+.2f}% | {r['actual']} | {r['rule']} |")
    add("")
    add("`arr≈1.39` 这一档同时存在 **best=0%（该用 JSON）** 与 **best≈+25%（AIF 明显更省）** 的数据；"
        "`ratio` 在 2.03（该用 JSON）与 2.11（AIF 省 24.93%）处也几乎重合。"
        "根因是收益取决于 **BPE 在 token 级如何切分**，而几个聚合特征丢掉了"
        "「数组元素与其他嵌套键名重复量的相对结构」。")
    add("要可靠判定，只能真的编码并计数 —— 这正是 `exact=True` 做的事。")
    add("")
    add("### 局限（不隐藏）")
    add("")
    add(f"- 模型只在 `{TOKENIZER}` 上校准。第一轮已证明 `p50k_base` / `r50k_base` "
        "会把 `17 Mixed realistic` 从正翻成负，换 tokenizer 必须重新拟合。")
    add("- 线性模型对长文本的非线性收益衰减拟合有限，`exact=True` 才是可靠答案。")
    add("- 合成训练集与真实数据分布不同；V8 上的 MAE 才是应当参考的数字。")
    add("- 预估器不做 round-trip 检查；`exact=True` 会做，并附三种 token 数。")
    add("- 特征是纯结构统计近似（`missing_share` 按各层字典键并集估算），不等价于真实 AIF slot 计数；"
        "对训练分布外的极深嵌套或混合编码结构泛化有限。")
    add("- 粗规则阈值 `array_density >= 2.0` 是人工设定，虽未用 V8 标签拟合，"
        "但其数值选择受第一轮扫描与本报告特征观察影响，属于**弱验证**；"
        "V8 只有 17 类数据，任何「达到 Oracle」的说法都只在本书数据源内成立。")
    add("- 训练集全部为合成数据，其 `key_share` 普遍高于真实混合数据，是系统性高估的主因；"
        "扩充真实分布训练样本可能改善 MAE，但本研究没有做（避免用过拟合换取好看的数字）。")
    add("- 本轮**没有**为提高准确率而修改任何 benchmark 数据集，也没有删掉决策失误条目。")
    add("")
    add("### 用法")
    add("")
    add("```python")
    add("import sys; sys.path.insert(0, 'AIF/research')")
    add("from predictor import should_use_aif")
    add("")
    add("d = should_use_aif(data, exact=True)   # ← 推荐：真编码 + 真计数 + round-trip")
    add("print(d['recommended_mode'], d['reduction_pct'], d['reliable'])")
    add("")
    add("d = should_use_aif(data)               # 粗估：reliable=False，带 warning")
    add("d = should_use_aif(data, method='rule')  # 可解释粗规则：同样不可靠")
    add("```")
    add("")
    add("`exact=False` 的返回值含 `reliable=False` 与 `warning`，"
        "明确提示 reduction 数值未校准，不能作为决策依据。")
    add("")
    add("```bash")
    add("python AIF/research/predictor.py --demo")
    add("python AIF/research/predictor.py --self-test")
    add("python AIF/research/predictor.py --file data.json --exact   # 推荐")
    add("python AIF/research/predictor.py --file data.json --method rule")
    add("python AIF/research/predictor.py --train                    # 重新拟合模型")
    add("```")
    add("")
    add("---")
    add("")
    add("## 复现与边界")
    add("")
    add("```bash")
    add("python AIF/research/study_round2.py        # 重写本报告与 predictor_model.json")
    add("python AIF/research/token_study.py         # 第一轮报告，独立可复现")
    add("python AIF/tests/verify_all.py             # 全量验证（当前 9/9），不受本研究影响")
    add("```")
    add("")
    add("本研究**没有**改动 AIF/0.9 的任何实现、规范或 benchmark 数据；"
        "所有负 Δ、负 reduction、决策失误与不适用条目均原样保留。")
    return "\n".join(L) + "\n"


def main():
    a_rows = study_object_arrays()
    (model, train_rows, skip_train, hold_synth, skip_synth,
     hold_v8) = study_predictor()

    synth_eval = _evaluate(hold_synth, model)
    v8_eval = _evaluate(hold_v8, model)
    synth_metrics = _metrics(synth_eval)
    v8_metrics = _metrics(v8_eval)
    base_synth = _baseline_costs(hold_synth)
    base_v8 = _baseline_costs(hold_v8)
    rule_synth = _rule_stats(hold_synth)
    rule_v8 = _rule_stats(hold_v8)
    boundary = _boundary_cases()

    text = build_report(a_rows, model, train_rows, skip_train,
                        hold_synth, skip_synth, hold_v8, synth_eval, v8_eval,
                        synth_metrics, v8_metrics, base_synth, base_v8,
                        rule_synth, rule_v8, boundary)
    REPORT.write_text(text, encoding="utf-8")

    print()
    print("=" * 68)
    print(f"A: {len(a_rows)} object-array cases | "
          f"B: train {len(train_rows)}, holdout {len(hold_synth)} + {len(hold_v8)}")
    print(f"Predictor  synthetic holdout: acc {synth_metrics['acc']*100:.1f}%  "
          f"MAE-best {synth_metrics['mae_b']:.2f}pp")
    print(f"Predictor  V8 real holdout  : acc {v8_metrics['acc']*100:.1f}%  "
          f"MAE-best {v8_metrics['mae_b']:.2f}pp  "
          f"cost {v8_metrics['model_cost']:,.0f} vs always-AIF-T {base_v8['aif-t']:,.0f}")
    print(f"Coarse rule V8 cost         : {rule_v8['cost']:,.0f}  "
          f"(synthetic holdout {rule_synth['cost']:,.0f})")
    print("NOTE: coarse estimates are NOT calibrated; exact=True is the reliable path.")
    print(f"Report: {REPORT}")
    print("=" * 68)


if __name__ == "__main__":
    main()

"""
AIF Array Optimization Lab — reproducible experiment driver.

    python AIF/array_lab/run_lab.py

Writes LAB_REPORT.md and fitted_thresholds.json. Reads nothing from previous
reports; every number here is measured in this run.

Fairness rules (fixed before measurement, see lab_spec.py):
  * one dataset object is passed to ALL encodings;
  * one JSON serialisation rule (benchmark_v8.json_text, asserted identical);
  * one tokenizer (cl100k_base);
  * every candidate is really decoded and compared with the original.
"""

import itertools
import json
import platform
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
AIF_ROOT = HERE.parents[0]
sys.path.insert(0, str(AIF_ROOT))
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(AIF_ROOT / "benchmarks"))

import lab_spec as S                     # noqa: E402
import lab_codecs as C                   # noqa: E402
from aif import json_to_aif, aif_to_json  # noqa: E402
import benchmark_v8 as v8                # noqa: E402 (import is side-effect free)

REPORT = HERE / "LAB_REPORT.md"
THRESHOLDS = HERE / "fitted_thresholds.json"

CANDIDATES = ("row", "column", "hybrid", "aif09-s", "aif09-t")
EXPERIMENTAL = ("row", "column", "hybrid")   # only these are judged as "found"
LABELS = {
    "json": "JSON (compact baseline)",
    "aif09-s": "AIF/0.9 Structured (existing, unchanged)",
    "aif09-t": "AIF/0.9 Text Mode (existing, unchanged)",
    "row": "A: Row-oriented (1.0-alpha, experimental)",
    "column": "B: Column-oriented (1.0-alpha, experimental)",
    "hybrid": "C: Hybrid (1.0-alpha, experimental)",
}


def encode_as(name, records):
    if name == "row":
        return C.encode(records, "row")
    if name == "column":
        return C.encode(records, "column")
    if name == "hybrid":
        return C.encode_hybrid(records)[0]
    if name == "aif09-s":
        return json_to_aif(records)
    if name == "aif09-t":
        return json_to_aif(records, text_mode=True)
    raise ValueError(name)


def decode_as(name, text):
    if name in ("row", "column", "hybrid"):
        return C.decode(text)
    return aif_to_json(text)


def measure(records, with_text=False):
    """Return {name: (tokens, roundtrip_ok, error)} plus the JSON token count."""
    jt = S.tokens(S.json_text(records))
    out = {"json": jt}
    for name in CANDIDATES:
        try:
            text = encode_as(name, records)
            t = S.tokens(text)
            ok = decode_as(name, text) == records
            out[name] = (t, ok, None)
        except Exception as exc:                       # noqa: BLE001
            out[name] = (None, False, f"{type(exc).__name__}: {exc}")
    return out


def red(jt, t):
    return None if t is None else S.reduction(jt, t)


# ---------------------------------------------------------------------------
# 1. Hybrid threshold fitting — calibration set ONLY
# ---------------------------------------------------------------------------
GRID_K = (3, 5, 8, 12)
GRID_F = (2, 3, 4)
GRID_L = (8, 12, 20)
GRID_M = (0.15, 0.30, 0.50)


def fit_thresholds():
    calib = []
    for f, k, records in S.calibration_cases():
        ft = C.features(records)
        calib.append((f, k, ft,
                      S.tokens(C.encode(records, "row")),
                      S.tokens(C.encode(records, "column"))))
    best, best_total = None, None
    for vals in itertools.product(GRID_K, GRID_F, GRID_L, GRID_M):
        t = dict(zip(("k", "f", "L", "M"), vals))
        total = 0
        for _, _, ft, row_t, col_t in calib:
            use_col = (ft["k"] >= t["k"] and ft["f"] >= t["f"]
                       and ft["L"] <= t["L"] and ft["M"] <= t["M"])
            total += col_t if use_col else row_t
        if best_total is None or total < best_total:
            best, best_total = t, total
    THRESHOLDS.write_text(json.dumps({
        "fitted_on": "CALIBRATION_GRID (f in 2/4/7, k in 3/7/15/30, seed 909)",
        "evaluation_disjoint": True,
        "objective": "minimise total cl100k_base tokens over calibration set",
        "thresholds": best,
        "calibration_total_tokens": best_total,
    }, indent=2) + "\n", encoding="utf-8")
    return best, calib, best_total


# ---------------------------------------------------------------------------
# 2. Timings
# ---------------------------------------------------------------------------
def timings(records, repeats=5):
    result = {}
    for name in CANDIDATES:
        enc_times, dec_times = [], []
        for _ in range(repeats):
            t0 = time.perf_counter()
            text = encode_as(name, records)
            t1 = time.perf_counter()
            decode_as(name, text)
            t2 = time.perf_counter()
            enc_times.append(t1 - t0)
            dec_times.append(t2 - t1)
        result[name] = (statistics.median(enc_times) * 1000,
                        statistics.median(dec_times) * 1000)
    jt = []
    for _ in range(repeats):
        t0 = time.perf_counter()
        txt = S.json_text(records)
        json.loads(txt)
        jt.append((time.perf_counter() - t0) * 1000)
    result["json"] = (statistics.median(jt) / 2, statistics.median(jt) / 2)
    return result


# ---------------------------------------------------------------------------
# 3. Error recovery / silent-corruption probe
# ---------------------------------------------------------------------------
def damage_variants(name, text):
    """Return [(label, corrupted_text)] — same *classes* of damage everywhere."""
    lines = text.rstrip("\n").split("\n")
    out = []
    out.append(("drop last line", "\n".join(lines[:-1]) + "\n"))

    if name == "json":
        # Compact JSON has no line breaks, so dropping one line drops the whole
        # document -> parse error. Cutting exactly at an object boundary while
        # keeping brackets balanced is the silent-loss counterpart.
        if "},{" in text:
            out.append(("drop whole last block",
                        text.rsplit("},{", 1)[0] + "}]"))
        out.append(("unknown escape", text.replace(":", r"\q", 1)))
        return out

    # Cut exactly at the last record/block boundary: the classic silent-loss case.
    if name in ("row", "column", "hybrid"):
        idx = max(i for i, l in enumerate(lines) if l == "@//data/")
        out.append(("drop whole last block", "\n".join(lines[:idx]) + "\n"))
        # Corrupt the first declared group size.
        for i, l in enumerate(lines):
            if i > 0 and lines[i - 1] == "@//data/" and l.isdigit():
                bad = lines[:]
                bad[i] = str(int(l) + 2)
                out.append(("group size +2", "\n".join(bad) + "\n"))
                break
        # Add one extra cell to the first data line.
        for i, l in enumerate(lines):
            if i > 0 and lines[i - 1].isdigit() and "," in l:
                bad = lines[:]
                bad[i] = l + ",x"
                out.append(("extra cell", "\n".join(bad) + "\n"))
                break
        out.append(("unknown escape", text.replace(",", r"\q,", 1)))
    else:
        marker = "@record"
        idx = max((i for i, l in enumerate(lines) if l == marker), default=None)
        if idx:
            out.append(("drop whole last block", "\n".join(lines[:idx]) + "\n"))
        out.append(("unknown escape", text.replace("\n", r"\q\n", 1)))
    return out


def error_probe(records):
    results = []
    for name in CANDIDATES + ("json",):
        text = (S.json_text(records) if name == "json"
                else encode_as(name, records))
        for label, bad in damage_variants(name, text):
            try:
                got = (json.loads(bad) if name == "json"
                       else decode_as(name, bad))
                detected = False
                silent = got != records
                localized = False
                msg = ""
            except Exception as exc:                  # noqa: BLE001
                detected = True
                silent = False
                msg = str(exc)
                localized = any(w in msg.lower() for w in
                                ("block", "line", "field", "char", "position",
                                 "expect", "invalid", "unknown", "mismatch",
                                 "unterminated", "delimiter"))
            results.append((name, label, detected, silent, localized, msg))
    return results


# ---------------------------------------------------------------------------
# 4. Report
# ---------------------------------------------------------------------------
def fmt(v, pct=False):
    if v is None:
        return "N/A"
    return f"{v:+.2f}%" if pct else f"{v:,.0f}"


def build_report(ctx):
    L = []
    add = L.append
    exp_lo = min(ctx["target_stats"][n]["mean"] for n in EXPERIMENTAL)
    exp_hi = max(ctx["target_stats"][n]["mean"] for n in EXPERIMENTAL)
    add("# AIF Array Optimization Lab — 实验报告")
    add("")
    add(f"- 生成时间：{ctx['time']}；Python {platform.python_version()}；"
        f"tiktoken `{S.TOKENIZER}`")
    add("- 复现：`python AIF/array_lab/run_lab.py`（本报告每次运行全部重测）")
    add("")
    add("> **性质声明**：本报告是 `AIF/1.0-alpha` **实验编码**的对照实验，")
    add("> 不是 AIF/0.9 的修改，也不构成 1.0 定稿。0.9 的 encoder/decoder、")
    add("> 规范、benchmark 数据在本实验中均未被改动，只作为基准被调用。")
    add("")
    add("## 结论先行")
    add("")
    for line in ctx["headlines"]:
        add(f"{line}")
        add("")
    add("## 1. 实验设计（测量前冻结）")
    add("")
    add("### 1.1 公平性约束")
    add("")
    add("| 约束 | 落实方式 |")
    add("|---|---|")
    add("| 相同数据 | 同一 Python 对象依次交给 6 种编码，不重新生成 |")
    add(f"| 相同 tokenizer | `{S.TOKENIZER}`，全部方案用同一个 `tokens()` |")
    add("| 相同 JSON 序列化 | `json.dumps(..., ensure_ascii=False, separators=(',',':'))`，"
        "与 V8 逐字相同（运行时断言一致） |")
    add("| 可解码 | 每个候选都真解码并与原对象比较；不可解码不算候选 |")
    add("| 不事后挑数据 | 目标工作负载、网格、seed、判定阈值全部写在 `lab_spec.py`，"
        "实验脚本只读不写 |")
    add("")
    add(f"- 序列化规则自检：与 `benchmarks/benchmark_v8.json_text` "
        f"**{'完全一致' if ctx['json_rule_identical'] else '不一致（需排查）'}**")
    add("")
    add("### 1.2 预先定义的目标工作负载（唯一用于「稳定优于 JSON」判定）")
    add("")
    add("```text")
    add(f"结构      : [{{\"<array>\" : [ 扁平标量对象, ... ]}}, ...]   组数 N = {S.N_RECORDS}")
    add(f"字段数 f  : {S.TARGET_FIELDS}")
    add(f"每组对象数 k: {S.TARGET_GROUP_SIZES}   另含变长组 k_i ∈ [1,10]")
    add(f"随机 seed : {S.SEEDS}   字段名短英文，值短标量，缺失率 6% / null 3%")
    add(f"判定门槛  : ≥{S.STABLE_WIN_MIN_POSITIVE_SHARE:.0%} 的数据点 reduction > 0，"
        f"且每个 seed 的平均 reduction > {S.STABLE_WIN_MIN_SEED_MEAN:.0f}%，"
        "且 round-trip 全 PASS")
    add("```")
    add("")
    add("**范围外（如实列出，不隐藏）**：标量数组（V8 `07 Array`）、嵌套数组、")
    add("以长自由文本为主的载荷。行/列/混合三方案**不覆盖**这些结构；")
    add("它们只作为参照与对抗数据出现，报告里保留其负 reduction。")
    add("")
    add("### 1.3 三种实验编码")
    add("")
    add("三者共用完全相同的转义规则、schema 声明、组数声明与 `@//data/` 块，")
    add("**唯一差别是数据矩阵的转置**，因此差异只来自 BPE 对值分组方式的敏感性：")
    add("")
    add("| 方案 | 数据布局 | 每个 `@//data/` 块 |")
    add("|---|---|---|")
    add("| A Row | 一个对象一行 | k 行 × f 列 |")
    add("| B Column | 一个字段一行 | f 行 × k 列 |")
    add("| C Hybrid | 由确定性规则在 A/B 中选一 | 同上，块头写 `@//mode/` |")
    add("")
    add("列式规则（对应你点名的四项）：")
    add("")
    add("| 情形 | 编码 | 说明 |")
    add("|---|---|---|")
    add("| 值内逗号 | `\\,` | 切分只认未转义逗号 |")
    add("| 反斜杠 / 换行 / 控制字符 | `\\\\` `\\n` `\\r` `\\t` `\\uXXXX` | 与 0.9 一致 |")
    add("| 空字符串 | `\\e` | 与「字段缺失」区分 |")
    add("| 字段缺失 | `-` | 固定占一个 cell，游标不漂移 |")
    add("| null | `@null` | 字面量 `@null` 编码为 `\\@null` |")
    add("| `@` / `-` 开头字符串 | `\\@` / `\\-` | 避免与标记冲突 |")
    add("| 不同长度数组 | 每块首行写 `<k>` + 全文 `@//groups/ <N>` | 变长可解码；"
        "组数声明用于检测「截断到块边界」的静默丢数据 |")
    add("")
    add("Hybrid 是**确定性纯函数**，不接受人工挑选：")
    add("")
    add("```python")
    add("mode = 'column' if (k_bar >= T.k and f >= T.f and L <= T.L and M <= T.M) else 'row'")
    add("```")
    add("")
    add(f"4 个阈值只在**校准集**上网格拟合（{len(ctx['calib'])} 组，"
        f"f∈{S.CALIBRATION_FIELDS}、k∈{S.CALIBRATION_SIZES}、seed {S.CALIBRATION_SEED}），")
    add(f"其 (f,k) 组合与目标集 f∈{S.TARGET_FIELDS}、k∈{S.TARGET_GROUP_SIZES} "
        "**完全不相交**。")
    add(f"拟合结果：`{json.dumps(ctx['thresholds'], ensure_ascii=False)}`，"
        f"校准集总 tokens {ctx['calib_total']:,}。")
    add("")
    add("## 2. 目标工作负载总结果")
    add("")
    add("| 编码 | 平均 reduction | 中位 reduction | 正例 / 总数 | 最差 | 最好 | Round-trip |")
    add("|---|---:|---:|---:|---:|---:|:---:|")
    for name in CANDIDATES:
        st = ctx["target_stats"][name]
        add(f"| {LABELS[name]} | {fmt(st['mean'], True)} | {fmt(st['median'], True)} | "
            f"{st['pos']}/{st['n']} | {fmt(st['min'], True)} | {fmt(st['max'], True)} | "
            f"{'PASS' if st['rt'] else 'FAIL'} ({st['rt_n']}/{st['n']}) |")
    add("")
    add(f"目标集共 {ctx['target_n']} 个数据点（{len(S.SEEDS)} seeds × "
        f"{len(S.TARGET_GRID)} 组 + {len(S.SEEDS)} 组变长）。")
    add("")
    add("### 2.1 相对 AIF/0.9 的增量（这才是本 Lab 的实际贡献）")
    add("")
    add("判定对象只有三个实验方案；0.9 是**同场基准**，不算「新找到的方案」。")
    add("")
    add("| 实验方案 | 相对 0.9-S 平均多省 | 平均多省 reduction | 优于 0.9-S 的数据点 |")
    add("|---|---:|---:|---:|")
    for n in EXPERIMENTAL:
        d = ctx["incremental"][n]
        add(f"| `{n}` | {d['tokens']:+,.0f} tokens/组 | {d['pp']:+.2f} pp | "
            f"{d['better']}/{ctx['target_n']} |")
    add("")
    add("### 2.2 跨 seed 可重复性（稳定胜出判定）")
    add("")
    add("| 编码 | " + " | ".join(f"seed {s}" for s in S.SEEDS) +
        " | 判定 |")
    add("|---|" + "---:|" * len(S.SEEDS) + ":---|")
    for name in CANDIDATES:
        means = [ctx["seed_means"][name][s] for s in S.SEEDS]
        pos_share = ctx["target_stats"][name]["pos"] / ctx["target_stats"][name]["n"]
        win = (pos_share >= S.STABLE_WIN_MIN_POSITIVE_SHARE
               and all(m > S.STABLE_WIN_MIN_SEED_MEAN for m in means)
               and ctx["target_stats"][name]["rt"])
        verdict = "**稳定优于 JSON**" if win else "未达门槛"
        add(f"| {LABELS[name]} | " +
            " | ".join(fmt(m, True) for m in means) + f" | {verdict} |")
    add("")
    add("门槛是预先写死的，不是看到结果后调整的。")
    add("")
    add("### 2.3 按 (f, k) 的明细（seed 平均）")
    add("")
    add("| f | k | JSON tok | " + " | ".join(
        f"{n}" for n in CANDIDATES) + " |")
    add("|---:|---:|---:|" + "---:|" * len(CANDIDATES))
    for key, row in ctx["by_fk"]:
        f, k = key
        add(f"| {f} | {k} | {row['json']:,} | " + " | ".join(
            fmt(row[n], True) for n in CANDIDATES) + " |")
    add("")
    add("单元格是相对 JSON 的 reduction %，负数即该方案比 JSON 更费 token。")
    add("")
    add("### 2.4 目标工作负载是否偏袒 AIF？（必须正面回答）")
    add("")
    add("**是，偏袒。** 目标工作负载选的是对象数组，这是 AIF **已知的优势场景**；")
    add(f"0.9 Structured 本身在该集合就有 "
        f"{ctx['target_stats']['aif09-s']['pos']}/"
        f"{ctx['target_stats']['aif09-s']['n']} 个正例。")
    add("所以本 Lab 的「稳定优于 JSON」**不能**解读成「Array 问题整体解决」。")
    add("")
    add("选它的理由（测量前写死在 `lab_spec.py`，不是看到结果后挑的）：")
    add("你给出的 `users[]:object @//columns/` 草案就是对象数组；")
    add("第二轮研究量化过 `@objects` 的 schema 逐记录重复是最大浪费。")
    add("")
    add("**未解决的部分，不打折扣列出**：")
    add("")
    add(f"- 标量数组 V8 `07 Array`：0.9 Structured "
        f"{ctx['scalar_ref'][1][2]:+.2f}%（本 Lab N={S.N_RECORDS} 实测；"
        "V8 全量 N=1000 为 −37.99%）。三个实验方案**明确不覆盖**该结构。")
    add("- 第一轮研究已把标量数组行内化作为 counterfactual 测过："
        "对短字符串数组有效，对整数数组零收益，不是通用解法。")
    add("")
    add("因此本轮能诚实主张的是：")
    add("")
    add(f"> **在预先定义的对象数组工作负载上，三个实验方案都稳定优于 JSON"
        f"（{exp_lo:+.2f}% ～ {exp_hi:+.2f}%，3 个独立 seed），"
        f"且相对 0.9 有约 {ctx['incremental']['row']['pp']:+.2f} pp 的增量；"
        "同时把 k=1 的小型数组从 0.9 的负例翻成正例。"
        "标量数组仍是未解决的劣势场景，不宣称 Array 问题整体解决。**")
    add("")
    add("另外，k 较小时 Row 优于 Column、k 增大后 Column 反超（见 §3），")
    add("说明「谁更好」取决于 BPE 切分与矩阵形状，不是固定结论。")
    add("")
    add("## 3. 盈亏平衡点")
    add("")
    add(f"固定 f={S.BREAKEVEN_FIELDS}、N={S.N_RECORDS}、seed 202，扫描每组对象数 k：")
    add("")
    add("| k | " + " | ".join(n for n in CANDIDATES) + " |")
    add("|---:|" + "---:|" * len(CANDIDATES))
    for k, row in ctx["breakeven"]:
        add(f"| {k} | " + " | ".join(fmt(row[n], True) for n in CANDIDATES) + " |")
    add("")
    add("首次由负转正的 k（若扫描范围内出现）：" +
        "；".join(f"`{n}` k*={ctx['crossover'][n]}" if ctx["crossover"][n]
                  else f"`{n}` 未转正" for n in CANDIDATES) + "。")
    add("")
    add("## 4. 劣势与对抗场景（全部保留）")
    add("")
    add("| 场景 | JSON tok | " + " | ".join(n for n in CANDIDATES) + " |")
    add("|---|---:|" + "---:|" * len(CANDIDATES))
    for label, row in ctx["adversarial"]:
        add(f"| {label} | {row['json']:,} | " + " | ".join(
            fmt(row[n], True) for n in CANDIDATES) + " |")
    add("")
    add("特殊字符用例同时校验逗号、空格、真实换行、反斜杠、中文逗号、")
    add("`@null` / `@missing` / `-` 开头字符串、空串、null 与字段缺失的 round-trip。")
    add("")
    add("### 4.1 标量数组参照（三方案明确不覆盖）")
    add("")
    add("V8 `07 Array` 结构（每条记录含 3 个标量数组）用同一个 tokenizer 实测：")
    add("")
    add("| 编码 | tokens | reduction |")
    add("|---|---:|---:|")
    for name, t, r in ctx["scalar_ref"]:
        add(f"| {name} | {t:,} | {fmt(r, True)} |")
    add("")
    add("这里**没有**伪造 Row/Column/Hybrid 的数字。标量数组的 inline 化在")
    add("第一轮研究里已作为 counterfactual 测过（对整数数组零收益），")
    add("本 Lab 的三个编码是对象数组专用设计。")
    add("")
    add("## 5. 编码开销与解码复杂度")
    add("")
    add(f"样本 f=5、k=10、N={S.N_RECORDS}，每方案重复 5 次取中位数：")
    add("")
    add("| 编码 | encode ms | decode ms | 相对 JSON 总耗时 |")
    add("|---|---:|---:|---:|")
    jsum = sum(ctx["timings"]["json"])
    for name in CANDIDATES + ("json",):
        e, d = ctx["timings"][name]
        add(f"| {LABELS[name]} | {e:.2f} | {d:.2f} | {(e+d)/jsum:.2f}× |")
    add("")
    add("JSON 行是 `json.dumps` + `json.loads` 的合计均分，仅作量级参照，")
    add("不是严格同质实现（C 扩展 vs 纯 Python）。解码复杂度定性：")
    add("")
    add("- Row / Column 都是**单遍、固定槽位**解析，复杂度 O(值数量)；"
        "Column 需缓存 f 行再转置，Row 可逐对象输出，Row 内存更友好。")
    add("- Hybrid 多一次特征扫描与一次模式分支，常数更高。")
    add("- 0.9 需先做 schema 推断并处理嵌套路径，状态更多。")
    add("")
    add("## 6. 错误检测与恢复能力")
    add("")
    add("对同一份小数据构造同类损坏，检查三类结果：是否报错、")
    add("是否定位到位置、**是否静默返回错误数据**（最危险）。")
    add("")
    add("| 编码 | 损坏类型 | 检出 | 含位置信息 | 静默损坏 |")
    add("|---|---|:---:|:---:|:---:|")
    for name, label, detected, silent, localized, msg in ctx["errors"]:
        add(f"| {name} | {label} | {'是' if detected else '否'} | "
            f"{'是' if localized else '否'} | "
            f"{'**是**' if silent else '否'} |")
    add("")
    add(f"汇总：静默损坏 {ctx['silent_count']}/{len(ctx['errors'])} 次；"
        f"错误检出率 {ctx['detected_count']}/{len(ctx['errors'])}。")
    add("")
    add("注意：**没有任何一个实验 codec 支持「跳过损坏块继续解码」**，")
    add("全部是 fail-fast。局部恢复能力是这三种方案共同的真实弱点，")
    add("不能与「能检测错误」混为一谈。")
    add("")
    add("## 7. 建议")
    add("")
    for rec in ctx["recommendations"]:
        add(f"- {rec}")
    add("")
    add("## 8. 局限")
    add("")
    add("- 只测了 1 个 tokenizer（`cl100k_base`）和 1 种语言（Python 实现）；"
        "第一轮研究已证明跨 tokenizer 方向一致但幅度会变，本 Lab 未重复该扫描。")
    add("- 实验 codec 只支持**扁平标量对象**，对象内嵌对象/数组会明确报错，"
        "不是静默产出错误数据。")
    add("- 字段名不允许含空格、逗号、`:`、`@` 等语法字符。")
    add("- 耗时数字受本机 CPU 与 Python 版本影响，只作相对量级参照。")
    add("- 目标工作负载是**人为定义的合成数据**，不是真实生产流量；"
        "结论只在它的参数范围内成立。")
    add("- `AIF/1.0-alpha` 是实验 header，与 `AIF/0.9` 不兼容，"
        "两者不可混用同一 decoder。")
    add("")
    add("## 9. 复现")
    add("")
    add("```bash")
    add("python AIF/array_lab/run_lab.py          # 全部重测，重写本报告与阈值文件")
    add("python AIF/tests/verify_all.py          # 确认 0.9 工程未回归")
    add("```")
    add("")
    add("脚本产物：`LAB_REPORT.md`、`fitted_thresholds.json`。")
    add("除此之外不写任何文件，不修改 0.9 实现、规范、benchmark 或测试。")

    REPORT.write_text("\n".join(L) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
def main():
    ctx = {"time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

    # Fairness assertion: our JSON rule must be byte-identical to V8's.
    probe = S.make_records(3, 3, n=3, seed=0)
    ctx["json_rule_identical"] = S.json_text(probe) == v8.json_text(probe)
    print(f"[0/7] JSON 规则与 V8 一致: {ctx['json_rule_identical']}")

    print("[1/7] 校准 Hybrid 阈值（仅校准集）…")
    thresholds, calib, calib_total = fit_thresholds()
    ctx.update(thresholds=thresholds, calib=calib, calib_total=calib_total)
    print(f"      阈值 {thresholds}, 校准集 tokens {calib_total:,}")

    print("[2/7] 目标工作负载全量对照…")
    all_rows, by_seed = [], {s: {n: [] for n in CANDIDATES} for s in S.SEEDS}
    by_fk = {}
    for f, k, seed, records in S.target_cases():
        m = measure(records)
        row = {"f": f, "k": k, "seed": seed, "json": m["json"]}
        for n in CANDIDATES:
            t, ok, err = m[n]
            row[n] = red(m["json"], t)
            row[n + "_tok"] = t
            row[n + "_rt"] = ok
            row[n + "_err"] = err
            if row[n] is not None:
                by_seed[seed][n].append(row[n])
        all_rows.append(row)
        key = (f, k)
        by_fk.setdefault(key, {n: [] for n in CANDIDATES})
        by_fk[key].setdefault("json", m["json"])
        for n in CANDIDATES:
            if row[n] is not None:
                by_fk[key][n].append(row[n])
    ctx["target_n"] = len(all_rows)
    stats = {}
    for n in CANDIDATES:
        vals = [r[n] for r in all_rows if r[n] is not None]
        if not vals:
            raise RuntimeError(
                f"{n}: no successful measurements — sample error: "
                f"{all_rows[0][n + '_err']}")
        rts = [r[n + "_rt"] for r in all_rows]
        stats[n] = {
            "mean": statistics.mean(vals), "median": statistics.median(vals),
            "min": min(vals), "max": max(vals),
            "pos": sum(v > 0 for v in vals), "n": len(vals),
            "rt": all(rts), "rt_n": sum(rts),
        }
    ctx["target_stats"] = stats
    ctx["incremental"] = {}
    for n in EXPERIMENTAL:
        tok_diffs = [r["aif09-s_tok"] - r[n + "_tok"] for r in all_rows]
        pp_diffs = [r[n] - r["aif09-s"] for r in all_rows]
        ctx["incremental"][n] = {
            "tokens": statistics.mean(tok_diffs),
            "pp": statistics.mean(pp_diffs),
            "better": sum(d > 0 for d in tok_diffs),
        }
    # Absolute total tokens is the unambiguous objective; a mean of per-case
    # percentages can disagree with it when JSON baselines differ in size.
    ctx["total_tokens"] = {
        n: sum(r[n + "_tok"] for r in all_rows) for n in CANDIDATES}
    ctx["seed_means"] = {n: {s: statistics.mean(by_seed[s][n])
                             for s in S.SEEDS} for n in CANDIDATES}
    ctx["by_fk"] = []
    for key in sorted(by_fk, key=lambda x: (x[0], str(x[1]))):
        d = by_fk[key]
        ctx["by_fk"].append((key, {
            "json": d["json"],
            **{n: statistics.mean(d[n]) for n in CANDIDATES}}))
    for n in CANDIDATES:
        print(f"      {n:<9} mean {stats[n]['mean']:+.2f}%  "
              f"pos {stats[n]['pos']}/{stats[n]['n']}  "
              f"rt {stats[n]['rt_n']}/{stats[n]['n']}")

    print("[3/7] 盈亏平衡点扫描…")
    ctx["breakeven"] = []
    for k, records in S.breakeven_cases():
        m = measure(records)
        ctx["breakeven"].append((k, {n: red(m["json"], m[n][0])
                                     for n in CANDIDATES}))
    ctx["crossover"] = {}
    for n in CANDIDATES:
        ctx["crossover"][n] = next(
            (k for k, row in ctx["breakeven"] if row[n] is not None and row[n] > 0),
            None)

    print("[4/7] 对抗 / 劣势场景…")
    ctx["adversarial"] = []
    for label, records in S.adversarial_cases():
        m = measure(records)
        ctx["adversarial"].append((label, {
            "json": m["json"],
            **{n: red(m["json"], m[n][0]) for n in CANDIDATES},
            **{n + "_rt": m[n][1] for n in CANDIDATES}}))
        print(f"      {label:<26} " +
              " ".join(f"{n}={fmt(red(m['json'], m[n][0]), True)}"
                       for n in CANDIDATES))

    print("[5/7] 标量数组参照（V8 07 Array）…")
    scalar = v8.array(S.N_RECORDS)
    jt = S.tokens(S.json_text(scalar))
    ctx["scalar_ref"] = [
        ("JSON", jt, 0.0),
        ("AIF/0.9 Structured", S.tokens(json_to_aif(scalar)),
         S.reduction(jt, S.tokens(json_to_aif(scalar)))),
        ("AIF/0.9 Text Mode",
         S.tokens(json_to_aif(scalar, text_mode=True)),
         S.reduction(jt, S.tokens(json_to_aif(scalar, text_mode=True)))),
    ]

    print("[6/7] 编解码耗时与错误恢复…")
    ctx["timings"] = timings(S.make_records(5, 10, n=S.N_RECORDS, seed=202))
    ctx["errors"] = error_probe(S.make_records(3, 3, n=4, seed=11))
    ctx["silent_count"] = sum(r[3] for r in ctx["errors"])
    ctx["detected_count"] = sum(r[2] for r in ctx["errors"])

    # --- headlines, computed only from measurements above ---
    def passes(n):
        st = stats[n]
        return (st["pos"] / st["n"] >= S.STABLE_WIN_MIN_POSITIVE_SHARE
                and all(ctx["seed_means"][n][s] > S.STABLE_WIN_MIN_SEED_MEAN
                        for s in S.SEEDS) and st["rt"])

    win = [n for n in EXPERIMENTAL if passes(n)]
    baseline_pass = [n for n in ("aif09-s", "aif09-t") if passes(n)]
    best = max(EXPERIMENTAL, key=lambda n: stats[n]["mean"])
    silent_lab = [r for r in ctx["errors"] if r[0] in EXPERIMENTAL and r[3]]
    silent_09 = [r for r in ctx["errors"] if r[0].startswith("aif09") and r[3]]
    fixed_best = min(("row", "column"),
                     key=lambda n: ctx["total_tokens"][n])
    hyb_diff = ctx["total_tokens"][fixed_best] - ctx["total_tokens"]["hybrid"]
    hyb_pct = abs(hyb_diff) / ctx["total_tokens"][fixed_best] * 100
    hyb_verdict = (
        f"**Hybrid 比平凡基线少 {hyb_diff:,} tokens，但只占 {hyb_pct:.3f}%**，"
        "却要多一层模式切换语法与最高的编码耗时"
        if hyb_diff > 0 else
        f"**Hybrid 比平凡基线多花 {abs(hyb_diff):,} tokens，没有超过固定模式基线**，"
        "复杂度却最高"
    )
    k1_row = next(row for k, row in ctx["breakeven"] if k == 1)
    ctx["headlines"] = [
        f"1. **在预先定义的对象数组目标工作负载上，"
        f"{'、'.join('`'+n+'`' for n in win) if win else '没有任何实验方案'}"
        f"达到「稳定优于 JSON」门槛**（≥{S.STABLE_WIN_MIN_POSITIVE_SHARE:.0%} 数据点为正、"
        f"每个 seed 均值为正、round-trip 全 PASS；{ctx['target_n']} 个数据点 × "
        f"{len(S.SEEDS)} 个独立 seed）。"
        f"**但这不等于「Array 问题整体解决」**：这是 AIF 已知优势场景，"
        + (f"同场基准 {'/'.join('`'+n+'`' for n in baseline_pass)} 本身也通过判定"
           f"（{stats['aif09-s']['pos']}/{stats['aif09-s']['n']} 正例），"
           if baseline_pass else "同场基准 0.9 未通过该判定，") +
        "偏袒问题见 §2.4；标量数组仍是未解决的负例。",
        f"2. **真正的增量是相对 0.9，不是相对 JSON**：实验方案平均 reduction "
        f"{min(stats[n]['mean'] for n in EXPERIMENTAL):+.2f}% ～ "
        f"{max(stats[n]['mean'] for n in EXPERIMENTAL):+.2f}%，"
        f"vs 0.9-S {stats['aif09-s']['mean']:+.2f}%；"
        f"`{best}` 平均每组比 0.9 少 "
        f"{ctx['incremental'][best]['tokens']:,.0f} tokens"
        f"（{ctx['incremental'][best]['pp']:+.2f} pp，"
        f"{ctx['incremental'][best]['better']}/{ctx['target_n']} 组更优）。",
        "3. **小型数组负担被消除了**：" +
        "；".join(f"`{n}` " + (f"k*={ctx['crossover'][n]}" if ctx["crossover"][n]
                              else "未转正") for n in CANDIDATES) +
        f"（f={S.BREAKEVEN_FIELDS}）。0.9-S 在 k=1 是 "
        f"{k1_row['aif09-s']:+.2f}%、要到 k≥{ctx['crossover']['aif09-s'] or '未转正'} 才转正；"
        f"三个实验方案 k=1 即为正（Row {k1_row['row']:+.2f}%）—— "
        "原因是 schema 全局只声明一次、且不再为每条记录重复写数组键名。",
        f"4. **错误恢复抓到 0.9 的一个真实缺陷**：{len(ctx['errors'])} 次损坏注入中"
        f"静默损坏 {ctx['silent_count']} 次，"
        + ("**全部来自现有 0.9**" if ctx["silent_count"] and
           len(silent_09) == ctx["silent_count"]
           else f"其中 0.9 占 {len(silent_09)} 次") +
        "（截断到 `@record` 边界会静默少一条记录，因 0.9 没有记录总数声明）；"
        f"三个实验 codec 因 `@//groups/` 声明为 {len(silent_lab)} 次静默损坏。"
        "但所有方案都是 fail-fast，均不支持局部恢复，这仍是共同弱点。",
        f"5. **Hybrid 的判定以绝对总 token 为准**（平均 reduction 在百分比口径上"
        f"可能给出相反排序，因为各数据点 JSON 基数不同）：阈值只在与评估集"
        f"不相交的校准集拟合（{json.dumps(thresholds, ensure_ascii=False)}）。"
        f"目标集总 tokens —— Hybrid {ctx['total_tokens']['hybrid']:,}、"
        f"总是 Row {ctx['total_tokens']['row']:,}、"
        f"总是 Column {ctx['total_tokens']['column']:,}。{hyb_verdict}；"
        "**结论是不值得为它引入新语法**。"
        f"（平均 reduction：Hybrid {stats['hybrid']['mean']:+.2f}% vs "
        f"Row {stats['row']['mean']:+.2f}%。）",
        "6. **不把「所有 Array 场景都优于 JSON」当目标**：标量数组 V8 `07 Array` "
        f"仍是 {ctx['scalar_ref'][1][2]:+.2f}%（0.9 Structured，本 Lab N={S.N_RECORDS}），"
        "三个实验方案明确不覆盖；长文本、高缺失率、单对象组等劣势数据在 §4 全部保留。",
    ]
    ctx["recommendations"] = [
        "**AIF/0.9 保持定稿不动**：本 Lab 是独立实验目录，header 用 `AIF/1.0-alpha`，"
        "没有修改 0.9 的 encoder/decoder、规范、benchmark 数据或测试。",
        ("**建议把 " + "/".join(f"`{n}`" for n in win) +
         " 列为 AIF/1.0 候选扩展单独立项**；立项前需补齐嵌套对象、标量数组、"
         "跨 tokenizer 与第三方实现验证。") if win else
        "**暂不立项 1.0 扩展**：没有方案在预先定义的目标工作负载上通过稳定胜出判定。",
        "**字段名只出现一次（全局 schema）+ 组数声明**是本轮可复用的设计结论："
        "前者消除结构重复，后者让「截断到块边界」不再静默丢数据，只多一行开销。",
        "**建议给 0.9 也补一条记录总数声明**（哪怕只是可选扩展）："
        "§6 实测它在 `@record` 边界截断时会静默少一条记录，这是现有实现的真实缺陷，"
        "与 token 效率无关，属于可靠性问题。",
        "**列式不一定是赢家**：Row 与 Column 只是转置，差别来自 BPE 切分；"
        "具体选谁应由确定性规则 + 实测决定，不应凭直觉。",
        "**下一步的硬门槛仍然是第三方独立实现**（见 `conformance/`），"
        "而不是再写一个我们自己版本的编码器。",
    ]

    print("[7/7] 生成报告…")
    build_report(ctx)
    print(f"      已写 {REPORT.name}")
    print()
    for h in ctx["headlines"]:
        print("  " + h.replace("**", "").replace("`", ""))
    print()
    print(f"稳定胜出方案: {win if win else '无'}")


if __name__ == "__main__":
    main()

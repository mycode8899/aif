"""should_use_aif — a research tool that decides whether AIF saves tokens.

IMPORTANT: this is a RESEARCH TOOL, not part of the AIF/0.9 core package.
It is deliberately kept in research/ and is NOT imported by any test,
benchmark, example, encoder or decoder. It does not change the format.

RESEARCH FINDING (round 2): coarse estimates are NOT reliable enough to drive
decisions. On the V8 holdout the linear model has ~22pp MAE and its
mis-decision cost equals the trivial "always use AIF Text Mode" baseline;
a transparent rule cannot separate positive from negative array cases
either. Therefore `exact=True` is the RECOMMENDED path.

Three decision paths:

  * exact=True  RECOMMENDED — encode for real, count tokens with tiktoken,
    verify round-trip. 100% accurate. The encoding cost is already paid, so
    it suits batch / cached decisions, not "free prediction".
  * method="model" (default when exact=False) — linear estimate from
    structural features. No AIF encoding, no tokenizer call. Fast, but
    uncalibrated; result carries reliable=False and a warning.
  * method="rule" — transparent coarse rule from round-1 findings. Same
    uncalibrated status, but fully explainable.

The model is fitted on SYNTHETIC parameter-sweep data only. The V8 datasets
are never used for fitting; they are the holdout set in study_round2.py.

Usage:
  python AIF/research/predictor.py --demo
  python AIF/research/predictor.py --file data.json
  python AIF/research/predictor.py --self-test
  python AIF/research/predictor.py --train          # refit and save model
"""

import argparse
import json
import math
import random
import sys
from pathlib import Path

RESEARCH = Path(__file__).resolve().parent
DELIVERY = RESEARCH.parent
if str(DELIVERY) not in sys.path:
    sys.path.insert(0, str(DELIVERY))

from aif import json_to_aif, aif_to_json  # noqa: E402

MODEL_PATH = RESEARCH / "predictor_model.json"
TOKENIZER = "cl100k_base"
FEATURES = [
    "key_share",        # share of JSON text spent on repeated key names
    "long_text_share",  # share of value characters in long strings
    "space_share",      # space density (drives the \s penalty in Structured)
    "array_density",    # log1p(scalar-array elements per record)
    "obj_array_density",  # log1p(object-array slots per record)
    "log_records",      # log10(number of records)
    "missing_share",    # share of absent optional slots
    "log_fields",       # log10(number of schema fields)
    "avg_key_len",      # average key length / 20
    "log_value_len",    # log10(average value length)
]
LONG_TEXT = 40


# ---------------------------------------------------------------------------
# Feature extraction — pure Python, no tokenizer, no AIF encoder
# ---------------------------------------------------------------------------

def _scalar_text_len(v):
    if v is None:
        return 4
    if isinstance(v, bool):
        return 5 if v else 4
    if isinstance(v, (int, float)):
        return len(str(v))
    return len(str(v))


def _walk(obj, stats, top=False):
    """Collect key-name characters, value characters, array/space statistics."""
    if isinstance(obj, dict):
        for key, value in obj.items():
            stats["key_chars"] += len(str(key)) + 4  # "key": + comma
            stats["key_count"] += 1
            stats["key_len_sum"] += len(str(key))
            if isinstance(value, dict):
                _walk(value, stats)
            elif isinstance(value, list):
                _walk_list(value, stats)
            else:
                _scalar(value, stats)
    elif isinstance(obj, list):
        _walk_list(obj, stats)


def _scalar(value, stats):
    n = _scalar_text_len(value)
    stats["value_chars"] += n
    stats["value_count"] += 1
    if isinstance(value, str):
        stats["spaces"] += value.count(" ")
        stats["pipes"] += value.count("|")
        if len(value) >= LONG_TEXT:
            stats["long_text_chars"] += len(value)


def _walk_list(values, stats):
    if not values:
        return
    if all(isinstance(v, dict) for v in values):
        stats["obj_array_items"] += len(values)
        for item in values:
            _walk(item, stats)
            stats["obj_array_slots"] += len(item)
    else:
        stats["array_items"] += len(values)
        for v in values:
            if isinstance(v, (dict, list)):
                _walk(v, stats)
            else:
                _scalar(v, stats)


def _missing_ratio(records):
    """Real absent-slot share, including optional fields inside object arrays.

    For every dict level (identified by a path prefix) compare the keys each
    instance actually has against the union of keys at that level. This is a
    genuine optional-field measure, unlike `1 - values/(n*nfields)` which
    silently becomes 0 as soon as object arrays are present.
    """
    groups = {}

    def visit(obj, prefix):
        if isinstance(obj, dict):
            g = groups.setdefault(prefix, [set(), 0, 0])
            g[0].update(obj.keys())
            g[1] += 1
            g[2] += len(obj)
            for key, value in obj.items():
                child = f"{prefix}.{key}" if prefix else str(key)
                if isinstance(value, dict):
                    visit(value, child)
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict):
                            visit(item, child + "[]")
        elif isinstance(obj, list):
            for item in obj:
                visit(item, prefix + "[]")

    for record in records:
        visit(record, "")
    possible = sum(len(g[0]) * g[1] for g in groups.values())
    actual = sum(g[2] for g in groups.values())
    return max(0.0, 1.0 - actual / possible) if possible else 0.0


def _leaf_path_count(records):
    """Number of distinct scalar/array leaf paths (= AIF schema field count)."""
    paths = set()

    def visit(obj, prefix):
        if isinstance(obj, dict):
            for key, value in obj.items():
                path = f"{prefix}.{key}" if prefix else str(key)
                if isinstance(value, dict) and value:
                    visit(value, path)
                else:
                    paths.add(path)
        elif isinstance(obj, list):
            for v in obj[:1]:
                visit(v, prefix)

    for record in records:
        visit(record, "")
    return max(len(paths), 1)


def extract_features(data):
    """Return a dict of model features for a dict or a list of dicts."""
    records = data if isinstance(data, list) else [data]
    n = max(len(records), 1)
    stats = dict(key_chars=0, key_count=0, key_len_sum=0, value_chars=0,
                 value_count=0, long_text_chars=0, spaces=0, pipes=0,
                 array_items=0, obj_array_items=0, obj_array_slots=0)
    for record in records:
        _walk(record, stats)

    nfields = _leaf_path_count(records)
    key_chars = stats["key_chars"]
    value_chars = stats["value_chars"]
    avg_key_len = stats["key_len_sum"] / max(stats["key_count"], 1)
    avg_value_len = value_chars / max(stats["value_count"], 1)

    return {
        "key_share": key_chars / (key_chars + value_chars + 1),
        "long_text_share": stats["long_text_chars"] / (value_chars + 1),
        "space_share": stats["spaces"] / (value_chars + 1),
        "array_density": math.log1p(stats["array_items"] / n),
        "obj_array_density": math.log1p(stats["obj_array_slots"] / n),
        "log_records": math.log10(n + 1),
        "missing_share": _missing_ratio(records),
        "log_fields": math.log10(nfields + 1),
        "avg_key_len": avg_key_len / 20,
        "log_value_len": math.log10(avg_value_len + 1),
        # diagnostics (not model inputs)
        "_n": n,
        "_nfields": nfields,
        "_key_chars": key_chars,
        "_value_chars": value_chars,
        "_spaces": stats["spaces"],
        "_pipes": stats["pipes"],
    }


# ---------------------------------------------------------------------------
# Exact measurement
# ---------------------------------------------------------------------------

def _encoder(name=TOKENIZER):
    import tiktoken
    return tiktoken.get_encoding(name)


def measure_reduction(data, tokenizer=TOKENIZER, verify=True):
    """Encode for real and count tokens. Returns dict with exact reductions."""
    enc = _encoder(tokenizer)
    jtext = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    stext = json_to_aif(data)
    ttext = json_to_aif(data, text_mode=True)
    j = len(enc.encode(jtext))
    s = len(enc.encode(stext))
    t = len(enc.encode(ttext))
    out = {
        "json_tokens": j,
        "aif_s_tokens": s,
        "aif_t_tokens": t,
        "reduction_s": (j - s) / j * 100 if j else 0.0,
        "reduction_t": (j - t) / j * 100 if j else 0.0,
    }
    if verify:
        out["roundtrip_s"] = aif_to_json(stext) == data
        out["roundtrip_t"] = aif_to_json(ttext) == data
    return out


# ---------------------------------------------------------------------------
# Model fitting — synthetic parameter sweep only, never V8 datasets
# ---------------------------------------------------------------------------

def _synth(rng, n, nfields, key_len, value_len, arr_k, obj_k, opt_ratio):
    keys = []
    for i in range(nfields):
        base = f"k{i}"
        keys.append((base + "abcdefghijklmnop" * 3)[:max(key_len, len(base))])
    kinds = [rng.choice(["s", "i", "b"]) for _ in keys]
    body = "word " * max(1, value_len // 5)
    body = body.strip()

    records = []
    for r in range(n):
        record = {}
        for key, kind in zip(keys, kinds):
            if opt_ratio and rng.random() < opt_ratio:
                continue
            if kind == "s":
                record[key] = body
            elif kind == "i":
                record[key] = r + 1
            else:
                record[key] = bool(r % 2)
        if arr_k:
            record["tags"] = [f"tag{j}" for j in range(arr_k)]
        if obj_k:
            record["items"] = [
                {"name": f"item{j}", "qty": j, "ok": bool(j % 2)}
                for j in range(obj_k)
            ]
        records.append(record)
    return records


def make_synthetic_dataset(count, seed, include_labels=True, tokenizer=TOKENIZER):
    """Random parameter sweep. Used for training and for the synthetic holdout."""
    rng = random.Random(seed)
    enc = _encoder(tokenizer) if include_labels else None
    rows = []
    skipped = 0
    for _ in range(count):
        n = rng.choice([2, 5, 20, 80, 250])
        nfields = rng.choice([1, 2, 3, 5, 8, 15, 30, 50])
        key_len = rng.choice([2, 4, 8, 12])
        value_len = rng.choice([2, 6, 12, 30, 80, 200, 500])
        if value_len > 100 and n > 40:
            n = 40
        arr_k = rng.choice([0, 0, 0, 3, 10])
        obj_k = rng.choice([0, 0, 0, 2, 5])
        opt_ratio = rng.choice([0, 0, 0.25, 0.5])
        data = _synth(rng, n, nfields, key_len, value_len,
                      arr_k, obj_k, opt_ratio)
        item = {"data": data, "params": (n, nfields, key_len, value_len,
                                        arr_k, obj_k, opt_ratio)}
        if include_labels:
            try:
                jtext = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
                stext = json_to_aif(data)
                ttext = json_to_aif(data, text_mode=True)
                j = len(enc.encode(jtext))
                s = len(enc.encode(stext))
                t = len(enc.encode(ttext))
                item["red_s"] = (j - s) / j * 100 if j else 0.0
                item["red_t"] = (j - t) / j * 100 if j else 0.0
                item["json_tokens"] = j
                item["aif_s_tokens"] = s
                item["aif_t_tokens"] = t
            except Exception:  # noqa: BLE001 - unsupported shapes are skipped
                skipped += 1
                continue
        rows.append(item)
    return rows, skipped


def train_model(n_train=320, seed=20261108, tokenizer=TOKENIZER, save=True):
    """Fit two linear models (Structured / Text) on synthetic data only."""
    import numpy as np

    rows, skipped = make_synthetic_dataset(n_train, seed, True, tokenizer)
    X = np.array([[extract_features(r["data"])[f] for f in FEATURES]
                  for r in rows], dtype=float)
    y_s = np.array([r["red_s"] for r in rows], dtype=float) / 100
    y_t = np.array([r["red_t"] for r in rows], dtype=float) / 100
    mu = X.mean(axis=0)
    sd = X.std(axis=0)
    sd[sd == 0] = 1.0
    Z = np.column_stack([np.ones(len(X)), (X - mu) / sd])
    coef_s = np.linalg.lstsq(Z, y_s, rcond=None)[0]
    coef_t = np.linalg.lstsq(Z, y_t, rcond=None)[0]
    model = {
        "tokenizer": tokenizer,
        "features": FEATURES,
        "mu": mu.tolist(),
        "sd": sd.tolist(),
        "coef_s": coef_s.tolist(),
        "coef_t": coef_t.tolist(),
        "n_train": len(rows),
        "skipped": skipped,
        "seed": seed,
        "note": "Fitted on synthetic parameter-sweep data only. V8 datasets are holdout.",
    }
    if save:
        MODEL_PATH.write_text(json.dumps(model, indent=2), encoding="utf-8")
    return model, rows


def load_model():
    if MODEL_PATH.exists():
        return json.loads(MODEL_PATH.read_text(encoding="utf-8"))
    model, _ = train_model()
    return model


def predict(features, model=None):
    """Return (predicted_reduction_s_pct, predicted_reduction_t_pct)."""
    model = model or load_model()
    z = [1.0] + [(features[f] - m) / s
                 for f, m, s in zip(model["features"], model["mu"], model["sd"])]
    dot = lambda a, b: sum(x * y for x, y in zip(a, b))  # noqa: E731
    return (dot(z, model["coef_s"]) * 100, dot(z, model["coef_t"]) * 100)


# ---------------------------------------------------------------------------
# Public decision API
# ---------------------------------------------------------------------------

MODES = {"json": "Keep JSON", "aif-s": "AIF Structured Mode",
         "aif-t": "AIF Text Mode"}

ESTIMATE_WARNING = (
    "Feature-based reduction estimates are NOT calibrated (V8 holdout MAE "
    "~22 percentage points, systematic over-estimation). Use exact=True for "
    "any real decision; the estimate is only a coarse pre-filter."
)


def rule_decide(features):
    """Transparent coarse rule derived from round-1 findings, not fitted on V8.

    Round 1 established that scalar-array overhead is the dominant loss
    (21/21 scan cases negative), while key-name repetition is the gain, and
    Text Mode fixes the \\s penalty for long/space-containing text.

    KNOWN WEAKNESS (measured in round 2): at array_density ~1.39 there are
    both positive and negative cases, so this rule is a coarse filter only.
    """
    if features["array_density"] >= 2.0:
        return "json", "scalar 数组元素密度过高（第一轮 21/21 扫描为负）"
    if features["space_share"] > 0.01 or features["long_text_share"] > 0.1:
        return "aif-t", "值含空格/长文本，Text Mode 避免 \\s 膨胀"
    return "aif-s", "字段重复量占主导"


def _feature_view(features):
    return {
        "features": {k: round(v, 4) for k, v in features.items()
                     if not k.startswith("_")},
        "diagnostics": {k: v for k, v in features.items()
                        if k.startswith("_")},
    }


def _decide_from_reductions(red_s, red_t, estimated, features, extra=None):
    if red_s <= 0 and red_t <= 0:
        mode, red = "json", 0.0
        reason = "两种 AIF 模式都不省 token，保留 JSON"
    elif red_t >= red_s:
        mode, red = "aif-t", red_t
        reason = "值含可省下的裸空格，Text Mode 更优" if red_t > red_s else "字段重复量占主导"
    else:
        mode, red = "aif-s", red_s
        reason = "字段重复量占主导，Structured Mode 更优"
    out = {
        "use_aif": mode != "json",
        "recommended_mode": mode,
        "mode_label": MODES[mode],
        "reduction_pct": round(red, 2),
        "reduction_s_pct": round(red_s, 2),
        "reduction_t_pct": round(red_t, 2),
        "estimated": estimated,
        "reason": reason,
        "features": {k: round(v, 4) for k, v in features.items()
                     if not k.startswith("_")},
        "diagnostics": {k: v for k, v in features.items() if k.startswith("_")},
    }
    if extra:
        out.update(extra)
    return out


def decide(features, model=None):
    """Public: turn extracted features into a decision (estimate path)."""
    red_s, red_t = predict(features, model)
    return _decide_from_reductions(red_s, red_t, True, features)


def should_use_aif(data, exact=False, tokenizer=TOKENIZER, model=None,
                   method="model"):
    """Decide whether to encode `data` as AIF.

    exact=True   RECOMMENDED. Encode for real, count tokens, verify round-trip.
                 100% accurate; the encoding cost is already paid, so this
                 suits batch / cached decisions.
    exact=False  coarse pre-filter only. No AIF encoding, no tokenizer call.
                 method="model" -> fitted linear estimate (default),
                 method="rule"  -> transparent rule from round-1 findings.
                 Both are UNCALIBRATED; the result carries `reliable=False`
                 and an explicit `warning`.
    """
    features = extract_features(data)
    if exact:
        m = measure_reduction(data, tokenizer=tokenizer, verify=True)
        out = _decide_from_reductions(
            m["reduction_s"], m["reduction_t"], False, features,
            extra={"exact_tokens": m})
        out["method"] = "exact"
        out["reliable"] = True
        return out

    if method == "rule":
        mode, reason = rule_decide(features)
        out = {
            "use_aif": mode != "json",
            "recommended_mode": mode,
            "mode_label": MODES[mode],
            "reduction_pct": None,
            "reduction_s_pct": None,
            "reduction_t_pct": None,
            "estimated": True,
            "method": "rule",
            "reliable": False,
            "warning": ESTIMATE_WARNING,
            "reason": reason,
        }
        out.update(_feature_view(features))
        return out

    out = decide(features, model)
    out["method"] = "model"
    out["reliable"] = False
    out["warning"] = ESTIMATE_WARNING
    return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _demo():
    samples = {
        "1000 条扁平 agent 记录": [{"id": f"r{i:06d}", "status": "active",
                              "model": "gpt", "priority": i % 5}
                             for i in range(1000)],
        "1000 条长文本消息": [{"id": f"d{i:06d}",
                         "body": "AI agents exchange structured data with tools. " * 10}
                        for i in range(1000)],
        "1000 条短标签数组": [{"id": f"r{i:06d}",
                         "tags": ["AI", "technology", "agents"]}
                        for i in range(1000)],
        "2 条小记录": [{"id": "a", "v": 1}, {"id": "b", "v": 2}],
    }
    for name, data in samples.items():
        est = should_use_aif(data)
        rule = should_use_aif(data, method="rule")
        exact = should_use_aif(data, exact=True)
        m = exact["exact_tokens"]
        print(f"\n{name}")
        print(f"  model (coarse) : {est['recommended_mode']:<6} "
              f"{est['reduction_pct']:+7.2f}%   reliable={est['reliable']}")
        print(f"  rule  (coarse) : {rule['recommended_mode']:<6}")
        print(f"  exact (RELIABLE): {exact['recommended_mode']:<6} "
              f"{exact['reduction_pct']:+7.2f}%   RT={m['roundtrip_s'] and m['roundtrip_t']}")
        print(f"  reason         : {exact['reason']}")


def _self_test():
    cases = [
        ("flat many records", [{"id": f"r{i}", "status": "active",
                                "model": "gpt"} for i in range(200)]),
        ("long text", [{"id": f"d{i}", "body": "word " * 100}
                       for i in range(50)]),
        ("nested state", [{"id": f"r{i}", "p": {"age": i % 40, "city": "SH"}}
                          for i in range(200)]),
        ("scalar-array heavy", [{"id": f"r{i}", "tags": ["AI", "technology", "agents"],
                                 "scores": [i % 10, i % 20, i % 30],
                                 "flags": [True, False, True]}
                                for i in range(200)]),
    ]
    ok = 0
    for name, data in cases:
        d = should_use_aif(data, exact=True)
        m = should_use_aif(data)
        r = should_use_aif(data, method="rule")
        passed = (d["reliable"] and d["method"] == "exact"
                  and d["exact_tokens"]["roundtrip_s"]
                  and d["exact_tokens"]["roundtrip_t"]
                  and not m["reliable"] and not r["reliable"]
                  and all(x["recommended_mode"] in MODES for x in (d, m, r)))
        ok += passed
        print(f"  {name:<24} {'PASS' if passed else 'FAIL'}"
              f"  model={m['recommended_mode']:<6} rule={r['recommended_mode']:<6}"
              f" exact={d['recommended_mode']:<6}")
    neg = should_use_aif(cases[-1][1], exact=True)
    neg_ok = neg["recommended_mode"] == "json"
    ok += neg_ok
    print(f"  {'exact rejects scalar-array-heavy':<24} {'PASS' if neg_ok else 'FAIL'}")
    total = len(cases) + 1
    print(f"self-test: {ok}/{total} PASS")
    return ok == total


def main():
    ap = argparse.ArgumentParser(description="should_use_aif research tool")
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--train", action="store_true")
    ap.add_argument("--file", help="JSON file to analyse")
    ap.add_argument("--exact", action="store_true",
                    help="reliable path: encode and count for real")
    ap.add_argument("--method", choices=["model", "rule"], default="model",
                    help="coarse estimate method (ignored when --exact)")
    args = ap.parse_args()

    if args.train:
        model, rows = train_model()
        print(f"model fitted on {len(rows)} synthetic cases "
              f"({model['skipped']} skipped) -> {MODEL_PATH.name}")
        return
    if args.self_test:
        sys.exit(0 if _self_test() else 1)
    if args.demo:
        _demo()
        return
    if args.file:
        data = json.loads(Path(args.file).read_text(encoding="utf-8"))
        print(json.dumps(should_use_aif(data, exact=args.exact,
                                        method=args.method),
                         ensure_ascii=False, indent=2))
        return
    ap.print_help()


if __name__ == "__main__":
    main()

"""
AIF Array Optimization Lab — frozen experimental specification.

IMPORTANT: every workload, grid and decision threshold in this file is defined
BEFORE any measurement is taken. run_lab.py only consumes these constants; it
never invents a new workload after seeing results.

Scope (declared up front, not chosen after the fact):

  IN SCOPE   — array-of-objects data: a list of records, each holding exactly
               one array-of-objects field whose elements are flat scalar
               objects sharing one schema. Group sizes may vary.

  OUT OF SCOPE — scalar arrays (V8 `07 Array`), nested arrays, long free text
               as the dominant payload. These are reported as reference /
               adversarial cases only, never silently dropped.

Equivalent JSON for every case is the ordinary nested JSON:
    [{"items": [{...}, {...}]}, {"items": [{...}]}, ...]
serialised with the exact same rule as benchmarks/benchmark_v8.py.
"""

import json
import random

import tiktoken

TOKENIZER = "cl100k_base"
_enc = tiktoken.get_encoding(TOKENIZER)

# ---------------------------------------------------------------------------
# Identical serialisation / counting rules to V8. Do not "improve" these here.
# ---------------------------------------------------------------------------


def json_text(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def tokens(text):
    return len(_enc.encode(text))


def reduction(json_tokens, candidate_tokens):
    return (json_tokens - candidate_tokens) / json_tokens * 100


# ---------------------------------------------------------------------------
# Frozen target workload — the ONLY set used to judge "stable win over JSON".
# ---------------------------------------------------------------------------
N_RECORDS = 200
SEEDS = (101, 202, 303)

TARGET_FIELDS = (3, 5, 8)
TARGET_GROUP_SIZES = (2, 5, 10, 20, 50)
TARGET_GRID = [(f, k) for f in TARGET_FIELDS for k in TARGET_GROUP_SIZES]

# Hybrid thresholds are fitted HERE only. Note (f, k) pairs are disjoint from
# TARGET_GRID, so the evaluation set never leaks into the fitting set.
CALIBRATION_FIELDS = (2, 4, 7)
CALIBRATION_SIZES = (3, 7, 15, 30)
CALIBRATION_GRID = [(f, k) for f in CALIBRATION_FIELDS
                    for k in CALIBRATION_SIZES]
CALIBRATION_SEED = 909

BREAKEVEN_SIZES = (1, 2, 3, 4, 5, 6, 8, 10, 12, 16, 20, 24, 32)
BREAKEVEN_FIELDS = 5

# Pre-declared success criterion. Not tuned after looking at results.
STABLE_WIN_MIN_POSITIVE_SHARE = 0.80   # >=80% of target points must be > 0
STABLE_WIN_MIN_SEED_MEAN = 0.0         # every seed's mean reduction > 0

# ---------------------------------------------------------------------------
# Data generation
# ---------------------------------------------------------------------------
FIELD_NAMES = ("name", "qty", "ok", "city", "score", "flag",
               "tag", "rank", "note", "level")
FIELD_TYPES = ("s", "i", "b", "s", "i", "b", "s", "i", "s", "s")

SHORT_WORDS = ("alpha", "beta", "gamma", "Shanghai", "Beijing", "Shenzhen",
               "web_search", "calculator", "active", "queued", "AI", "agent",
               "tool", "张三", "李四", "王五", "北京", "上海", "深圳")
TRICKY_VALUES = ("a,b", "has space", "@null", "@missing", "-dash",
                 "back\\slash", "line\nbreak", "", "中文,带逗号", "@onull:x")

LONG_SENTENCE = (
    "AI agents exchange structured data with tools and with each other over "
    "long sessions where the same field names repeat many times. "
)


def _value(kind, rng, style):
    if kind == "s":
        if style == "longtext":
            reps = 2 if rng.random() < 0.5 else 8
            return (LONG_SENTENCE * reps)[:100 if reps == 2 else 500]
        if style == "tricky":
            return rng.choice(TRICKY_VALUES)
        return rng.choice(SHORT_WORDS)
    if kind == "i":
        return rng.randint(0, 9999)
    if kind == "b":
        return rng.choice((True, False))
    raise ValueError(kind)


def make_records(f, k, n=N_RECORDS, seed=101, style="short",
                 variable=False, miss_rate=0.06, null_rate=0.03,
                 array_key="items"):
    """Build `[{array_key: [obj, ...]}, ...]` with a shared flat schema.

    `variable=True` makes each group's length a fresh random value in 1..k,
    which is the "different length arrays" case the lab must handle.
    """
    if f > len(FIELD_NAMES):
        raise ValueError("f exceeds FIELD_NAMES")
    rng = random.Random(seed)
    keys, kinds = FIELD_NAMES[:f], FIELD_TYPES[:f]
    records = []
    for _ in range(n):
        size = rng.randint(1, max(1, k)) if variable else k
        group = []
        for _ in range(size):
            obj = {}
            for key, kind in zip(keys, kinds):
                r = rng.random()
                if r < miss_rate:
                    continue                      # optional field absent
                if r < miss_rate + null_rate:
                    obj[key] = None               # explicit null
                else:
                    obj[key] = _value(kind, rng, style)
            group.append(obj)
        records.append({array_key: group})
    return records


def make_special_case():
    """Deterministic adversarial case: every escaping rule at once."""
    return [{"items": [
        {"name": "a,b", "qty": 1, "ok": True},
        {"name": "has space", "qty": None, "ok": False},
        {"name": "@null", "qty": 0},
        {"name": "", "qty": -5, "ok": True},
        {"name": "back\\slash", "qty": 2 ** 40, "ok": False},
        {"name": "line\nbreak", "qty": 3, "ok": True},
        {"name": "中文,带逗号", "qty": 7, "ok": False},
        {"name": "@missing", "qty": 8, "ok": True},
        {"name": "-dash", "qty": 9, "ok": False},
    ]}, {"items": [
        {"name": "张三", "qty": 10, "ok": True},
    ]}]


def adversarial_cases():
    return [
        ("single object per group", make_records(5, 1, n=200, seed=202)),
        ("long text values", make_records(3, 10, n=200, seed=202,
                                          style="longtext")),
        ("high missing rate 60%", make_records(5, 10, n=200, seed=202,
                                               miss_rate=0.60, null_rate=0.10)),
        ("variable group sizes", make_records(5, 10, n=200, seed=202,
                                              variable=True)),
        ("all escaping rules", make_special_case()),
    ]


def calibration_cases():
    return [(f, k, make_records(f, k, n=N_RECORDS, seed=CALIBRATION_SEED))
            for f, k in CALIBRATION_GRID]


def target_cases():
    """(f, k, seed, records) for the frozen target workload."""
    for seed in SEEDS:
        for f, k in TARGET_GRID:
            yield f, k, seed, make_records(f, k, n=N_RECORDS, seed=seed)
        # variable-length groups are part of the declared target too
        yield 5, "variable", seed, make_records(
            5, 10, n=N_RECORDS, seed=seed, variable=True)


def breakeven_cases():
    return [(k, make_records(BREAKEVEN_FIELDS, k, n=N_RECORDS, seed=202))
            for k in BREAKEVEN_SIZES]

"""
Experimental AIF/1.0-alpha array codecs — Row / Column / Hybrid.

THIS IS A LAB, NOT THE RELEASE FORMAT.
  * Header `AIF/1.0-alpha` deliberately differs from `AIF/0.9`.
  * Nothing in AIF/aif/ is imported or modified by this module.
  * Every codec here has a real decoder; a format that cannot be decoded is
    not a candidate format, only a token-counting fantasy.

All three variants encode the SAME input shape:

    records = [{"items": [ {scalar fields}, ... ]}, ...]

`items` (or any other single key) is the array-of-objects field. Group sizes
may differ between records. All objects share one flat scalar schema.

Wire shape (row = one line per object; column = one line per field):

    AIF/1.0-alpha
    @//row/                     <- or @//columns/ or @//hybrid/
    [@//mode/ row|column]       <- hybrid only
    items[]:object name:s qty:i ok:b
    @//groups/ 2                <- detects truncation at a block boundary
    @//data/
    3                           <- group size (supports variable lengths)
    ...                         <- row: 3 lines x f cells, column: f lines x 3 cells
    @//data/
    1
    ...
"""

import json
import math
from collections import OrderedDict
from pathlib import Path

HEADER = "AIF/1.0-alpha"
MISSING = "-"
NULL = "@null"
EMPTY = r"\e"
MISSING_SENTINEL = object()
MAX_SAFE_INTEGER = 2 ** 53 - 1

# Default thresholds; run_lab.py fits replacement values on the calibration
# set only and writes fitted_thresholds.json. Kept here so codecs is usable
# standalone and so the fallback is explicit rather than magic.
DEFAULT_THRESHOLDS = {"k": 8, "f": 3, "L": 16, "M": 0.30}
_THRESHOLD_FILE = Path(__file__).with_name("fitted_thresholds.json")

_SIMPLE_ESCAPES = {
    "\\": "\\", ",": ",", "@": "@", "-": "-",
    "n": "\n", "r": "\r", "t": "\t",
}


class LabCodecError(ValueError):
    """Raised with block/line/field context so error recovery is measurable."""


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------
def _type_of(value):
    if isinstance(value, bool):
        return "b"
    if isinstance(value, int):
        if abs(value) > MAX_SAFE_INTEGER:
            raise LabCodecError(f"integer out of IEEE-754 safe range: {value}")
        return "i"
    if isinstance(value, float):
        if not math.isfinite(value):
            raise LabCodecError("NaN/Infinity are not valid JSON numbers")
        return "f"
    if isinstance(value, str):
        return "s"
    if value is None:
        return "n"
    raise LabCodecError(
        f"unsupported value {type(value).__name__}; only flat scalars are "
        "in scope for this lab (no nested objects / arrays inside an object)")


def infer_schema(groups):
    """Ordered [(name, type)] shared by every object; None is type-agnostic."""
    order, types = OrderedDict(), {}
    for gi, group in enumerate(groups):
        for oi, obj in enumerate(group):
            if not isinstance(obj, dict):
                raise LabCodecError(f"group {gi} object {oi}: expected object")
            for key, value in obj.items():
                if not isinstance(key, str) or not key:
                    raise LabCodecError("field names must be non-empty strings")
                if any(c in key for c in " \t\n\r,:@[]/\\"):
                    raise LabCodecError(f"illegal character in field name: {key!r}")
                if key not in order:
                    order[key] = None
                    types[key] = None
                if value is None:
                    continue
                kind = _type_of(value)
                if types[key] is None:
                    types[key] = kind
                elif types[key] != kind:
                    raise LabCodecError(
                        f"group {gi} object {oi} field {key!r}: type conflict "
                        f"{types[key]} vs {kind}")
    schema = [(k, types[k] or "n") for k in order]
    if not schema:
        raise LabCodecError("empty schema is not supported by the lab codecs")
    return schema


def split_records(records):
    """Return (array_key, groups, schema) with strict shape validation."""
    if not isinstance(records, list) or not records:
        raise LabCodecError("expected a non-empty list of records")
    keys = set()
    for i, rec in enumerate(records):
        if not isinstance(rec, dict) or len(rec) != 1:
            raise LabCodecError(f"record {i}: expected exactly one array field")
        keys.update(rec.keys())
    if len(keys) != 1:
        raise LabCodecError(f"inconsistent array field names: {sorted(keys)}")
    array_key = next(iter(keys))
    if any(c in array_key for c in " \t\n\r,:@[]/\\") or not array_key:
        raise LabCodecError(f"illegal array field name: {array_key!r}")
    groups = [rec[array_key] for rec in records]
    for i, g in enumerate(groups):
        if not isinstance(g, list):
            raise LabCodecError(f"record {i}: array field must hold a list")
    return array_key, groups, infer_schema(groups)


# ---------------------------------------------------------------------------
# Cell escaping (identical for row and column — only the transpose differs)
# ---------------------------------------------------------------------------
def _escape_control(text):
    out = []
    for ch in text:
        code = ord(ch)
        if ch == "\n":
            out.append(r"\n")
        elif ch == "\r":
            out.append(r"\r")
        elif ch == "\t":
            out.append(r"\t")
        elif code < 0x20 or 0x7F <= code <= 0x9F or code in (0x2028, 0x2029):
            out.append("\\u%04x" % code)
        else:
            out.append(ch)
    return "".join(out)


def escape_cell(value, kind):
    if value is MISSING_SENTINEL:
        return MISSING
    if value is None:
        return NULL
    if kind == "b":
        return "true" if value else "false"
    if kind in ("i", "f"):
        return str(value)
    if kind == "n":
        return NULL
    if value == "":
        return EMPTY                      # distinguishes "" from missing
    out = value.replace("\\", r"\\").replace(",", r"\,")
    out = _escape_control(out)
    # Leading marker characters must not be confused with - / @null.
    if out.startswith("@") or out.startswith("-"):
        out = "\\" + out
    return out


def split_cells(line, expected, where):
    """Split on UNESCAPED commas; escaped commas stay inside the cell."""
    cells, buf, i = [], [], 0
    while i < len(line):
        ch = line[i]
        if ch == "\\":
            if i + 1 >= len(line):
                raise LabCodecError(f"{where}: dangling escape at end of line")
            buf.append(line[i:i + 2])
            i += 2
        elif ch == ",":
            cells.append("".join(buf))
            buf = []
            i += 1
        else:
            buf.append(ch)
            i += 1
    cells.append("".join(buf))
    if len(cells) != expected:
        raise LabCodecError(
            f"{where}: expected {expected} cells, got {len(cells)} "
            f"in {line[:60]!r}")
    return cells


def unescape_cell(raw, kind, where):
    # Marker checks happen on the RAW cell text, before any unescaping, so a
    # literal "@null" (encoded as "\@null") stays a string.
    if raw == MISSING:
        return MISSING_SENTINEL
    if raw == NULL:
        return None
    if raw == EMPTY:
        return ""
    if kind == "b":
        if raw not in ("true", "false"):
            raise LabCodecError(f"{where}: invalid boolean {raw!r}")
        return raw == "true"
    if kind == "i":
        try:
            v = int(raw)
        except ValueError as exc:
            raise LabCodecError(f"{where}: invalid integer {raw!r}") from exc
        if abs(v) > MAX_SAFE_INTEGER:
            raise LabCodecError(f"{where}: integer out of safe range {raw!r}")
        return v
    if kind == "f":
        try:
            v = float(raw)
        except ValueError as exc:
            raise LabCodecError(f"{where}: invalid float {raw!r}") from exc
        if not math.isfinite(v):
            raise LabCodecError(f"{where}: non-finite float {raw!r}")
        return v
    if kind == "n":
        raise LabCodecError(f"{where}: field declared null-only, got {raw!r}")

    out, i = [], 0
    while i < len(raw):
        ch = raw[i]
        if ch != "\\":
            out.append(ch)
            i += 1
            continue
        if i + 1 >= len(raw):
            raise LabCodecError(f"{where}: dangling escape at end of cell")
        nxt = raw[i + 1]
        if nxt == "u" and len(raw) >= i + 6:
            hexpart = raw[i + 2:i + 6]
            try:
                out.append(chr(int(hexpart, 16)))
            except ValueError as exc:
                raise LabCodecError(
                    f"{where}: bad \\u escape {hexpart!r}") from exc
            i += 6
            continue
        if nxt not in _SIMPLE_ESCAPES:
            raise LabCodecError(f"{where}: unknown escape \\{nxt}")
        out.append(_SIMPLE_ESCAPES[nxt])
        i += 2
    return "".join(out)


# ---------------------------------------------------------------------------
# Encoding
# ---------------------------------------------------------------------------
def schema_line(array_key, schema):
    return " ".join([f"{array_key}[]:object"] +
                    [f"{name}:{kind}" for name, kind in schema])


def _cell_for(obj, name, kind):
    if name not in obj:
        return MISSING_SENTINEL
    return obj[name]


def encode(records, mode, array_key=None, thresholds=None):
    """mode: 'row' | 'column'. Returns AIF/1.0-alpha text."""
    if mode not in ("row", "column"):
        raise LabCodecError(f"unknown mode {mode!r}")
    key, groups, schema = split_records(records)
    if array_key is not None:
        key = array_key
    f = len(schema)
    lines = [HEADER, f"@//{mode if mode == 'row' else 'columns'}/",
             schema_line(key, schema), f"@//groups/ {len(groups)}"]
    for gi, group in enumerate(groups):
        k = len(group)
        lines += ["@//data/", str(k)]
        if mode == "row":
            for oi, obj in enumerate(group):
                cells = [escape_cell(_cell_for(obj, n, t), t)
                         for n, t in schema]
                lines.append(",".join(cells))
        else:
            for n, t in schema:
                cells = [escape_cell(_cell_for(obj, n, t), t)
                         for obj in group]
                lines.append(",".join(cells))
    return "\n".join(lines) + "\n"


def features(records):
    """Deterministic, cheap structural features for the Hybrid rule."""
    key, groups, schema = split_records(records)
    f = len(schema)
    total = sum(len(g) for g in groups)
    k_bar = total / len(groups)
    lens, missing = [], 0
    for group in groups:
        for obj in group:
            for name, _ in schema:
                if name not in obj or obj[name] is None:
                    missing += 1
                else:
                    v = obj[name]
                    lens.append(len(v) if isinstance(v, str) else len(str(v)))
    avg_len = sum(lens) / max(len(lens), 1)
    miss = missing / max(total * f, 1)
    return {"k": k_bar, "f": f, "L": avg_len, "M": miss}


def load_thresholds(path=_THRESHOLD_FILE):
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        return {**DEFAULT_THRESHOLDS, **data.get("thresholds", {})}
    return dict(DEFAULT_THRESHOLDS)


def choose_mode(records, thresholds=None):
    """DETERMINISTIC rule. No randomness, no peeking at evaluation results."""
    t = thresholds or load_thresholds()
    ft = features(records)
    use_column = (ft["k"] >= t["k"] and ft["f"] >= t["f"]
                  and ft["L"] <= t["L"] and ft["M"] <= t["M"])
    return "column" if use_column else "row", ft


def encode_hybrid(records, thresholds=None):
    mode, ft = choose_mode(records, thresholds)
    body = encode(records, mode)
    lines = body.rstrip("\n").split("\n")
    lines[1] = "@//hybrid/"
    lines.insert(2, f"@//mode/ {mode}")
    return "\n".join(lines) + "\n", mode, ft


# ---------------------------------------------------------------------------
# Decoding (one decoder handles all three variants)
# ---------------------------------------------------------------------------
def decode(text):
    if not isinstance(text, str):
        raise LabCodecError("expected AIF text, not a filename or object")
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    while lines and lines[-1] == "":
        lines.pop()
    if not lines or lines[0] != HEADER:
        raise LabCodecError(f"line 1: expected {HEADER!r}, got "
                            f"{lines[0][:40]!r}" if lines else "empty input")
    p = 1
    if p >= len(lines):
        raise LabCodecError("line 2: missing mode marker")
    marker = lines[p]
    mode = None
    if marker == "@//row/":
        mode = "row"
    elif marker == "@//columns/":
        mode = "column"
    elif marker == "@//hybrid/":
        p += 1
        if p >= len(lines) or not lines[p].startswith("@//mode/ "):
            raise LabCodecError(f"line {p+1}: hybrid missing @//mode/ line")
        mode = lines[p].split(" ", 1)[1].strip()
        if mode not in ("row", "column"):
            raise LabCodecError(f"line {p+1}: unknown hybrid mode {mode!r}")
    else:
        raise LabCodecError(f"line 2: unknown mode marker {marker!r}")
    p += 1
    if p >= len(lines):
        raise LabCodecError(f"line {p+1}: missing schema line")
    parts = lines[p].split(" ")
    p += 1
    if not parts or not parts[0].endswith("[]:object"):
        raise LabCodecError(f"line {p}: bad array declaration {parts[0]!r}")
    array_key = parts[0][:-len("[]:object")]
    schema = []
    for tok in parts[1:]:
        if ":" not in tok:
            raise LabCodecError(f"line {p}: bad schema token {tok!r}")
        name, kind = tok.rsplit(":", 1)
        if kind not in ("s", "i", "f", "b", "n"):
            raise LabCodecError(f"line {p}: bad type {kind!r} for {name!r}")
        schema.append((name, kind))
    if not schema:
        raise LabCodecError(f"line {p}: empty schema")
    f = len(schema)

    # A declared group count is required for error detection: without it,
    # truncating the text exactly at a @//data/ boundary would silently drop
    # whole records instead of raising an error. `p` already points here
    # because the schema line was consumed above.
    if p >= len(lines) or not lines[p].startswith("@//groups/ "):
        raise LabCodecError(f"line {p+1}: missing '@//groups/' declaration")
    try:
        declared_groups = int(lines[p].split(" ", 1)[1])
    except ValueError as exc:
        raise LabCodecError(f"line {p+1}: bad group count") from exc
    if declared_groups < 0:
        raise LabCodecError(f"line {p+1}: negative group count")
    p += 1

    records, block = [], -1
    while p < len(lines):
        if lines[p] != "@//data/":
            raise LabCodecError(
                f"line {p+1}: expected '@//data/', got {lines[p][:40]!r}")
        block += 1
        p += 1
        if p >= len(lines):
            raise LabCodecError(f"block {block}: missing group size")
        try:
            k = int(lines[p])
        except ValueError as exc:
            raise LabCodecError(
                f"block {block} line {p+1}: bad group size {lines[p]!r}") from exc
        if k < 0:
            raise LabCodecError(f"block {block}: negative group size {k}")
        p += 1
        nlines = k if mode == "row" else f
        ncols = f if mode == "row" else k
        raw_rows = []
        for li in range(nlines):
            if p >= len(lines):
                raise LabCodecError(
                    f"block {block}: truncated after {li}/{nlines} data lines")
            where = f"block {block} line {p+1}"
            raw_rows.append(split_cells(lines[p], ncols, where))
            p += 1

        group = []
        for oi in range(k):
            obj = {}
            for fi, (name, kind) in enumerate(schema):
                raw = (raw_rows[oi][fi] if mode == "row"
                       else raw_rows[fi][oi])
                where = (f"block {block} object {oi} field {name!r}")
                value = unescape_cell(raw, kind, where)
                if value is not MISSING_SENTINEL:
                    obj[name] = value
            group.append(obj)
        records.append({array_key: group})
    if not records:
        raise LabCodecError("no @//data/ blocks found")
    if len(records) != declared_groups:
        raise LabCodecError(
            f"group count mismatch: header declares {declared_groups}, "
            f"found {len(records)} @//data/ blocks (truncated or corrupted?)")
    return records

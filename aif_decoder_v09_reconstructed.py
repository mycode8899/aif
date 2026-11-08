"""
AIF/0.9 decoder - reconstructed robust implementation.

The original decoder snapshot is preserved separately as aif_decoder_v09_original.py.
This implementation uses explicit @missing markers so optional fields cannot shift
subsequent values or be mistaken for another field.
"""
HEADER = "AIF/0.9"

def decode_string(value):
    if value == r"\e": return ""
    out, i = [], 0
    escapes = {"s":" ", "n":"\n", "r":"\r", "t":"\t", "\\":"\\"}
    while i < len(value):
        if value[i] == "\\" and i + 1 < len(value):
            out.append(escapes.get(value[i+1], value[i+1])); i += 2
        else:
            out.append(value[i]); i += 1
    return "".join(out)

def parse_schema(line):
    result = []
    for token in line.split():
        if ":" not in token:
            raise ValueError(f"Invalid schema token: {token}")
        name, kind = token.rsplit(":", 1)
        result.append({"name":name, "type":kind})
    return result

def set_path(obj, path, value):
    parts = path.split(".")
    cur = obj
    for part in parts[:-1]:
        if part not in cur or not isinstance(cur[part], dict):
            cur[part] = {}
        cur = cur[part]
    cur[parts[-1]] = value

def decode_scalar(raw, kind):
    if raw == "@null": return None
    if kind == "s": return decode_string(raw)
    if kind == "i": return int(raw)
    if kind == "f": return float(raw)
    if kind == "b":
        if raw == "true": return True
        if raw == "false": return False
        raise ValueError(f"Invalid boolean value: {raw!r}")
    if kind == "n": return None
    raise ValueError(f"Unsupported scalar type: {kind}")

def read_value(lines, pos, kind):
    if pos >= len(lines): raise ValueError("Unexpected end of AIF data")
    raw = lines[pos]
    if raw == "@missing":
        return None, pos + 1, False
    if raw == "@null":
        return None, pos + 1, True
    if kind.startswith("array_"):
        item_kind = kind.split("_", 1)[1]
        if item_kind == "object":
            values, pos2 = read_object_array(lines, pos)
            return values, pos2, True
        if raw != "@array": raise ValueError(f"Expected @array, got {raw!r}")
        if pos + 1 >= len(lines): raise ValueError("Missing array count")
        count = int(lines[pos+1]); p = pos + 2
        values = []
        for _ in range(count):
            if p >= len(lines): raise ValueError("Truncated scalar array")
            values.append(decode_scalar(lines[p], item_kind)); p += 1
        return values, p, True
    return decode_scalar(raw, kind), pos + 1, True

def read_object_array(lines, pos):
    if pos >= len(lines) or lines[pos] != "@objects":
        raise ValueError("Expected @objects")
    if pos + 2 >= len(lines): raise ValueError("Incomplete @objects header")
    schema = parse_schema(lines[pos+1])
    count = int(lines[pos+2])
    p = pos + 3
    objects = []
    for _ in range(count):
        obj = {}
        for field in schema:
            value, p, present = read_value(lines, p, field["type"])
            if present:
                set_path(obj, field["name"], value)
        objects.append(obj)
    return objects, p

def aif_to_json(aif_text):
    lines = aif_text.splitlines()
    while lines and lines[-1] == "": lines.pop()
    if not lines or lines[0].strip() != HEADER:
        raise ValueError("Expected AIF/0.9")
    if len(lines) == 1: return []
    p = 1
    while p < len(lines) and lines[p] == "": p += 1
    if p >= len(lines): return []
    schema = parse_schema(lines[p]); p += 1
    records = []
    while p < len(lines):
        if lines[p] == "":
            p += 1; continue
        if lines[p] != "@record":
            raise ValueError(f"Expected @record, got: {lines[p]}")
        p += 1
        record = {}
        for field in schema:
            value, p, present = read_value(lines, p, field["type"])
            if present:
                set_path(record, field["name"], value)
        records.append(record)
    return records[0] if len(records) == 1 else records

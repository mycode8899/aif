"""
AIF/0.9 encoder - reconstructed recovery implementation.

This is a clean reconstruction from the surviving AIF/0.9 examples and design notes.
It is NOT claimed to be byte-for-byte identical to the lost original encoder.
"""
from collections import OrderedDict

HEADER = "AIF/0.9"

def get_type(value):
    if isinstance(value, bool): return "b"
    if isinstance(value, int): return "i"
    if isinstance(value, float): return "f"
    if isinstance(value, str): return "s"
    if value is None: return "n"
    if isinstance(value, dict): return "object"
    if isinstance(value, list): return "array"
    raise TypeError(f"Unsupported value type: {type(value).__name__}")

def encode_string(value):
    value = str(value)
    if value == "":
        return r"\e"
    return (value.replace("\\", r"\\")
                 .replace("\n", r"\n")
                 .replace("\r", r"\r")
                 .replace("\t", r"\t")
                 .replace(" ", r"\s"))

def encode_scalar(value, kind):
    if value is None:
        return "@null"
    if kind == "s": return encode_string(value)
    if kind in ("i", "f"): return str(value)
    if kind == "b": return "true" if value else "false"
    if kind == "n": return "@null"
    raise ValueError(f"Unsupported scalar type: {kind}")

def decode_string(value):
    if value == r"\e":
        return ""
    out, i = [], 0
    escapes = {"s":" ", "n":"\n", "r":"\r", "t":"\t", "\\":"\\"}
    while i < len(value):
        if value[i] == "\\" and i + 1 < len(value):
            out.append(escapes.get(value[i+1], value[i+1]))
            i += 2
        else:
            out.append(value[i]); i += 1
    return "".join(out)

def get_path(obj, path):
    cur = obj
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None, False
        cur = cur[part]
    return cur, True

def set_path(obj, path, value):
    parts = path.split(".")
    cur = obj
    for part in parts[:-1]:
        if part not in cur or not isinstance(cur[part], dict):
            cur[part] = {}
        cur = cur[part]
    cur[parts[-1]] = value

def merge_schema(records):
    """Build an ordered flattened schema, recursively handling nested objects."""
    fields = OrderedDict()

    def visit(objects, prefix=""):
        keys = []
        for obj in objects:
            if isinstance(obj, dict):
                for key in obj:
                    if key not in keys:
                        keys.append(key)

        for key in keys:
            full_name = f"{prefix}.{key}" if prefix else str(key)
            values = []
            present_count = 0

            for obj in objects:
                if isinstance(obj, dict) and key in obj:
                    present_count += 1
                    values.append(obj[key])

            nonnull = [v for v in values if v is not None]
            sample = nonnull[0] if nonnull else None
            kind = get_type(sample) if nonnull else "n"

            if kind == "object":
                visit([v for v in nonnull if isinstance(v, dict)], full_name)
                continue

            if kind == "array":
                items = [
                    item
                    for value in nonnull
                    if isinstance(value, list)
                    for item in value
                    if item is not None
                ]
                if items and isinstance(items[0], dict):
                    kind = "array_object"
                elif items:
                    kind = "array_" + get_type(items[0])
                else:
                    kind = "array_s"

            fields[full_name] = {
                "name": full_name,
                "type": kind,
                "optional": present_count < len(objects)
            }

    visit(records)
    return list(fields.values())

def schema_token(field):
    return f'{field["name"]}:{field["type"]}'

def encode_field_value(value, kind, object_schema=None):
    if value is None:
        return ["@null"]
    if kind.startswith("array_"):
        item_kind = kind.split("_", 1)[1]
        if item_kind == "object":
            return encode_object_array(value)
        lines = ["@array", str(len(value))]
        lines.extend(encode_scalar(x, item_kind) for x in value)
        return lines
    return [encode_scalar(value, kind)]

def encode_object_array(items):
    if not isinstance(items, list):
        raise TypeError("Expected list for array of objects")
    schema = merge_schema(items)
    lines = ["@objects", " ".join(schema_token(f) for f in schema), str(len(items))]
    for item in items:
        for field in schema:
            value, exists = get_path(item, field["name"])
            if not exists:
                lines.append("@missing")
            else:
                lines.extend(encode_field_value(value, field["type"]))
    return lines

def encode_record(record, schema):
    lines = []
    for field in schema:
        value, exists = get_path(record, field["name"])
        if not exists:
            lines.append("@missing")
        else:
            lines.extend(encode_field_value(value, field["type"]))
    return lines

def json_to_aif(data):
    single = isinstance(data, dict)
    records = [data] if single else data
    if not isinstance(records, list):
        raise TypeError("json_to_aif expects a dict or a list of dicts")
    if not records:
        return HEADER
    if not all(isinstance(x, dict) for x in records):
        raise TypeError("Top-level records must be objects")
    schema = merge_schema(records)
    lines = [HEADER, "", " ".join(schema_token(f) for f in schema)]
    for record in records:
        lines.append("@record")
        lines.extend(encode_record(record, schema))
    return "\n".join(lines)

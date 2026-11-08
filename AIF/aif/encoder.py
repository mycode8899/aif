"""
AIF/0.9 encoder — AIF 1.0 release line.

Implements the syntax defined in specification/AIF-0.9.md.

Design rule: every schema field occupies exactly one value slot in a record.
A missing field is written as '-' (never omitted), so the decoder cursor can
never drift. This is what fixed the old V7 "Invalid boolean value: English"
and "Expected @record, got: AI" failures.

text_mode=True keeps spaces unescaped in string values. Because AIF reads a
whole line as one value, spaces are structurally harmless there; escaping
them only inflates long natural-language text. The decoder accepts both
forms, so Text Mode needs no decoder change and no version bump.
"""

import math
from collections import OrderedDict

HEADER = "AIF/0.9"
MISSING = "-"
NULL = "@null"
OBJECT_NULL = "@onull:"
SCALAR_TYPES = ("s", "i", "f", "b", "n")

# Python's int is unbounded and Python floats allow NaN/Infinity, but neither
# is valid JSON. Emitting them would produce AIF that other languages cannot
# decode, so the encoder rejects them instead of silently losing data.
MAX_SAFE_INTEGER = 2 ** 53 - 1

# Characters that would be ambiguous in a schema token or in a flattened path.
_FORBIDDEN_KEY_CHARS = set(" \t\n\r\v\f:?[]{}/\\\"'")


def validate_field_name(key):
    if not isinstance(key, str) or not key:
        raise TypeError("AIF/0.9 field names must be non-empty strings")
    if "." in key:
        raise TypeError(f"AIF/0.9 field names cannot contain '.': {key!r}")
    bad = sorted(set(key) & _FORBIDDEN_KEY_CHARS)
    if bad:
        raise TypeError(
            f"AIF/0.9 field names cannot contain {bad}: {key!r}"
        )
    if key[0] in "@-":
        raise TypeError(
            f"AIF/0.9 field names cannot start with '@' or '-': {key!r}"
        )


def get_type(value):
    if isinstance(value, bool):
        return "b"
    if isinstance(value, int):
        return "i"
    if isinstance(value, float):
        return "f"
    if isinstance(value, str):
        return "s"
    if value is None:
        return "n"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    raise TypeError(f"Unsupported value type: {type(value).__name__}")


def _escape_control_chars(text):
    """Keep every value on exactly one line in *every* language.

    Python's str.splitlines() treats VT, FF, FS/GS/RS, NEL, U+2028 and U+2029
    as line boundaries too. A raw one of those inside a string silently split
    a value into two lines and shifted the decoder cursor. Escape all C0/C1
    controls and Unicode line separators as \\uXXXX instead.
    """
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


def encode_string(value, escape_spaces=True):
    """Escape a string so it stays on one line and cannot become a marker."""
    value = str(value)
    if value == "":
        return r"\e"
    out = value.replace("\\", r"\\")
    out = _escape_control_chars(out)
    if escape_spaces:
        out = out.replace(" ", r"\s")
    # A leading '@' collides with @null / @array / @objects / @record,
    # and a leading '-' collides with the missing marker.
    if out.startswith("@") or out.startswith("-"):
        out = "\\" + out
    return out


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


def _array_item_type(values, field_name):
    items = [
        item
        for value in values
        if isinstance(value, list)
        for item in value
        if item is not None
    ]
    if not items:
        return "array_s"
    kinds = {get_type(item) for item in items}
    if len(kinds) > 1:
        raise TypeError(
            f"Conflicting array item types for '{field_name}': {sorted(kinds)}"
        )
    kind = kinds.pop()
    if kind == "object":
        return "array_object"
    if kind in SCALAR_TYPES:
        return "array_" + kind
    raise TypeError(
        f"Unsupported array item type for '{field_name}': {kind}. "
        "Nested arrays are not supported by AIF/0.9."
    )


def merge_schema(objects):
    """Build an ordered, flattened schema with type-conflict detection."""
    fields = OrderedDict()

    def visit(objs, prefix="", total=None):
        if total is None:
            total = len(objs)

        keys = []
        for obj in objs:
            if isinstance(obj, dict):
                for key in obj:
                    if key not in keys:
                        keys.append(key)

        for key in keys:
            validate_field_name(key)
            full_name = f"{prefix}.{key}" if prefix else str(key)
            values = []
            present = 0
            for obj in objs:
                if isinstance(obj, dict) and key in obj:
                    present += 1
                    values.append(obj[key])

            nonnull = [v for v in values if v is not None]
            kinds = {get_type(v) for v in nonnull}
            if len(kinds) > 1:
                raise TypeError(
                    f"Conflicting types for field '{full_name}': {sorted(kinds)}"
                )
            kind = kinds.pop() if kinds else "n"

            if kind == "object":
                visit(
                    [v for v in nonnull if isinstance(v, dict)],
                    full_name,
                    total,
                )
                continue

            if kind == "array":
                kind = _array_item_type(nonnull, full_name)

            fields[full_name] = {
                "name": full_name,
                "type": kind,
                "optional": present < total,
            }

    visit(objects)

    # Specification rule: optional fields live at the tail of the schema.
    required = [f for f in fields.values() if not f["optional"]]
    optional = [f for f in fields.values() if f["optional"]]
    return required + optional


def schema_token(field):
    name = field["name"]
    leaf = name.rsplit(".", 1)[-1]
    validate_field_name(leaf)
    kind = field["type"]
    q = "?" if field["optional"] else ""
    if kind == "array_object":
        return f"{name}[]{q}:object"
    if kind.startswith("array_"):
        return f"{name}[]{q}:{kind[6:]}"
    return f"{name}{q}:{kind}"


def encode_scalar(value, kind, escape_spaces=True):
    if value is None:
        return NULL
    if kind == "s":
        return encode_string(value, escape_spaces)
    if kind == "i":
        if not isinstance(value, int) or isinstance(value, bool):
            raise TypeError(f"Expected integer for i field, got {value!r}")
        if not -MAX_SAFE_INTEGER <= value <= MAX_SAFE_INTEGER:
            raise TypeError(
                f"Integer out of IEEE-754 safe range (±{MAX_SAFE_INTEGER}): "
                f"{value!r}. Use a string to preserve exact large integers."
            )
        return str(value)
    if kind == "f":
        if not math.isfinite(value):
            raise TypeError(
                f"NaN / Infinity are not valid JSON numbers: {value!r}"
            )
        return str(value)
    if kind == "b":
        return "true" if value else "false"
    if kind == "n":
        return NULL
    raise ValueError(f"Unsupported scalar type: {kind}")


def encode_field_value(value, kind, escape_spaces=True):
    if value is None:
        return [NULL]
    if kind == "array_object":
        return encode_object_array(value, escape_spaces)
    if kind.startswith("array_"):
        item_kind = kind[6:]
        if not isinstance(value, list):
            raise TypeError(f"Expected list for array field, got {type(value).__name__}")
        lines = ["@array", str(len(value))]
        lines.extend(encode_scalar(item, item_kind, escape_spaces) for item in value)
        return lines
    return [encode_scalar(value, kind, escape_spaces)]


def _null_ancestor(record, field_name):
    """Return the highest ancestor path that exists and is explicitly null."""
    parts = field_name.split(".")
    for i in range(1, len(parts)):
        parent = ".".join(parts[:i])
        value, exists = get_path(record, parent)
        if exists and value is None:
            return parent
    return None


def encode_slots(record, schema, escape_spaces=True):
    """Emit exactly one value slot per schema field.

    A nested object that is explicitly null cannot be represented by simply
    omitting its flattened children: that would be indistinguishable from an
    absent object. The first slot of such a group is written as
    '@onull:<ancestor path>' and the remaining slots of the group as '-'.
    """
    lines = []
    emitted = set()
    for field in schema:
        name = field["name"]
        null_parent = _null_ancestor(record, name) if "." in name else None
        if null_parent is not None:
            if null_parent not in emitted:
                lines.append(OBJECT_NULL + null_parent)
                emitted.add(null_parent)
            else:
                lines.append(MISSING)
            continue
        value, exists = get_path(record, name)
        if not exists:
            lines.append(MISSING)
        else:
            lines.extend(encode_field_value(value, field["type"], escape_spaces))
    return lines


def encode_object_array(items, escape_spaces=True):
    if not isinstance(items, list):
        raise TypeError("Expected list for array of objects")
    schema = merge_schema(items)
    lines = [
        "@objects",
        " ".join(schema_token(f) for f in schema),
        str(len(items)),
    ]
    for item in items:
        lines.extend(encode_slots(item, schema, escape_spaces))
    return lines


def encode_record(record, schema, escape_spaces=True):
    return encode_slots(record, schema, escape_spaces)


def json_to_aif(data, text_mode=False):
    """Encode a dict or a list of dicts into AIF/0.9 text.

    text_mode=True leaves spaces unescaped in string values. The output is
    still valid AIF/0.9 and decodes with the very same decoder.
    """
    single = isinstance(data, dict)
    records = [data] if single else data
    escape_spaces = not text_mode

    if not isinstance(records, list):
        raise TypeError("json_to_aif expects a dict or a list of dicts")

    lines = [HEADER, ""]

    if not records:
        return "\n".join(lines)

    if not all(isinstance(x, dict) for x in records):
        raise TypeError("Top-level records must be objects")

    if single:
        lines.append("@single")

    schema = merge_schema(records)
    lines.append(" ".join(schema_token(f) for f in schema))

    for record in records:
        lines.append("@record")
        lines.extend(encode_record(record, schema, escape_spaces))

    return "\n".join(lines)

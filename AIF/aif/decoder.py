"""
AIF/0.9 decoder — AIF 1.0 release line.

Cursor model: every schema field consumes exactly one value slot. Structs
(@array / @objects) consume a deterministic number of lines and return the
next cursor position. No field is ever guessed from "what does the next line
look like", which is why the old V7 misalignment bugs cannot recur.
"""

HEADER = "AIF/0.9"
MISSING = "-"
NULL = "@null"
OBJECT_NULL_PREFIX = "@onull:"
OBJECT_NULL_TAG = "@onull"
VALID_KINDS = {"s", "i", "f", "b", "n"}


def decode_string(value):
    if value == r"\e":
        return ""
    escapes = {
        "s": " ",
        "n": "\n",
        "r": "\r",
        "t": "\t",
        "\\": "\\",
        "@": "@",
        "-": "-",
    }
    out = []
    i = 0
    while i < len(value):
        if value[i] == "\\" and i + 1 < len(value):
            nxt = value[i + 1]
            # \\uXXXX restores control characters / Unicode line separators
            # that the encoder had to escape (see specification §4).
            if (nxt == "u" and i + 6 <= len(value)
                    and all(c in "0123456789abcdefABCDEF"
                            for c in value[i + 2:i + 6])):
                out.append(chr(int(value[i + 2:i + 6], 16)))
                i += 6
                continue
            if nxt not in escapes:
                raise ValueError(f"Unknown escape sequence: \\{nxt}")
            out.append(escapes[nxt])
            i += 2
        else:
            out.append(value[i])
            i += 1
    return "".join(out)


def parse_schema(line):
    """Parse tokens such as name:s, name?:s, tags[]:s, tools[]?:object."""
    fields = []
    for token in line.split():
        if ":" not in token:
            raise ValueError(f"Invalid schema token: {token!r}")

        name_part, kind = token.rsplit(":", 1)
        optional = False
        if name_part.endswith("?"):
            optional = True
            name_part = name_part[:-1]

        is_array = name_part.endswith("[]")
        if is_array:
            name_part = name_part[:-2]

        if not name_part:
            raise ValueError(f"Invalid schema token: {token!r}")

        if is_array:
            if kind != "object" and kind not in VALID_KINDS:
                raise ValueError(f"Invalid array item type in {token!r}")
            field_type = "array_" + kind
        else:
            if kind not in VALID_KINDS:
                raise ValueError(f"Invalid field type in {token!r}")
            field_type = kind

        fields.append({
            "name": name_part,
            "type": field_type,
            "optional": optional,
        })
    return fields


def set_path(obj, path, value):
    parts = path.split(".")
    cur = obj
    for part in parts[:-1]:
        if part not in cur or not isinstance(cur[part], dict):
            cur[part] = {}
        cur = cur[part]
    cur[parts[-1]] = value


def apply_value(obj, field, value):
    """Place a decoded value, honouring an explicit null ancestor object."""
    if (isinstance(value, tuple) and len(value) == 2
            and value[0] == OBJECT_NULL_TAG):
        set_path(obj, value[1], None)
    else:
        set_path(obj, field["name"], value)


def decode_scalar(raw, kind, line_no=None):
    where = f" (line {line_no})" if line_no else ""
    if raw == NULL:
        return None
    if kind == "s":
        return decode_string(raw)
    if kind == "i":
        try:
            return int(raw)
        except ValueError:
            raise ValueError(f"Invalid integer value: {raw!r}{where}") from None
    if kind == "f":
        try:
            return float(raw)
        except ValueError:
            raise ValueError(f"Invalid float value: {raw!r}{where}") from None
    if kind == "b":
        if raw == "true":
            return True
        if raw == "false":
            return False
        raise ValueError(f"Invalid boolean value: {raw!r}{where}")
    if kind == "n":
        return None
    raise ValueError(f"Unsupported scalar type: {kind}{where}")


def read_value(lines, pos, field):
    """Return (value, next_position, present). 'present' is False for '-'."""
    if pos >= len(lines):
        raise ValueError(
            f"Unexpected end of AIF data, expected field '{field['name']}'"
        )

    raw = lines[pos]
    line_no = pos + 1
    name = field["name"]

    if raw == MISSING:
        return None, pos + 1, False
    if raw == NULL:
        return None, pos + 1, True

    if raw.startswith(OBJECT_NULL_PREFIX):
        path = raw[len(OBJECT_NULL_PREFIX):]
        if not path or not name.startswith(path + "."):
            raise ValueError(
                f"Invalid @onull marker for '{name}': {raw!r} (line {line_no})"
            )
        return (OBJECT_NULL_TAG, path), pos + 1, True

    kind = field["type"]

    if kind == "array_object":
        values, next_pos = read_object_array(lines, pos)
        return values, next_pos, True

    if kind.startswith("array_"):
        item_kind = kind[6:]
        if raw != "@array":
            raise ValueError(
                f"Expected @array for '{name}', got {raw!r} (line {line_no})"
            )
        if pos + 1 >= len(lines):
            raise ValueError(f"Missing array count for '{name}'")
        try:
            count = int(lines[pos + 1])
        except ValueError:
            raise ValueError(
                f"Invalid array count for '{name}': {lines[pos + 1]!r}"
            ) from None
        if count < 0:
            raise ValueError(f"Negative array count for '{name}': {count}")
        p = pos + 2
        values = []
        for _ in range(count):
            if p >= len(lines):
                raise ValueError(f"Truncated array for '{name}'")
            values.append(decode_scalar(lines[p], item_kind, p + 1))
            p += 1
        return values, p, True

    return decode_scalar(raw, kind, line_no), pos + 1, True


def read_object_array(lines, pos):
    if pos >= len(lines) or lines[pos] != "@objects":
        got = lines[pos] if pos < len(lines) else "<end of data>"
        raise ValueError(f"Expected @objects, got {got!r} (line {pos + 1})")
    if pos + 2 >= len(lines):
        raise ValueError("Incomplete @objects header (need schema and count)")

    schema = parse_schema(lines[pos + 1])
    try:
        count = int(lines[pos + 2])
    except ValueError:
        raise ValueError(f"Invalid object count: {lines[pos + 2]!r}") from None
    if count < 0:
        raise ValueError(f"Negative object count: {count}")

    p = pos + 3
    objects = []
    for _ in range(count):
        obj = {}
        for field in schema:
            value, p, present = read_value(lines, p, field)
            if present:
                apply_value(obj, field, value)
        objects.append(obj)
    return objects, p


def decode_record(lines, pos, schema):
    record = {}
    for field in schema:
        value, pos, present = read_value(lines, pos, field)
        if present:
            apply_value(record, field, value)
    return record, pos


def aif_to_json(aif_text):
    """Decode AIF/0.9 text back into a dict or a list of dicts."""
    if not isinstance(aif_text, str):
        raise TypeError(
            "aif_to_json expects AIF text, not a filename or a Python object"
        )

    # Only LF / CRLF / CR are line separators. Python's str.splitlines() also
    # splits on VT, FF, NEL and U+2028/U+2029, which would make independent
    # implementations disagree on the very same text.
    lines = aif_text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    while lines and lines[-1] == "":
        lines.pop()
    if not lines:
        raise ValueError("Empty AIF input")
    if lines[0].strip() != HEADER:
        raise ValueError(f"Expected {HEADER}, got {lines[0]!r}")

    p = 1
    # The encoder emits exactly ONE blank separator line after the header.
    # The schema line itself may ALSO be blank (a record with no fields), so
    # it must be consumed by position — never by "skip all blank lines",
    # which used to eat the empty schema and mistake '@record' for a token.
    if p < len(lines) and lines[p] == "":
        p += 1
    if p >= len(lines):
        return []

    single = False
    if lines[p] == "@single":
        single = True
        p += 1

    if p >= len(lines):
        raise ValueError("Missing schema line")

    schema = parse_schema(lines[p])  # empty line => empty schema, which is legal
    p += 1

    records = []
    while p < len(lines):
        if lines[p] == "":
            p += 1
            continue
        if lines[p] != "@record":
            raise ValueError(
                f"Expected @record, got: {lines[p]!r} (line {p + 1})"
            )
        p += 1
        record, p = decode_record(lines, p, schema)
        records.append(record)

    if single:
        if len(records) != 1:
            raise ValueError(
                f"@single requires exactly one @record, got {len(records)}"
            )
        return records[0]
    return records

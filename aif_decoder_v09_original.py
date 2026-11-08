def decode_string(value):
    """
    Decode an AIF string.

    \\e represents an empty string.
    \\s represents a space.
    """

    if value == "\\e":
        return ""

    result = ""
    i = 0

    while i < len(value):

        if value[i] == "\\" and i + 1 < len(value):

            next_char = value[i + 1]

            if next_char == "s":
                result += " "

            elif next_char == "\\":
                result += "\\"

            else:
                result += next_char

            i += 2

        else:

            result += value[i]

            i += 1

    return result


def decode_value(
    value,
    value_type
):
    if value == "@null":
        return None

    if value_type == "s":
        return decode_string(value)

    if value_type == "i":
        return int(value)

    if value_type == "f":
        return float(value)

    if value_type == "b":

        if value == "true":
            return True

        if value == "false":
            return False

        raise ValueError(
            f"Invalid boolean value: {value}"
        )

    if value_type == "n":
        return None

    raise ValueError(
        f"Unsupported value type: {value_type}"
    )


def parse_schema(schema_line):
    """
    Parse an AIF schema line.

    Examples:

        name:s

        arguments.query:s

        result.success?:b

        tags[]:s

        tools[]:object
    """

    fields = []

    tokens = schema_line.split()

    for token in tokens:

        optional = False

        # Array of objects
        if token.endswith(
            "[]?:object"
        ):

            name = token[:-10]

            fields.append({
                "name": name,
                "type": "array_object",
                "optional": True
            })

            continue

        if token.endswith(
            "[]:object"
        ):

            name = token[:-9]

            fields.append({
                "name": name,
                "type": "array_object",
                "optional": False
            })

            continue

        # Scalar / normal array

        if "?:" in token:

            name, value_type = (
                token.split(
                    "?:",
                    1
                )
            )

            optional = True

        elif ":" in token:

            name, value_type = (
                token.split(
                    ":",
                    1
                )
            )

        else:

            raise ValueError(
                f"Invalid schema token: {token}"
            )

        # Normal array
        if value_type.startswith(
            "array_"
        ):

            fields.append({
                "name": name,
                "type": value_type,
                "optional": optional
            })

        else:

            fields.append({
                "name": name,
                "type": value_type,
                "optional": optional
            })

    return fields


def set_nested_value(
    obj,
    field_name,
    value
):
    """
    Set a flattened nested path.

    Example:

        arguments.query

    becomes:

        {
            "arguments": {
                "query": value
            }
        }
    """

    parts = field_name.split(".")

    current = obj

    for part in parts[:-1]:

        if part not in current:
            current[part] = {}

        current = current[part]

    current[parts[-1]] = value


def decode_array(
    lines,
    position,
    value_type
):
    """
    Decode:

        @array
        count
        values...
    """

    if position >= len(lines):
        raise ValueError(
            "Unexpected end while decoding array"
        )

    if lines[position] != "@array":
        raise ValueError(
            "Expected @array"
        )

    position += 1

    if position >= len(lines):
        raise ValueError(
            "Missing array count"
        )

    count = int(
        lines[position]
    )

    position += 1

    values = []

    for _ in range(count):

        if position >= len(lines):
            raise ValueError(
                "Unexpected end while decoding array values"
            )

        value = lines[position]

        position += 1

        values.append(
            decode_value(
                value,
                value_type
            )
        )

    return values, position


def decode_object_array(
    lines,
    position
):
    """
    Decode an AIF 0.9 array of objects.

    Format:

        @objects
        schema
        count

        object values...
    """

    if position >= len(lines):
        raise ValueError(
            "Unexpected end while decoding object array"
        )

    if lines[position] != "@objects":
        raise ValueError(
            "Expected @objects"
        )

    position += 1

    if position >= len(lines):
        raise ValueError(
            "Missing object schema"
        )

    object_schema_line = (
        lines[position]
    )

    position += 1

    object_schema = parse_schema(
        object_schema_line
    )

    if position >= len(lines):
        raise ValueError(
            "Missing object count"
        )

    count = int(
        lines[position]
    )

    position += 1

    objects = []

    for _ in range(count):

        obj = {}

        for field in object_schema:

            field_name = field["name"]
            field_type = field["type"]
            optional = field["optional"]

            # No value available
            if position >= len(lines):

                if optional:
                    continue

                raise ValueError(
                    f"Missing required field: {field_name}"
                )

            value = lines[position]

            # A new structure marker means
            # this optional field is absent.
            if optional and value in (
                "@record",
                "@objects",
                "@array"
            ):
                continue

            # Nested array of objects
            if field_type == "array_object":

                if value != "@objects":

                    if optional:
                        continue

                    raise ValueError(
                        f"Expected @objects for {field_name}"
                    )

                nested_objects, position = (
                    decode_object_array(
                        lines,
                        position
                    )
                )

                set_nested_value(
                    obj,
                    field_name,
                    nested_objects
                )

                continue

            # Normal array
            if field_type.startswith(
                "array_"
            ):

                value_type = (
                    field_type.split(
                        "_",
                        1
                    )[1]
                )

                array_values, position = (
                    decode_array(
                        lines,
                        position,
                        value_type
                    )
                )

                set_nested_value(
                    obj,
                    field_name,
                    array_values
                )

                continue

            # Scalar
            position += 1

            decoded = decode_value(
                value,
                field_type
            )

            set_nested_value(
                obj,
                field_name,
                decoded
            )

        objects.append(obj)

    return objects, position


def decode_record(
    lines,
    position,
    schema_fields
):
    """
    Decode one normal AIF record.
    """

    record = {}

    for field in schema_fields:

        field_name = field["name"]
        field_type = field["type"]
        optional = field["optional"]

        if position >= len(lines):

            if optional:
                continue

            raise ValueError(
                f"Missing required field: {field_name}"
            )

        value = lines[position]

        # Optional field absent because
        # next record has started.
        if optional and value == "@record":
            break

        # Array of objects
        if field_type == "array_object":

            if value != "@objects":

                if optional:
                    continue

                raise ValueError(
                    f"Expected @objects for {field_name}"
                )

            objects, position = (
                decode_object_array(
                    lines,
                    position
                )
            )

            set_nested_value(
                record,
                field_name,
                objects
            )

            continue

        # Normal array
        if field_type.startswith(
            "array_"
        ):

            value_type = (
                field_type.split(
                    "_",
                    1
                )[1]
            )

            values, position = (
                decode_array(
                    lines,
                    position,
                    value_type
                )
            )

            set_nested_value(
                record,
                field_name,
                values
            )

            continue

        # Scalar
        position += 1

        decoded = decode_value(
            value,
            field_type
        )

        set_nested_value(
            record,
            field_name,
            decoded
        )

    return record, position


def aif_to_json(aif_text):
    """
    Convert AIF/0.9 text back to JSON-compatible
    Python objects.
    """

    lines = aif_text.splitlines()

    # Remove trailing empty lines only.
    while lines and lines[-1] == "":
        lines.pop()

    if not lines:
        raise ValueError(
            "Empty AIF input"
        )

    if lines[0].strip() != "AIF/0.9":
        raise ValueError(
            "Expected AIF/0.9"
        )

    position = 1

    # Skip blank lines before schema.
    while (
        position < len(lines)
        and lines[position] == ""
    ):
        position += 1

    if position >= len(lines):
        return []

    schema_line = lines[position]

    position += 1

    schema_fields = parse_schema(
        schema_line
    )

    records = []

    while position < len(lines):

        # Skip blank lines.
        if lines[position] == "":
            position += 1
            continue

        if lines[position] != "@record":
            raise ValueError(
                f"Expected @record, got: {lines[position]}"
            )

        position += 1

        record, position = (
            decode_record(
                lines,
                position,
                schema_fields
            )
        )

        records.append(record)

    if len(records) == 1:
        return records[0]

    return records
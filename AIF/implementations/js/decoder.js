'use strict';
/**
 * AIF/0.9 decoder — independent reference implementation B (JavaScript).
 *
 * Written from specification/AIF-0.9.md, not ported from the Python decoder.
 * Its purpose is cross-language conformance verification: if two independent
 * implementations agree on the same AIF text, the specification is precise
 * enough for a third party to implement.
 *
 * Strategy differs from the Python implementation on purpose:
 *   - a Reader object owns the cursor and records line numbers
 *   - recursive descent readValue / readArray / readObjectArray
 *   - null-prototype objects (avoids prototype pollution on keys like __proto__)
 *
 * Deliberately strict where the specification must be explicit for interop:
 *   - integers must be IEEE-754 safe integers
 *   - NaN / Infinity are rejected
 *   - only LF / CRLF / CR are line separators
 */

const HEADER = 'AIF/0.9';
const MISSING = '-';
const NULL = '@null';
const ONULL = '@onull:';
const SCALAR_KINDS = new Set(['s', 'i', 'f', 'b', 'n']);

function fail(message) {
  throw new Error(message);
}

function splitLines(text) {
  // Specification: a value occupies one whole line. Only LF/CRLF/CR split.
  return text.split(/\r\n|\n|\r/);
}

function newObject() {
  return Object.create(null);
}

/* ------------------------------------------------------------------ strings */

function decodeString(raw, lineNo) {
  if (raw === '\\e') return '';
  const escapes = {
    s: ' ', n: '\n', r: '\r', t: '\t',
    '\\': '\\', '@': '@', '-': '-',
  };
  let out = '';
  for (let i = 0; i < raw.length; i++) {
    if (raw[i] === '\\') {
      if (i + 1 >= raw.length) {
        fail(`Unknown escape sequence: \\ (line ${lineNo})`);
      }
      const next = raw[i + 1];
      // \uXXXX restores control characters / Unicode line separators.
      if (next === 'u' && i + 6 <= raw.length
          && /^[0-9a-fA-F]{4}$/.test(raw.slice(i + 2, i + 6))) {
        out += String.fromCharCode(parseInt(raw.slice(i + 2, i + 6), 16));
        i += 5;
        continue;
      }
      if (!Object.prototype.hasOwnProperty.call(escapes, next)) {
        fail(`Unknown escape sequence: \\${next} (line ${lineNo})`);
      }
      out += escapes[next];
      i++;
    } else {
      out += raw[i];
    }
  }
  return out;
}

/* ------------------------------------------------------------------- schema */

function parseSchema(line, lineNo) {
  const fields = [];
  const tokens = line.trim() === '' ? [] : line.trim().split(/\s+/);
  for (const token of tokens) {
    if (!token.includes(':')) fail(`Invalid schema token: ${token} (line ${lineNo})`);

    const colon = token.lastIndexOf(':');
    let namePart = token.slice(0, colon);
    const kind = token.slice(colon + 1);

    let optional = false;
    if (namePart.endsWith('?')) {
      optional = true;
      namePart = namePart.slice(0, -1);
    }

    const isArray = namePart.endsWith('[]');
    if (isArray) namePart = namePart.slice(0, -2);
    if (!namePart) fail(`Invalid schema token: ${token} (line ${lineNo})`);

    let type;
    if (isArray) {
      if (kind !== 'object' && !SCALAR_KINDS.has(kind)) {
        fail(`Invalid array item type in ${token} (line ${lineNo})`);
      }
      type = 'array_' + kind;
    } else {
      if (!SCALAR_KINDS.has(kind)) {
        fail(`Invalid field type in ${token} (line ${lineNo})`);
      }
      type = kind;
    }
    fields.push({ name: namePart, type, optional });
  }
  return fields;
}

/* -------------------------------------------------------------------- paths */

function setPath(obj, path, value) {
  const parts = path.split('.');
  let cur = obj;
  for (const part of parts.slice(0, -1)) {
    if (!Object.prototype.hasOwnProperty.call(cur, part)
        || cur[part] === null
        || typeof cur[part] !== 'object') {
      cur[part] = newObject();
    }
    cur = cur[part];
  }
  cur[parts[parts.length - 1]] = value;
}

function applyValue(obj, field, slot) {
  if (slot.onullPath !== undefined) {
    setPath(obj, slot.onullPath, null);
  } else {
    setPath(obj, field.name, slot.value);
  }
}

/* ------------------------------------------------------------------ scalars */

function decodeScalar(raw, kind, lineNo) {
  if (raw === NULL) return null;
  switch (kind) {
    case 's':
      return decodeString(raw, lineNo);
    case 'i': {
      if (!/^[+-]?\d+$/.test(raw)) {
        fail(`Invalid integer value: ${raw} (line ${lineNo})`);
      }
      const n = Number(raw);
      if (!Number.isSafeInteger(n)) {
        fail(`Integer out of IEEE-754 safe range: ${raw} (line ${lineNo})`);
      }
      return n;
    }
    case 'f': {
      const n = Number(raw);
      if (raw.trim() === '' || Number.isNaN(n)) {
        fail(`Invalid float value: ${raw} (line ${lineNo})`);
      }
      if (!Number.isFinite(n)) {
        fail(`Non-finite float is not valid JSON: ${raw} (line ${lineNo})`);
      }
      return n;
    }
    case 'b':
      if (raw === 'true') return true;
      if (raw === 'false') return false;
      fail(`Invalid boolean value: ${raw} (line ${lineNo})`);
      break;
    case 'n':
      return null;
    default:
      fail(`Unsupported scalar type: ${kind} (line ${lineNo})`);
  }
}

/* ------------------------------------------------------------------- reader */

class Reader {
  constructor(lines) {
    this.lines = lines;
    this.pos = 0;
    this.lastLineNo = 0;
  }

  next(what) {
    if (this.pos >= this.lines.length) {
      fail(`Unexpected end of AIF data, expected ${what}`);
    }
    this.lastLineNo = this.pos + 1;
    return this.lines[this.pos++];
  }

  peek() {
    return this.pos < this.lines.length ? this.lines[this.pos] : undefined;
  }

  expect(marker, what) {
    const raw = this.next(what);
    if (raw !== marker) {
      fail(`Expected ${marker}${what ? ' for ' + what : ''}, got ${JSON.stringify(raw)} `
           + `(line ${this.lastLineNo})`);
    }
    return raw;
  }

  count(what) {
    const raw = this.next(`${what} count`);
    if (!/^\d+$/.test(raw)) {
      fail(`Invalid ${what} count: ${JSON.stringify(raw)} (line ${this.lastLineNo})`);
    }
    return Number(raw);
  }
}

/* -------------------------------------------------------------------- values */

function readObjectArray(rd) {
  // The '@objects' marker was already consumed and checked by readValue.
  const schemaLine = rd.next('object schema');
  const schema = parseSchema(schemaLine, rd.lastLineNo);
  const count = rd.count('object');

  const objects = [];
  for (let i = 0; i < count; i++) {
    const obj = newObject();
    for (const field of schema) {
      const slot = readValue(rd, field);
      if (slot.present) applyValue(obj, field, slot);
    }
    objects.push(obj);
  }
  return objects;
}

function readScalarArray(rd, field, itemKind) {
  // The '@array' marker was already consumed and checked by readValue.
  const count = rd.count('array');
  const values = [];
  for (let i = 0; i < count; i++) {
    const raw = rd.next(`array element of '${field.name}'`);
    values.push(decodeScalar(raw, itemKind, rd.lastLineNo));
  }
  return values;
}

function readValue(rd, field) {
  const raw = rd.next(`field '${field.name}'`);
  const lineNo = rd.lastLineNo;

  if (raw === MISSING) return { present: false };
  if (raw === NULL) return { present: true, value: null };

  if (raw.startsWith(ONULL)) {
    const path = raw.slice(ONULL.length);
    if (!path || !field.name.startsWith(path + '.')) {
      fail(`Invalid @onull marker for '${field.name}': ${raw} (line ${lineNo})`);
    }
    return { present: true, onullPath: path };
  }

  const kind = field.type;
  if (kind === 'array_object') {
    if (raw !== '@objects') {
      fail(`Expected @objects for '${field.name}', got ${JSON.stringify(raw)} `
           + `(line ${lineNo})`);
    }
    return { present: true, value: readObjectArray(rd) };
  }
  if (kind.startsWith('array_')) {
    if (raw !== '@array') {
      fail(`Expected @array for '${field.name}', got ${JSON.stringify(raw)} `
           + `(line ${lineNo})`);
    }
    return { present: true, value: readScalarArray(rd, field, kind.slice(6)) };
  }
  return { present: true, value: decodeScalar(raw, kind, lineNo) };
}

function decodeRecord(rd, schema) {
  const record = newObject();
  for (const field of schema) {
    const slot = readValue(rd, field);
    if (slot.present) applyValue(record, field, slot);
  }
  return record;
}

/* ------------------------------------------------------------------ document */

function aifToJson(aifText) {
  if (typeof aifText !== 'string') {
    throw new TypeError('aifToJson expects AIF text, not a filename or object');
  }

  const lines = splitLines(aifText);
  while (lines.length && lines[lines.length - 1] === '') lines.pop();
  if (!lines.length) fail('Empty AIF input');
  if (lines[0].trim() !== HEADER) {
    fail(`Expected ${HEADER}, got ${JSON.stringify(lines[0])}`);
  }

  let p = 1;
  // Exactly ONE blank separator line follows the header. The schema line
  // itself may also be blank (a record with no fields), so consume it by
  // position instead of skipping every blank line.
  if (p < lines.length && lines[p] === '') p++;
  if (p >= lines.length) return [];

  let single = false;
  if (lines[p] === '@single') {
    single = true;
    p++;
  }
  if (p >= lines.length) fail('Missing schema line');

  const schema = parseSchema(lines[p], p + 1);
  p++;

  const rd = new Reader(lines);
  rd.pos = p;

  const records = [];
  while (rd.pos < lines.length) {
    if (rd.peek() === '') {
      rd.pos++;
      continue;
    }
    rd.expect('@record', 'a record boundary');
    records.push(decodeRecord(rd, schema));
  }

  if (single) {
    if (records.length !== 1) {
      fail(`@single requires exactly one @record, got ${records.length}`);
    }
    return records[0];
  }
  return records;
}

module.exports = { aifToJson, parseSchema, decodeString };

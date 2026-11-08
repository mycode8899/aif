'use strict';
/**
 * AIF/0.9 encoder — reference implementation B (JavaScript).
 *
 * Written from specification/AIF-0.9.md. NOT a third-party implementation:
 * it was produced in the same project/session as the Python encoder, so it
 * can only prove that the bidirectional conformance harness works. It does
 * NOT satisfy release gate #6 ("a developer who did not take part in the
 * original implementation").
 *
 * Intentional design differences from the Python encoder:
 *   - schema collected with plain arrays/Maps instead of OrderedDict
 *   - slot emission writes into an output array directly
 * nevertheless the emitted AIF text is byte-for-byte comparable, because the
 * specification fixes token order, optional ordering and escaping.
 */

const HEADER = 'AIF/0.9';
const MISSING = '-';
const NULL = '@null';
const ONULL = '@onull:';
const SCALAR_KINDS = new Set(['s', 'i', 'f', 'b', 'n']);
const MAX_SAFE_INTEGER = Number.MAX_SAFE_INTEGER;   // 2^53 - 1

// Same character set as the Python encoder's validate_field_name(), including
// '.' which is the nested-path separator. Kept as a plain string to avoid
// regex character-class ambiguity with [ ] { } and backslash.
const FORBIDDEN_KEY_CHARS = " \t\n\r\v\f:?[]{}/\\\"'.";

function fail(message) {
  throw new TypeError(message);
}

function isPlainObject(v) {
  return v !== null && typeof v === 'object' && !Array.isArray(v);
}

function hasOwn(obj, key) {
  return Object.prototype.hasOwnProperty.call(obj, key);
}

/* ------------------------------------------------------------------- fields */

function validateFieldName(key) {
  if (typeof key !== 'string' || key.length === 0) {
    fail('AIF/0.9 field names must be non-empty strings');
  }
  for (const ch of key) {
    if (FORBIDDEN_KEY_CHARS.includes(ch)) {
      fail(`AIF/0.9 field name contains a syntax character: ${JSON.stringify(key)}`);
    }
  }
  if (key[0] === '@' || key[0] === '-') {
    fail(`AIF/0.9 field names cannot start with '@' or '-': ${JSON.stringify(key)}`);
  }
}

function getType(value) {
  if (typeof value === 'boolean') return 'b';
  if (typeof value === 'number') return Number.isInteger(value) ? 'i' : 'f';
  if (typeof value === 'string') return 's';
  if (value === null) return 'n';
  if (Array.isArray(value)) return 'array';
  if (isPlainObject(value)) return 'object';
  fail(`Unsupported value type: ${typeof value}`);
}

function getPath(obj, path) {
  let cur = obj;
  for (const part of path.split('.')) {
    if (!isPlainObject(cur) || !hasOwn(cur, part)) {
      return { value: undefined, exists: false };
    }
    cur = cur[part];
  }
  return { value: cur, exists: true };
}

function arrayItemType(values, fieldName) {
  const items = [];
  for (const value of values) {
    if (!Array.isArray(value)) continue;
    for (const item of value) if (item !== null) items.push(item);
  }
  if (!items.length) return 'array_s';
  const kinds = new Set(items.map(getType));
  if (kinds.size > 1) {
    fail(`Conflicting array item types for '${fieldName}': ${[...kinds].sort()}`);
  }
  const kind = [...kinds][0];
  if (kind === 'object') return 'array_object';
  if (SCALAR_KINDS.has(kind)) return 'array_' + kind;
  fail(`Unsupported array item type for '${fieldName}': ${kind}. `
       + 'Nested arrays are not supported by AIF/0.9.');
}

/* ------------------------------------------------------------------- schema */

function mergeSchema(objects) {
  const fields = new Map();

  function visit(objs, prefix, total) {
    const keys = [];
    for (const obj of objs) {
      if (!isPlainObject(obj)) continue;
      for (const key of Object.keys(obj)) {
        if (!keys.includes(key)) keys.push(key);
      }
    }
    for (const key of keys) {
      validateFieldName(key);
      const fullName = prefix ? `${prefix}.${key}` : key;
      const values = [];
      let present = 0;
      for (const obj of objs) {
        if (isPlainObject(obj) && hasOwn(obj, key)) {
          present++;
          values.push(obj[key]);
        }
      }
      const nonnull = values.filter((v) => v !== null);
      const kinds = new Set(nonnull.map(getType));
      if (kinds.size > 1) {
        fail(`Conflicting types for field '${fullName}': ${[...kinds].sort()}`);
      }
      let kind = kinds.size ? [...kinds][0] : 'n';
      if (kind === 'object') {
        visit(nonnull.filter(isPlainObject), fullName, total);
        continue;
      }
      if (kind === 'array') kind = arrayItemType(nonnull, fullName);
      fields.set(fullName, {
        name: fullName, type: kind, optional: present < total,
      });
    }
  }

  visit(objects, '', objects.length);
  const all = [...fields.values()];
  // Specification rule: optional fields live at the tail of the schema.
  return [...all.filter((f) => !f.optional), ...all.filter((f) => f.optional)];
}

function schemaToken(field) {
  const q = field.optional ? '?' : '';
  if (field.type === 'array_object') return `${field.name}[]${q}:object`;
  if (field.type.startsWith('array_')) {
    return `${field.name}[]${q}:${field.type.slice(6)}`;
  }
  return `${field.name}${q}:${field.type}`;
}

/* ------------------------------------------------------------------ escaping */

function escapeControl(text) {
  let out = '';
  for (const ch of text) {
    const code = ch.codePointAt(0);
    if (ch === '\n') out += '\\n';
    else if (ch === '\r') out += '\\r';
    else if (ch === '\t') out += '\\t';
    else if (code < 0x20 || (code >= 0x7F && code <= 0x9F)
             || code === 0x2028 || code === 0x2029) {
      out += '\\u' + code.toString(16).padStart(4, '0');
    } else out += ch;
  }
  return out;
}

function encodeString(value, textMode) {
  if (typeof value !== 'string') fail('expected a string value');
  if (value === '') return '\\e';
  let out = value.replace(/\\/g, '\\\\');
  out = escapeControl(out);
  if (!textMode) out = out.replace(/ /g, '\\s');
  if (out.startsWith('@') || out.startsWith('-')) out = '\\' + out;
  return out;
}

function encodeScalar(value, kind, textMode) {
  if (value === null) return NULL;
  if (kind === 's') return encodeString(value, textMode);
  if (kind === 'i') {
    if (typeof value !== 'number' || !Number.isSafeInteger(value)) {
      fail(`Integer out of IEEE-754 safe range (±${MAX_SAFE_INTEGER}): ${value}`);
    }
    return String(value);
  }
  if (kind === 'f') {
    if (!Number.isFinite(value)) fail('NaN / Infinity are not valid JSON numbers');
    return String(value);
  }
  if (kind === 'b') return value ? 'true' : 'false';
  if (kind === 'n') return NULL;
  fail(`Unsupported scalar type: ${kind}`);
}

function encodeFieldValue(value, kind, textMode) {
  if (value === null) return [NULL];
  if (kind === 'array_object') return encodeObjectArray(value, textMode);
  if (kind.startsWith('array_')) {
    if (!Array.isArray(value)) fail('Expected list for array field');
    const itemKind = kind.slice(6);
    return ['@array', String(value.length),
            ...value.map((item) => encodeScalar(item, itemKind, textMode))];
  }
  return [encodeScalar(value, kind, textMode)];
}

function nullAncestor(record, fieldName) {
  const parts = fieldName.split('.');
  for (let i = 1; i < parts.length; i++) {
    const parent = parts.slice(0, i).join('.');
    const got = getPath(record, parent);
    if (got.exists && got.value === null) return parent;
  }
  return null;
}

function encodeSlots(record, schema, textMode) {
  const lines = [];
  const emitted = new Set();
  for (const field of schema) {
    const name = field.name;
    const nullParent = name.includes('.') ? nullAncestor(record, name) : null;
    if (nullParent !== null) {
      if (!emitted.has(nullParent)) {
        lines.push(ONULL + nullParent);
        emitted.add(nullParent);
      } else {
        lines.push(MISSING);
      }
      continue;
    }
    const got = getPath(record, name);
    if (!got.exists) lines.push(MISSING);
    else lines.push(...encodeFieldValue(got.value, field.type, textMode));
  }
  return lines;
}

function encodeObjectArray(items, textMode) {
  if (!Array.isArray(items)) fail('Expected list for array of objects');
  const schema = mergeSchema(items);
  const lines = ['@objects', schema.map(schemaToken).join(' '),
                 String(items.length)];
  for (const item of items) lines.push(...encodeSlots(item, schema, textMode));
  return lines;
}

/* ------------------------------------------------------------------ document */

function jsonToAif(data, textMode = false) {
  const single = isPlainObject(data);
  const records = single ? [data] : data;
  const lines = [HEADER, ''];
  if (!Array.isArray(records)) fail('jsonToAif expects a dict or a list of dicts');
  if (records.length === 0) return lines.join('\n');
  for (const r of records) {
    if (!isPlainObject(r)) fail('Top-level records must be objects');
  }
  if (single) lines.push('@single');
  const schema = mergeSchema(records);
  lines.push(schema.map(schemaToken).join(' '));
  for (const record of records) {
    lines.push('@record');
    lines.push(...encodeSlots(record, schema, textMode));
  }
  return lines.join('\n');
}

module.exports = { jsonToAif, mergeSchema, schemaToken, encodeString };

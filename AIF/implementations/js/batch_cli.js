'use strict';
/**
 * Batch bridge for fuzz testing. Reads a JSON array of AIF texts from stdin,
 * writes a JSON array of {ok, value} / {ok, error} results to stdout.
 * One Node process handles every case, so fuzzing thousands of documents
 * stays fast.
 */
const fs = require('fs');
const { aifToJson } = require('./decoder');

let input;
try {
  input = JSON.parse(fs.readFileSync(0, 'utf8'));
} catch (err) {
  console.error('ERROR: invalid batch input: ' + err.message);
  process.exit(1);
}

const results = input.map((text) => {
  try {
    return { ok: true, value: aifToJson(text) };
  } catch (err) {
    return { ok: false, error: err.message };
  }
});
process.stdout.write(JSON.stringify(results));

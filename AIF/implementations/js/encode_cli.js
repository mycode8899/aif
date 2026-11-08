'use strict';
/**
 * CLI bridge for the JavaScript reference encoder (implementation B).
 *
 *   node encode_cli.js < data.json                 -> AIF text on stdout
 *   node encode_cli.js --text-mode < data.json     -> AIF Text Mode
 *   node encode_cli.js --batch < cases.json        -> JSON array of results
 *   node encode_cli.js --self-test                 -> prints "JS_ENCODER_OK"
 *
 * Batch input : [{"data": <any JSON>, "textMode": false}, ...]
 * Batch output: [{"ok": true, "text": "AIF/0.9..."} | {"ok": false, "error": "..."}]
 */
const fs = require('fs');
const { jsonToAif } = require('./encoder');

const args = process.argv.slice(2);

if (args.includes('--self-test')) {
  const cases = [
    { name: 'Alice', age: 30, active: true },
    [
      { id: 'a', profile: { city: 'Shanghai' }, tags: ['x', 'y'] },
      { id: 'b', profile: { city: 'Beijing' } },
    ],
    { agent: 'a1', tools: [
      { name: 'web_search', result: { ok: true } },
      { name: 'calculator', result: null },
    ] },
    { v: '@null', w: '-', x: '', y: 'a,b', z: 'line\nbreak' },
  ];
  const { aifToJson } = require('./decoder');
  for (const data of cases) {
    for (const textMode of [false, true]) {
      const text = jsonToAif(data, textMode);
      const back = aifToJson(text);
      if (JSON.stringify(back) !== JSON.stringify(data)) {
        console.error('SELF-TEST FAILED (round-trip): ' + JSON.stringify(data));
        process.exit(1);
      }
    }
  }
  console.log('JS_ENCODER_OK');
  process.exit(0);
}

let input;
try {
  input = JSON.parse(fs.readFileSync(0, 'utf8'));
} catch (err) {
  console.error('ERROR: invalid JSON input: ' + err.message);
  process.exit(1);
}

if (args.includes('--batch')) {
  if (!Array.isArray(input)) {
    console.error('ERROR: --batch expects a JSON array');
    process.exit(1);
  }
  const results = input.map((item) => {
    try {
      const data = Object.prototype.hasOwnProperty.call(item, 'data')
        ? item.data : item;
      const textMode = Boolean(item.textMode);
      return { ok: true, text: jsonToAif(data, textMode) };
    } catch (err) {
      return { ok: false, error: err.message };
    }
  });
  process.stdout.write(JSON.stringify(results));
} else {
  try {
    process.stdout.write(jsonToAif(input, args.includes('--text-mode')));
  } catch (err) {
    console.error('ERROR: ' + err.message);
    process.exit(1);
  }
}

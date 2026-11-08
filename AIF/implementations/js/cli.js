'use strict';
/**
 * CLI bridge for cross-language conformance tests.
 *
 *   node cli.js < file.aif          -> prints decoded JSON to stdout
 *   node cli.js --self-test         -> prints "JS_DECODER_OK"
 *
 * On a decode error: prints "ERROR: <message>" to stderr and exits 1.
 */
const fs = require('fs');
const { aifToJson } = require('./decoder');

if (process.argv.includes('--self-test')) {
  const sample = [
    'AIF/0.9', '', '@single', 'name:s age:i', '@record', 'Alice', '30',
  ].join('\n');
  const out = aifToJson(sample);
  if (out.name !== 'Alice' || out.age !== 30) {
    console.error('ERROR: self-test failed');
    process.exit(1);
  }
  console.log('JS_DECODER_OK');
  process.exit(0);
}

let text = '';
try {
  text = fs.readFileSync(0, 'utf8');
} catch (err) {
  console.error('ERROR: cannot read stdin: ' + err.message);
  process.exit(1);
}

try {
  process.stdout.write(JSON.stringify(aifToJson(text)));
} catch (err) {
  console.error('ERROR: ' + err.message);
  process.exit(1);
}

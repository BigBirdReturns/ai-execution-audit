import assert from 'node:assert/strict';
import test from 'node:test';
import { readFile } from 'node:fs/promises';

const root = new URL('../', import.meta.url);

async function text(path) {
  return readFile(new URL(path, root), 'utf8');
}

function rgbToHue(red, green, blue) {
  const r = red / 255;
  const g = green / 255;
  const b = blue / 255;
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  const delta = max - min;
  if (delta === 0) return { hue: 0, saturation: 0 };
  let hue;
  if (max === r) hue = 60 * (((g - b) / delta) % 6);
  else if (max === g) hue = 60 * (((b - r) / delta) + 2);
  else hue = 60 * (((r - g) / delta) + 4);
  if (hue < 0) hue += 360;
  const lightness = (max + min) / 2;
  const saturation = delta / (1 - Math.abs(2 * lightness - 1));
  return { hue, saturation };
}

test('evaluator workspace is separate from automatic scenario evaluation', async () => {
  const html = await text('public/evaluator.html');
  assert.match(html, /SEPARATE EVALUATOR WORKSPACE/);
  assert.match(html, /Automatic evidence/);
  assert.match(html, /Evaluator disposition/);
  assert.match(html, /Disposition custody/);
  assert.match(html, /does not calculate scenario acceptance/);
  assert.match(html, /does not authenticate the evaluator/);
  assert.equal(/<style\b/i.test(html), false);
  assert.equal(/<script(?![^>]*src=)/i.test(html), false);
});

test('evaluator browser submits inputs and renders receipts without signing or acceptance logic', async () => {
  const app = await text('public/evaluator.js');
  for (const forbidden of [
    'createHash(',
    'generateKeyPairSync',
    'signBytes(',
    'verifyBytes(',
    'new MessageAuthorityRuntime',
    "from '../semantic/authority_sidecar.mjs'",
    'evaluationStatus === \'pass\' &&',
  ]) {
    assert.equal(app.includes(forbidden), false, `evaluator browser contains server-side token ${forbidden}`);
  }
  assert.match(app, /requestJson\('\/api\/state'/);
  assert.match(app, /requestJson\('\/api\/verify'/);
  assert.match(app, /requestJson\('\/api\/disposition'/);
  assert.match(app, /requestJson\('\/api\/disposition\/verify'/);
  assert.match(app, /requestJson\('\/api\/acceptance-package'/);
});

test('server owns evaluator signing, immutable registry, verification, and package assembly', async () => {
  const server = await text('server.mjs');
  assert.match(server, /createLocalEvaluatorSigner\(\)/);
  assert.match(server, /new EvaluatorDispositionRegistry/);
  assert.match(server, /url\.pathname === '\/api\/disposition'/);
  assert.match(server, /url\.pathname === '\/api\/disposition\/verify'/);
  assert.match(server, /url\.pathname === '\/api\/acceptance-package'/);
  assert.match(server, /verifySessionReceipt\(/);
  assert.match(server, /verifyEvaluatorDisposition\(/);
  assert.match(server, /createAcceptancePackage\(/);
});

test('evaluator workspace remains provider-neutral and outside the rejected green theme', async () => {
  const [html, app, css] = await Promise.all([
    text('public/evaluator.html'),
    text('public/evaluator.js'),
    text('public/evaluator.css'),
  ]);
  const combined = `${html}\n${app}\n${css}`;
  for (const phrase of [
    'axm',
    'dandelion',
    'polybolos',
    'defense solution arcade',
    'command core',
  ]) {
    assert.equal(new RegExp(phrase, 'i').test(combined), false, `evaluator surface contains ${phrase}`);
  }
  assert.equal(/\bgreen\b/i.test(css), false, 'evaluator stylesheet names green directly');
  for (const match of css.matchAll(/#[0-9a-f]{6}\b/gi)) {
    const color = match[0];
    const red = Number.parseInt(color.slice(1, 3), 16);
    const green = Number.parseInt(color.slice(3, 5), 16);
    const blue = Number.parseInt(color.slice(5, 7), 16);
    const { hue, saturation } = rgbToHue(red, green, blue);
    assert.equal(
      saturation > 0.18 && hue >= 72 && hue <= 172,
      false,
      `evaluator stylesheet contains rejected green-range color ${color}`,
    );
  }
});

test('runnable pack and role documentation include the evaluator lane', async () => {
  const [pack, docs, guide] = await Promise.all([
    text('build_pack.mjs'),
    text('docs/README.md'),
    text('docs/EVALUATOR_DISPOSITION.md'),
  ]);
  for (const path of [
    'rehearsal_console/evaluator_disposition.mjs',
    'public/evaluator.html',
    'public/evaluator.css',
    'public/evaluator.js',
  ]) assert.match(pack, new RegExp(path.replaceAll('.', '\\.')));
  assert.match(pack, /evaluatorDisposition: 'separate_local_signed_receipt'/);
  assert.match(docs, /EVALUATOR_DISPOSITION\.md/);
  assert.match(guide, /automatic non-pass cannot be locally accepted/i);
  assert.match(guide, /does not prove the evaluator's real-world identity/i);
});

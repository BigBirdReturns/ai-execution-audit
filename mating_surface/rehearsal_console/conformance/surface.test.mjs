import assert from 'node:assert/strict';
import test from 'node:test';
import { readFile } from 'node:fs/promises';

const root = new URL('../', import.meta.url);

async function text(path) {
  return readFile(new URL(path, root), 'utf8');
}

function rgbToHue(red, blueGreen, blue) {
  const r = red / 255;
  const g = blueGreen / 255;
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

function hexColors(css) {
  return [...css.matchAll(/#[0-9a-f]{6}\b/gi)].map((match) => match[0]);
}

test('public surface contains no provider, AXM, or rejected arcade branding', async () => {
  const combined = await Promise.all([
    text('public/index.html'),
    text('public/styles.css'),
    text('public/app.js'),
  ]).then((values) => values.join('\n'));
  for (const phrase of ['axm', 'dandelion', 'polybolos', 'defense solution arcade', 'command core']) {
    assert.equal(new RegExp(phrase, 'i').test(combined), false, `public surface contains ${phrase}`);
  }
  assert.equal(/https?:\/\//i.test(combined), false, 'public surface contains a remote URL');
});

test('visual palette contains no green theme colors', async () => {
  const css = await text('public/styles.css');
  assert.equal(/\bgreen\b/i.test(css), false, 'stylesheet names green directly');
  for (const color of hexColors(css)) {
    const red = Number.parseInt(color.slice(1, 3), 16);
    const blueGreen = Number.parseInt(color.slice(3, 5), 16);
    const blue = Number.parseInt(color.slice(5, 7), 16);
    const { hue, saturation } = rgbToHue(red, blueGreen, blue);
    assert.equal(
      saturation > 0.18 && hue >= 72 && hue <= 172,
      false,
      `stylesheet contains green-range color ${color} at hue ${hue.toFixed(1)}`,
    );
  }
});

test('browser code renders receipts and does not implement authority decisions', async () => {
  const app = await text('public/app.js');
  for (const forbidden of [
    'new MessageAuthorityRuntime',
    'createDefaultRehearsalAuthorityProfile',
    'allowedMessageClasses.includes',
    'offlineElapsedSteps >',
    'createHash(',
    "from '../semantic/authority_sidecar.mjs'",
  ]) {
    assert.equal(app.includes(forbidden), false, `browser code contains authority implementation token ${forbidden}`);
  }
  assert.match(app, /fetch\('\/api\/action'/);
  assert.match(app, /requestJson\('\/api\/state'/);
});

test('server-side session imports and instantiates the canonical authority runtime', async () => {
  const session = await text('session.mjs');
  assert.match(session, /from '\.\.\/semantic\/authority_sidecar\.mjs'/);
  assert.match(session, /new MessageAuthorityRuntime\(this\.profile\)/);
  assert.match(session, /runFaultScenario\(/);
  assert.match(session, /verifyConversation\(/);
});

test('host is loopback-only and serves a strict content security policy', async () => {
  const server = await text('server.mjs');
  assert.match(server, /host: '127\.0\.0\.1'/);
  assert.match(server, /the rehearsal console may bind only to the loopback interface/);
  assert.match(server, /default-src 'self'/);
  assert.match(server, /frame-ancestors 'none'/);
  assert.match(server, /object-src 'none'/);
});

test('HTML uses external presentation assets and states the execution boundary', async () => {
  const html = await text('public/index.html');
  assert.equal(/<style\b/i.test(html), false);
  assert.equal(/<script(?![^>]*src=)/i.test(html), false);
  assert.match(html, /The browser requests actions\. The server imports the canonical authority runtime/);
  assert.match(html, /No operational command, targeting, engagement, effector, execution, or weapons authority/);
});

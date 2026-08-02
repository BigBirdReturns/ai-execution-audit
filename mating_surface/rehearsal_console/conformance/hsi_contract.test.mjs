import assert from 'node:assert/strict';
import test from 'node:test';
import { readdir, readFile } from 'node:fs/promises';

const root = new URL('../', import.meta.url);

async function text(path) {
  return readFile(new URL(path, root), 'utf8');
}

const requiredDocuments = [
  'README.md',
  'OPERATOR_QUICKSTART.md',
  'USER_GUIDE.md',
  'TEST_CONDUCTOR_GUIDE.md',
  'VERIFIER_GUIDE.md',
  'INTERFACE_DESIGN_DESCRIPTION.md',
  'TEST_PLAN.md',
  'TEST_REPORT.md',
  'ACCESSIBILITY_AND_HUMAN_FACTORS.md',
  'TRACEABILITY_MATRIX.md',
  'VERSION_DESCRIPTION.md',
  'REFERENCE_BASELINE.md',
];

test('operator workflow separates plan, run, evaluation, evidence, and guidance', async () => {
  const html = await text('public/index.html');
  for (const view of ['plan', 'run', 'evaluate', 'evidence', 'guide']) {
    assert.match(html, new RegExp(`id="tab-${view}"[^>]*role="tab"`));
    assert.match(html, new RegExp(`id="view-${view}"[^>]*role="tabpanel"`));
  }
  assert.match(html, /role="tablist"/);
  assert.match(html, /Select a qualified scenario/);
  assert.match(html, /NEXT EXPECTED ACTION/);
  assert.match(html, /Expected versus observed/);
  assert.match(html, /Chronological evidence/);
});

test('run, communications, and authority state remain independent and color-independent', async () => {
  const html = await text('public/index.html');
  for (const id of ['runChip', 'commsChip', 'authorityChip', 'runPlane', 'linkPlane', 'authorityPlane']) {
    assert.match(html, new RegExp(`id="${id}"`));
  }
  assert.match(html, /<small>Run<\/small>/);
  assert.match(html, /<small>Communications<\/small>/);
  assert.match(html, /<small>Authority<\/small>/);
  assert.match(html, /status-symbol/);
  assert.match(html, /LATEST AUTHORITY RECEIPT/);
});

test('scenario cards declare objective, expected result, pass condition, and procedure before execution', async () => {
  const [html, app] = await Promise.all([
    text('public/index.html'),
    text('public/app.js'),
  ]);
  for (const id of ['scenarioObjective', 'scenarioExpected', 'scenarioPass', 'scenarioProcedure']) {
    assert.match(html, new RegExp(`id="${id}"`));
  }
  for (const scenario of [
    'baseline',
    'operatorAbsent',
    'leaseExpired',
    'isolated',
    'conflictingReturn',
    'noReturn',
  ]) {
    assert.match(app, new RegExp(`${scenario}:\\s*\\{`));
  }
  assert.match(app, /objective:/);
  assert.match(app, /expected:/);
  assert.match(app, /pass:/);
  assert.match(app, /procedure:/);
});

test('actions provide persistent feedback, recovery, and critical confirmations', async () => {
  const [html, app] = await Promise.all([
    text('public/index.html'),
    text('public/app.js'),
  ]);
  assert.match(html, /id="actionFeedback"[^>]*role="status"[^>]*aria-live="polite"[^>]*tabindex="-1"/);
  assert.match(html, /id="feedbackRecovery"/);
  assert.match(html, /id="confirmDialog"/);
  assert.match(html, /data-confirm="isolate"/);
  assert.match(html, /data-confirm="reconcile"/);
  assert.match(html, /data-confirm="reset"/);
  assert.match(app, /recoveryByCode/);
  assert.match(app, /Next expected action:/);
  assert.match(app, /SESSION_CLOSED/);
});

test('keyboard navigation and native semantic controls are present', async () => {
  const [html, app] = await Promise.all([
    text('public/index.html'),
    text('public/app.js'),
  ]);
  assert.match(html, /class="skip-link"/);
  assert.match(html, /<button[^>]+role="tab"/);
  assert.match(html, /<fieldset/);
  assert.match(html, /<legend/);
  assert.match(html, /<table class="acceptance-table">/);
  assert.match(html, /<dialog class="confirm-dialog"/);
  for (const key of ['ArrowLeft', 'ArrowRight', 'Home', 'End']) {
    assert.match(app, new RegExp(key));
  }
});

test('guide and package provide role-specific documentation without claiming formal compliance', async () => {
  const html = await text('public/index.html');
  const docs = await readdir(new URL('docs/', root));
  for (const name of requiredDocuments) {
    assert.equal(docs.includes(name), true, `missing support document ${name}`);
    assert.match(html, new RegExp(`/docs/${name.replace(/[.*+?^${}()|[\\]\\]/g, '\\$&')}`));
  }
  const combined = await Promise.all(requiredDocuments.map((name) => text(`docs/${name}`)))
    .then((values) => values.join('\n'));
  assert.match(combined, /Test conductor/);
  assert.match(combined, /Operator or mission/);
  assert.match(combined, /V&V reviewer|Verifier/);
  assert.match(combined, /Interface Design Description/);
  assert.match(combined, /Software Test Plan/);
  assert.match(combined, /Software Test Report/);
  assert.match(combined, /Formal Section 508|formal Section 508/);
  assert.match(combined, /MIL-STD-1472/);
  assert.match(combined, /does not claim formal|Formal .* pending|formal .* pending/i);
});

test('host serves packaged markdown documentation through the bounded static resolver', async () => {
  const server = await text('server.mjs');
  const pack = await text('build_pack.mjs');
  assert.match(server, /DEFAULT_DOCS_DIR/);
  assert.match(server, /url\.pathname === '\/docs'/);
  assert.match(server, /url\.pathname\.startsWith\('\/docs\/'\)/);
  assert.match(server, /text\/markdown; charset=utf-8/);
  assert.match(pack, /rehearsal_console\/docs/);
  assert.match(pack, /interactionModel: 'plan_run_evaluate_evidence_guide'/);
  assert.match(pack, /supportDocumentation: true/);
});

test('browser remains presentation-only while exposing verification and evidence tasks', async () => {
  const app = await text('public/app.js');
  for (const forbidden of [
    'new MessageAuthorityRuntime',
    'createDefaultRehearsalAuthorityProfile',
    "from '../semantic/authority_sidecar.mjs'",
    'allowedMessageClasses.includes',
  ]) {
    assert.equal(app.includes(forbidden), false, `browser contains authority token ${forbidden}`);
  }
  assert.match(app, /requestJson\('\/api\/action'/);
  assert.match(app, /requestJson\('\/api\/verify'/);
  assert.match(app, /requestJson\('\/api\/export'/);
  assert.match(app, /evaluationRows/);
  assert.match(app, /renderEvidence/);
});

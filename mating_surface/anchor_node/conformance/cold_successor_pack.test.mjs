import assert from 'node:assert/strict';
import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';
import {
  ColdSuccessorPackError,
  buildColdSuccessorPack,
  verifyColdSuccessorPack,
} from '../cold_successor_pack.mjs';

const SOURCE_COMMIT = '1'.repeat(40);
const PACK_FILE_COUNT = 15;

async function tempPack() {
  const root = await mkdtemp(join(tmpdir(), 'anchor-cold-successor-'));
  await buildColdSuccessorPack(root, { sourceCommit: SOURCE_COMMIT });
  return root;
}

function assertCode(promise, code) {
  return assert.rejects(
    promise,
    (error) => error instanceof ColdSuccessorPackError && error.code === code,
  );
}

test('cold successor pack builds and verifies the complete synthetic campaign', async (t) => {
  const root = await tempPack();
  t.after(() => rm(root, { recursive: true, force: true }));
  const receipt = await verifyColdSuccessorPack(root);
  assert.equal(receipt.status, 'PASS');
  assert.equal(receipt.fiveQuestionStatus, 'PASS');
  assert.equal(receipt.faultWorkerStatus, 'PASS');
  assert.equal(receipt.hostileRecoveryStatus, 'PASS');
  assert.equal(receipt.afterActionReceiptOnly, true);
  assert.equal(receipt.deterministicReconstruction, true);
  assert.equal(receipt.externalServiceCalls, 0);
  assert.equal(receipt.operationalCredentials, 0);
  assert.equal(receipt.latticeRequired, false);
  assert.equal(receipt.authority, 'none');
});

test('pack manifest binds the complete declared file denominator', async (t) => {
  const root = await tempPack();
  t.after(() => rm(root, { recursive: true, force: true }));
  const manifest = JSON.parse(await readFile(join(root, 'manifest.json'), 'utf8'));
  assert.equal(manifest.fileCount, PACK_FILE_COUNT);
  assert.equal(manifest.files.length, PACK_FILE_COUNT);
  assert.equal(new Set(manifest.files.map((row) => row.path)).size, PACK_FILE_COUNT);
  assert.deepEqual(
    manifest.files.slice(-6).map((row) => row.path),
    [
      'fault-worker-campaign.json',
      'fault-worker-verification.json',
      'hostile-recovery-campaign.json',
      'hostile-recovery-verification.json',
      'after-action.html',
      'five-question-answer.json',
    ],
  );
  assert.match(manifest.packId, /^anchorcoldsuccessorpack1_[0-9a-f]{64}$/);
});

test('five-question answer binds proof, authority, obligations, and safe next action', async (t) => {
  const root = await tempPack();
  t.after(() => rm(root, { recursive: true, force: true }));
  const answer = JSON.parse(await readFile(join(root, 'five-question-answer.json'), 'utf8'));
  assert.deepEqual(
    Object.keys(answer.questions).sort(),
    ['whatExists', 'whatIsUnresolved', 'whatIsSafeNext', 'whatProvesIt', 'whoMayAct'].sort(),
  );
  assert.equal(answer.questions.whoMayAct.modelAuthority, false);
  assert.equal(answer.questions.whatIsSafeNext.allowedEffect, 'local_review_only');
  assert.equal(answer.questions.whatProvesIt.receiptIds.length, 5);
  assert.equal(answer.questions.whatIsUnresolved.obligations.length, 3);
  assert.equal(answer.authority, 'none');
});

test('pack carries the receipt-only static after-action surface', async (t) => {
  const root = await tempPack();
  t.after(() => rm(root, { recursive: true, force: true }));
  const html = await readFile(join(root, 'after-action.html'), 'utf8');
  const campaign = JSON.parse(
    await readFile(join(root, 'hostile-recovery-campaign.json'), 'utf8'),
  );
  assert.match(html, /Spectra Anchor Node Mission Profile 01/);
  assert.match(html, /human_required/);
  assert.match(html, /INTERFACE_DRIFT/);
  assert.doesNotMatch(html, /<script/i);
  assert.equal(campaign.afterAction.generatedFromReceiptsOnly, true);
  assert.equal(campaign.afterAction.hiddenBrowserState, false);
});

test('repeated pack builds are byte-identical for one source commit', async (t) => {
  const a = await mkdtemp(join(tmpdir(), 'anchor-pack-a-'));
  const b = await mkdtemp(join(tmpdir(), 'anchor-pack-b-'));
  t.after(() => Promise.all([
    rm(a, { recursive: true, force: true }),
    rm(b, { recursive: true, force: true }),
  ]));
  const ma = await buildColdSuccessorPack(a, { sourceCommit: SOURCE_COMMIT });
  const mb = await buildColdSuccessorPack(b, { sourceCommit: SOURCE_COMMIT });
  assert.deepEqual(ma, mb);
  for (const row of ma.files) {
    assert.deepEqual(await readFile(join(a, row.path)), await readFile(join(b, row.path)));
  }
  assert.deepEqual(
    await readFile(join(a, 'manifest.json')),
    await readFile(join(b, 'manifest.json')),
  );
});

test('tampered pack file fails hash verification', async (t) => {
  const root = await tempPack();
  t.after(() => rm(root, { recursive: true, force: true }));
  const path = join(root, 'synthetic-observations.json');
  const original = await readFile(path, 'utf8');
  await writeFile(path, original.replace('eastbound', 'westbound'), 'utf8');
  await assertCode(verifyColdSuccessorPack(root), 'PACK_FILE_HASH_MISMATCH');
});

test('tampered after-action surface fails hash verification', async (t) => {
  const root = await tempPack();
  t.after(() => rm(root, { recursive: true, force: true }));
  const path = join(root, 'after-action.html');
  const original = await readFile(path, 'utf8');
  await writeFile(path, original.replace('INTERFACE_DRIFT', 'INTERFACE_SHIFT'), 'utf8');
  await assertCode(verifyColdSuccessorPack(root), 'PACK_FILE_HASH_MISMATCH');
});

test('missing pack file fails closed', async (t) => {
  const root = await tempPack();
  t.after(() => rm(root, { recursive: true, force: true }));
  await rm(join(root, 'vertical-slice.json'));
  await assertCode(verifyColdSuccessorPack(root), 'PACK_FILE_MISSING');
});

test('source commit must be an exact full hash', async (t) => {
  const root = await mkdtemp(join(tmpdir(), 'anchor-invalid-source-'));
  t.after(() => rm(root, { recursive: true, force: true }));
  await assertCode(
    buildColdSuccessorPack(root, { sourceCommit: 'main' }),
    'SOURCE_COMMIT_INVALID',
  );
});

test('manifest cannot make Lattice mandatory or grant authority', async (t) => {
  const root = await tempPack();
  t.after(() => rm(root, { recursive: true, force: true }));
  const path = join(root, 'manifest.json');
  const manifest = JSON.parse(await readFile(path, 'utf8'));
  manifest.latticeRequired = true;
  await writeFile(path, `${JSON.stringify(manifest, null, 2)}\n`, 'utf8');
  await assertCode(verifyColdSuccessorPack(root), 'MANIFEST_INVALID');
});

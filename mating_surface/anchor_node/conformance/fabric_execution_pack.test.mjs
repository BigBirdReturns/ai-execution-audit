import assert from 'node:assert/strict';
import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';
import {
  FabricExecutionPackError,
  buildFabricExecutionColdSuccessorPack,
  verifyFabricExecutionColdSuccessorPack,
} from '../fabric_execution_pack.mjs';

const SOURCE_COMMIT = '1'.repeat(40);

async function tempPack() {
  const root = await mkdtemp(join(tmpdir(), 'mp01-fabric-terminal-pack-'));
  const outDir = join(root, 'pack');
  const manifest = await buildFabricExecutionColdSuccessorPack(outDir, {
    sourceCommit: SOURCE_COMMIT,
  });
  return { root, outDir, manifest };
}

async function withPack(fn) {
  const pack = await tempPack();
  try {
    await fn(pack);
  } finally {
    await rm(pack.root, { recursive: true, force: true });
  }
}

function assertRejectCode(promise, code) {
  return assert.rejects(
    promise,
    (error) => error instanceof FabricExecutionPackError && error.code === code,
  );
}

test('terminal cold-successor pack builds and verifies the complete fabric campaign', async () => {
  await withPack(async ({ outDir, manifest }) => {
    const verification = await verifyFabricExecutionColdSuccessorPack(outDir);
    assert.equal(verification.status, 'PASS');
    assert.equal(verification.packId, manifest.packId);
    assert.equal(verification.acceptedCompletionCount, 1);
    assert.equal(verification.candidateCount, 6);
    assert.equal(verification.refusalCount, 5);
    assert.equal(verification.sixQuestionStatus, 'complete_for_synthetic_terminal_qualification');
    assert.equal(verification.deterministicReconstruction, true);
    assert.equal(verification.authority, 'none');
  });
});

test('pack manifest binds the complete declared file denominator', async () => {
  await withPack(async ({ outDir, manifest }) => {
    assert.equal(manifest.fileCount, 11);
    assert.equal(manifest.files.length, 11);
    assert.deepEqual(
      manifest.files.map((row) => row.path),
      [
        'fabric-profile.json',
        'invented-seat-registry.json',
        'synthetic-observations.json',
        'vertical-slice.json',
        'routing-slice.json',
        'routing-verification.json',
        'fabric-run.json',
        'terminal-verification.json',
        'receipt-only-projection.json',
        'receipt-only-review.html',
        'six-question-answer.json',
      ],
    );
    await verifyFabricExecutionColdSuccessorPack(outDir);
  });
});

test('six-question answer covers run, seat, qualification, proof, refusals, and unresolved work', async () => {
  await withPack(async ({ outDir }) => {
    const answer = JSON.parse(await readFile(join(outDir, 'six-question-answer.json'), 'utf8'));
    assert.deepEqual(Object.keys(answer.questions), [
      'whatRan',
      'whereItRan',
      'whyTheSeatQualified',
      'whatProvedCompletion',
      'whatWasRefused',
      'whatRemainsUnresolved',
    ]);
    assert.equal(answer.questions.whereItRan.leaseGeneration, 2);
    assert.equal(answer.questions.whyTheSeatQualified.memoryAggregationUsed, false);
    assert.equal(answer.questions.whatWasRefused.refusalIds.length, 5);
    assert.equal(answer.questions.whatRemainsUnresolved.physicalEstateQualified, false);
  });
});

test('repeated source-pinned pack builds are byte-identical', async () => {
  const root = await mkdtemp(join(tmpdir(), 'mp01-fabric-terminal-pack-repeat-'));
  try {
    const firstDir = join(root, 'a');
    const secondDir = join(root, 'b');
    const first = await buildFabricExecutionColdSuccessorPack(firstDir, {
      sourceCommit: SOURCE_COMMIT,
    });
    const second = await buildFabricExecutionColdSuccessorPack(secondDir, {
      sourceCommit: SOURCE_COMMIT,
    });
    assert.deepEqual(first, second);
    for (const row of first.files) {
      const [a, b] = await Promise.all([
        readFile(join(firstDir, row.path)),
        readFile(join(secondDir, row.path)),
      ]);
      assert.deepEqual(a, b);
    }
    assert.deepEqual(
      await readFile(join(firstDir, 'manifest.json')),
      await readFile(join(secondDir, 'manifest.json')),
    );
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test('tampered fabric run fails pack hash verification', async () => {
  await withPack(async ({ outDir }) => {
    const path = join(outDir, 'fabric-run.json');
    const bytes = await readFile(path);
    const changed = Buffer.from(bytes);
    const index = changed.indexOf(Buffer.from('completed_exactly_once'));
    assert.notEqual(index, -1);
    changed[index] = changed[index] === 99 ? 100 : 99;
    await writeFile(path, changed);
    await assertRejectCode(
      verifyFabricExecutionColdSuccessorPack(outDir),
      'PACK_FILE_HASH_MISMATCH',
    );
  });
});

test('tampered receipt-only HTML fails pack hash verification', async () => {
  await withPack(async ({ outDir }) => {
    const path = join(outDir, 'receipt-only-review.html');
    const bytes = await readFile(path);
    const changed = Buffer.from(bytes);
    changed[changed.length - 2] = changed[changed.length - 2] === 10 ? 32 : 10;
    await writeFile(path, changed);
    await assertRejectCode(
      verifyFabricExecutionColdSuccessorPack(outDir),
      'PACK_FILE_HASH_MISMATCH',
    );
  });
});

test('manifest cannot grant authority', async () => {
  await withPack(async ({ outDir }) => {
    const path = join(outDir, 'manifest.json');
    const manifest = JSON.parse(await readFile(path, 'utf8'));
    manifest.authority = 'field';
    await writeFile(path, `${JSON.stringify(manifest, null, 2)}\n`, 'utf8');
    await assertRejectCode(
      verifyFabricExecutionColdSuccessorPack(outDir),
      'PACK_CLAIM_INVALID',
    );
  });
});

test('source commit must be an exact full hash', async () => {
  const root = await mkdtemp(join(tmpdir(), 'mp01-fabric-terminal-pack-source-'));
  try {
    await assertRejectCode(
      buildFabricExecutionColdSuccessorPack(join(root, 'pack'), {
        sourceCommit: 'abc123',
      }),
      'SOURCE_COMMIT_INVALID',
    );
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test('receipt-only review remains static and local', async () => {
  await withPack(async ({ outDir }) => {
    const html = await readFile(join(outDir, 'receipt-only-review.html'), 'utf8');
    assert.match(html, /MP01 Estate Fabric Terminal Receipt/);
    assert.doesNotMatch(html, /<script/i);
    assert.doesNotMatch(html, /https?:\/\//i);
    assert.doesNotMatch(html, /fetch\s*\(/i);
  });
});

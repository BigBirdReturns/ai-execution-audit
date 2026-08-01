#!/usr/bin/env node
import { createHash } from 'node:crypto';
import {
  copyFileSync,
  mkdirSync,
  readFileSync,
  rmSync,
  writeFileSync,
} from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { spawnSync } from 'node:child_process';
import { pathToFileURL } from 'node:url';
import {
  createPartitionDecisionFrame,
  createPartitionReconciliationFrame,
} from './partition_cabinet.mjs';
import { verifyPartitionJournal } from './partition_evidence.mjs';

const HERE = dirname(new URL(import.meta.url).pathname);
const MAME_PLUGIN = join(HERE, 'cabinet', 'mame', 'polybolospartition', 'init.lua');
const MAME_HARNESS = join(HERE, 'cabinet', 'mame', 'test_harness.lua');
const MOTIONDECK_MANIFEST = join(
  HERE,
  'cabinet',
  'motiondeck',
  'polybolos-partition-bridge.json',
);

function writeJson(path, value) {
  mkdirSync(dirname(path), { recursive: true });
  writeFileSync(path, `${JSON.stringify(value, null, 2)}\n`, 'utf8');
}

function readJson(path) {
  return JSON.parse(readFileSync(path, 'utf8'));
}

function sha256(path) {
  return createHash('sha256').update(readFileSync(path)).digest('hex');
}

function requireCondition(condition, message) {
  if (!condition) throw new Error(message);
}

function normalizedKey(value) {
  return String(value).replace(/[^a-z0-9]/gi, '').toLowerCase();
}

function assertReadOnlyFrame(value, path = '$') {
  const forbidden = new Set([
    'payload',
    'signature',
    'privatekey',
    'command',
    'targeting',
    'engagement',
    'effector',
    'execute',
    'actuation',
    'weapon',
  ]);
  if (Array.isArray(value)) {
    value.forEach((row, index) => assertReadOnlyFrame(row, `${path}[${index}]`));
    return;
  }
  if (value === null || typeof value !== 'object') return;
  for (const [key, nested] of Object.entries(value)) {
    requireCondition(!forbidden.has(normalizedKey(key)), `forbidden frame key ${key} at ${path}`);
    assertReadOnlyFrame(nested, `${path}.${key}`);
  }
}

function observationForDecision(journal, decisionId) {
  const record = journal.records.find((row) =>
    row.event?.type === 'candidate_evaluated' && row.event?.decisionId === decisionId
  );
  requireCondition(record, `signed journal contains no record for decision ${decisionId}`);
  requireCondition(record.stateAfter?.lastObservation, `signed decision ${decisionId} has no retained observation`);
  return record.stateAfter.lastObservation;
}

function runMame(framePath, mode, disposition, logPath) {
  const result = spawnSync(
    'lua5.4',
    [MAME_HARNESS, MAME_PLUGIN, mode, disposition],
    {
      encoding: 'utf8',
      env: {
        ...process.env,
        POLYBOLOS_PARTITION_CABINET_FRAME: framePath,
      },
    },
  );
  writeFileSync(logPath, `${result.stdout ?? ''}${result.stderr ?? ''}`, 'utf8');
  requireCondition(result.status === 0, `MAME partition harness failed: ${result.stdout}${result.stderr}`);
  requireCondition(
    String(result.stdout).includes('POLYBOLOS_PARTITION_MAME_FRAME_PASS'),
    'MAME partition harness did not emit its pass token',
  );
}

function validateMotionDeckManifest() {
  const manifest = readJson(MOTIONDECK_MANIFEST);
  requireCondition(
    manifest.schema === 'polybolos-partition-authority-motiondeck-bridge/1',
    'MotionDeck partition bridge schema is invalid',
  );
  requireCondition(
    JSON.stringify(manifest.authority) === JSON.stringify(['observe.derived']),
    'MotionDeck partition bridge carries authority beyond observation',
  );
  requireCondition(manifest.mode === 'read-only-local-file', 'MotionDeck partition bridge is not local read-only');
  const forbidden = new Set(manifest.forbidden ?? []);
  for (const required of [
    'authority.command',
    'authority.delegate',
    'authority.reconcile',
    'authority.lease-reset',
    'execution.weapons',
    'output.input',
    'network.remote',
  ]) {
    requireCondition(forbidden.has(required), `MotionDeck bridge did not forbid ${required}`);
  }
  requireCondition(
    manifest.input?.schema === 'polybolos-partition-cabinet-frame/1',
    'MotionDeck bridge expects the wrong frame schema',
  );
  return manifest;
}

async function main(argv) {
  if (argv.length !== 2) {
    console.error('usage: run_partition_cabinet_e2e.mjs <partition-authority-e2e-dir> <output-dir>');
    return 2;
  }
  const inputDir = resolve(argv[0]);
  const outputDir = resolve(argv[1]);
  rmSync(outputDir, { recursive: true, force: true });
  mkdirSync(outputDir, { recursive: true });

  for (const required of [MAME_PLUGIN, MAME_HARNESS, MOTIONDECK_MANIFEST]) {
    requireCondition(readFileSync(required).length > 0, `cabinet dependency is missing: ${required}`);
  }

  const authority = readJson(join(inputDir, 'partition-authority.json'));
  const returningAuthority = readJson(join(inputDir, 'returning-authority.json'));
  const authorityTrustStore = readJson(join(inputDir, 'authority-trust.json'));
  const nodeTrustStore = readJson(join(inputDir, 'node-trust.json'));
  const initialDecision = readJson(join(inputDir, 'decision-partitionInitial.json'));
  const expiredDecision = readJson(join(inputDir, 'decision-expiredPartition.json'));
  const restoredObservation = readJson(join(inputDir, 'link-restored.json'));
  const reconciliation = readJson(join(inputDir, 'reconciliation.json'));
  const journalPath = join(inputDir, 'partition-authority.journal');
  const journal = verifyPartitionJournal(journalPath, nodeTrustStore);

  const initialObservation = observationForDecision(journal, initialDecision.decisionId);
  const expiredObservation = observationForDecision(journal, expiredDecision.decisionId);
  const initialFrame = createPartitionDecisionFrame({
    authority,
    authorityTrustStore,
    observation: initialObservation,
    nodeTrustStore,
    decision: initialDecision,
    journalPath,
    capturedAt: initialDecision.checkedAt,
  });
  const initialFrameRecaptured = createPartitionDecisionFrame({
    authority,
    authorityTrustStore,
    observation: initialObservation,
    nodeTrustStore,
    decision: initialDecision,
    journalPath,
    capturedAt: new Date(Date.parse(initialDecision.checkedAt) + 1_000).toISOString(),
  });
  const expiredFrame = createPartitionDecisionFrame({
    authority,
    authorityTrustStore,
    observation: expiredObservation,
    nodeTrustStore,
    decision: expiredDecision,
    journalPath,
    capturedAt: expiredDecision.checkedAt,
  });
  const reconciliationFrame = createPartitionReconciliationFrame({
    returningAuthority,
    authorityTrustStore,
    restoredObservation,
    nodeTrustStore,
    reconciliation,
    journalPath,
    capturedAt: reconciliation.reconciledAt,
  });

  const initialPath = join(outputDir, 'partition-frame-eligible.json');
  const expiredPath = join(outputDir, 'partition-frame-safe-state.json');
  const reconciliationPath = join(outputDir, 'partition-frame-reconciled.json');
  writeJson(initialPath, initialFrame);
  writeJson(join(outputDir, 'partition-frame-eligible-recaptured.json'), initialFrameRecaptured);
  writeJson(expiredPath, expiredFrame);
  writeJson(reconciliationPath, reconciliationFrame);

  for (const frame of [initialFrame, initialFrameRecaptured, expiredFrame, reconciliationFrame]) {
    assertReadOnlyFrame(frame);
    requireCondition(frame.verification?.signedJournal === true, 'frame omitted signed journal verification');
    requireCondition(frame.lamps?.signedEvidence === true, 'frame omitted signed evidence lamp');
    requireCondition(frame.evidence?.journalSha256 === journal.journalSha256, 'frame cites the wrong journal');
  }
  requireCondition(initialFrame.stateId === initialFrameRecaptured.stateId, 'recapture changed semantic partition state');
  requireCondition(initialFrame.frameId !== initialFrameRecaptured.frameId, 'recapture did not change capture identity');
  requireCondition(initialFrame.disposition === 'allow', 'eligible partition frame did not remain allowed');
  requireCondition(initialFrame.lamps.partitioned && initialFrame.lamps.candidateEligible, 'eligible partition lamps are wrong');
  requireCondition(expiredFrame.disposition === 'safe_state', 'expired lease frame did not enter safe state');
  requireCondition(expiredFrame.lamps.safeState && expiredFrame.lamps.leaseExpired, 'expired lease lamps are wrong');
  requireCondition(expiredFrame.reasonCode === 'partition_offline_lease_expired', 'expired lease reason is wrong');
  requireCondition(
    reconciliationFrame.disposition === 'explicitly_superseded'
      && reconciliationFrame.lamps.reconciliationComplete,
    'reconciliation frame did not show explicit completion',
  );

  const tamperedDecision = structuredClone(expiredDecision);
  tamperedDecision.disposition = 'allow';
  let tamperedDecisionRefused = false;
  try {
    createPartitionDecisionFrame({
      authority,
      authorityTrustStore,
      observation: expiredObservation,
      nodeTrustStore,
      decision: tamperedDecision,
      journalPath,
      capturedAt: expiredDecision.checkedAt,
    });
  } catch {
    tamperedDecisionRefused = true;
  }
  requireCondition(tamperedDecisionRefused, 'tampered decision produced a cabinet frame');

  const tamperedJournalPath = join(outputDir, 'tampered-partition-authority.journal');
  copyFileSync(journalPath, tamperedJournalPath);
  const lines = readFileSync(tamperedJournalPath, 'utf8').trimEnd().split('\n');
  const tamperedRecord = JSON.parse(lines.at(-1));
  tamperedRecord.event.disposition = 'allow';
  lines[lines.length - 1] = JSON.stringify(tamperedRecord);
  writeFileSync(tamperedJournalPath, `${lines.join('\n')}\n`, 'utf8');
  let tamperedJournalRefused = false;
  try {
    createPartitionReconciliationFrame({
      returningAuthority,
      authorityTrustStore,
      restoredObservation,
      nodeTrustStore,
      reconciliation,
      journalPath: tamperedJournalPath,
      capturedAt: reconciliation.reconciledAt,
    });
  } catch {
    tamperedJournalRefused = true;
  }
  requireCondition(tamperedJournalRefused, 'tampered journal produced a cabinet frame');

  const motionDeckManifest = validateMotionDeckManifest();
  runMame(initialPath, 'candidate', 'allow', join(outputDir, 'mame-eligible.log'));
  runMame(expiredPath, 'candidate', 'safe_state', join(outputDir, 'mame-safe-state.log'));
  runMame(
    reconciliationPath,
    'reconciliation',
    'explicitly_superseded',
    join(outputDir, 'mame-reconciled.log'),
  );

  const receipt = {
    schema: 'ai-execution-audit/polybolos-partition-cabinet-e2e@1',
    status: 'pass',
    identities: {
      journalSha256: journal.journalSha256,
      journalLastRecordId: journal.lastRecordId,
      eligibleStateId: initialFrame.stateId,
      eligibleFrameId: initialFrame.frameId,
      safeStateId: expiredFrame.stateId,
      safeFrameId: expiredFrame.frameId,
      reconciliationStateId: reconciliationFrame.stateId,
      reconciliationFrameId: reconciliationFrame.frameId,
    },
    checks: {
      candidate_frame_verified_against_signed_journal: true,
      safe_state_frame_verified_against_signed_journal: true,
      reconciliation_frame_verified_against_signed_journal: true,
      recapture_preserves_semantic_state_and_changes_capture_identity: true,
      tampered_decision_refused: tamperedDecisionRefused,
      tampered_journal_refused: tamperedJournalRefused,
      mame_reads_eligible_frame_offline: true,
      mame_reads_safe_state_frame_offline: true,
      mame_reads_reconciliation_frame_offline: true,
      motiondeck_bridge_observation_only: motionDeckManifest.authority[0] === 'observe.derived',
    },
    artifacts: Object.fromEntries(
      [
        'partition-frame-eligible.json',
        'partition-frame-eligible-recaptured.json',
        'partition-frame-safe-state.json',
        'partition-frame-reconciled.json',
        'tampered-partition-authority.journal',
        'mame-eligible.log',
        'mame-safe-state.log',
        'mame-reconciled.log',
      ].map((name) => {
        const path = join(outputDir, name);
        return [name, { bytes: readFileSync(path).length, sha256: sha256(path) }];
      }),
    ),
    claimBoundary:
      'This transaction projects signed partition-authority receipts into read-only MAME and MotionDeck diagnostic surfaces. It grants no command, targeting, engagement, effector, emulator-input, process-launch, weapons-employment, or combat-effectiveness authority or claim.',
  };
  writeJson(join(outputDir, 'partition-cabinet-e2e-receipt.json'), receipt);
  process.stdout.write(`${JSON.stringify(receipt, null, 2)}\n`);
  return 0;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  process.exitCode = await main(process.argv.slice(2));
}

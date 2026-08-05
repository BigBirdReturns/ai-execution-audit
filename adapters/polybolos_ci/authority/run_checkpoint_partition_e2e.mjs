#!/usr/bin/env node
import { createHash, generateKeyPairSync } from 'node:crypto';
import {
  appendFileSync,
  mkdirSync,
  readFileSync,
  rmSync,
  writeFileSync,
} from 'node:fs';
import { dirname, join } from 'node:path';
import { pathToFileURL } from 'node:url';
import {
  signAuthorityEnvelope,
  signLinkObservation,
} from './partition_runtime.mjs';
import { CheckpointPartitionAuthorityRuntime } from './checkpoint_partition_runtime.mjs';
import { verifyPartitionJournal } from './partition_evidence.mjs';

function writeJson(path, value) {
  mkdirSync(dirname(path), { recursive: true });
  writeFileSync(path, `${JSON.stringify(value, null, 2)}\n`, 'utf8');
}

function sha256(path) {
  return createHash('sha256').update(readFileSync(path)).digest('hex');
}

function iso(milliseconds) {
  return new Date(milliseconds).toISOString();
}

function keyPair() {
  const { privateKey, publicKey } = generateKeyPairSync('ed25519');
  return {
    privateKeyPem: privateKey.export({ type: 'pkcs8', format: 'pem' }),
    publicKeyPem: publicKey.export({ type: 'spki', format: 'pem' }),
  };
}

function percentile(values, fraction) {
  const ordered = [...values].sort((a, b) => a - b);
  if (ordered.length === 0) throw new Error('percentile requires values');
  if (ordered.length === 1) return ordered[0];
  const position = (ordered.length - 1) * fraction;
  const lower = Math.floor(position);
  const upper = Math.ceil(position);
  if (lower === upper) return ordered[lower];
  const weight = position - lower;
  return ordered[lower] * (1 - weight) + ordered[upper] * weight;
}

function authorityBody(transaction, overrides = {}) {
  const checkpointMs = Date.parse(transaction.checkpoint.observedAt);
  const candidateMs = Date.parse(transaction.candidate.createdAt);
  return {
    schema: 'axm-command-authority/1',
    issuer: 'fixture-commander',
    subject: 'polybolos-command-candidate',
    notBefore: iso(checkpointMs - 1_000),
    expiresAt: iso(candidateMs + 20 * 60_000),
    maxObservationAgeMs: 20 * 60_000,
    allowedProducers: [transaction.candidate.producer],
    allowedActionClasses: [transaction.candidate.actionClass],
    allowedSoftwareRecordIds: [transaction.checkpoint.softwareRecordId],
    maxEvidenceWitnesses: transaction.witnesses.length,
    maxObservedEntities: transaction.checkpoint.entityCount,
    requiredPayloadFields: ['entityIds', 'priority'],
    allowedPayloadFields: ['entityIds', 'priority', 'explanation'],
    maxPayloadBytes: 4_096,
    partitionPolicy: {
      links: ['headquarters', 'local-control'],
      profiles: [
        {
          id: 'connected',
          states: { headquarters: 'up', 'local-control': 'up' },
          partition: false,
          allowedActionClasses: [transaction.candidate.actionClass],
          maxOfflineMs: 0,
          requiresLocalOperator: false,
          expiryDisposition: 'safe_state',
        },
        {
          id: 'headquarters-denied',
          states: { headquarters: 'down', 'local-control': 'up' },
          partition: true,
          allowedActionClasses: [transaction.candidate.actionClass],
          maxOfflineMs: 5_000,
          requiresLocalOperator: true,
          expiryDisposition: 'safe_state',
        },
        {
          id: 'total-isolation',
          states: { headquarters: 'down', 'local-control': 'down' },
          partition: true,
          allowedActionClasses: [],
          maxOfflineMs: 1_000,
          requiresLocalOperator: false,
          expiryDisposition: 'safe_state',
        },
      ],
    },
    ...overrides,
  };
}

function observation(nodeKeys, observedAt, links, localOperatorPresent = true) {
  return signLinkObservation(
    {
      schema: 'axm-link-observation/1',
      nodeId: 'fixture-node-1',
      observedAt,
      links,
      localOperatorPresent,
    },
    'node-key-1',
    nodeKeys.privateKeyPem,
  );
}

function reasonCode(decision) {
  return decision.reason?.code ?? decision.baseDecision?.reasons?.[0]?.code;
}

async function main(argv) {
  if (argv.length !== 2) {
    console.error('usage: run_checkpoint_partition_e2e.mjs <bounded-candidate-transaction.json> <output-dir>');
    return 2;
  }
  const [transactionPath, outputDir] = argv;
  rmSync(outputDir, { recursive: true, force: true });
  mkdirSync(outputDir, { recursive: true });
  const transaction = JSON.parse(readFileSync(transactionPath, 'utf8'));
  if (transaction.schema !== 'polybolos-command-candidate-transaction/2') {
    throw new Error('bounded CI candidate transaction is missing or invalid');
  }
  if ('snapshot' in transaction || 'entities' in transaction.checkpoint) {
    throw new Error('bounded transaction unexpectedly contains the full COP');
  }

  const authorityKeys = keyPair();
  const nodeKeys = keyPair();
  const authorityTrustStore = {
    schema: 'axm-authority-trust/1',
    keys: [{
      keyId: 'authority-key-1',
      issuer: 'fixture-commander',
      algorithm: 'Ed25519',
      publicKeyPem: authorityKeys.publicKeyPem,
    }],
  };
  const nodeTrustStore = {
    schema: 'axm-node-trust/1',
    keys: [{
      keyId: 'node-key-1',
      nodeId: 'fixture-node-1',
      algorithm: 'Ed25519',
      publicKeyPem: nodeKeys.publicKeyPem,
    }],
  };
  const authority = signAuthorityEnvelope(
    authorityBody(transaction),
    'authority-key-1',
    authorityKeys.privateKeyPem,
  );
  writeJson(join(outputDir, 'authority-trust.json'), authorityTrustStore);
  writeJson(join(outputDir, 'node-trust.json'), nodeTrustStore);
  writeJson(join(outputDir, 'checkpoint-authority.json'), authority);
  writeFileSync(join(outputDir, 'node-public.pem'), nodeKeys.publicKeyPem, 'utf8');

  const candidateBaseMs = Date.parse(transaction.candidate.createdAt);
  let clockMs = candidateBaseMs + 1_000;
  const clock = () => clockMs;
  const setClock = (offsetMs) => {
    clockMs = candidateBaseMs + offsetMs;
  };
  const journalPath = join(outputDir, 'checkpoint-partition-authority.journal');
  const runtimeConfig = {
    journalPath,
    nodeId: 'fixture-node-1',
    journalKeyId: 'node-key-1',
    journalPrivateKeyPem: nodeKeys.privateKeyPem,
    nodeTrustStore,
    authorityTrustStore,
    clock,
  };
  const checks = {};
  const decisions = {};
  const warmDecisionMs = [];
  let runtime = new CheckpointPartitionAuthorityRuntime(runtimeConfig);

  const connectedObservation = observation(
    nodeKeys,
    iso(clockMs),
    { headquarters: 'up', 'local-control': 'up' },
  );
  writeJson(join(outputDir, 'link-connected.json'), connectedObservation);
  runtime.observe(connectedObservation, authority);
  decisions.connected = runtime.evaluateCheckpoint(transaction, authority);
  if (decisions.connected.disposition !== 'allow') {
    throw new Error(`connected checkpoint candidate was not eligible: ${reasonCode(decisions.connected)}`);
  }
  if (decisions.connected.baseDecision.checkpointVerified !== true) {
    throw new Error('connected decision did not verify its checkpoint');
  }
  checks.actual_bounded_ci_candidate_allowed_while_connected = true;

  const wrongSoftwareAuthority = signAuthorityEnvelope(
    authorityBody(transaction, { allowedSoftwareRecordIds: ['unapproved-build'] }),
    'authority-key-1',
    authorityKeys.privateKeyPem,
  );
  decisions.wrongSoftware = runtime.evaluateCheckpoint(transaction, wrongSoftwareAuthority);
  if (
    decisions.wrongSoftware.disposition !== 'refuse'
    || reasonCode(decisions.wrongSoftware) !== 'checkpoint_software_not_authorized'
  ) {
    throw new Error('unapproved checkpoint software identity was not refused');
  }
  checks.software_identity_is_inside_signed_authority = true;

  setClock(2_000);
  const partitionObservation = observation(
    nodeKeys,
    iso(clockMs),
    { headquarters: 'down', 'local-control': 'up' },
  );
  writeJson(join(outputDir, 'link-headquarters-denied.json'), partitionObservation);
  const partitionReceipt = runtime.observe(partitionObservation, authority);
  const epochId = partitionReceipt.activeEpochId;
  const epochStartedAt = runtime.snapshot().activeEpoch.startedAt;
  if (!epochId) throw new Error('partition observation did not create an epoch');
  decisions.partitionInitial = runtime.evaluateCheckpoint(transaction, authority);
  if (decisions.partitionInitial.disposition !== 'allow') {
    throw new Error(`partition candidate was not eligible: ${reasonCode(decisions.partitionInitial)}`);
  }
  checks.signed_headquarters_loss_starts_one_checkpoint_epoch = true;
  checks.checkpoint_candidate_survives_admitted_partition = true;

  setClock(4_000);
  const repeatedObservation = observation(
    nodeKeys,
    iso(clockMs),
    { headquarters: 'down', 'local-control': 'up' },
  );
  const repeatedReceipt = runtime.observe(repeatedObservation, authority);
  if (repeatedReceipt.activeEpochId !== epochId) throw new Error('repeated observation reset the epoch');
  if (runtime.snapshot().activeEpoch.startedAt !== epochStartedAt) {
    throw new Error('repeated observation reset the offline lease');
  }
  checks.repeated_observation_cannot_reset_checkpoint_lease = true;

  for (let index = 0; index < 50; index += 1) {
    setClock(4_100 + index);
    const started = process.hrtime.bigint();
    const decision = runtime.evaluateCheckpoint(transaction, authority);
    const elapsedMs = Number(process.hrtime.bigint() - started) / 1_000_000;
    if (decision.disposition !== 'allow') {
      throw new Error(`warm checkpoint decision failed: ${reasonCode(decision)}`);
    }
    warmDecisionMs.push(elapsedMs);
  }
  checks.fifty_checkpoint_authority_decisions_remain_inside_lease = true;

  setClock(4_500);
  const absentOperator = observation(
    nodeKeys,
    iso(clockMs),
    { headquarters: 'down', 'local-control': 'up' },
    false,
  );
  runtime.observe(absentOperator, authority);
  decisions.operatorAbsent = runtime.evaluateCheckpoint(transaction, authority);
  if (
    decisions.operatorAbsent.disposition !== 'safe_state'
    || reasonCode(decisions.operatorAbsent) !== 'partition_local_operator_absent'
  ) {
    throw new Error('missing local operator did not enter safe state');
  }
  checks.local_operator_requirement_is_runtime_owned = true;

  setClock(4_700);
  const operatorRestored = observation(
    nodeKeys,
    iso(clockMs),
    { headquarters: 'down', 'local-control': 'up' },
    true,
  );
  runtime.observe(operatorRestored, authority);
  decisions.operatorRestored = runtime.evaluateCheckpoint(transaction, authority);
  if (decisions.operatorRestored.disposition !== 'allow') {
    throw new Error('restored local operator did not recover candidate eligibility');
  }

  runtime.close();
  setClock(5_000);
  runtime = new CheckpointPartitionAuthorityRuntime(runtimeConfig);
  if (runtime.snapshot().activeEpoch.epochId !== epochId) throw new Error('restart changed the active epoch');
  if (runtime.snapshot().activeEpoch.startedAt !== epochStartedAt) throw new Error('restart reset the offline lease');
  decisions.partitionAfterRestart = runtime.evaluateCheckpoint(transaction, authority);
  if (decisions.partitionAfterRestart.disposition !== 'allow') {
    throw new Error(`candidate failed inside replayed partition: ${reasonCode(decisions.partitionAfterRestart)}`);
  }
  checks.restart_preserves_checkpoint_epoch_and_lease = true;

  setClock(8_000);
  decisions.expiredPartition = runtime.evaluateCheckpoint(transaction, authority);
  if (
    decisions.expiredPartition.disposition !== 'safe_state'
    || reasonCode(decisions.expiredPartition) !== 'partition_offline_lease_expired'
  ) {
    throw new Error('expired checkpoint offline lease did not enter safe state');
  }
  checks.runtime_owned_checkpoint_lease_expires_safe = true;

  setClock(8_500);
  const totalIsolation = observation(
    nodeKeys,
    iso(clockMs),
    { headquarters: 'down', 'local-control': 'down' },
    false,
  );
  runtime.observe(totalIsolation, authority);
  decisions.totalIsolation = runtime.evaluateCheckpoint(transaction, authority);
  if (
    decisions.totalIsolation.disposition !== 'refuse'
    || reasonCode(decisions.totalIsolation) !== 'partition_action_not_surviving'
  ) {
    throw new Error('action class incorrectly survived total isolation');
  }
  checks.total_isolation_refuses_unlisted_action_class = true;

  setClock(9_000);
  const restoredObservation = observation(
    nodeKeys,
    iso(clockMs),
    { headquarters: 'up', 'local-control': 'up' },
  );
  writeJson(join(outputDir, 'link-restored.json'), restoredObservation);
  runtime.observe(restoredObservation, authority);
  if (runtime.snapshot().pendingReconciliation?.epoch?.epochId !== epochId) {
    throw new Error('communications restoration did not preserve the checkpoint partition');
  }
  checks.reconnect_preserves_checkpoint_decision_history = true;

  const nonSupersedingAuthority = signAuthorityEnvelope(
    authorityBody(transaction, { note: 'returning authority without explicit supersession' }),
    'authority-key-1',
    authorityKeys.privateKeyPem,
  );
  const humanRequired = runtime.reconcile(nonSupersedingAuthority);
  writeJson(join(outputDir, 'reconciliation-human-required.json'), humanRequired);
  if (humanRequired.disposition !== 'human_required') {
    throw new Error('non-superseding authority silently reconciled the partition');
  }
  if (!runtime.snapshot().pendingReconciliation) {
    throw new Error('human-required reconciliation cleared pending history');
  }
  checks.non_superseding_authority_remains_human_required = true;

  const returningAuthority = signAuthorityEnvelope(
    authorityBody(transaction, { supersedes: [authority.authorityId] }),
    'authority-key-1',
    authorityKeys.privateKeyPem,
  );
  writeJson(join(outputDir, 'returning-authority.json'), returningAuthority);
  const reconciliation = runtime.reconcile(returningAuthority);
  writeJson(join(outputDir, 'reconciliation-explicit.json'), reconciliation);
  if (reconciliation.disposition !== 'explicitly_superseded') {
    throw new Error('explicit returning authority did not reconcile the partition');
  }
  if (!reconciliation.localDecisionIds.includes(decisions.expiredPartition.decisionId)) {
    throw new Error('reconciliation omitted a local checkpoint decision');
  }
  checks.explicit_supersession_reconciles_without_rewriting_history = true;
  runtime.close();

  const signedPrefix = readFileSync(journalPath);
  const journalVerification = verifyPartitionJournal(journalPath, nodeTrustStore);
  if (journalVerification.recordCount < 60) {
    throw new Error('signed journal omitted checkpoint decisions');
  }
  checks.node_signed_journal_verifies_detached = true;

  const incompleteTail = Buffer.from('{"incomplete":', 'utf8');
  appendFileSync(journalPath, incompleteTail);
  const recovered = new CheckpointPartitionAuthorityRuntime(runtimeConfig);
  if (recovered.snapshot().diagnostics.truncatedTailBytes !== incompleteTail.length) {
    throw new Error('checkpoint partition journal did not report the incomplete tail');
  }
  recovered.close();
  if (!readFileSync(journalPath).equals(signedPrefix)) {
    throw new Error('checkpoint partition journal recovery rewrote the signed prefix');
  }
  checks.incomplete_tail_recovers_exact_checkpoint_prefix = true;

  for (const [name, decision] of Object.entries(decisions)) {
    writeJson(join(outputDir, `decision-${name}.json`), decision);
  }

  const metrics = {
    transactionBytes: readFileSync(transactionPath).length,
    checkpointEntityCount: transaction.checkpoint.entityCount,
    witnessCount: transaction.witnesses.length,
    witnessDepths: transaction.witnesses.map((row) => row.siblings.length),
    warmDecisionSamples: warmDecisionMs.length,
    warmDecisionP50Ms: Number(percentile(warmDecisionMs, 0.50).toFixed(3)),
    warmDecisionP95Ms: Number(percentile(warmDecisionMs, 0.95).toFixed(3)),
    warmDecisionP99Ms: Number(percentile(warmDecisionMs, 0.99).toFixed(3)),
    signedJournalRecords: journalVerification.recordCount,
    localDecisionCount: reconciliation.localDecisionIds.length,
  };
  writeJson(join(outputDir, 'checkpoint-partition-performance.json'), metrics);

  const artifactNames = [
    'checkpoint-authority.json',
    'returning-authority.json',
    'authority-trust.json',
    'node-trust.json',
    'node-public.pem',
    'link-connected.json',
    'link-headquarters-denied.json',
    'link-restored.json',
    'reconciliation-human-required.json',
    'reconciliation-explicit.json',
    'checkpoint-partition-authority.journal',
    'checkpoint-partition-performance.json',
    ...Object.keys(decisions).map((name) => `decision-${name}.json`),
  ];
  const receipt = {
    schema: 'ai-execution-audit/polybolos-ci-checkpoint-partition-e2e@1',
    status: 'pass',
    actualCiTransaction: {
      checkpointId: transaction.checkpoint.checkpointId,
      candidateId: transaction.candidate.candidateId,
      softwareRecordId: transaction.checkpoint.softwareRecordId,
      transactionSha256: sha256(transactionPath),
    },
    identities: {
      authorityId: authority.authorityId,
      returningAuthorityId: returningAuthority.authorityId,
      epochId,
      epochStartedAt,
      humanRequiredReconciliationId: humanRequired.reconciliationId,
      explicitReconciliationId: reconciliation.reconciliationId,
      journalSha256: sha256(journalPath),
      lastRecordId: recovered.snapshot().diagnostics.lastRecordId,
    },
    decisions: Object.fromEntries(
      Object.entries(decisions).map(([name, decision]) => [name, {
        decisionId: decision.decisionId,
        disposition: decision.disposition,
        reasonCode: reasonCode(decision),
        checkpointId: decision.checkpointId,
      }]),
    ),
    checks,
    metrics,
    artifacts: Object.fromEntries(
      artifactNames.map((name) => {
        const path = join(outputDir, name);
        return [name, { bytes: readFileSync(path).length, sha256: sha256(path) }];
      }),
    ),
    claimBoundary:
      'This transaction applies signed software, evidence, and communications-partition constraints to a bounded candidate from the actual public Command Intelligence server. It carries no actuation, targeting, engagement, effector, emulator-input, weapons-employment, or combat-effectiveness claim.',
  };
  writeJson(join(outputDir, 'checkpoint-partition-e2e-receipt.json'), receipt);
  process.stdout.write(`${JSON.stringify(receipt, null, 2)}\n`);
  return 0;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  process.exitCode = await main(process.argv.slice(2));
}

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
  PartitionAuthorityRuntime,
  signAuthorityEnvelope,
  signLinkObservation,
  verifyLinkObservation,
} from './partition_runtime.mjs';

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

function authorityBody(transaction, overrides = {}) {
  const snapshotMs = Date.parse(transaction.snapshot.observedAt);
  const candidateMs = Date.parse(transaction.candidate.createdAt);
  return {
    schema: 'axm-command-authority/1',
    issuer: 'fixture-commander',
    subject: 'polybolos-command-candidate',
    notBefore: iso(snapshotMs - 1_000),
    expiresAt: iso(candidateMs + 20 * 60_000),
    maxSnapshotAgeMs: 20 * 60_000,
    allowedProducers: [transaction.candidate.producer],
    allowedActionClasses: [transaction.candidate.actionClass],
    requiredPayloadFields: ['entityId', 'priority'],
    allowedPayloadFields: ['entityId', 'priority', 'explanation'],
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
    console.error('usage: run_partition_authority_e2e.mjs <candidate-transaction.json> <output-dir>');
    return 2;
  }
  const [transactionPath, outputDir] = argv;
  rmSync(outputDir, { recursive: true, force: true });
  mkdirSync(outputDir, { recursive: true });
  const transaction = JSON.parse(readFileSync(transactionPath, 'utf8'));
  if (transaction.schema !== 'polybolos-command-candidate-transaction/1') {
    throw new Error('actual CI candidate transaction is missing or invalid');
  }

  const authorityKeys = keyPair();
  const nodeKeys = keyPair();
  const authorityTrustStore = {
    schema: 'axm-authority-trust/1',
    keys: [
      {
        keyId: 'authority-key-1',
        issuer: 'fixture-commander',
        algorithm: 'Ed25519',
        publicKeyPem: authorityKeys.publicKeyPem,
      },
    ],
  };
  const nodeTrustStore = {
    schema: 'axm-node-trust/1',
    keys: [
      {
        keyId: 'node-key-1',
        nodeId: 'fixture-node-1',
        algorithm: 'Ed25519',
        publicKeyPem: nodeKeys.publicKeyPem,
      },
    ],
  };
  const authority = signAuthorityEnvelope(
    authorityBody(transaction),
    'authority-key-1',
    authorityKeys.privateKeyPem,
  );
  writeJson(join(outputDir, 'authority-trust.json'), authorityTrustStore);
  writeJson(join(outputDir, 'node-trust.json'), nodeTrustStore);
  writeJson(join(outputDir, 'partition-authority.json'), authority);
  writeFileSync(join(outputDir, 'node-public.pem'), nodeKeys.publicKeyPem, 'utf8');

  let clockMs = Date.parse(transaction.candidate.createdAt) + 1_000;
  const clock = () => clockMs;
  const setClock = (offsetMs) => {
    clockMs = Date.parse(transaction.candidate.createdAt) + offsetMs;
  };
  const journalPath = join(outputDir, 'partition-authority.journal');
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
  let runtime = new PartitionAuthorityRuntime(runtimeConfig);

  const connectedObservation = observation(
    nodeKeys,
    iso(clockMs),
    { headquarters: 'up', 'local-control': 'up' },
  );
  writeJson(join(outputDir, 'link-connected.json'), connectedObservation);
  runtime.observe(connectedObservation, authority);
  decisions.connected = runtime.evaluate(transaction, authority);
  if (decisions.connected.disposition !== 'allow') {
    throw new Error(`connected candidate was not eligible: ${reasonCode(decisions.connected)}`);
  }
  checks.actual_ci_candidate_allowed_while_connected = true;

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
  decisions.partitionInitial = runtime.evaluate(transaction, authority);
  if (decisions.partitionInitial.disposition !== 'allow') {
    throw new Error(`initial partition candidate was not eligible: ${reasonCode(decisions.partitionInitial)}`);
  }
  checks.signed_headquarters_loss_starts_one_epoch = true;
  checks.candidate_survives_admitted_partition_profile = true;

  setClock(4_000);
  const repeatedObservation = observation(
    nodeKeys,
    iso(clockMs),
    { headquarters: 'down', 'local-control': 'up' },
  );
  const repeatedReceipt = runtime.observe(repeatedObservation, authority);
  if (repeatedReceipt.activeEpochId !== epochId) throw new Error('repeated observation reset the partition epoch');
  if (runtime.snapshot().activeEpoch.startedAt !== epochStartedAt) {
    throw new Error('repeated observation changed the runtime-owned lease start');
  }
  checks.repeated_observation_cannot_reset_offline_lease = true;

  const alternateAuthority = signAuthorityEnvelope(
    authorityBody(transaction, { note: 'different signed authority during active partition' }),
    'authority-key-1',
    authorityKeys.privateKeyPem,
  );
  const alternateObservation = observation(
    nodeKeys,
    iso(clockMs + 250),
    { headquarters: 'down', 'local-control': 'up' },
  );
  let authorityChangeCode = null;
  try {
    runtime.observe(alternateObservation, alternateAuthority);
  } catch (error) {
    authorityChangeCode = error.code;
  }
  if (authorityChangeCode !== 'PARTITION_AUTHORITY_CHANGE_REQUIRES_RECONCILIATION') {
    throw new Error(`active partition accepted an authority change: ${authorityChangeCode}`);
  }
  checks.authority_change_inside_partition_refused = true;

  const tamperedObservation = JSON.parse(JSON.stringify(repeatedObservation));
  tamperedObservation.links.headquarters = 'up';
  let tamperRefused = false;
  try {
    verifyLinkObservation(tamperedObservation, nodeTrustStore);
  } catch {
    tamperRefused = true;
  }
  if (!tamperRefused) throw new Error('tampered link observation verified');
  checks.tampered_link_observation_refused = true;

  runtime.close();
  setClock(5_000);
  runtime = new PartitionAuthorityRuntime(runtimeConfig);
  if (runtime.snapshot().activeEpoch.epochId !== epochId) throw new Error('restart changed the active epoch');
  if (runtime.snapshot().activeEpoch.startedAt !== epochStartedAt) throw new Error('restart reset the offline lease');
  decisions.partitionAfterRestart = runtime.evaluate(transaction, authority);
  if (decisions.partitionAfterRestart.disposition !== 'allow') {
    throw new Error(`candidate failed inside unexpired replayed partition: ${reasonCode(decisions.partitionAfterRestart)}`);
  }
  checks.restart_preserves_epoch_and_unexpired_lease = true;

  setClock(8_000);
  decisions.expiredPartition = runtime.evaluate(transaction, authority);
  if (
    decisions.expiredPartition.disposition !== 'safe_state'
    || reasonCode(decisions.expiredPartition) !== 'partition_offline_lease_expired'
  ) {
    throw new Error('expired offline lease did not enter safe state');
  }
  checks.runtime_owned_lease_expiry_enters_safe_state = true;

  const restoredObservation = observation(
    nodeKeys,
    iso(clockMs),
    { headquarters: 'up', 'local-control': 'up' },
  );
  writeJson(join(outputDir, 'link-restored.json'), restoredObservation);
  runtime.observe(restoredObservation, authority);
  if (runtime.snapshot().pendingReconciliation?.epoch?.epochId !== epochId) {
    throw new Error('communications restoration did not preserve the partition for reconciliation');
  }
  checks.reconnect_preserves_disconnected_history = true;

  const returningAuthority = signAuthorityEnvelope(
    authorityBody(transaction, { supersedes: [authority.authorityId] }),
    'authority-key-1',
    authorityKeys.privateKeyPem,
  );
  writeJson(join(outputDir, 'returning-authority.json'), returningAuthority);
  const reconciliation = runtime.reconcile(returningAuthority);
  writeJson(join(outputDir, 'reconciliation.json'), reconciliation);
  if (reconciliation.disposition !== 'explicitly_superseded') {
    throw new Error('returning authority did not explicitly supersede the partition authority');
  }
  if (!reconciliation.localDecisionIds.includes(decisions.expiredPartition.decisionId)) {
    throw new Error('reconciliation omitted a local partition decision');
  }
  checks.explicit_supersession_reconciles_without_rewriting_history = true;
  runtime.close();

  const prefix = readFileSync(journalPath);
  const incompleteTail = Buffer.from('{"incomplete":', 'utf8');
  appendFileSync(journalPath, incompleteTail);
  const recovered = new PartitionAuthorityRuntime(runtimeConfig);
  if (recovered.snapshot().diagnostics.truncatedTailBytes !== incompleteTail.length) {
    throw new Error('partition journal did not report the incomplete tail');
  }
  recovered.close();
  if (!readFileSync(journalPath).equals(prefix)) {
    throw new Error('partition journal tail recovery rewrote the signed prefix');
  }
  checks.incomplete_tail_recovers_exact_signed_prefix = true;

  for (const [name, decision] of Object.entries(decisions)) {
    writeJson(join(outputDir, `decision-${name}.json`), decision);
  }

  const receipt = {
    schema: 'ai-execution-audit/polybolos-ci-partition-authority-e2e@1',
    status: 'pass',
    actualCiTransaction: {
      snapshotId: transaction.snapshot.snapshotId,
      candidateId: transaction.candidate.candidateId,
      transactionSha256: sha256(transactionPath),
    },
    identities: {
      authorityId: authority.authorityId,
      returningAuthorityId: returningAuthority.authorityId,
      epochId,
      epochStartedAt,
      reconciliationId: reconciliation.reconciliationId,
      journalSha256: sha256(journalPath),
      lastRecordId: recovered.snapshot().diagnostics.lastRecordId,
    },
    decisions: Object.fromEntries(
      Object.entries(decisions).map(([name, decision]) => [
        name,
        {
          decisionId: decision.decisionId,
          disposition: decision.disposition,
          reasonCode: reasonCode(decision),
        },
      ]),
    ),
    checks,
    artifacts: Object.fromEntries(
      [
        'partition-authority.json',
        'returning-authority.json',
        'authority-trust.json',
        'node-trust.json',
        'node-public.pem',
        'link-connected.json',
        'link-headquarters-denied.json',
        'link-restored.json',
        'reconciliation.json',
        'partition-authority.journal',
        ...Object.keys(decisions).map((name) => `decision-${name}.json`),
      ].map((name) => {
        const path = join(outputDir, name);
        return [name, { bytes: readFileSync(path).length, sha256: sha256(path) }];
      }),
    ),
    claimBoundary:
      'This transaction applies a signed runtime-owned communications partition to the candidate emitted by the actual public Command Intelligence server. It carries no actuation, targeting, engagement, effector, emulator-input, weapons-employment, or combat-effectiveness claim.',
  };
  writeJson(join(outputDir, 'partition-authority-e2e-receipt.json'), receipt);
  process.stdout.write(`${JSON.stringify(receipt, null, 2)}\n`);
  return 0;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  process.exitCode = await main(process.argv.slice(2));
}

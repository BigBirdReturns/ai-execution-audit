#!/usr/bin/env node
import { createHash, generateKeyPairSync } from 'node:crypto';
import { mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { pathToFileURL } from 'node:url';
import {
  deriveCandidateId,
  verifyCheckpointCandidateTransaction,
} from '../../polybolos_ci/checkpoint/checkpoint_verifier.mjs';
import {
  signAuthorityEnvelope,
  signLinkObservation,
} from '../../polybolos_ci/authority/partition_runtime.mjs';
import { CheckpointPartitionAuthorityRuntime } from '../../polybolos_ci/authority/checkpoint_partition_runtime.mjs';
import { verifyPartitionJournal } from '../../polybolos_ci/authority/partition_evidence.mjs';
import {
  CongruenceError,
  toBoundedCandidateRequest,
  translateExternalProposal,
} from '../translation/congruence.mjs';

const ROOT = dirname(dirname(new URL(import.meta.url).pathname));

function readJson(path) {
  return JSON.parse(readFileSync(path, 'utf8'));
}

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

function reasonCode(decision) {
  return decision.reason?.code ?? decision.baseDecision?.reasons?.[0]?.code ?? 'unspecified';
}

function authorityBody(transaction) {
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
    allowedPayloadFields: ['entityIds', 'priority'],
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
      ],
    },
  };
}

function observation(nodeKeys, observedAt, links) {
  return signLinkObservation({
    schema: 'axm-link-observation/1',
    nodeId: 'fixture-node-1',
    observedAt,
    links,
    localOperatorPresent: true,
  }, 'node-key-1', nodeKeys.privateKeyPem);
}

async function main(argv) {
  if (argv.length !== 2) {
    console.error('usage: run_spoke_e2e.mjs <bounded-base-transaction.json> <output-dir>');
    return 2;
  }
  const [baseTransactionPath, outputDir] = argv;
  rmSync(outputDir, { recursive: true, force: true });
  mkdirSync(outputDir, { recursive: true });

  const base = readJson(baseTransactionPath);
  if (base.schema !== 'polybolos-command-candidate-transaction/2') {
    throw new Error('bounded base transaction is missing or invalid');
  }
  const map = readJson(join(ROOT, 'contract/provisional-shape-map.json'));
  const losses = readJson(join(ROOT, 'contract/declared-losses.json'));
  const external = readJson(join(ROOT, 'fixtures/public-known-minimum/provisional-input.json'));
  const entityIds = base.witnesses.map((witness) => witness.entityId).sort();
  external.entity_ids = entityIds;
  external.created_at = base.candidate.createdAt;
  external.deadline_at = iso(Date.parse(base.candidate.createdAt) + 10_000);
  external.action_class = base.candidate.actionClass;
  external.decision.priority = base.candidate.payload.priority;

  let liveBlocked = false;
  try {
    translateExternalProposal(external, map, losses, { mode: 'live' });
  } catch (error) {
    liveBlocked = error instanceof CongruenceError && error.code === 'MAPPING_NOT_CONFIRMED';
  }
  if (!liveBlocked) throw new Error('provisional shape map unexpectedly entered live mode');

  const projection = translateExternalProposal(external, map, losses, { mode: 'fixture' });
  const bounded = toBoundedCandidateRequest(projection);
  const evidence = base.witnesses
    .map((witness) => ({ entityId: witness.entityId, witnessId: witness.witnessId }))
    .sort((a, b) => a.entityId.localeCompare(b.entityId));
  const candidate = {
    schema: 'polybolos-command-candidate/2',
    candidateId: '',
    checkpointId: base.checkpoint.checkpointId,
    evidence,
    producer: bounded.request.producer,
    createdAt: bounded.request.createdAt,
    actionClass: bounded.request.actionClass,
    payload: bounded.request.payload,
    claimBoundary:
      'This synthetic candidate was produced through the provisional Polybolos congruent-shape adapter and carries no command authority.',
  };
  candidate.candidateId = deriveCandidateId(candidate);
  const transaction = {
    schema: 'polybolos-command-candidate-transaction/2',
    checkpoint: base.checkpoint,
    witnesses: base.witnesses,
    candidate,
    persistence: base.persistence,
    claimBoundary:
      'This fixture transaction proves adapter congruence with the existing bounded AXM spoke. It is not a Polybolos native or operational transaction.',
  };
  const verification = verifyCheckpointCandidateTransaction(transaction);
  if (!verification.candidateVerified || !verification.checkpointVerified) {
    throw new Error('adapter-generated candidate did not verify against the bounded checkpoint');
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
  const candidateMs = Date.parse(candidate.createdAt);
  let clockMs = candidateMs + 1_000;
  const journalPath = join(outputDir, 'polybolos-congruence-partition.journal');
  const runtime = new CheckpointPartitionAuthorityRuntime({
    journalPath,
    nodeId: 'fixture-node-1',
    journalKeyId: 'node-key-1',
    journalPrivateKeyPem: nodeKeys.privateKeyPem,
    nodeTrustStore,
    authorityTrustStore,
    clock: () => clockMs,
  });

  const connected = observation(nodeKeys, iso(clockMs), {
    headquarters: 'up',
    'local-control': 'up',
  });
  runtime.observe(connected, authority);
  const connectedDecision = runtime.evaluateCheckpoint(transaction, authority);
  if (connectedDecision.disposition !== 'allow') {
    throw new Error(`adapter candidate failed while connected: ${reasonCode(connectedDecision)}`);
  }

  clockMs = candidateMs + 2_000;
  const denied = observation(nodeKeys, iso(clockMs), {
    headquarters: 'down',
    'local-control': 'up',
  });
  runtime.observe(denied, authority);
  const partitionDecision = runtime.evaluateCheckpoint(transaction, authority);
  if (partitionDecision.disposition !== 'allow') {
    throw new Error(`adapter candidate failed in admitted partition: ${reasonCode(partitionDecision)}`);
  }

  clockMs = candidateMs + 8_000;
  const expiredDecision = runtime.evaluateCheckpoint(transaction, authority);
  if (
    expiredDecision.disposition !== 'safe_state'
    || reasonCode(expiredDecision) !== 'partition_offline_lease_expired'
  ) {
    throw new Error('adapter candidate did not enter safe state after lease expiry');
  }
  runtime.close();
  const journal = verifyPartitionJournal(journalPath, nodeTrustStore);

  writeJson(join(outputDir, 'adapter-projection.json'), projection);
  writeJson(join(outputDir, 'bounded-request.json'), bounded);
  writeJson(join(outputDir, 'candidate-transaction.json'), transaction);
  writeJson(join(outputDir, 'authority.json'), authority);
  writeJson(join(outputDir, 'authority-trust.json'), authorityTrustStore);
  writeJson(join(outputDir, 'node-trust.json'), nodeTrustStore);
  writeJson(join(outputDir, 'decision-connected.json'), connectedDecision);
  writeJson(join(outputDir, 'decision-partition.json'), partitionDecision);
  writeJson(join(outputDir, 'decision-expired.json'), expiredDecision);

  const receipt = {
    schema: 'ai-execution-audit/polybolos-congruent-spoke-e2e@1',
    status: 'pass',
    mappingStatus: projection.mappingStatus,
    livePromotionBlocked: liveBlocked,
    identities: {
      projectionId: projection.projectionId,
      boundedRequestId: bounded.requestId,
      checkpointId: transaction.checkpoint.checkpointId,
      candidateId: transaction.candidate.candidateId,
      authorityId: authority.authorityId,
      epochId: partitionDecision.epochId,
      journalSha256: journal.journalSha256,
      lastRecordId: journal.lastRecordId,
    },
    checks: {
      provisional_map_refused_live_mode: liveBlocked,
      translated_candidate_verified_against_existing_checkpoint: true,
      connected_authority_allowed: true,
      admitted_partition_allowed: true,
      expired_partition_entered_safe_state: true,
      node_signed_journal_verified_detached: true,
    },
    decisions: {
      connected: { disposition: connectedDecision.disposition, reasonCode: reasonCode(connectedDecision) },
      partition: { disposition: partitionDecision.disposition, reasonCode: reasonCode(partitionDecision) },
      expired: { disposition: expiredDecision.disposition, reasonCode: reasonCode(expiredDecision) },
    },
    artifacts: {
      baseTransactionSha256: sha256(baseTransactionPath),
      journalRecords: journal.recordCount,
    },
    claimBoundary:
      'This transaction proves only that the provisional synthetic adapter shape is congruent with the existing AXM-neutral checkpoint and partition path. It does not assert Polybolos private field names, source, Command Intelligence, COMMAND CORE behavior, or operational qualification.',
  };
  writeJson(join(outputDir, 'polybolos-congruent-spoke-e2e-receipt.json'), receipt);
  process.stdout.write(`${JSON.stringify(receipt, null, 2)}\n`);
  return 0;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  process.exitCode = await main(process.argv.slice(2));
}

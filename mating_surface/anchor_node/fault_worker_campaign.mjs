import { createHash } from 'node:crypto';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  MessageAuthorityRuntime,
  canonicalJson,
  verifyAdmissionTicket,
  verifyAuthorityDecision,
} from '../semantic/authority_sidecar.mjs';
import {
  createFaultFrame,
  createTestPacket,
  runFaultScenario,
} from '../test_hosts/core/fault_machine.mjs';
import { verifyFaultFrame } from '../test_hosts/core/fault_verifier.mjs';
import { verifyVerticalSlice } from './vertical_slice.mjs';

export class FaultWorkerCampaignError extends Error {
  constructor(code, message) {
    super(message);
    this.name = 'FaultWorkerCampaignError';
    this.code = code;
  }
}

function requireCondition(condition, code, message) {
  if (!condition) throw new FaultWorkerCampaignError(code, message);
}

function isRecord(value) {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) return false;
  const prototype = Object.getPrototypeOf(value);
  return prototype === Object.prototype || prototype === null;
}

function digest(prefix, value) {
  return `${prefix}_${createHash('sha256').update(canonicalJson(value), 'utf8').digest('hex')}`;
}

function sha256Text(text) {
  return createHash('sha256').update(text, 'utf8').digest('hex');
}

function bodyWithoutId(value, idKey) {
  const copy = structuredClone(value);
  delete copy[idKey];
  return copy;
}

function createArtifactBinding(bundle) {
  const artifactSha256 = sha256Text(canonicalJson(bundle.sourcePackage));
  const artifactTransaction = {
    schema: 'standards-mating-surface-artifact-transaction/1',
    status: 'pass',
    admission: {
      schema: 'standards-mating-surface-artifact-admission/1',
      admissionId: 'standardartifactadmission1_anchor_mp01',
      standardId: 'siso-std-019-2020-c2sim',
      standardRevision: 'synthetic-interface-binding-only',
      artifactSha256,
    },
    use: {
      schema: 'standards-mating-surface-artifact-use/1',
      useId: 'standardartifactuse1_anchor_mp01',
      profileId: 'joint-edge-command-authority/0.1',
      mode: 'rehearsal',
      portId: 'simulation-and-rehearsal',
    },
  };
  const catalog = {
    schema: 'standards-mating-surface-xsd11-catalog/1',
    catalogId: 'standardxsd11catalog1_anchor_mp01',
    artifactAdmissionId: artifactTransaction.admission.admissionId,
    artifactUseId: artifactTransaction.use.useId,
    artifactSha256,
    standardId: artifactTransaction.admission.standardId,
  };
  return { artifactTransaction, catalog };
}

function packetFixture({ bundle, artifactTransaction, catalog, messageIdentity, sourceSystemId, value, observedAt }) {
  const payloadText = canonicalJson(value);
  const payload = Buffer.from(payloadText, 'utf8');
  const packet = createTestPacket({
    artifactTransaction,
    catalog,
    payload,
    messageIdentity,
    sourceSystemId,
    observedAt,
  });
  return { packet, payload };
}

function buildFaultInputs(bundle) {
  const { artifactTransaction, catalog } = createArtifactBinding(bundle);
  const rows = [
    packetFixture({
      bundle,
      artifactTransaction,
      catalog,
      messageIdentity: bundle.semanticMessageReceipt.messageId,
      sourceSystemId: 'spectra-anchor-node-local-model-interface',
      value: bundle.modelProposal,
      observedAt: bundle.sourcePackage.capturedAt,
    }),
    packetFixture({
      bundle,
      artifactTransaction,
      catalog,
      messageIdentity: `state/${bundle.missionStateBefore.missionStateId}`,
      sourceSystemId: 'spectra-anchor-node-canonical-state',
      value: bundle.missionStateBefore,
      observedAt: bundle.sourcePackage.capturedAt,
    }),
    packetFixture({
      bundle,
      artifactTransaction,
      catalog,
      messageIdentity: `result/${bundle.taskReceipt.taskReceiptId}`,
      sourceSystemId: 'spectra-anchor-node-local-executor',
      value: bundle.taskReceipt,
      observedAt: bundle.sourcePackage.capturedAt,
    }),
  ];
  const packets = rows.map((row) => row.packet);
  const payloads = new Map(rows.map((row) => [row.packet.packetId, row.payload]));
  const scenario = {
    schema: 'standards-port-fault-scenario/1',
    scenarioId: 'anchor-mp01-duplicate-buffer-delay',
    mode: 'rehearsal',
    profileId: artifactTransaction.use.profileId,
    portId: artifactTransaction.use.portId,
    standardId: artifactTransaction.admission.standardId,
    artifactUseId: artifactTransaction.use.useId,
    initialLinkState: 'up',
    partitionPolicy: 'buffer',
    queueCapacity: 1,
    events: [
      { step: 0, type: 'send', packetId: packets[0].packetId, behavior: 'duplicate', copies: 2 },
      { step: 1, type: 'link', state: 'down' },
      { step: 2, type: 'send', packetId: packets[1].packetId, behavior: 'pass' },
      { step: 3, type: 'send', packetId: packets[2].packetId, behavior: 'delay', releaseAt: 4 },
      { step: 4, type: 'link', state: 'up' },
    ],
    claimBoundary: 'Invented synthetic transport-fault campaign for Mission Profile 01. It carries no operational network, payload, command, targeting, engagement, effector, or weapons claim.',
  };
  return { artifactTransaction, catalog, rows, packets, payloads, scenario };
}

function exerciseDuplicateReceiver(bundle, faultRun) {
  verifyAuthorityDecision(bundle.authorityDecision, bundle.authorityProfile);
  verifyAdmissionTicket(bundle.admissionTicket, bundle.authorityDecision, bundle.authorityProfile);
  const matching = faultRun.deliveries.filter(
    (delivery) => delivery.messageIdentity === bundle.semanticMessageReceipt.messageId,
  );
  requireCondition(matching.length === 2, 'DUPLICATE_DELIVERY_DENOMINATOR_INVALID', 'expected exactly two proposal deliveries');
  const runtime = new MessageAuthorityRuntime(bundle.authorityProfile);
  const receipts = matching.map((delivery) => runtime.receiveDelivery(
    bundle.admissionTicket,
    delivery,
    delivery.deliveryStep,
  ));
  requireCondition(receipts[0].disposition === 'accept', 'DUPLICATE_RECEIVER_INVALID', 'first proposal delivery was not accepted');
  requireCondition(receipts[1].disposition === 'refuse' && receipts[1].reason === 'MESSAGE_REPLAY', 'DUPLICATE_RECEIVER_INVALID', 'duplicate proposal delivery was not refused as replay');
  return receipts;
}

const WORKER_STATES = new Set(['ACTIVE', 'EXITED', 'INACCESSIBLE', 'INVALID_PID']);

function leaseBody({ jobId, workerId, generation, issuedAtStep, expiresAtStep }) {
  return {
    schema: 'spectra-anchor-node-worker-lease/1',
    jobId,
    workerId,
    generation,
    issuedAtStep,
    expiresAtStep,
    claimBoundary: 'Synthetic worker lease for Mission Profile 01 qualification only. It grants no field or command authority.',
  };
}

function createLease(args) {
  const body = leaseBody(args);
  return { ...body, leaseId: digest('anchorworkerlease1', body) };
}

function refusal({ jobId, candidateId, workerId, leaseId, reason, observedAtStep }) {
  const body = {
    schema: 'spectra-anchor-node-completion-refusal/1',
    jobId,
    candidateId,
    workerId,
    leaseId,
    reason,
    observedAtStep,
    claimBoundary: 'This refusal prevents a stale, inaccessible, invalid, or duplicate synthetic worker result from becoming terminal success.',
  };
  return { ...body, refusalId: digest('anchorcompletionrefusal1', body) };
}

function completionCandidate({ jobId, workerId, lease, outputDigest, completedAtStep }) {
  const body = {
    schema: 'spectra-anchor-node-worker-completion-candidate/1',
    jobId,
    workerId,
    leaseId: lease.leaseId,
    leaseGeneration: lease.generation,
    outputDigest,
    completedAtStep,
    claimBoundary: 'Synthetic completion candidate. It is not successful until the scheduler verifies the active lease, worker state, output, and duplicate status.',
  };
  return { ...body, candidateId: digest('anchorworkercompletioncandidate1', body) };
}

export function runWorkerLossRecovery(bundle) {
  verifyVerticalSlice(bundle);
  const jobId = `job/${bundle.taskReceipt.taskReceiptId}`;
  const expectedOutputDigest = bundle.taskReceipt.outputDigest;
  const workers = new Map([
    ['SYN-WORKER-PRIMARY', { workerId: 'SYN-WORKER-PRIMARY', admitted: true, state: 'ACTIVE' }],
    ['SYN-WORKER-FALLBACK', { workerId: 'SYN-WORKER-FALLBACK', admitted: true, state: 'ACTIVE' }],
  ]);
  for (const worker of workers.values()) {
    requireCondition(WORKER_STATES.has(worker.state), 'WORKER_STATE_INVALID', `worker state invalid: ${worker.state}`);
  }

  const primaryLease = createLease({
    jobId,
    workerId: 'SYN-WORKER-PRIMARY',
    generation: 1,
    issuedAtStep: 0,
    expiresAtStep: 2,
  });
  workers.get('SYN-WORKER-PRIMARY').state = 'EXITED';
  const fallbackLease = createLease({
    jobId,
    workerId: 'SYN-WORKER-FALLBACK',
    generation: 2,
    issuedAtStep: 2,
    expiresAtStep: 6,
  });

  const stalePrimary = completionCandidate({
    jobId,
    workerId: 'SYN-WORKER-PRIMARY',
    lease: primaryLease,
    outputDigest: expectedOutputDigest,
    completedAtStep: 3,
  });
  const acceptedFallback = completionCandidate({
    jobId,
    workerId: 'SYN-WORKER-FALLBACK',
    lease: fallbackLease,
    outputDigest: expectedOutputDigest,
    completedAtStep: 4,
  });
  const duplicateFallback = completionCandidate({
    jobId,
    workerId: 'SYN-WORKER-FALLBACK',
    lease: fallbackLease,
    outputDigest: expectedOutputDigest,
    completedAtStep: 5,
  });

  const refusals = [];
  requireCondition(workers.get(stalePrimary.workerId).state === 'EXITED', 'WORKER_LOSS_NOT_OBSERVED', 'primary worker did not exit');
  refusals.push(refusal({
    jobId,
    candidateId: stalePrimary.candidateId,
    workerId: stalePrimary.workerId,
    leaseId: stalePrimary.leaseId,
    reason: 'STALE_OR_EXITED_WORKER_LEASE',
    observedAtStep: stalePrimary.completedAtStep,
  }));

  requireCondition(acceptedFallback.leaseId === fallbackLease.leaseId, 'FALLBACK_LEASE_INVALID', 'fallback completion cites another lease');
  requireCondition(acceptedFallback.leaseGeneration === 2, 'FALLBACK_LEASE_INVALID', 'fallback completion generation is invalid');
  requireCondition(acceptedFallback.completedAtStep <= fallbackLease.expiresAtStep, 'FALLBACK_LEASE_EXPIRED', 'fallback lease expired');
  requireCondition(acceptedFallback.outputDigest === expectedOutputDigest, 'FALLBACK_OUTPUT_INVALID', 'fallback output differs');
  requireCondition(workers.get(acceptedFallback.workerId).state === 'ACTIVE', 'FALLBACK_WORKER_INVALID', 'fallback worker is not active');

  const completionBody = {
    schema: 'spectra-anchor-node-worker-completion-receipt/1',
    jobId,
    acceptedCandidateId: acceptedFallback.candidateId,
    workerId: acceptedFallback.workerId,
    leaseId: acceptedFallback.leaseId,
    leaseGeneration: acceptedFallback.leaseGeneration,
    outputDigest: acceptedFallback.outputDigest,
    completedAtStep: acceptedFallback.completedAtStep,
    status: 'completed',
    claimBoundary: 'This receipt proves one synthetic fallback worker completed the local artifact job under the active replacement lease. It records no external or operational effect.',
  };
  const completionReceipt = { ...completionBody, completionReceiptId: digest('anchorworkercompletionreceipt1', completionBody) };

  refusals.push(refusal({
    jobId,
    candidateId: duplicateFallback.candidateId,
    workerId: duplicateFallback.workerId,
    leaseId: duplicateFallback.leaseId,
    reason: 'DUPLICATE_TERMINAL_COMPLETION',
    observedAtStep: duplicateFallback.completedAtStep,
  }));

  const body = {
    schema: 'spectra-anchor-node-worker-loss-recovery/1',
    jobId,
    expectedOutputDigest,
    workers: [...workers.values()],
    leases: [primaryLease, fallbackLease],
    completionCandidates: [stalePrimary, acceptedFallback, duplicateFallback],
    refusals,
    completionReceipt,
    acceptedCompletionCount: 1,
    terminalState: 'completed',
    operatorInterventions: 0,
    externalServiceCalls: 0,
    authority: false,
    claimBoundary: 'Synthetic lease and replacement exercise only. It is not target-hardware qualification, production scheduling, field readiness, or command authority.',
  };
  return { ...body, recoveryId: digest('anchorworkerlossrecovery1', body) };
}

export function verifyWorkerLossRecovery(recovery, bundle) {
  requireCondition(isRecord(recovery) && recovery.schema === 'spectra-anchor-node-worker-loss-recovery/1', 'WORKER_RECOVERY_INVALID', 'worker recovery schema is invalid');
  requireCondition(recovery.authority === false, 'WORKER_RECOVERY_INVALID', 'worker recovery cannot carry authority');
  requireCondition(recovery.externalServiceCalls === 0, 'WORKER_RECOVERY_INVALID', 'worker recovery contains external calls');
  requireCondition(recovery.operatorInterventions === 0, 'WORKER_RECOVERY_INVALID', 'worker recovery records operator intervention');
  requireCondition(recovery.acceptedCompletionCount === 1, 'WORKER_RECOVERY_INVALID', 'worker recovery did not produce exactly one accepted completion');
  requireCondition(recovery.refusals.length === 2, 'WORKER_RECOVERY_INVALID', 'worker recovery refusal denominator differs');
  requireCondition(recovery.refusals.some((row) => row.reason === 'STALE_OR_EXITED_WORKER_LEASE'), 'WORKER_RECOVERY_INVALID', 'stale worker completion refusal is missing');
  requireCondition(recovery.refusals.some((row) => row.reason === 'DUPLICATE_TERMINAL_COMPLETION'), 'WORKER_RECOVERY_INVALID', 'duplicate completion refusal is missing');
  const replayed = runWorkerLossRecovery(bundle);
  requireCondition(canonicalJson(replayed) === canonicalJson(recovery), 'WORKER_RECOVERY_REPLAY_MISMATCH', 'worker recovery does not replay');
  return recovery;
}

export function runFaultWorkerCampaign(bundle) {
  verifyVerticalSlice(bundle);
  const inputs = buildFaultInputs(bundle);
  const faultRun = runFaultScenario({
    scenario: inputs.scenario,
    packets: inputs.packets,
    payloads: inputs.payloads,
    artifactTransaction: inputs.artifactTransaction,
    catalog: inputs.catalog,
  });
  const faultFrame = createFaultFrame(faultRun);
  const faultVerification = verifyFaultFrame(faultFrame, faultRun);
  requireCondition(faultVerification.status === 'pass', 'FAULT_VERIFICATION_INVALID', 'transport fault verification failed');
  const duplicateReceiverReceipts = exerciseDuplicateReceiver(bundle, faultRun);
  const workerRecovery = runWorkerLossRecovery(bundle);
  verifyWorkerLossRecovery(workerRecovery, bundle);

  const body = {
    schema: 'spectra-anchor-node-fault-worker-campaign/1',
    profileId: bundle.profileId,
    runId: bundle.runId,
    classification: bundle.classification,
    scenario: inputs.scenario,
    packets: inputs.packets,
    faultRun,
    faultFrame,
    faultVerification,
    duplicateReceiverReceipts,
    workerRecovery,
    externalServiceCalls: 0,
    operationalCredentials: 0,
    authority: false,
    claimBoundary: 'This campaign proves deterministic synthetic transport faults, duplicate refusal, and worker-loss recovery. It is not operational network performance, target-hardware qualification, field readiness, command authority, targeting, engagement, effector, or weapons capability.',
  };
  return { ...body, campaignId: digest('anchorfaultworkercampaign1', body) };
}

export function verifyFaultWorkerCampaign(campaign, bundle) {
  requireCondition(isRecord(campaign) && campaign.schema === 'spectra-anchor-node-fault-worker-campaign/1', 'CAMPAIGN_INVALID', 'campaign schema is invalid');
  requireCondition(campaign.classification === 'invented_unclassified_synthetic_only', 'CAMPAIGN_INVALID', 'campaign classification is invalid');
  requireCondition(campaign.externalServiceCalls === 0, 'CAMPAIGN_INVALID', 'campaign contains external calls');
  requireCondition(campaign.operationalCredentials === 0, 'CAMPAIGN_INVALID', 'campaign contains operational credentials');
  requireCondition(campaign.authority === false, 'CAMPAIGN_INVALID', 'campaign cannot carry authority');
  requireCondition(campaign.faultRun.metrics.duplicateExtraCopies === 1, 'CAMPAIGN_INVALID', 'duplicate fault was not exercised');
  requireCondition(campaign.faultRun.metrics.bufferedPackets === 1, 'CAMPAIGN_INVALID', 'buffer fault was not exercised');
  requireCondition(campaign.faultRun.metrics.delayedPackets === 1, 'CAMPAIGN_INVALID', 'delay fault was not exercised');
  requireCondition(campaign.faultRun.metrics.pendingDelayedPackets === 0 && campaign.faultRun.metrics.pendingBufferedPackets === 0, 'CAMPAIGN_INVALID', 'fault campaign did not close pending state');
  requireCondition(campaign.duplicateReceiverReceipts[0].disposition === 'accept', 'CAMPAIGN_INVALID', 'first duplicate receiver receipt was not accepted');
  requireCondition(campaign.duplicateReceiverReceipts[1].reason === 'MESSAGE_REPLAY', 'CAMPAIGN_INVALID', 'duplicate receiver receipt was not refused as replay');
  verifyWorkerLossRecovery(campaign.workerRecovery, bundle);
  const replayed = runFaultWorkerCampaign(bundle);
  requireCondition(canonicalJson(replayed) === canonicalJson(campaign), 'CAMPAIGN_REPLAY_MISMATCH', 'fault/worker campaign does not replay');
  requireCondition(campaign.campaignId === digest('anchorfaultworkercampaign1', bodyWithoutId(campaign, 'campaignId')), 'CAMPAIGN_ID_INVALID', 'campaign identity is invalid');
  const receiptBody = {
    schema: 'spectra-anchor-node-fault-worker-verification/1',
    campaignId: campaign.campaignId,
    runId: campaign.runId,
    status: 'PASS',
    duplicateReplayRefused: true,
    workerLossRecovered: true,
    acceptedCompletionCount: campaign.workerRecovery.acceptedCompletionCount,
    pendingFaultState: 0,
    externalServiceCalls: 0,
    authority: 'none',
    claimBoundary: 'This receipt proves deterministic reconstruction of one synthetic fault and worker-loss campaign. It grants no field, operational, evaluator, adoption, or command authority.',
  };
  return { ...receiptBody, verificationId: digest('anchorfaultworkerverification1', receiptBody) };
}

async function writeJson(path, value) {
  await mkdir(dirname(path), { recursive: true });
  await writeFile(path, `${JSON.stringify(value, null, 2)}\n`, 'utf8');
}

async function main(argv) {
  const command = argv[2];
  if (command === 'run') {
    const bundle = JSON.parse(await readFile(resolve(argv[3]), 'utf8'));
    const outputPath = resolve(argv[4]);
    const campaign = runFaultWorkerCampaign(bundle);
    await writeJson(outputPath, campaign);
    process.stdout.write(`${JSON.stringify({ status: 'PASS', campaignId: campaign.campaignId }, null, 2)}\n`);
    return;
  }
  if (command === 'verify') {
    const bundle = JSON.parse(await readFile(resolve(argv[3]), 'utf8'));
    const campaign = JSON.parse(await readFile(resolve(argv[4]), 'utf8'));
    const outputPath = resolve(argv[5]);
    const receipt = verifyFaultWorkerCampaign(campaign, bundle);
    await writeJson(outputPath, receipt);
    process.stdout.write(`${JSON.stringify(receipt, null, 2)}\n`);
    return;
  }
  throw new FaultWorkerCampaignError('COMMAND_INVALID', `unknown command ${command}`);
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  main(process.argv).catch((error) => {
    const code = error instanceof FaultWorkerCampaignError ? error.code : 'UNEXPECTED_ERROR';
    process.stderr.write(`${code}: ${error.message}\n`);
    process.exitCode = 1;
  });
}

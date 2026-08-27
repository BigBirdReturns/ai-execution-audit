import { createHash } from 'node:crypto';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { canonicalJson } from '../semantic/authority_sidecar.mjs';
import { verifyVerticalSlice } from './vertical_slice.mjs';

const OUTBOUND_KEYS = new Set([
  'schema',
  'envelopeId',
  'adapterMode',
  'classification',
  'canonicalMissionStateId',
  'canonicalStateOwner',
  'operationalCredentials',
  'entities',
  'tasks',
  'objects',
  'claimBoundary',
]);
const OUTBOUND_ENTITY_KEYS = new Set([
  'schema',
  'entityProjectionId',
  'externalId',
  'entityType',
  'sourceMissionStateId',
  'attributes',
  'uncertainty',
  'authority',
  'claimBoundary',
]);
const OUTBOUND_TASK_KEYS = new Set([
  'schema',
  'taskProjectionId',
  'externalId',
  'taskType',
  'sourceTaskReceiptId',
  'effectClass',
  'status',
  'authority',
  'claimBoundary',
]);
const OUTBOUND_OBJECT_KEYS = new Set([
  'schema',
  'objectProjectionId',
  'externalId',
  'objectType',
  'sourceTaskReceiptId',
  'contentDigest',
  'authority',
  'claimBoundary',
]);
const INBOUND_KEYS = new Set([
  'schema',
  'externalEnvelopeId',
  'adapterMode',
  'classification',
  'entities',
  'tasks',
  'objects',
  'authority',
  'operationalCredentials',
  'claimBoundary',
]);

export class LatticeMembraneError extends Error {
  constructor(code, message) {
    super(message);
    this.name = 'LatticeMembraneError';
    this.code = code;
  }
}

function requireCondition(condition, code, message) {
  if (!condition) throw new LatticeMembraneError(code, message);
}

function isRecord(value) {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) return false;
  const prototype = Object.getPrototypeOf(value);
  return prototype === Object.prototype || prototype === null;
}

function exactKeys(value, expected, code, label) {
  requireCondition(isRecord(value), code, `${label} must be an object`);
  const actual = Object.keys(value).sort();
  const wanted = [...expected].sort();
  requireCondition(canonicalJson(actual) === canonicalJson(wanted), code, `${label} fields differ`);
}

function boundedString(value, code, label, max = 1024) {
  requireCondition(typeof value === 'string', code, `${label} must be a string`);
  const normalized = value.trim();
  requireCondition(normalized.length > 0 && normalized.length <= max, code, `${label} is empty or unbounded`);
  return normalized;
}

function digest(prefix, value) {
  return `${prefix}_${createHash('sha256').update(canonicalJson(value), 'utf8').digest('hex')}`;
}

function bodyWithoutId(value, idKey) {
  const copy = structuredClone(value);
  delete copy[idKey];
  return copy;
}

function assertSyntheticBoundary(value, code, label) {
  requireCondition(value.classification === 'invented_unclassified_synthetic_only', code, `${label} must remain synthetic-only`);
  requireCondition(value.operationalCredentials === 0, code, `${label} cannot require operational credentials`);
}

function entityProjection(entity, missionStateId) {
  const body = {
    schema: 'spectra-anchor-node-lattice-entity-projection/1',
    externalId: entity.externalId,
    entityType: entity.entityType,
    sourceMissionStateId: missionStateId,
    attributes: structuredClone(entity.attributes),
    uncertainty: structuredClone(entity.uncertainty),
    authority: false,
    claimBoundary: 'Contract-simulator projection of one invented local entity. It is not a Lattice production entity, operational track, targeting object, or authority-bearing record.',
  };
  return { ...body, entityProjectionId: digest('anchorlatticeentity1', body) };
}

function taskProjection(taskReceipt) {
  const body = {
    schema: 'spectra-anchor-node-lattice-task-projection/1',
    externalId: `SYN-TASK-${taskReceipt.taskReceiptId.slice(-16)}`,
    taskType: taskReceipt.taskType,
    sourceTaskReceiptId: taskReceipt.taskReceiptId,
    effectClass: taskReceipt.effectClass,
    status: taskReceipt.status,
    authority: false,
    claimBoundary: 'Contract-simulator projection of one completed local synthetic artifact task. It is not operational tasking, command authority, targeting, engagement, or effector control.',
  };
  return { ...body, taskProjectionId: digest('anchorlatticetask1', body) };
}

function objectProjection(taskReceipt) {
  const body = {
    schema: 'spectra-anchor-node-lattice-object-projection/1',
    externalId: `SYN-OBJECT-${taskReceipt.outputDigest.slice(-16)}`,
    objectType: 'local_review_artifact_receipt',
    sourceTaskReceiptId: taskReceipt.taskReceiptId,
    contentDigest: taskReceipt.outputDigest,
    authority: false,
    claimBoundary: 'Contract-simulator file/object reference for one local synthetic receipt. It carries no operational payload, credential, command, targeting, engagement, or effector authority.',
  };
  return { ...body, objectProjectionId: digest('anchorlatticeobject1', body) };
}

export function projectVerticalSliceToLattice(bundle) {
  verifyVerticalSlice(bundle);
  const state = bundle.missionStateAfter;
  const body = {
    schema: 'spectra-anchor-node-lattice-contract-envelope/1',
    adapterMode: 'contract_simulator_only',
    classification: bundle.classification,
    canonicalMissionStateId: state.missionStateId,
    canonicalStateOwner: false,
    operationalCredentials: 0,
    entities: state.entities.map((entity) => entityProjection(entity, state.missionStateId)),
    tasks: [taskProjection(bundle.taskReceipt)],
    objects: [objectProjection(bundle.taskReceipt)],
    claimBoundary: 'This envelope exercises only the public entity/task/object integration shape. It is not a production Lattice SDK payload, Lattice credential, operational integration, or canonical mission-state owner.',
  };
  return { ...body, envelopeId: digest('anchorlatticeenvelope1', body) };
}

export function validateOutboundLatticeEnvelope(envelope) {
  exactKeys(envelope, OUTBOUND_KEYS, 'OUTBOUND_ENVELOPE_INVALID', 'outbound Lattice envelope');
  requireCondition(envelope.schema === 'spectra-anchor-node-lattice-contract-envelope/1', 'OUTBOUND_ENVELOPE_INVALID', 'outbound envelope schema is invalid');
  requireCondition(envelope.adapterMode === 'contract_simulator_only', 'OUTBOUND_ENVELOPE_INVALID', 'outbound adapter mode is invalid');
  assertSyntheticBoundary(envelope, 'OUTBOUND_ENVELOPE_INVALID', 'outbound envelope');
  requireCondition(envelope.canonicalStateOwner === false, 'LATTICE_CANONICAL_OWNERSHIP_INVALID', 'Lattice envelope cannot own canonical state');
  boundedString(envelope.canonicalMissionStateId, 'OUTBOUND_ENVELOPE_INVALID', 'canonicalMissionStateId');
  requireCondition(Array.isArray(envelope.entities) && envelope.entities.length > 0, 'OUTBOUND_ENVELOPE_INVALID', 'outbound envelope requires entity projections');
  requireCondition(Array.isArray(envelope.tasks) && envelope.tasks.length === 1, 'OUTBOUND_ENVELOPE_INVALID', 'outbound envelope requires one task projection');
  requireCondition(Array.isArray(envelope.objects) && envelope.objects.length === 1, 'OUTBOUND_ENVELOPE_INVALID', 'outbound envelope requires one object projection');
  for (const entity of envelope.entities) {
    exactKeys(entity, OUTBOUND_ENTITY_KEYS, 'OUTBOUND_ENTITY_INVALID', 'entity projection');
    requireCondition(entity.externalId.startsWith('SYN-'), 'OUTBOUND_ENTITY_INVALID', 'entity external id must remain synthetic');
    requireCondition(entity.sourceMissionStateId === envelope.canonicalMissionStateId, 'OUTBOUND_ENTITY_INVALID', 'entity projection cites another state');
    requireCondition(entity.authority === false, 'LATTICE_AUTHORITY_INVALID', 'entity projection cannot carry authority');
    requireCondition(entity.entityProjectionId === digest('anchorlatticeentity1', bodyWithoutId(entity, 'entityProjectionId')), 'OUTBOUND_ENTITY_INVALID', 'entity projection identity is invalid');
  }
  for (const task of envelope.tasks) {
    exactKeys(task, OUTBOUND_TASK_KEYS, 'OUTBOUND_TASK_INVALID', 'task projection');
    requireCondition(task.externalId.startsWith('SYN-TASK-'), 'OUTBOUND_TASK_INVALID', 'task external id must remain synthetic');
    requireCondition(task.effectClass === 'local_artifact_only', 'OUTBOUND_TASK_INVALID', 'task effect is wider than the local artifact boundary');
    requireCondition(task.authority === false, 'LATTICE_AUTHORITY_INVALID', 'task projection cannot carry authority');
    requireCondition(task.taskProjectionId === digest('anchorlatticetask1', bodyWithoutId(task, 'taskProjectionId')), 'OUTBOUND_TASK_INVALID', 'task projection identity is invalid');
  }
  for (const object of envelope.objects) {
    exactKeys(object, OUTBOUND_OBJECT_KEYS, 'OUTBOUND_OBJECT_INVALID', 'object projection');
    requireCondition(object.externalId.startsWith('SYN-OBJECT-'), 'OUTBOUND_OBJECT_INVALID', 'object external id must remain synthetic');
    requireCondition(object.authority === false, 'LATTICE_AUTHORITY_INVALID', 'object projection cannot carry authority');
    requireCondition(object.objectProjectionId === digest('anchorlatticeobject1', bodyWithoutId(object, 'objectProjectionId')), 'OUTBOUND_OBJECT_INVALID', 'object projection identity is invalid');
  }
  requireCondition(envelope.envelopeId === digest('anchorlatticeenvelope1', bodyWithoutId(envelope, 'envelopeId')), 'OUTBOUND_ENVELOPE_INVALID', 'outbound envelope identity is invalid');
  return envelope;
}

export function validateInboundLatticeEnvelope(envelope) {
  exactKeys(envelope, INBOUND_KEYS, 'INBOUND_ENVELOPE_INVALID', 'inbound Lattice envelope');
  requireCondition(envelope.schema === 'spectra-anchor-node-lattice-inbound-candidate/1', 'INBOUND_ENVELOPE_INVALID', 'inbound envelope schema is invalid');
  requireCondition(envelope.adapterMode === 'contract_simulator_only', 'INBOUND_ENVELOPE_INVALID', 'inbound adapter mode is invalid');
  assertSyntheticBoundary(envelope, 'INBOUND_ENVELOPE_INVALID', 'inbound envelope');
  boundedString(envelope.externalEnvelopeId, 'INBOUND_ENVELOPE_INVALID', 'externalEnvelopeId');
  requireCondition(envelope.authority === false, 'LATTICE_AUTHORITY_INVALID', 'inbound candidate cannot carry authority');
  for (const key of ['entities', 'tasks', 'objects']) {
    requireCondition(Array.isArray(envelope[key]), 'INBOUND_ENVELOPE_INVALID', `${key} must be an array`);
  }
  requireCondition(envelope.entities.length > 0, 'INBOUND_ENVELOPE_INVALID', 'inbound candidate must contain at least one entity');
  for (const entity of envelope.entities) {
    requireCondition(isRecord(entity), 'INBOUND_ENVELOPE_INVALID', 'inbound entity must be an object');
    boundedString(entity.externalId, 'INBOUND_ENVELOPE_INVALID', 'inbound entity externalId');
    requireCondition(entity.externalId.startsWith('SYN-'), 'INBOUND_ENVELOPE_INVALID', 'inbound entity id must remain synthetic');
    requireCondition(entity.authority === false, 'LATTICE_AUTHORITY_INVALID', 'inbound entity cannot carry authority');
  }
  for (const task of envelope.tasks) {
    requireCondition(isRecord(task), 'INBOUND_ENVELOPE_INVALID', 'inbound task must be an object');
    requireCondition(task.authority === false, 'LATTICE_AUTHORITY_INVALID', 'inbound task cannot carry authority');
  }
  return envelope;
}

export function reconcileInboundCandidate(canonicalMissionState, inboundEnvelope) {
  requireCondition(canonicalMissionState?.schema === 'spectra-anchor-node-canonical-mission-state/1', 'CANONICAL_STATE_INVALID', 'canonical mission state is invalid');
  validateInboundLatticeEnvelope(inboundEnvelope);
  const beforeStateId = canonicalMissionState.missionStateId;
  const candidateDigest = digest('anchorlatticeinboundcandidate1', inboundEnvelope);
  const obligationBody = {
    schema: 'spectra-anchor-node-reconciliation-obligation/1',
    claimKind: 'obligation',
    obligationType: 'review_external_lattice_candidate',
    status: 'human_required',
    canonicalMissionStateId: beforeStateId,
    externalEnvelopeId: inboundEnvelope.externalEnvelopeId,
    externalCandidateDigest: candidateDigest,
    externalEntityIds: inboundEnvelope.entities.map((row) => row.externalId).sort(),
    authority: false,
    claimBoundary: 'This obligation preserves one synthetic external candidate for explicit review. It does not merge remote state, promote authority, or modify canonical mission state.',
  };
  const obligation = { ...obligationBody, obligationId: digest('anchorlatticereconciliationobligation1', obligationBody) };
  const receiptBody = {
    schema: 'spectra-anchor-node-lattice-reconciliation-receipt/1',
    status: 'human_required',
    canonicalMissionStateIdBefore: beforeStateId,
    canonicalMissionStateIdAfter: canonicalMissionState.missionStateId,
    canonicalStateMutated: false,
    externalEnvelopeId: inboundEnvelope.externalEnvelopeId,
    externalCandidateDigest: candidateDigest,
    obligation,
    authority: false,
    claimBoundary: 'This receipt proves that an inbound synthetic Lattice-shaped candidate remained external and created a review obligation without mutating canonical local state.',
  };
  return { ...receiptBody, reconciliationReceiptId: digest('anchorlatticereconciliationreceipt1', receiptBody) };
}

export function verifyLatticeRemoval(bundle, envelope) {
  const replay = verifyVerticalSlice(bundle);
  validateOutboundLatticeEnvelope(envelope);
  requireCondition(envelope.canonicalMissionStateId === bundle.missionStateAfter.missionStateId, 'LATTICE_STATE_BINDING_INVALID', 'outbound envelope cites another canonical state');
  const receiptBody = {
    schema: 'spectra-anchor-node-lattice-removal-verification/1',
    status: 'PASS',
    runId: bundle.runId,
    envelopeId: envelope.envelopeId,
    canonicalMissionStateIdBeforeRemoval: bundle.missionStateAfter.missionStateId,
    canonicalMissionStateIdAfterRemoval: replay.finalMissionStateId,
    localContinuityPreserved: replay.finalMissionStateId === bundle.missionStateAfter.missionStateId,
    latticeRequired: false,
    operationalCredentials: 0,
    claimBoundary: 'This receipt proves local synthetic state continuity after removing the contract simulator. It is not production Lattice integration or field qualification.',
  };
  requireCondition(receiptBody.localContinuityPreserved, 'LATTICE_REMOVAL_FAILED', 'local continuity did not survive adapter removal');
  return { ...receiptBody, removalVerificationId: digest('anchorlatticeremovalverification1', receiptBody) };
}

async function writeJson(path, value) {
  await mkdir(dirname(path), { recursive: true });
  await writeFile(path, `${JSON.stringify(value, null, 2)}\n`, 'utf8');
}

async function main(argv) {
  const command = argv[2];
  if (command === 'project') {
    const bundle = JSON.parse(await readFile(resolve(argv[3]), 'utf8'));
    const outputPath = resolve(argv[4]);
    const envelope = projectVerticalSliceToLattice(bundle);
    validateOutboundLatticeEnvelope(envelope);
    await writeJson(outputPath, envelope);
    process.stdout.write(`${JSON.stringify({ status: 'PASS', envelopeId: envelope.envelopeId }, null, 2)}\n`);
    return;
  }
  if (command === 'verify-removal') {
    const bundle = JSON.parse(await readFile(resolve(argv[3]), 'utf8'));
    const envelope = JSON.parse(await readFile(resolve(argv[4]), 'utf8'));
    const outputPath = resolve(argv[5]);
    const receipt = verifyLatticeRemoval(bundle, envelope);
    await writeJson(outputPath, receipt);
    process.stdout.write(`${JSON.stringify(receipt, null, 2)}\n`);
    return;
  }
  if (command === 'reconcile') {
    const bundle = JSON.parse(await readFile(resolve(argv[3]), 'utf8'));
    const inbound = JSON.parse(await readFile(resolve(argv[4]), 'utf8'));
    const outputPath = resolve(argv[5]);
    const receipt = reconcileInboundCandidate(bundle.missionStateAfter, inbound);
    await writeJson(outputPath, receipt);
    process.stdout.write(`${JSON.stringify(receipt, null, 2)}\n`);
    return;
  }
  throw new LatticeMembraneError('COMMAND_INVALID', `unknown command ${command}`);
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  main(process.argv).catch((error) => {
    const code = error instanceof LatticeMembraneError ? error.code : 'UNEXPECTED_ERROR';
    process.stderr.write(`${code}: ${error.message}\n`);
    process.exitCode = 1;
  });
}

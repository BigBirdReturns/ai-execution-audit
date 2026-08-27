import { createHash } from 'node:crypto';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { canonicalJson } from '../semantic/authority_sidecar.mjs';
import {
  fabricProfileReceipt,
  validateFabricProfile,
} from './validate_fabric_profile.mjs';
import { verifyVerticalSlice } from './vertical_slice.mjs';

const HERE = dirname(fileURLToPath(import.meta.url));
const DEFAULT_PROFILE = resolve(HERE, 'fabric-profile-01.json');
const DEFAULT_REGISTRY = resolve(HERE, 'fixtures/mp01-invented-seat-registry.json');

const SHA256 = /^[0-9a-f]{64}$/;
const MAX_STEP = 1_000_000_000;
const MAX_MEMORY_MIB = 1_048_576;
const MAX_LEASE_STEPS = 1_000_000;
const MODEL_DIGEST = 'bd14617d51d579adff77b9d359ca8e32c48167420919b0d5df73672e1672ea53';
const TEMPLATE_DIGEST = 'be9142c3f6586867f2e6b14deb5434fd90883c98e342c63751635f5d879486cc';
const CONTEXT_DIGEST = '589c33eb597c451b5dc586ca8d1f1be51a3fbcbfeb910f9c1022f1d3b7da6e96';
const VERIFIER_ID = 'SYN-VERIFIER-LOCAL-01';

const ROLES = new Set(['resident', 'fallback', 'optional']);
const ROLE_RANK = new Map([['resident', 0], ['fallback', 1], ['optional', 2]]);
const STATES = new Set(['available', 'inaccessible', 'retired']);
const RESIDENCY = new Set(['resident', 'resident_fallback', 'optional_burst']);
const POWER = new Set(['not_measured', 'synthetic_available', 'synthetic_unavailable']);
const REASONS = new Set([
  'SEAT_NOT_IN_SNAPSHOT',
  'SEAT_NOT_AVAILABLE',
  'WORKLOAD_CLASS_UNSUPPORTED',
  'RUNTIME_VERSION_MISMATCH',
  'ADAPTER_VERSION_MISMATCH',
  'MODEL_OR_EXECUTABLE_NOT_ADMITTED',
  'VERIFIER_NOT_ADMITTED',
  'INSUFFICIENT_INDEPENDENT_SEAT_MEMORY',
]);

const KEYS = Object.freeze({
  registry: ['schema', 'registryId', 'classification', 'capturedAtStep', 'topologyPolicy', 'seats', 'claimBoundary'],
  seat: ['seatId', 'role', 'state', 'hostIdentityClass', 'acceleratorIdentityClass', 'acceleratorMemoryMiB', 'endpointIdentity', 'runtimeVersion', 'adapterVersion', 'supportedWorkloadClasses', 'modelOrExecutableDigests', 'verifierIds', 'residencyEvidence', 'powerStateEvidence', 'claimBoundary'],
  residency: ['residencyClass', 'evidenceClass', 'evidenceDigest'],
  power: ['claim', 'evidenceClass', 'evidenceDigest'],
  snapshot: ['schema', 'snapshotId', 'sourceRegistryId', 'sourceRegistryDigest', 'classification', 'capturedAtStep', 'topologyPolicy', 'memoryAccounting', 'aggregateFitAllowed', 'seatCount', 'seats', 'authority', 'claimBoundary'],
  workload: ['schema', 'workloadId', 'sourceProfileId', 'sourceRunId', 'sourceTaskReceiptId', 'canonicalMissionStateIdBefore', 'canonicalMissionStateIdAfter', 'workloadClass', 'effectClass', 'minimumAcceleratorMemoryMiB', 'requiredRuntimeVersion', 'requiredAdapterVersion', 'requiredModelOrExecutableDigest', 'invocationContract', 'contextAndKvContract', 'acceptancePredicate', 'expectedOutputDigest', 'authority', 'claimBoundary'],
  invocation: ['schema', 'templateId', 'templateDigest', 'inputDigest', 'sourceTaskReceiptId'],
  context: ['schema', 'policy', 'contractDigest', 'sourceReceiptDigest', 'kvCachePolicy', 'maximumContextBytes'],
  acceptance: ['schema', 'type', 'expectedOutputDigest', 'independentVerifierIdentity', 'terminalReceiptRequired'],
  admission: ['schema', 'admissionId', 'snapshotId', 'workloadId', 'seatId', 'seatPresent', 'seatRole', 'seatState', 'seatMemoryMiB', 'minimumMemoryMiB', 'memoryAccounting', 'checks', 'disposition', 'reasons', 'authority', 'claimBoundary'],
  checks: ['seatPresent', 'stateAvailable', 'workloadClassSupported', 'runtimeExact', 'adapterExact', 'modelOrExecutableAdmitted', 'verifierAdmitted', 'independentMemoryFit'],
  route: ['schema', 'routeSelectionId', 'profileId', 'workloadId', 'selectionPolicy', 'selectedSeatId', 'seatIdentity', 'seatSnapshotDigest', 'hostIdentityClass', 'acceleratorIdentityClass', 'endpointIdentity', 'runtimeVersion', 'adapterVersion', 'modelOrExecutableDigest', 'invocationContract', 'contextAndKvContract', 'workloadClass', 'acceptancePredicate', 'residencyEvidence', 'powerStateEvidence', 'independentVerifierIdentity', 'outputDigest', 'terminalReceipt', 'candidateAdmissionIds', 'rejectedAdmissionIds', 'memoryAggregationUsed', 'status', 'authority', 'claimBoundary'],
  terminal: ['required', 'expectedSchema', 'currentReceiptId', 'status'],
  lease: ['schema', 'leaseId', 'routeSelectionId', 'workloadId', 'seatId', 'generation', 'issuedAtStep', 'expiresAtStep', 'leaseDurationSteps', 'status', 'completionAuthority', 'releaseEvidenceRequired', 'authority', 'claimBoundary'],
  slice: ['schema', 'routingSliceId', 'fabricProfileId', 'fabricProfileValidationSha256', 'sourceRunId', 'sourceTaskReceiptId', 'canonicalMissionStateIdBeforeRouting', 'canonicalMissionStateIdAfterRouting', 'seatSnapshot', 'workload', 'admissions', 'routeSelection', 'workerLease', 'acceptedRouteCount', 'admittedSeatCount', 'refusedSeatCount', 'executionStarted', 'completionAccepted', 'externalServiceCalls', 'operationalCredentials', 'physicalEvidenceBodies', 'authority', 'claimBoundary'],
});

export class FabricRuntimeError extends Error {
  constructor(code, message) {
    super(message);
    this.name = 'FabricRuntimeError';
    this.code = code;
  }
}

function requireCondition(condition, code, message) {
  if (!condition) throw new FabricRuntimeError(code, message);
}

function isRecord(value) {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) return false;
  const prototype = Object.getPrototypeOf(value);
  return prototype === Object.prototype || prototype === null;
}

function exactKeys(value, expected, code, label) {
  requireCondition(isRecord(value), code, `${label} must be an object`);
  requireCondition(
    canonicalJson(Object.keys(value).sort()) === canonicalJson([...expected].sort()),
    code,
    `${label} fields differ`,
  );
}

function boundedString(value, code, label, max = 4096) {
  requireCondition(typeof value === 'string', code, `${label} must be a string`);
  const normalized = value.trim();
  requireCondition(normalized.length > 0 && normalized.length <= max, code, `${label} is empty or unbounded`);
  return normalized;
}

function safeInteger(value, min, max, code, label) {
  requireCondition(Number.isSafeInteger(value) && value >= min && value <= max, code, `${label} is outside ${min}..${max}`);
  return value;
}

function uniqueStrings(values, code, label, allowEmpty = false) {
  requireCondition(Array.isArray(values), code, `${label} must be an array`);
  requireCondition(allowEmpty || values.length > 0, code, `${label} must be non-empty`);
  requireCondition(values.every((value) => typeof value === 'string' && value.trim().length > 0), code, `${label} contains an invalid value`);
  requireCondition(new Set(values).size === values.length, code, `${label} contains duplicates`);
}

function digest(prefix, value) {
  return `${prefix}_${createHash('sha256').update(canonicalJson(value), 'utf8').digest('hex')}`;
}

function bodyWithoutId(value, idKey) {
  const copy = structuredClone(value);
  delete copy[idKey];
  return copy;
}

function assertIdentity(value, prefix, idKey, code) {
  requireCondition(value[idKey] === digest(prefix, bodyWithoutId(value, idKey)), code, `${idKey} differs from content identity`);
}

function exactObject(value, expected, code, label) {
  requireCondition(canonicalJson(value) === canonicalJson(expected), code, `${label} differs`);
}

function validateResidency(value) {
  exactKeys(value, KEYS.residency, 'RESIDENCY_EVIDENCE_INVALID', 'residency evidence');
  requireCondition(RESIDENCY.has(value.residencyClass), 'RESIDENCY_EVIDENCE_INVALID', 'residency class is invalid');
  requireCondition(value.evidenceClass === 'synthetic_registry_assertion', 'RESIDENCY_EVIDENCE_INVALID', 'residency evidence is not synthetic');
  requireCondition(typeof value.evidenceDigest === 'string' && SHA256.test(value.evidenceDigest), 'RESIDENCY_EVIDENCE_INVALID', 'residency evidence digest is invalid');
}

function validatePower(value) {
  exactKeys(value, KEYS.power, 'POWER_EVIDENCE_INVALID', 'power-state evidence');
  requireCondition(POWER.has(value.claim), 'POWER_EVIDENCE_INVALID', 'power-state claim is invalid');
  if (value.claim === 'not_measured') {
    requireCondition(value.evidenceClass === 'none' && value.evidenceDigest === null, 'POWER_EVIDENCE_INVALID', 'unmeasured power state carries evidence');
    return;
  }
  requireCondition(value.evidenceClass === 'synthetic_registry_assertion' && typeof value.evidenceDigest === 'string' && SHA256.test(value.evidenceDigest), 'POWER_EVIDENCE_INVALID', 'synthetic power evidence is invalid');
}

function validateSeat(seat) {
  exactKeys(seat, KEYS.seat, 'SEAT_INVALID', 'seat');
  requireCondition(boundedString(seat.seatId, 'SEAT_INVALID', 'seatId').startsWith('SYN-SEAT-'), 'SEAT_INVALID', 'seat identity must remain synthetic');
  requireCondition(ROLES.has(seat.role), 'SEAT_INVALID', 'seat role is invalid');
  requireCondition(STATES.has(seat.state), 'SEAT_INVALID', 'seat state is invalid');
  requireCondition(boundedString(seat.hostIdentityClass, 'SEAT_INVALID', 'hostIdentityClass').startsWith('synthetic-'), 'SEAT_INVALID', 'host class is not synthetic');
  requireCondition(boundedString(seat.acceleratorIdentityClass, 'SEAT_INVALID', 'acceleratorIdentityClass').startsWith('synthetic-'), 'SEAT_INVALID', 'accelerator class is not synthetic');
  safeInteger(seat.acceleratorMemoryMiB, 1, MAX_MEMORY_MIB, 'SEAT_INVALID', 'acceleratorMemoryMiB');
  requireCondition(boundedString(seat.endpointIdentity, 'SEAT_INVALID', 'endpointIdentity').startsWith('SYN-ENDPOINT-'), 'SEAT_INVALID', 'endpoint identity is not synthetic');
  boundedString(seat.runtimeVersion, 'SEAT_INVALID', 'runtimeVersion');
  boundedString(seat.adapterVersion, 'SEAT_INVALID', 'adapterVersion');
  uniqueStrings(seat.supportedWorkloadClasses, 'SEAT_INVALID', 'supportedWorkloadClasses');
  uniqueStrings(seat.modelOrExecutableDigests, 'SEAT_INVALID', 'modelOrExecutableDigests');
  requireCondition(seat.modelOrExecutableDigests.every((row) => SHA256.test(row)), 'SEAT_INVALID', 'model or executable digest is invalid');
  uniqueStrings(seat.verifierIds, 'SEAT_INVALID', 'verifierIds');
  requireCondition(seat.verifierIds.every((row) => row.startsWith('SYN-VERIFIER-')), 'SEAT_INVALID', 'verifier identity is not synthetic');
  validateResidency(seat.residencyEvidence);
  validatePower(seat.powerStateEvidence);
  requireCondition(boundedString(seat.claimBoundary, 'SEAT_INVALID', 'seat claimBoundary').toLowerCase().includes('invented'), 'SEAT_INVALID', 'seat boundary does not say invented');
  return seat;
}

export function validateInventedSeatRegistry(registry) {
  exactKeys(registry, KEYS.registry, 'SEAT_REGISTRY_INVALID', 'seat registry');
  requireCondition(registry.schema === 'spectra-anchor-node-invented-seat-registry/1', 'SEAT_REGISTRY_SCHEMA_INVALID', 'seat registry schema is invalid');
  requireCondition(boundedString(registry.registryId, 'SEAT_REGISTRY_INVALID', 'registryId').startsWith('SYN-'), 'SEAT_REGISTRY_INVALID', 'registry identity is not synthetic');
  requireCondition(registry.classification === 'invented_unclassified_synthetic_only', 'SEAT_REGISTRY_CLASSIFICATION_INVALID', 'seat registry classification differs');
  safeInteger(registry.capturedAtStep, 0, MAX_STEP, 'SEAT_REGISTRY_INVALID', 'capturedAtStep');
  requireCondition(registry.topologyPolicy === 'independent_seats_no_memory_pooling', 'SEAT_REGISTRY_TOPOLOGY_INVALID', 'registry permits memory pooling');
  requireCondition(Array.isArray(registry.seats) && registry.seats.length > 0 && registry.seats.length <= 64, 'SEAT_REGISTRY_INVALID', 'seat denominator is invalid');
  const seatIds = new Set();
  const endpoints = new Set();
  for (const seat of registry.seats) {
    validateSeat(seat);
    requireCondition(!seatIds.has(seat.seatId), 'SEAT_REGISTRY_DUPLICATE', `duplicate seat ${seat.seatId}`);
    requireCondition(!endpoints.has(seat.endpointIdentity), 'SEAT_REGISTRY_DUPLICATE', `duplicate endpoint ${seat.endpointIdentity}`);
    seatIds.add(seat.seatId);
    endpoints.add(seat.endpointIdentity);
  }
  requireCondition(boundedString(registry.claimBoundary, 'SEAT_REGISTRY_INVALID', 'registry claimBoundary').toLowerCase().includes('no real estate topology'), 'SEAT_REGISTRY_INVALID', 'registry boundary does not exclude real Estate topology');
  const encoded = canonicalJson(registry).toLowerCase();
  for (const forbidden of ['octo-w01', 'octo-l01', 'c:\\', '/home/', 'ssh://', 'http://', 'https://', 'authorization: bearer', 'begin private key']) {
    requireCondition(!encoded.includes(forbidden), 'PRIVATE_EVIDENCE_BOUNDARY_INVALID', `public registry contains forbidden material: ${forbidden}`);
  }
  return registry;
}

export function createSeatSnapshot(registry) {
  validateInventedSeatRegistry(registry);
  const body = {
    schema: 'estate-seat-snapshot/1',
    sourceRegistryId: registry.registryId,
    sourceRegistryDigest: digest('estateinventedregistry1', registry),
    classification: registry.classification,
    capturedAtStep: registry.capturedAtStep,
    topologyPolicy: registry.topologyPolicy,
    memoryAccounting: 'per_seat_only',
    aggregateFitAllowed: false,
    seatCount: registry.seats.length,
    seats: registry.seats.map(structuredClone).sort((a, b) => a.seatId.localeCompare(b.seatId)),
    authority: false,
    claimBoundary: 'Content-addressed snapshot of an invented public seat registry. It is not a physical inventory, pooled-memory surface, scheduler grant, or mission authority source.',
  };
  return { ...body, snapshotId: digest('estateseatsnapshot1', body) };
}

export function validateSeatSnapshot(snapshot) {
  exactKeys(snapshot, KEYS.snapshot, 'SEAT_SNAPSHOT_INVALID', 'seat snapshot');
  requireCondition(snapshot.schema === 'estate-seat-snapshot/1', 'SEAT_SNAPSHOT_SCHEMA_INVALID', 'seat snapshot schema is invalid');
  requireCondition(snapshot.classification === 'invented_unclassified_synthetic_only', 'SEAT_SNAPSHOT_INVALID', 'snapshot classification differs');
  requireCondition(snapshot.topologyPolicy === 'independent_seats_no_memory_pooling' && snapshot.memoryAccounting === 'per_seat_only' && snapshot.aggregateFitAllowed === false, 'SEAT_SNAPSHOT_MEMORY_INVALID', 'snapshot permits pooled memory');
  requireCondition(Number.isSafeInteger(snapshot.seatCount) && snapshot.seatCount > 0 && Array.isArray(snapshot.seats) && snapshot.seats.length === snapshot.seatCount, 'SEAT_SNAPSHOT_INVALID', 'snapshot denominator differs');
  const ids = new Set();
  for (const seat of snapshot.seats) {
    validateSeat(seat);
    requireCondition(!ids.has(seat.seatId), 'SEAT_SNAPSHOT_INVALID', `duplicate seat ${seat.seatId}`);
    ids.add(seat.seatId);
  }
  requireCondition(snapshot.authority === false, 'SEAT_SNAPSHOT_AUTHORITY_INVALID', 'snapshot carries authority');
  assertIdentity(snapshot, 'estateseatsnapshot1', 'snapshotId', 'SEAT_SNAPSHOT_ID_INVALID');
  return snapshot;
}

export function verifySeatSnapshot(snapshot, registry) {
  validateSeatSnapshot(snapshot);
  exactObject(snapshot, createSeatSnapshot(registry), 'SEAT_SNAPSHOT_REPLAY_MISMATCH', 'seat snapshot replay');
  return snapshot;
}

export function createFabricWorkload(bundle) {
  verifyVerticalSlice(bundle);
  requireCondition(bundle.taskReceipt.effectClass === 'local_artifact_only', 'FABRIC_WORKLOAD_EFFECT_INVALID', 'source task is not local-artifact-only');
  const stateId = bundle.missionStateAfter.missionStateId;
  const body = {
    schema: 'estate-fabric-workload/1',
    sourceProfileId: bundle.profileId,
    sourceRunId: bundle.runId,
    sourceTaskReceiptId: bundle.taskReceipt.taskReceiptId,
    canonicalMissionStateIdBefore: stateId,
    canonicalMissionStateIdAfter: stateId,
    workloadClass: 'local_artifact_reconstruction',
    effectClass: 'local_artifact_only',
    minimumAcceleratorMemoryMiB: 16384,
    requiredRuntimeVersion: 'synthetic-local-executor/1.0.0',
    requiredAdapterVersion: 'spectra-estate-fabric-adapter/0.1.0',
    requiredModelOrExecutableDigest: MODEL_DIGEST,
    invocationContract: {
      schema: 'estate-fabric-invocation-contract/1',
      templateId: 'spectra-anchor-node-local-artifact-template/1',
      templateDigest: TEMPLATE_DIGEST,
      inputDigest: digest('estatefabricinput1', bundle.taskReceipt.output),
      sourceTaskReceiptId: bundle.taskReceipt.taskReceiptId,
    },
    contextAndKvContract: {
      schema: 'estate-fabric-context-contract/1',
      policy: 'exact_source_receipt_only',
      contractDigest: CONTEXT_DIGEST,
      sourceReceiptDigest: digest('estatefabricsourcereceipt1', bundle.taskReceipt),
      kvCachePolicy: 'none',
      maximumContextBytes: 65536,
    },
    acceptancePredicate: {
      schema: 'estate-fabric-acceptance-predicate/1',
      type: 'exact_output_digest_and_independent_verifier',
      expectedOutputDigest: bundle.taskReceipt.outputDigest,
      independentVerifierIdentity: VERIFIER_ID,
      terminalReceiptRequired: true,
    },
    expectedOutputDigest: bundle.taskReceipt.outputDigest,
    authority: false,
    claimBoundary: 'Synthetic reconstruction workload derived from one admitted MP01 local artifact. It is not a new mission task, command, field action, model qualification, or physical Estate claim.',
  };
  return { ...body, workloadId: digest('estatefabricworkload1', body) };
}

export function validateFabricWorkload(workload) {
  exactKeys(workload, KEYS.workload, 'FABRIC_WORKLOAD_INVALID', 'fabric workload');
  requireCondition(workload.schema === 'estate-fabric-workload/1', 'FABRIC_WORKLOAD_SCHEMA_INVALID', 'workload schema is invalid');
  requireCondition(workload.canonicalMissionStateIdBefore === workload.canonicalMissionStateIdAfter, 'FABRIC_WORKLOAD_STATE_MUTATION', 'workload mutates canonical state');
  requireCondition(workload.workloadClass === 'local_artifact_reconstruction' && workload.effectClass === 'local_artifact_only', 'FABRIC_WORKLOAD_EFFECT_INVALID', 'workload class or effect differs');
  safeInteger(workload.minimumAcceleratorMemoryMiB, 1, MAX_MEMORY_MIB, 'FABRIC_WORKLOAD_INVALID', 'minimumAcceleratorMemoryMiB');
  requireCondition(SHA256.test(workload.requiredModelOrExecutableDigest), 'FABRIC_WORKLOAD_INVALID', 'required model digest is invalid');
  exactKeys(workload.invocationContract, KEYS.invocation, 'FABRIC_WORKLOAD_INVALID', 'invocation contract');
  exactKeys(workload.contextAndKvContract, KEYS.context, 'FABRIC_WORKLOAD_INVALID', 'context contract');
  exactKeys(workload.acceptancePredicate, KEYS.acceptance, 'FABRIC_WORKLOAD_INVALID', 'acceptance predicate');
  requireCondition(workload.invocationContract.schema === 'estate-fabric-invocation-contract/1' && workload.invocationContract.templateDigest === TEMPLATE_DIGEST, 'FABRIC_WORKLOAD_INVALID', 'invocation contract differs');
  requireCondition(workload.contextAndKvContract.schema === 'estate-fabric-context-contract/1' && workload.contextAndKvContract.policy === 'exact_source_receipt_only' && workload.contextAndKvContract.contractDigest === CONTEXT_DIGEST && workload.contextAndKvContract.kvCachePolicy === 'none', 'FABRIC_WORKLOAD_INVALID', 'context contract differs');
  requireCondition(workload.acceptancePredicate.schema === 'estate-fabric-acceptance-predicate/1' && workload.acceptancePredicate.type === 'exact_output_digest_and_independent_verifier' && workload.acceptancePredicate.expectedOutputDigest === workload.expectedOutputDigest && workload.acceptancePredicate.independentVerifierIdentity === VERIFIER_ID && workload.acceptancePredicate.terminalReceiptRequired === true, 'FABRIC_WORKLOAD_INVALID', 'acceptance predicate differs');
  requireCondition(workload.authority === false, 'FABRIC_WORKLOAD_AUTHORITY_INVALID', 'workload carries authority');
  assertIdentity(workload, 'estatefabricworkload1', 'workloadId', 'FABRIC_WORKLOAD_ID_INVALID');
  return workload;
}

export function verifyFabricWorkload(workload, bundle) {
  validateFabricWorkload(workload);
  exactObject(workload, createFabricWorkload(bundle), 'FABRIC_WORKLOAD_REPLAY_MISMATCH', 'fabric workload replay');
  return workload;
}

function createChecks(seat, workload) {
  if (!seat) {
    return {
      seatPresent: false,
      stateAvailable: false,
      workloadClassSupported: false,
      runtimeExact: false,
      adapterExact: false,
      modelOrExecutableAdmitted: false,
      verifierAdmitted: false,
      independentMemoryFit: false,
    };
  }
  return {
    seatPresent: true,
    stateAvailable: seat.state === 'available',
    workloadClassSupported: seat.supportedWorkloadClasses.includes(workload.workloadClass),
    runtimeExact: seat.runtimeVersion === workload.requiredRuntimeVersion,
    adapterExact: seat.adapterVersion === workload.requiredAdapterVersion,
    modelOrExecutableAdmitted: seat.modelOrExecutableDigests.includes(workload.requiredModelOrExecutableDigest),
    verifierAdmitted: seat.verifierIds.includes(workload.acceptancePredicate.independentVerifierIdentity),
    independentMemoryFit: seat.acceleratorMemoryMiB >= workload.minimumAcceleratorMemoryMiB,
  };
}

function reasonsFor(checks) {
  if (!checks.seatPresent) return ['SEAT_NOT_IN_SNAPSHOT'];
  const rows = [];
  if (!checks.stateAvailable) rows.push('SEAT_NOT_AVAILABLE');
  if (!checks.workloadClassSupported) rows.push('WORKLOAD_CLASS_UNSUPPORTED');
  if (!checks.runtimeExact) rows.push('RUNTIME_VERSION_MISMATCH');
  if (!checks.adapterExact) rows.push('ADAPTER_VERSION_MISMATCH');
  if (!checks.modelOrExecutableAdmitted) rows.push('MODEL_OR_EXECUTABLE_NOT_ADMITTED');
  if (!checks.verifierAdmitted) rows.push('VERIFIER_NOT_ADMITTED');
  if (!checks.independentMemoryFit) rows.push('INSUFFICIENT_INDEPENDENT_SEAT_MEMORY');
  return rows;
}

export function createSeatAdmission({ snapshot, workload, seatId }) {
  validateSeatSnapshot(snapshot);
  validateFabricWorkload(workload);
  boundedString(seatId, 'SEAT_ADMISSION_INVALID', 'seatId');
  const seat = snapshot.seats.find((row) => row.seatId === seatId) ?? null;
  const checks = createChecks(seat, workload);
  const reasons = reasonsFor(checks);
  const body = {
    schema: 'estate-seat-admission/1',
    snapshotId: snapshot.snapshotId,
    workloadId: workload.workloadId,
    seatId,
    seatPresent: checks.seatPresent,
    seatRole: seat?.role ?? null,
    seatState: seat?.state ?? null,
    seatMemoryMiB: seat?.acceleratorMemoryMiB ?? null,
    minimumMemoryMiB: workload.minimumAcceleratorMemoryMiB,
    memoryAccounting: 'independent_seat_only',
    checks,
    disposition: reasons.length === 0 ? 'admit' : 'refuse',
    reasons,
    authority: false,
    claimBoundary: 'Seat-specific synthetic admission result. It does not pool memory, grant execution success, mutate mission state, qualify physical hardware, or create authority.',
  };
  return { ...body, admissionId: digest('estateseatadmission1', body) };
}

export function validateSeatAdmission(admission) {
  exactKeys(admission, KEYS.admission, 'SEAT_ADMISSION_INVALID', 'seat admission');
  requireCondition(admission.schema === 'estate-seat-admission/1', 'SEAT_ADMISSION_SCHEMA_INVALID', 'admission schema is invalid');
  exactKeys(admission.checks, KEYS.checks, 'SEAT_ADMISSION_INVALID', 'admission checks');
  requireCondition(KEYS.checks.every((key) => typeof admission.checks[key] === 'boolean'), 'SEAT_ADMISSION_INVALID', 'admission checks are not boolean');
  requireCondition(admission.memoryAccounting === 'independent_seat_only', 'SEAT_ADMISSION_MEMORY_INVALID', 'admission uses pooled memory');
  requireCondition(['admit', 'refuse'].includes(admission.disposition), 'SEAT_ADMISSION_INVALID', 'admission disposition is invalid');
  uniqueStrings(admission.reasons, 'SEAT_ADMISSION_INVALID', 'admission reasons', true);
  requireCondition(admission.reasons.every((reason) => REASONS.has(reason)), 'SEAT_ADMISSION_INVALID', 'admission reason is unsupported');
  requireCondition((admission.disposition === 'admit' && admission.reasons.length === 0) || (admission.disposition === 'refuse' && admission.reasons.length > 0), 'SEAT_ADMISSION_INVALID', 'admission reasons and disposition disagree');
  if (admission.seatPresent) {
    requireCondition(ROLES.has(admission.seatRole) && STATES.has(admission.seatState) && Number.isSafeInteger(admission.seatMemoryMiB), 'SEAT_ADMISSION_INVALID', 'present seat evidence is incomplete');
  } else {
    requireCondition(admission.seatRole === null && admission.seatState === null && admission.seatMemoryMiB === null && canonicalJson(admission.reasons) === canonicalJson(['SEAT_NOT_IN_SNAPSHOT']), 'SEAT_ADMISSION_INVALID', 'absent seat refusal is incomplete');
  }
  requireCondition(admission.authority === false, 'SEAT_ADMISSION_AUTHORITY_INVALID', 'admission carries authority');
  assertIdentity(admission, 'estateseatadmission1', 'admissionId', 'SEAT_ADMISSION_ID_INVALID');
  return admission;
}

export function verifySeatAdmission(admission, snapshot, workload) {
  validateSeatAdmission(admission);
  exactObject(admission, createSeatAdmission({ snapshot, workload, seatId: admission.seatId }), 'SEAT_ADMISSION_REPLAY_MISMATCH', 'seat admission replay');
  return admission;
}

export function createSeatAdmissions(snapshot, workload) {
  validateSeatSnapshot(snapshot);
  validateFabricWorkload(workload);
  return snapshot.seats.map((seat) => createSeatAdmission({ snapshot, workload, seatId: seat.seatId }));
}

function validateAdmissionDenominator(admissions, snapshot, workload) {
  requireCondition(Array.isArray(admissions) && admissions.length === snapshot.seatCount, 'SEAT_ADMISSION_DENOMINATOR_INVALID', 'admission denominator differs');
  requireCondition(canonicalJson(admissions.map((row) => row.seatId).sort()) === canonicalJson(snapshot.seats.map((row) => row.seatId).sort()), 'SEAT_ADMISSION_DENOMINATOR_INVALID', 'admissions do not exactly cover snapshot seats');
  for (const admission of admissions) verifySeatAdmission(admission, snapshot, workload);
}

export function selectRoute({ snapshot, workload, admissions, preferredSeatId = null }) {
  validateSeatSnapshot(snapshot);
  validateFabricWorkload(workload);
  validateAdmissionDenominator(admissions, snapshot, workload);
  const admitted = admissions.filter((row) => row.disposition === 'admit');
  requireCondition(admitted.length > 0, 'NO_QUALIFIED_ROUTE', 'no independently qualified seat can run the workload');
  let selected;
  let selectionPolicy;
  if (preferredSeatId !== null) {
    selected = admitted.find((row) => row.seatId === preferredSeatId);
    requireCondition(selected !== undefined, 'PREFERRED_SEAT_NOT_ADMITTED', 'preferred seat is not admitted');
    selectionPolicy = 'explicit_admitted_seat';
  } else {
    selected = [...admitted].sort((a, b) => ROLE_RANK.get(a.seatRole) - ROLE_RANK.get(b.seatRole) || a.seatId.localeCompare(b.seatId))[0];
    selectionPolicy = 'resident_then_fallback_then_optional_lexical';
  }
  const seat = snapshot.seats.find((row) => row.seatId === selected.seatId);
  const body = {
    schema: 'estate-route-selection/1',
    profileId: 'spectra-anchor-node/estate-fabric/0.1',
    workloadId: workload.workloadId,
    selectionPolicy,
    selectedSeatId: seat.seatId,
    seatIdentity: seat.seatId,
    seatSnapshotDigest: snapshot.snapshotId,
    hostIdentityClass: seat.hostIdentityClass,
    acceleratorIdentityClass: seat.acceleratorIdentityClass,
    endpointIdentity: seat.endpointIdentity,
    runtimeVersion: seat.runtimeVersion,
    adapterVersion: seat.adapterVersion,
    modelOrExecutableDigest: workload.requiredModelOrExecutableDigest,
    invocationContract: structuredClone(workload.invocationContract),
    contextAndKvContract: structuredClone(workload.contextAndKvContract),
    workloadClass: workload.workloadClass,
    acceptancePredicate: structuredClone(workload.acceptancePredicate),
    residencyEvidence: structuredClone(seat.residencyEvidence),
    powerStateEvidence: structuredClone(seat.powerStateEvidence),
    independentVerifierIdentity: workload.acceptancePredicate.independentVerifierIdentity,
    outputDigest: workload.expectedOutputDigest,
    terminalReceipt: {
      required: true,
      expectedSchema: 'estate-fabric-run/1',
      currentReceiptId: null,
      status: 'pending_execution',
    },
    candidateAdmissionIds: [...admitted].sort((a, b) => a.seatId.localeCompare(b.seatId)).map((row) => row.admissionId),
    rejectedAdmissionIds: admissions.filter((row) => row.disposition === 'refuse').sort((a, b) => a.seatId.localeCompare(b.seatId)).map((row) => row.admissionId),
    memoryAggregationUsed: false,
    status: 'selected_pending_execution',
    authority: false,
    claimBoundary: 'Deterministic seat-specific route selection over admitted synthetic evidence. It starts no execution, accepts no completion, pools no memory, qualifies no physical hardware, mutates no mission state, and grants no authority.',
  };
  return { ...body, routeSelectionId: digest('estaterouteselection1', body) };
}

export function validateRouteSelection(route) {
  exactKeys(route, KEYS.route, 'ROUTE_SELECTION_INVALID', 'route selection');
  requireCondition(route.schema === 'estate-route-selection/1', 'ROUTE_SELECTION_SCHEMA_INVALID', 'route schema is invalid');
  requireCondition(route.selectedSeatId === route.seatIdentity, 'ROUTE_SELECTION_INVALID', 'selected seat identities differ');
  exactKeys(route.invocationContract, KEYS.invocation, 'ROUTE_SELECTION_INVALID', 'route invocation contract');
  exactKeys(route.contextAndKvContract, KEYS.context, 'ROUTE_SELECTION_INVALID', 'route context contract');
  exactKeys(route.acceptancePredicate, KEYS.acceptance, 'ROUTE_SELECTION_INVALID', 'route acceptance predicate');
  validateResidency(route.residencyEvidence);
  validatePower(route.powerStateEvidence);
  exactKeys(route.terminalReceipt, KEYS.terminal, 'ROUTE_SELECTION_INVALID', 'terminal receipt contract');
  exactObject(route.terminalReceipt, { required: true, expectedSchema: 'estate-fabric-run/1', currentReceiptId: null, status: 'pending_execution' }, 'ROUTE_SELECTION_TERMINAL_INVALID', 'terminal receipt contract');
  uniqueStrings(route.candidateAdmissionIds, 'ROUTE_SELECTION_INVALID', 'candidateAdmissionIds');
  uniqueStrings(route.rejectedAdmissionIds, 'ROUTE_SELECTION_INVALID', 'rejectedAdmissionIds', true);
  requireCondition(route.memoryAggregationUsed === false, 'ROUTE_SELECTION_MEMORY_INVALID', 'route aggregates independent memory');
  requireCondition(route.status === 'selected_pending_execution', 'ROUTE_SELECTION_STATUS_INVALID', 'route serializes execution success');
  requireCondition(route.authority === false, 'ROUTE_SELECTION_AUTHORITY_INVALID', 'route carries authority');
  assertIdentity(route, 'estaterouteselection1', 'routeSelectionId', 'ROUTE_SELECTION_ID_INVALID');
  return route;
}

export function verifyRouteSelection(route, snapshot, workload, admissions) {
  validateRouteSelection(route);
  const preferredSeatId = route.selectionPolicy === 'explicit_admitted_seat' ? route.selectedSeatId : null;
  exactObject(route, selectRoute({ snapshot, workload, admissions, preferredSeatId }), 'ROUTE_SELECTION_REPLAY_MISMATCH', 'route selection replay');
  return route;
}

export function createWorkerLease({ routeSelection, generation = 1, issuedAtStep = 20, leaseDurationSteps = 5 }) {
  validateRouteSelection(routeSelection);
  safeInteger(generation, 1, MAX_STEP, 'WORKER_LEASE_INVALID', 'generation');
  safeInteger(issuedAtStep, 0, MAX_STEP, 'WORKER_LEASE_INVALID', 'issuedAtStep');
  safeInteger(leaseDurationSteps, 1, MAX_LEASE_STEPS, 'WORKER_LEASE_INVALID', 'leaseDurationSteps');
  requireCondition(issuedAtStep + leaseDurationSteps <= MAX_STEP, 'WORKER_LEASE_INVALID', 'lease expiry exceeds safe step bound');
  const body = {
    schema: 'estate-worker-lease/1',
    routeSelectionId: routeSelection.routeSelectionId,
    workloadId: routeSelection.workloadId,
    seatId: routeSelection.selectedSeatId,
    generation,
    issuedAtStep,
    expiresAtStep: issuedAtStep + leaseDurationSteps,
    leaseDurationSteps,
    status: 'active_pending_execution',
    completionAuthority: false,
    releaseEvidenceRequired: true,
    authority: false,
    claimBoundary: 'Finite synthetic worker lease for one selected seat. It grants no completion, mission, command, field, physical-hardware, or evaluator authority and may not be released without terminal evidence.',
  };
  return { ...body, leaseId: digest('estateworkerlease1', body) };
}

export function validateWorkerLease(lease) {
  exactKeys(lease, KEYS.lease, 'WORKER_LEASE_INVALID', 'worker lease');
  requireCondition(lease.schema === 'estate-worker-lease/1', 'WORKER_LEASE_SCHEMA_INVALID', 'lease schema is invalid');
  safeInteger(lease.generation, 1, MAX_STEP, 'WORKER_LEASE_INVALID', 'generation');
  safeInteger(lease.issuedAtStep, 0, MAX_STEP, 'WORKER_LEASE_INVALID', 'issuedAtStep');
  safeInteger(lease.expiresAtStep, 1, MAX_STEP, 'WORKER_LEASE_INVALID', 'expiresAtStep');
  safeInteger(lease.leaseDurationSteps, 1, MAX_LEASE_STEPS, 'WORKER_LEASE_INVALID', 'leaseDurationSteps');
  requireCondition(lease.expiresAtStep === lease.issuedAtStep + lease.leaseDurationSteps, 'WORKER_LEASE_INVALID', 'lease expiry differs from finite duration');
  requireCondition(lease.status === 'active_pending_execution', 'WORKER_LEASE_STATUS_INVALID', 'lease serializes completion');
  requireCondition(lease.completionAuthority === false && lease.releaseEvidenceRequired === true && lease.authority === false, 'WORKER_LEASE_AUTHORITY_INVALID', 'lease grants authority or evidence-free release');
  assertIdentity(lease, 'estateworkerlease1', 'leaseId', 'WORKER_LEASE_ID_INVALID');
  return lease;
}

export function verifyWorkerLease(lease, routeSelection) {
  validateWorkerLease(lease);
  validateRouteSelection(routeSelection);
  requireCondition(lease.routeSelectionId === routeSelection.routeSelectionId && lease.workloadId === routeSelection.workloadId && lease.seatId === routeSelection.selectedSeatId, 'WORKER_LEASE_BINDING_INVALID', 'lease belongs to another route, workload, or seat');
  exactObject(lease, createWorkerLease({ routeSelection, generation: lease.generation, issuedAtStep: lease.issuedAtStep, leaseDurationSteps: lease.leaseDurationSteps }), 'WORKER_LEASE_REPLAY_MISMATCH', 'worker lease replay');
  return lease;
}

export function workerLeaseStateAt(lease, observedAtStep) {
  validateWorkerLease(lease);
  safeInteger(observedAtStep, 0, MAX_STEP, 'WORKER_LEASE_OBSERVATION_INVALID', 'observedAtStep');
  return observedAtStep <= lease.expiresAtStep ? 'active' : 'expired';
}

export function runFabricRoutingSlice({ bundle, fabricProfile, registry, preferredSeatId = null, leaseGeneration = 1, leaseIssuedAtStep = 20, leaseDurationSteps = 5 }) {
  verifyVerticalSlice(bundle);
  validateFabricProfile(fabricProfile);
  const profileValidation = fabricProfileReceipt(fabricProfile);
  const seatSnapshot = createSeatSnapshot(registry);
  const workload = createFabricWorkload(bundle);
  const admissions = createSeatAdmissions(seatSnapshot, workload);
  const routeSelection = selectRoute({ snapshot: seatSnapshot, workload, admissions, preferredSeatId });
  const workerLease = createWorkerLease({ routeSelection, generation: leaseGeneration, issuedAtStep: leaseIssuedAtStep, leaseDurationSteps });
  const stateId = bundle.missionStateAfter.missionStateId;
  const body = {
    schema: 'spectra-anchor-node-estate-fabric-routing-slice/1',
    fabricProfileId: fabricProfile.profileId,
    fabricProfileValidationSha256: profileValidation.sha256,
    sourceRunId: bundle.runId,
    sourceTaskReceiptId: bundle.taskReceipt.taskReceiptId,
    canonicalMissionStateIdBeforeRouting: stateId,
    canonicalMissionStateIdAfterRouting: stateId,
    seatSnapshot,
    workload,
    admissions,
    routeSelection,
    workerLease,
    acceptedRouteCount: 1,
    admittedSeatCount: admissions.filter((row) => row.disposition === 'admit').length,
    refusedSeatCount: admissions.filter((row) => row.disposition === 'refuse').length,
    executionStarted: false,
    completionAccepted: false,
    externalServiceCalls: 0,
    operationalCredentials: 0,
    physicalEvidenceBodies: 0,
    authority: false,
    claimBoundary: 'This slice proves deterministic synthetic seat snapshot, admission, route selection, and finite lease construction. It starts no execution, accepts no completion, imports no private evidence, mutates no mission state, and grants no authority.',
  };
  return { ...body, routingSliceId: digest('estatefabricroutingslice1', body) };
}

export function validateFabricRoutingSlice(slice) {
  exactKeys(slice, KEYS.slice, 'FABRIC_ROUTING_SLICE_INVALID', 'fabric routing slice');
  requireCondition(slice.schema === 'spectra-anchor-node-estate-fabric-routing-slice/1', 'FABRIC_ROUTING_SLICE_SCHEMA_INVALID', 'routing slice schema is invalid');
  requireCondition(SHA256.test(slice.fabricProfileValidationSha256), 'FABRIC_ROUTING_SLICE_INVALID', 'profile validation digest is invalid');
  requireCondition(slice.canonicalMissionStateIdBeforeRouting === slice.canonicalMissionStateIdAfterRouting, 'FABRIC_ROUTING_STATE_MUTATION', 'routing mutated canonical state');
  validateSeatSnapshot(slice.seatSnapshot);
  validateFabricWorkload(slice.workload);
  validateAdmissionDenominator(slice.admissions, slice.seatSnapshot, slice.workload);
  verifyRouteSelection(slice.routeSelection, slice.seatSnapshot, slice.workload, slice.admissions);
  verifyWorkerLease(slice.workerLease, slice.routeSelection);
  requireCondition(slice.acceptedRouteCount === 1, 'FABRIC_ROUTING_SLICE_INVALID', 'routing did not select exactly one route');
  requireCondition(slice.admittedSeatCount === slice.admissions.filter((row) => row.disposition === 'admit').length && slice.refusedSeatCount === slice.admissions.filter((row) => row.disposition === 'refuse').length, 'FABRIC_ROUTING_SLICE_INVALID', 'admission counts differ');
  requireCondition(slice.executionStarted === false && slice.completionAccepted === false && slice.externalServiceCalls === 0 && slice.operationalCredentials === 0 && slice.physicalEvidenceBodies === 0 && slice.authority === false, 'FABRIC_ROUTING_CLAIM_INVALID', 'routing invents execution, completion, private evidence, dependency, or authority');
  assertIdentity(slice, 'estatefabricroutingslice1', 'routingSliceId', 'FABRIC_ROUTING_SLICE_ID_INVALID');
  return slice;
}

export function verifyFabricRoutingSlice(slice, { bundle, fabricProfile, registry }) {
  validateFabricRoutingSlice(slice);
  verifyVerticalSlice(bundle);
  validateFabricProfile(fabricProfile);
  verifySeatSnapshot(slice.seatSnapshot, registry);
  verifyFabricWorkload(slice.workload, bundle);
  const preferredSeatId = slice.routeSelection.selectionPolicy === 'explicit_admitted_seat' ? slice.routeSelection.selectedSeatId : null;
  const replayed = runFabricRoutingSlice({ bundle, fabricProfile, registry, preferredSeatId, leaseGeneration: slice.workerLease.generation, leaseIssuedAtStep: slice.workerLease.issuedAtStep, leaseDurationSteps: slice.workerLease.leaseDurationSteps });
  exactObject(slice, replayed, 'FABRIC_ROUTING_REPLAY_MISMATCH', 'fabric routing replay');
  const body = {
    schema: 'estate-fabric-verification/1',
    routingSliceId: slice.routingSliceId,
    sourceRunId: slice.sourceRunId,
    status: 'PASS',
    snapshotVerified: true,
    admissionDenominatorVerified: true,
    routeVerified: true,
    leaseVerified: true,
    canonicalStateUnchanged: true,
    memoryAggregationUsed: false,
    executionClaimed: false,
    completionClaimed: false,
    physicalQualification: false,
    representativeOperatorQualification: false,
    externalServiceCalls: 0,
    operationalCredentials: 0,
    authority: 'none',
    claimBoundary: 'This receipt proves deterministic replay of the synthetic routing slice only. It grants no execution success, physical, operator, field, evaluator, mission, or command authority.',
  };
  return { ...body, verificationId: digest('estatefabricverification1', body) };
}

async function writeJson(path, value) {
  await mkdir(dirname(path), { recursive: true });
  await writeFile(path, `${JSON.stringify(value, null, 2)}\n`, 'utf8');
}

async function loadDefaults() {
  const [fabricProfileText, registryText] = await Promise.all([
    readFile(DEFAULT_PROFILE, 'utf8'),
    readFile(DEFAULT_REGISTRY, 'utf8'),
  ]);
  return {
    fabricProfile: JSON.parse(fabricProfileText),
    registry: JSON.parse(registryText),
  };
}

async function main(argv) {
  const command = argv[2];
  if (command === 'run') {
    const bundle = JSON.parse(await readFile(resolve(argv[3]), 'utf8'));
    const outputPath = resolve(argv[4]);
    const defaults = await loadDefaults();
    const slice = runFabricRoutingSlice({ bundle, ...defaults });
    await writeJson(outputPath, slice);
    process.stdout.write(`${JSON.stringify({ status: 'PASS', routingSliceId: slice.routingSliceId, seatSnapshotId: slice.seatSnapshot.snapshotId, selectedSeatId: slice.routeSelection.selectedSeatId, leaseId: slice.workerLease.leaseId, outputPath }, null, 2)}\n`);
    return;
  }
  if (command === 'verify') {
    const [bundleText, sliceText, defaults] = await Promise.all([
      readFile(resolve(argv[3]), 'utf8'),
      readFile(resolve(argv[4]), 'utf8'),
      loadDefaults(),
    ]);
    const outputPath = resolve(argv[5]);
    const verification = verifyFabricRoutingSlice(JSON.parse(sliceText), {
      bundle: JSON.parse(bundleText),
      ...defaults,
    });
    await writeJson(outputPath, verification);
    process.stdout.write(`${JSON.stringify(verification, null, 2)}\n`);
    return;
  }
  throw new FabricRuntimeError('COMMAND_INVALID', 'usage: fabric_runtime.mjs run <vertical-slice.json> <routing-slice.json> | verify <vertical-slice.json> <routing-slice.json> <verification.json>');
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  main(process.argv).catch((error) => {
    process.stderr.write(`${error instanceof FabricRuntimeError ? error.code : 'UNEXPECTED_ERROR'}: ${error.message}\n`);
    process.exitCode = 1;
  });
}

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
const MAX_SEATS = 64;
const MAX_MEMORY_MIB = 1_048_576;
const MAX_STEP = 1_000_000_000;
const MAX_LEASE_STEPS = 1_000_000;
const MODEL_OR_EXECUTABLE_DIGEST = 'bd14617d51d579adff77b9d359ca8e32c48167420919b0d5df73672e1672ea53';
const TEMPLATE_DIGEST = 'be9142c3f6586867f2e6b14deb5434fd90883c98e342c63751635f5d879486cc';
const CONTEXT_CONTRACT_DIGEST = '589c33eb597c451b5dc586ca8d1f1be51a3fbcbfeb910f9c1022f1d3b7da6e96';
const VERIFIER_ID = 'SYN-VERIFIER-LOCAL-01';

const ROLES = new Set(['resident', 'fallback', 'optional']);
const ROLE_RANK = new Map([
  ['resident', 0],
  ['fallback', 1],
  ['optional', 2],
]);
const SEAT_STATES = new Set(['available', 'inaccessible', 'retired']);
const RESIDENCY_CLASSES = new Set(['resident', 'resident_fallback', 'optional_burst']);
const POWER_CLAIMS = new Set(['not_measured', 'synthetic_available', 'synthetic_unavailable']);
const ADMISSION_REASONS = new Set([
  'SEAT_NOT_IN_SNAPSHOT',
  'SEAT_NOT_AVAILABLE',
  'WORKLOAD_CLASS_UNSUPPORTED',
  'RUNTIME_VERSION_MISMATCH',
  'ADAPTER_VERSION_MISMATCH',
  'MODEL_OR_EXECUTABLE_NOT_ADMITTED',
  'VERIFIER_NOT_ADMITTED',
  'INSUFFICIENT_INDEPENDENT_SEAT_MEMORY',
]);

const REGISTRY_KEYS = new Set([
  'schema',
  'registryId',
  'classification',
  'capturedAtStep',
  'topologyPolicy',
  'seats',
  'claimBoundary',
]);
const SEAT_KEYS = new Set([
  'seatId',
  'role',
  'state',
  'hostIdentityClass',
  'acceleratorIdentityClass',
  'acceleratorMemoryMiB',
  'endpointIdentity',
  'runtimeVersion',
  'adapterVersion',
  'supportedWorkloadClasses',
  'modelOrExecutableDigests',
  'verifierIds',
  'residencyEvidence',
  'powerStateEvidence',
  'claimBoundary',
]);
const RESIDENCY_KEYS = new Set(['residencyClass', 'evidenceClass', 'evidenceDigest']);
const POWER_KEYS = new Set(['claim', 'evidenceClass', 'evidenceDigest']);
const SNAPSHOT_KEYS = new Set([
  'schema',
  'snapshotId',
  'sourceRegistryId',
  'sourceRegistryDigest',
  'classification',
  'capturedAtStep',
  'topologyPolicy',
  'memoryAccounting',
  'aggregateFitAllowed',
  'seatCount',
  'seats',
  'authority',
  'claimBoundary',
]);
const WORKLOAD_KEYS = new Set([
  'schema',
  'workloadId',
  'sourceProfileId',
  'sourceRunId',
  'sourceTaskReceiptId',
  'canonicalMissionStateIdBefore',
  'canonicalMissionStateIdAfter',
  'workloadClass',
  'effectClass',
  'minimumAcceleratorMemoryMiB',
  'requiredRuntimeVersion',
  'requiredAdapterVersion',
  'requiredModelOrExecutableDigest',
  'invocationContract',
  'contextAndKvContract',
  'acceptancePredicate',
  'expectedOutputDigest',
  'authority',
  'claimBoundary',
]);
const INVOCATION_KEYS = new Set([
  'schema',
  'templateId',
  'templateDigest',
  'inputDigest',
  'sourceTaskReceiptId',
]);
const CONTEXT_KEYS = new Set([
  'schema',
  'policy',
  'contractDigest',
  'sourceReceiptDigest',
  'kvCachePolicy',
  'maximumContextBytes',
]);
const ACCEPTANCE_KEYS = new Set([
  'schema',
  'type',
  'expectedOutputDigest',
  'independentVerifierIdentity',
  'terminalReceiptRequired',
]);
const ADMISSION_KEYS = new Set([
  'schema',
  'admissionId',
  'snapshotId',
  'workloadId',
  'seatId',
  'seatPresent',
  'seatRole',
  'seatState',
  'seatMemoryMiB',
  'minimumMemoryMiB',
  'memoryAccounting',
  'checks',
  'disposition',
  'reasons',
  'authority',
  'claimBoundary',
]);
const ADMISSION_CHECK_KEYS = new Set([
  'seatPresent',
  'stateAvailable',
  'workloadClassSupported',
  'runtimeExact',
  'adapterExact',
  'modelOrExecutableAdmitted',
  'verifierAdmitted',
  'independentMemoryFit',
]);
const ROUTE_KEYS = new Set([
  'schema',
  'routeSelectionId',
  'profileId',
  'workloadId',
  'selectionPolicy',
  'selectedSeatId',
  'seatIdentity',
  'seatSnapshotDigest',
  'hostIdentityClass',
  'acceleratorIdentityClass',
  'endpointIdentity',
  'runtimeVersion',
  'adapterVersion',
  'modelOrExecutableDigest',
  'invocationContract',
  'contextAndKvContract',
  'workloadClass',
  'acceptancePredicate',
  'residencyEvidence',
  'powerStateEvidence',
  'independentVerifierIdentity',
  'outputDigest',
  'terminalReceipt',
  'candidateAdmissionIds',
  'rejectedAdmissionIds',
  'memoryAggregationUsed',
  'status',
  'authority',
  'claimBoundary',
]);
const TERMINAL_RECEIPT_KEYS = new Set([
  'required',
  'expectedSchema',
  'currentReceiptId',
  'status',
]);
const LEASE_KEYS = new Set([
  'schema',
  'leaseId',
  'routeSelectionId',
  'workloadId',
  'seatId',
  'generation',
  'issuedAtStep',
  'expiresAtStep',
  'leaseDurationSteps',
  'status',
  'completionAuthority',
  'releaseEvidenceRequired',
  'authority',
  'claimBoundary',
]);
const SLICE_KEYS = new Set([
  'schema',
  'routingSliceId',
  'fabricProfileId',
  'fabricProfileValidationSha256',
  'sourceRunId',
  'sourceTaskReceiptId',
  'canonicalMissionStateIdBeforeRouting',
  'canonicalMissionStateIdAfterRouting',
  'seatSnapshot',
  'workload',
  'admissions',
  'routeSelection',
  'workerLease',
  'acceptedRouteCount',
  'admittedSeatCount',
  'refusedSeatCount',
  'executionStarted',
  'completionAccepted',
  'externalServiceCalls',
  'operationalCredentials',
  'physicalEvidenceBodies',
  'authority',
  'claimBoundary',
]);

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
  const actual = Object.keys(value).sort();
  const wanted = [...expected].sort();
  requireCondition(
    canonicalJson(actual) === canonicalJson(wanted),
    code,
    `${label} fields differ`,
  );
}

function boundedString(value, code, label, max = 1024) {
  requireCondition(typeof value === 'string', code, `${label} must be a string`);
  const normalized = value.trim();
  requireCondition(
    normalized.length > 0 && normalized.length <= max,
    code,
    `${label} is empty or unbounded`,
  );
  return normalized;
}

function safeInteger(value, min, max, code, label) {
  requireCondition(
    Number.isSafeInteger(value) && value >= min && value <= max,
    code,
    `${label} must be an integer between ${min} and ${max}`,
  );
  return value;
}

function uniqueStrings(values, code, label) {
  requireCondition(Array.isArray(values) && values.length > 0, code, `${label} must be a non-empty array`);
  requireCondition(
    values.every((value) => typeof value === 'string' && value.trim().length > 0),
    code,
    `${label} must contain bounded strings`,
  );
  requireCondition(new Set(values).size === values.length, code, `${label} contains duplicates`);
}

function digest(prefix, value) {
  return `${prefix}_${createHash('sha256').update(canonicalJson(value), 'utf8').digest('hex')}`;
}

function withoutKeys(value, keys) {
  const copy = structuredClone(value);
  for (const key of keys) delete copy[key];
  return copy;
}

function exactIdentity(value, prefix, idKey, code) {
  const expected = digest(prefix, withoutKeys(value, [idKey, 'claimBoundary']));
  requireCondition(value[idKey] === expected, code, `${idKey} differs from content identity`);
}

function validateResidencyEvidence(value) {
  exactKeys(value, RESIDENCY_KEYS, 'RESIDENCY_EVIDENCE_INVALID', 'residency evidence');
  requireCondition(
    RESIDENCY_CLASSES.has(value.residencyClass),
    'RESIDENCY_EVIDENCE_INVALID',
    'residency class is invalid',
  );
  requireCondition(
    value.evidenceClass === 'synthetic_registry_assertion',
    'RESIDENCY_EVIDENCE_INVALID',
    'residency evidence must remain synthetic',
  );
  requireCondition(
    typeof value.evidenceDigest === 'string' && SHA256.test(value.evidenceDigest),
    'RESIDENCY_EVIDENCE_INVALID',
    'residency evidence digest is invalid',
  );
}

function validatePowerStateEvidence(value) {
  exactKeys(value, POWER_KEYS, 'POWER_EVIDENCE_INVALID', 'power-state evidence');
  requireCondition(POWER_CLAIMS.has(value.claim), 'POWER_EVIDENCE_INVALID', 'power-state claim is invalid');
  if (value.claim === 'not_measured') {
    requireCondition(
      value.evidenceClass === 'none' && value.evidenceDigest === null,
      'POWER_EVIDENCE_INVALID',
      'unmeasured power state may not carry invented evidence',
    );
  } else {
    requireCondition(
      value.evidenceClass === 'synthetic_registry_assertion'
        && typeof value.evidenceDigest === 'string'
        && SHA256.test(value.evidenceDigest),
      'POWER_EVIDENCE_INVALID',
      'synthetic power claim requires synthetic digest evidence',
    );
  }
}

function validateSeat(seat) {
  exactKeys(seat, SEAT_KEYS, 'SEAT_INVALID', 'seat');
  requireCondition(
    boundedString(seat.seatId, 'SEAT_INVALID', 'seatId').startsWith('SYN-SEAT-'),
    'SEAT_INVALID',
    'public seat identifiers must use the SYN-SEAT- prefix',
  );
  requireCondition(ROLES.has(seat.role), 'SEAT_INVALID', 'seat role is invalid');
  requireCondition(SEAT_STATES.has(seat.state), 'SEAT_INVALID', 'seat state is invalid');
  requireCondition(
    boundedString(seat.hostIdentityClass, 'SEAT_INVALID', 'hostIdentityClass').startsWith('synthetic-'),
    'SEAT_INVALID',
    'host identity class must remain synthetic',
  );
  requireCondition(
    boundedString(seat.acceleratorIdentityClass, 'SEAT_INVALID', 'acceleratorIdentityClass').startsWith('synthetic-'),
    'SEAT_INVALID',
    'accelerator identity class must remain synthetic',
  );
  safeInteger(
    seat.acceleratorMemoryMiB,
    1,
    MAX_MEMORY_MIB,
    'SEAT_INVALID',
    'acceleratorMemoryMiB',
  );
  requireCondition(
    boundedString(seat.endpointIdentity, 'SEAT_INVALID', 'endpointIdentity').startsWith('SYN-ENDPOINT-'),
    'SEAT_INVALID',
    'endpoint identity must remain synthetic',
  );
  boundedString(seat.runtimeVersion, 'SEAT_INVALID', 'runtimeVersion');
  boundedString(seat.adapterVersion, 'SEAT_INVALID', 'adapterVersion');
  uniqueStrings(seat.supportedWorkloadClasses, 'SEAT_INVALID', 'supportedWorkloadClasses');
  uniqueStrings(seat.modelOrExecutableDigests, 'SEAT_INVALID', 'modelOrExecutableDigests');
  requireCondition(
    seat.modelOrExecutableDigests.every((value) => SHA256.test(value)),
    'SEAT_INVALID',
    'model or executable digest is invalid',
  );
  uniqueStrings(seat.verifierIds, 'SEAT_INVALID', 'verifierIds');
  requireCondition(
    seat.verifierIds.every((value) => value.startsWith('SYN-VERIFIER-')),
    'SEAT_INVALID',
    'verifier identity must remain synthetic',
  );
  validateResidencyEvidence(seat.residencyEvidence);
  validatePowerStateEvidence(seat.powerStateEvidence);
  requireCondition(
    boundedString(seat.claimBoundary, 'SEAT_INVALID', 'seat claimBoundary', 2048)
      .toLowerCase()
      .includes('invented'),
    'SEAT_INVALID',
    'seat claim boundary must remain explicitly invented',
  );
  return seat;
}

export function validateInventedSeatRegistry(registry) {
  exactKeys(registry, REGISTRY_KEYS, 'SEAT_REGISTRY_INVALID', 'seat registry');
  requireCondition(
    registry.schema === 'spectra-anchor-node-invented-seat-registry/1',
    'SEAT_REGISTRY_SCHEMA_INVALID',
    'seat registry schema is invalid',
  );
  requireCondition(
    boundedString(registry.registryId, 'SEAT_REGISTRY_INVALID', 'registryId').startsWith('SYN-'),
    'SEAT_REGISTRY_INVALID',
    'registry identity must remain synthetic',
  );
  requireCondition(
    registry.classification === 'invented_unclassified_synthetic_only',
    'SEAT_REGISTRY_CLASSIFICATION_INVALID',
    'seat registry must remain invented and synthetic-only',
  );
  safeInteger(registry.capturedAtStep, 0, MAX_STEP, 'SEAT_REGISTRY_INVALID', 'capturedAtStep');
  requireCondition(
    registry.topologyPolicy === 'independent_seats_no_memory_pooling',
    'SEAT_REGISTRY_TOPOLOGY_INVALID',
    'registry topology policy must prohibit memory pooling',
  );
  requireCondition(
    Array.isArray(registry.seats)
      && registry.seats.length > 0
      && registry.seats.length <= MAX_SEATS,
    'SEAT_REGISTRY_INVALID',
    `seat registry must contain between 1 and ${MAX_SEATS} seats`,
  );
  const seatIds = new Set();
  const endpointIds = new Set();
  for (const seat of registry.seats) {
    validateSeat(seat);
    requireCondition(!seatIds.has(seat.seatId), 'SEAT_REGISTRY_DUPLICATE', `duplicate seat ${seat.seatId}`);
    requireCondition(
      !endpointIds.has(seat.endpointIdentity),
      'SEAT_REGISTRY_DUPLICATE',
      `duplicate endpoint ${seat.endpointIdentity}`,
    );
    seatIds.add(seat.seatId);
    endpointIds.add(seat.endpointIdentity);
  }
  requireCondition(
    boundedString(registry.claimBoundary, 'SEAT_REGISTRY_INVALID', 'registry claimBoundary', 2048)
      .toLowerCase()
      .includes('no real estate topology'),
    'SEAT_REGISTRY_INVALID',
    'registry claim boundary must exclude real Estate topology',
  );
  const encoded = canonicalJson(registry).toLowerCase();
  for (const forbidden of [
    'octo-w01',
    'octo-l01',
    'c:\\',
    '/home/',
    'ssh://',
    'http://',
    'https://',
    'authorization: bearer',
    'begin private key',
  ]) {
    requireCondition(
      !encoded.includes(forbidden),
      'PRIVATE_EVIDENCE_BOUNDARY_INVALID',
      `public registry contains forbidden private or credential-shaped material: ${forbidden}`,
    );
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
    seats: [...registry.seats]
      .map((seat) => structuredClone(seat))
      .sort((left, right) => left.seatId.localeCompare(right.seatId)),
    authority: false,
    claimBoundary:
      'Content-addressed snapshot of one invented public seat registry. It is not a physical Estate inventory, pooled-memory surface, scheduler grant, or mission authority source.',
  };
  return { ...body, snapshotId: digest('estateseatsnapshot1', body) };
}

export function validateSeatSnapshot(snapshot) {
  exactKeys(snapshot, SNAPSHOT_KEYS, 'SEAT_SNAPSHOT_INVALID', 'seat snapshot');
  requireCondition(snapshot.schema === 'estate-seat-snapshot/1', 'SEAT_SNAPSHOT_SCHEMA_INVALID', 'seat snapshot schema is invalid');
  boundedString(snapshot.snapshotId, 'SEAT_SNAPSHOT_INVALID', 'snapshotId');
  boundedString(snapshot.sourceRegistryId, 'SEAT_SNAPSHOT_INVALID', 'sourceRegistryId');
  boundedString(snapshot.sourceRegistryDigest, 'SEAT_SNAPSHOT_INVALID', 'sourceRegistryDigest');
  requireCondition(
    snapshot.classification === 'invented_unclassified_synthetic_only',
    'SEAT_SNAPSHOT_INVALID',
    'seat snapshot classification differs',
  );
  safeInteger(snapshot.capturedAtStep, 0, MAX_STEP, 'SEAT_SNAPSHOT_INVALID', 'capturedAtStep');
  requireCondition(
    snapshot.topologyPolicy === 'independent_seats_no_memory_pooling'
      && snapshot.memoryAccounting === 'per_seat_only'
      && snapshot.aggregateFitAllowed === false,
    'SEAT_SNAPSHOT_MEMORY_INVALID',
    'seat snapshot permits pooled or ambiguous memory accounting',
  );
  requireCondition(
    Number.isSafeInteger(snapshot.seatCount)
      && snapshot.seatCount > 0
      && Array.isArray(snapshot.seats)
      && snapshot.seats.length === snapshot.seatCount,
    'SEAT_SNAPSHOT_INVALID',
    'seat snapshot denominator differs',
  );
  const ids = new Set();
  for (const seat of snapshot.seats) {
    validateSeat(seat);
    requireCondition(!ids.has(seat.seatId), 'SEAT_SNAPSHOT_INVALID', `duplicate seat ${seat.seatId}`);
    ids.add(seat.seatId);
  }
  requireCondition(snapshot.authority === false, 'SEAT_SNAPSHOT_AUTHORITY_INVALID', 'seat snapshot cannot carry authority');
  exactIdentity(snapshot, 'estateseatsnapshot1', 'snapshotId', 'SEAT_SNAPSHOT_ID_INVALID');
  return snapshot;
}

export function verifySeatSnapshot(snapshot, registry) {
  validateSeatSnapshot(snapshot);
  const rebuilt = createSeatSnapshot(registry);
  requireCondition(
    canonicalJson(snapshot) === canonicalJson(rebuilt),
    'SEAT_SNAPSHOT_REPLAY_MISMATCH',
    'seat snapshot does not replay from the registry fixture',
  );
  return snapshot;
}

export function createFabricWorkload(bundle) {
  verifyVerticalSlice(bundle);
  requireCondition(
    bundle.taskReceipt.effectClass === 'local_artifact_only',
    'FABRIC_WORKLOAD_EFFECT_INVALID',
    'fabric workload source task is not local-artifact-only',
  );
  const body = {
    schema: 'estate-fabric-workload/1',
    sourceProfileId: bundle.profileId,
    sourceRunId: bundle.runId,
    sourceTaskReceiptId: bundle.taskReceipt.taskReceiptId,
    canonicalMissionStateIdBefore: bundle.missionStateAfter.missionStateId,
    canonicalMissionStateIdAfter: bundle.missionStateAfter.missionStateId,
    workloadClass: 'local_artifact_reconstruction',
    effectClass: 'local_artifact_only',
    minimumAcceleratorMemoryMiB: 16384,
    requiredRuntimeVersion: 'synthetic-local-executor/1.0.0',
    requiredAdapterVersion: 'spectra-estate-fabric-adapter/0.1.0',
    requiredModelOrExecutableDigest: MODEL_OR_EXECUTABLE_DIGEST,
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
      contractDigest: CONTEXT_CONTRACT_DIGEST,
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
    claimBoundary:
      'Synthetic reconstruction workload derived from one admitted MP01 local artifact. It is not a new mission task, command, field action, model qualification, or physical Estate claim.',
  };
  return { ...body, workloadId: digest('estatefabricworkload1', body) };
}

export function validateFabricWorkload(workload) {
  exactKeys(workload, WORKLOAD_KEYS, 'FABRIC_WORKLOAD_INVALID', 'fabric workload');
  requireCondition(workload.schema === 'estate-fabric-workload/1', 'FABRIC_WORKLOAD_SCHEMA_INVALID', 'fabric workload schema is invalid');
  for (const key of [
    'workloadId',
    'sourceProfileId',
    'sourceRunId',
    'sourceTaskReceiptId',
    'canonicalMissionStateIdBefore',
    'canonicalMissionStateIdAfter',
    'workloadClass',
    'effectClass',
    'requiredRuntimeVersion',
    'requiredAdapterVersion',
    'requiredModelOrExecutableDigest',
    'expectedOutputDigest',
    'claimBoundary',
  ]) {
    boundedString(workload[key], 'FABRIC_WORKLOAD_INVALID', key, 4096);
  }
  requireCondition(
    workload.canonicalMissionStateIdBefore === workload.canonicalMissionStateIdAfter,
    'FABRIC_WORKLOAD_STATE_MUTATION',
    'fabric workload cannot mutate canonical mission state',
  );
  requireCondition(
    workload.workloadClass === 'local_artifact_reconstruction'
      && workload.effectClass === 'local_artifact_only',
    'FABRIC_WORKLOAD_EFFECT_INVALID',
    'fabric workload class or effect is invalid',
  );
  safeInteger(
    workload.minimumAcceleratorMemoryMiB,
    1,
    MAX_MEMORY_MIB,
    'FABRIC_WORKLOAD_INVALID',
    'minimumAcceleratorMemoryMiB',
  );
  requireCondition(SHA256.test(workload.requiredModelOrExecutableDigest), 'FABRIC_WORKLOAD_INVALID', 'required model or executable digest is invalid');
  exactKeys(workload.invocationContract, INVOCATION_KEYS, 'FABRIC_WORKLOAD_INVALID', 'invocation contract');
  exactKeys(workload.contextAndKvContract, CONTEXT_KEYS, 'FABRIC_WORKLOAD_INVALID', 'context contract');
  exactKeys(workload.acceptancePredicate, ACCEPTANCE_KEYS, 'FABRIC_WORKLOAD_INVALID', 'acceptance predicate');
  requireCondition(
    workload.invocationContract.schema === 'estate-fabric-invocation-contract/1'
      && workload.invocationContract.templateDigest === TEMPLATE_DIGEST,
    'FABRIC_WORKLOAD_INVALID',
    'invocation contract differs',
  );
  requireCondition(
    workload.contextAndKvContract.schema === 'estate-fabric-context-contract/1'
      && workload.contextAndKvContract.policy === 'exact_source_receipt_only'
      && workload.contextAndKvContract.contractDigest === CONTEXT_CONTRACT_DIGEST
      && workload.contextAndKvContract.kvCachePolicy === 'none',
    'FABRIC_WORKLOAD_INVALID',
    'context and KV contract differs',
  );
  requireCondition(
    workload.acceptancePredicate.schema === 'estate-fabric-acceptance-predicate/1'
      && workload.acceptancePredicate.type === 'exact_output_digest_and_independent_verifier'
      && workload.acceptancePredicate.expectedOutputDigest === workload.expectedOutputDigest
      && workload.acceptancePredicate.independentVerifierIdentity === VERIFIER_ID
      && workload.acceptancePredicate.terminalReceiptRequired === true,
    'FABRIC_WORKLOAD_INVALID',
    'acceptance predicate differs',
  );
  requireCondition(workload.authority === false, 'FABRIC_WORKLOAD_AUTHORITY_INVALID', 'fabric workload cannot carry authority');
  exactIdentity(workload, 'estatefabricworkload1', 'workloadId', 'FABRIC_WORKLOAD_ID_INVALID');
  return workload;
}

export function verifyFabricWorkload(workload, bundle) {
  validateFabricWorkload(workload);
  const rebuilt = createFabricWorkload(bundle);
  requireCondition(
    canonicalJson(workload) === canonicalJson(rebuilt),
    'FABRIC_WORKLOAD_REPLAY_MISMATCH',
    'fabric workload does not replay from the MP01 bundle',
  );
  return workload;
}

function admissionChecks(seat, workload) {
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

function admissionReasons(checks) {
  const rows = [];
  if (!checks.seatPresent) return ['SEAT_NOT_IN_SNAPSHOT'];
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
  const checks = admissionChecks(seat, workload);
  const reasons = admissionReasons(checks);
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
    claimBoundary:
      'Seat-specific synthetic admission result. It does not pool memory, grant execution success, mutate mission state, qualify physical hardware, or create authority.',
  };
  return { ...body, admissionId: digest('estateseatadmission1', body) };
}

export function validateSeatAdmission(admission) {
  exactKeys(admission, ADMISSION_KEYS, 'SEAT_ADMISSION_INVALID', 'seat admission');
  requireCondition(admission.schema === 'estate-seat-admission/1', 'SEAT_ADMISSION_SCHEMA_INVALID', 'seat admission schema is invalid');
  for (const key of ['admissionId', 'snapshotId', 'workloadId', 'seatId', 'memoryAccounting', 'disposition', 'claimBoundary']) {
    boundedString(admission[key], 'SEAT_ADMISSION_INVALID', key, 4096);
  }
  exactKeys(admission.checks, ADMISSION_CHECK_KEYS, 'SEAT_ADMISSION_INVALID', 'admission checks');
  requireCondition(
    [...ADMISSION_CHECK_KEYS].every((key) => typeof admission.checks[key] === 'boolean'),
    'SEAT_ADMISSION_INVALID',
    'admission checks must be boolean',
  );
  requireCondition(admission.memoryAccounting === 'independent_seat_only', 'SEAT_ADMISSION_MEMORY_INVALID', 'seat admission uses ambiguous memory accounting');
  requireCondition(['admit', 'refuse'].includes(admission.disposition), 'SEAT_ADMISSION_INVALID', 'seat admission disposition is invalid');
  requireCondition(Array.isArray(admission.reasons), 'SEAT_ADMISSION_INVALID', 'seat admission reasons must be an array');
  requireCondition(
    admission.reasons.every((reason) => ADMISSION_REASONS.has(reason)),
    'SEAT_ADMISSION_INVALID',
    'seat admission contains an unsupported reason',
  );
  requireCondition(
    new Set(admission.reasons).size === admission.reasons.length,
    'SEAT_ADMISSION_INVALID',
    'seat admission reasons contain duplicates',
  );
  requireCondition(
    (admission.disposition === 'admit' && admission.reasons.length === 0)
      || (admission.disposition === 'refuse' && admission.reasons.length > 0),
    'SEAT_ADMISSION_INVALID',
    'seat admission disposition and reasons disagree',
  );
  if (admission.seatPresent) {
    requireCondition(
      ROLES.has(admission.seatRole)
        && SEAT_STATES.has(admission.seatState)
        && Number.isSafeInteger(admission.seatMemoryMiB),
      'SEAT_ADMISSION_INVALID',
      'present seat admission lacks seat evidence',
    );
  } else {
    requireCondition(
      admission.seatRole === null
        && admission.seatState === null
        && admission.seatMemoryMiB === null
        && admission.reasons.length === 1
        && admission.reasons[0] === 'SEAT_NOT_IN_SNAPSHOT',
      'SEAT_ADMISSION_INVALID',
      'absent seat admission is not closed',
    );
  }
  safeInteger(admission.minimumMemoryMiB, 1, MAX_MEMORY_MIB, 'SEAT_ADMISSION_INVALID', 'minimumMemoryMiB');
  requireCondition(admission.authority === false, 'SEAT_ADMISSION_AUTHORITY_INVALID', 'seat admission cannot carry authority');
  exactIdentity(admission, 'estateseatadmission1', 'admissionId', 'SEAT_ADMISSION_ID_INVALID');
  return admission;
}

export function verifySeatAdmission(admission, snapshot, workload) {
  validateSeatAdmission(admission);
  const rebuilt = createSeatAdmission({ snapshot, workload, seatId: admission.seatId });
  requireCondition(
    canonicalJson(admission) === canonicalJson(rebuilt),
    'SEAT_ADMISSION_REPLAY_MISMATCH',
    'seat admission does not replay',
  );
  return admission;
}

export function createSeatAdmissions(snapshot, workload) {
  validateSeatSnapshot(snapshot);
  validateFabricWorkload(workload);
  return snapshot.seats.map((seat) => createSeatAdmission({ snapshot, workload, seatId: seat.seatId }));
}

function validateAdmissionDenominator(admissions, snapshot, workload) {
  requireCondition(
    Array.isArray(admissions) && admissions.length === snapshot.seatCount,
    'SEAT_ADMISSION_DENOMINATOR_INVALID',
    'seat admission denominator differs from the snapshot',
  );
  const expectedIds = snapshot.seats.map((seat) => seat.seatId).sort();
  const actualIds = admissions.map((row) => row.seatId).sort();
  requireCondition(
    canonicalJson(expectedIds) === canonicalJson(actualIds),
    'SEAT_ADMISSION_DENOMINATOR_INVALID',
    'seat admissions do not exactly cover the snapshot',
  );
  for (const admission of admissions) verifySeatAdmission(admission, snapshot, workload);
}

export function selectRoute({ snapshot, workload, admissions, preferredSeatId = null }) {
  validateSeatSnapshot(snapshot);
  validateFabricWorkload(workload);
  validateAdmissionDenominator(admissions, snapshot, workload);
  const admitted = admissions.filter((row) => row.disposition === 'admit');
  requireCondition(admitted.length > 0, 'NO_QUALIFIED_ROUTE', 'no independently qualified seat can run the workload');

  let selectedAdmission;
  let selectionPolicy;
  if (preferredSeatId !== null) {
    boundedString(preferredSeatId, 'ROUTE_SELECTION_INVALID', 'preferredSeatId');
    selectedAdmission = admitted.find((row) => row.seatId === preferredSeatId);
    requireCondition(
      selectedAdmission !== undefined,
      'PREFERRED_SEAT_NOT_ADMITTED',
      'preferred seat is not admitted for this workload',
    );
    selectionPolicy = 'explicit_admitted_seat';
  } else {
    selectedAdmission = [...admitted].sort((left, right) => {
      const roleDifference = ROLE_RANK.get(left.seatRole) - ROLE_RANK.get(right.seatRole);
      return roleDifference || left.seatId.localeCompare(right.seatId);
    })[0];
    selectionPolicy = 'resident_then_fallback_then_optional_lexical';
  }
  const seat = snapshot.seats.find((row) => row.seatId === selectedAdmission.seatId);
  requireCondition(seat !== undefined, 'ROUTE_SELECTION_INVALID', 'selected seat disappeared from snapshot');

  const terminalReceipt = {
    required: true,
    expectedSchema: 'estate-fabric-run/1',
    currentReceiptId: null,
    status: 'pending_execution',
  };
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
    terminalReceipt,
    candidateAdmissionIds: admitted
      .sort((left, right) => left.seatId.localeCompare(right.seatId))
      .map((row) => row.admissionId),
    rejectedAdmissionIds: admissions
      .filter((row) => row.disposition === 'refuse')
      .sort((left, right) => left.seatId.localeCompare(right.seatId))
      .map((row) => row.admissionId),
    memoryAggregationUsed: false,
    status: 'selected_pending_execution',
    authority: false,
    claimBoundary:
      'Deterministic seat-specific route selection over admitted synthetic evidence. It does not start execution, accept completion, pool memory, qualify physical hardware, mutate mission state, or grant authority.',
  };
  return { ...body, routeSelectionId: digest('estaterouteselection1', body) };
}

export function validateRouteSelection(route) {
  exactKeys(route, ROUTE_KEYS, 'ROUTE_SELECTION_INVALID', 'route selection');
  requireCondition(route.schema === 'estate-route-selection/1', 'ROUTE_SELECTION_SCHEMA_INVALID', 'route selection schema is invalid');
  for (const key of [
    'routeSelectionId',
    'profileId',
    'workloadId',
    'selectionPolicy',
    'selectedSeatId',
    'seatIdentity',
    'seatSnapshotDigest',
    'hostIdentityClass',
    'acceleratorIdentityClass',
    'endpointIdentity',
    'runtimeVersion',
    'adapterVersion',
    'modelOrExecutableDigest',
    'workloadClass',
    'independentVerifierIdentity',
    'outputDigest',
    'status',
    'claimBoundary',
  ]) {
    boundedString(route[key], 'ROUTE_SELECTION_INVALID', key, 4096);
  }
  requireCondition(route.selectedSeatId === route.seatIdentity, 'ROUTE_SELECTION_INVALID', 'selected seat identity differs');
  requireCondition(SHA256.test(route.modelOrExecutableDigest), 'ROUTE_SELECTION_INVALID', 'route model or executable digest is invalid');
  exactKeys(route.invocationContract, INVOCATION_KEYS, 'ROUTE_SELECTION_INVALID', 'route invocation contract');
  exactKeys(route.contextAndKvContract, CONTEXT_KEYS, 'ROUTE_SELECTION_INVALID', 'route context contract');
  exactKeys(route.acceptancePredicate, ACCEPTANCE_KEYS, 'ROUTE_SELECTION_INVALID', 'route acceptance predicate');
  validateResidencyEvidence(route.residencyEvidence);
  validatePowerStateEvidence(route.powerStateEvidence);
  exactKeys(route.terminalReceipt, TERMINAL_RECEIPT_KEYS, 'ROUTE_SELECTION_INVALID', 'terminal receipt contract');
  requireCondition(
    route.terminalReceipt.required === true
      && route.terminalReceipt.expectedSchema === 'estate-fabric-run/1'
      && route.terminalReceipt.currentReceiptId === null
      && route.terminalReceipt.status === 'pending_execution',
    'ROUTE_SELECTION_TERMINAL_INVALID',
    'route selection invented or weakened terminal completion evidence',
  );
  requireCondition(Array.isArray(route.candidateAdmissionIds) && route.candidateAdmissionIds.length > 0, 'ROUTE_SELECTION_INVALID', 'route has no admitted candidate lineage');
  requireCondition(Array.isArray(route.rejectedAdmissionIds), 'ROUTE_SELECTION_INVALID', 'route rejected lineage is missing');
  requireCondition(
    route.memoryAggregationUsed === false,
    'ROUTE_SELECTION_MEMORY_INVALID',
    'route selection cannot aggregate independent seat memory',
  );
  requireCondition(
    route.status === 'selected_pending_execution',
    'ROUTE_SELECTION_STATUS_INVALID',
    'route selection cannot serialize execution success',
  );
  requireCondition(route.authority === false, 'ROUTE_SELECTION_AUTHORITY_INVALID', 'route selection cannot carry authority');
  exactIdentity(route, 'estaterouteselection1', 'routeSelectionId', 'ROUTE_SELECTION_ID_INVALID');
  return route;
}

export function verifyRouteSelection(route, snapshot, workload, admissions) {
  validateRouteSelection(route);
  const preferredSeatId = route.selectionPolicy === 'explicit_admitted_seat'
    ? route.selectedSeatId
    : null;
  const rebuilt = selectRoute({ snapshot, workload, admissions, preferredSeatId });
  requireCondition(
    canonicalJson(route) === canonicalJson(rebuilt),
    'ROUTE_SELECTION_REPLAY_MISMATCH',
    'route selection does not replay',
  );
  return route;
}

export function createWorkerLease({
  routeSelection,
  generation = 1,
  issuedAtStep = 20,
  leaseDurationSteps = 5,
}) {
  validateRouteSelection(routeSelection);
  safeInteger(generation, 1, MAX_STEP, 'WORKER_LEASE_INVALID', 'generation');
  safeInteger(issuedAtStep, 0, MAX_STEP, 'WORKER_LEASE_INVALID', 'issuedAtStep');
  safeInteger(
    leaseDurationSteps,
    1,
    MAX_LEASE_STEPS,
    'WORKER_LEASE_INVALID',
    'leaseDurationSteps',
  );
  requireCondition(
    issuedAtStep + leaseDurationSteps <= MAX_STEP,
    'WORKER_LEASE_INVALID',
    'worker lease expiry exceeds the safe step bound',
  );
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
    claimBoundary:
      'Finite synthetic worker lease for one selected seat. It grants no completion, mission, command, field, physical-hardware, or evaluator authority and may not be released without terminal evidence.',
  };
  return { ...body, leaseId: digest('estateworkerlease1', body) };
}

export function validateWorkerLease(lease) {
  exactKeys(lease, LEASE_KEYS, 'WORKER_LEASE_INVALID', 'worker lease');
  requireCondition(lease.schema === 'estate-worker-lease/1', 'WORKER_LEASE_SCHEMA_INVALID', 'worker lease schema is invalid');
  for (const key of ['leaseId', 'routeSelectionId', 'workloadId', 'seatId', 'status', 'claimBoundary']) {
    boundedString(lease[key], 'WORKER_LEASE_INVALID', key, 4096);
  }
  safeInteger(lease.generation, 1, MAX_STEP, 'WORKER_LEASE_INVALID', 'generation');
  safeInteger(lease.issuedAtStep, 0, MAX_STEP, 'WORKER_LEASE_INVALID', 'issuedAtStep');
  safeInteger(lease.expiresAtStep, 1, MAX_STEP, 'WORKER_LEASE_INVALID', 'expiresAtStep');
  safeInteger(lease.leaseDurationSteps, 1, MAX_LEASE_STEPS, 'WORKER_LEASE_INVALID', 'leaseDurationSteps');
  requireCondition(
    lease.expiresAtStep === lease.issuedAtStep + lease.leaseDurationSteps,
    'WORKER_LEASE_INVALID',
    'worker lease expiry differs from its finite duration',
  );
  requireCondition(
    lease.status === 'active_pending_execution',
    'WORKER_LEASE_STATUS_INVALID',
    'worker lease cannot serialize completion',
  );
  requireCondition(
    lease.completionAuthority === false
      && lease.releaseEvidenceRequired === true
      && lease.authority === false,
    'WORKER_LEASE_AUTHORITY_INVALID',
    'worker lease grants authority or permits evidence-free release',
  );
  exactIdentity(lease, 'estateworkerlease1', 'leaseId', 'WORKER_LEASE_ID_INVALID');
  return lease;
}

export function verifyWorkerLease(lease, routeSelection) {
  validateWorkerLease(lease);
  validateRouteSelection(routeSelection);
  requireCondition(
    lease.routeSelectionId === routeSelection.routeSelectionId
      && lease.workloadId === routeSelection.workloadId
      && lease.seatId === routeSelection.selectedSeatId,
    'WORKER_LEASE_BINDING_INVALID',
    'worker lease belongs to another route, workload, or seat',
  );
  const rebuilt = createWorkerLease({
    routeSelection,
    generation: lease.generation,
    issuedAtStep: lease.issuedAtStep,
    leaseDurationSteps: lease.leaseDurationSteps,
  });
  requireCondition(
    canonicalJson(lease) === canonicalJson(rebuilt),
    'WORKER_LEASE_REPLAY_MISMATCH',
    'worker lease does not replay',
  );
  return lease;
}

export function workerLeaseStateAt(lease, observedAtStep) {
  validateWorkerLease(lease);
  safeInteger(observedAtStep, 0, MAX_STEP, 'WORKER_LEASE_OBSERVATION_INVALID', 'observedAtStep');
  return observedAtStep <= lease.expiresAtStep ? 'active' : 'expired';
}

export function runFabricRoutingSlice({
  bundle,
  fabricProfile,
  registry,
  preferredSeatId = null,
  leaseGeneration = 1,
  leaseIssuedAtStep = 20,
  leaseDurationSteps = 5,
}) {
  verifyVerticalSlice(bundle);
  validateFabricProfile(fabricProfile);
  const profileValidation = fabricProfileReceipt(fabricProfile);
  const seatSnapshot = createSeatSnapshot(registry);
  const workload = createFabricWorkload(bundle);
  const admissions = createSeatAdmissions(seatSnapshot, workload);
  const routeSelection = selectRoute({
    snapshot: seatSnapshot,
    workload,
    admissions,
    preferredSeatId,
  });
  const workerLease = createWorkerLease({
    routeSelection,
    generation: leaseGeneration,
    issuedAtStep: leaseIssuedAtStep,
    leaseDurationSteps,
  });
  const canonicalMissionStateId = bundle.missionStateAfter.missionStateId;
  const body = {
    schema: 'spectra-anchor-node-estate-fabric-routing-slice/1',
    fabricProfileId: fabricProfile.profileId,
    fabricProfileValidationSha256: profileValidation.sha256,
    sourceRunId: bundle.runId,
    sourceTaskReceiptId: bundle.taskReceipt.taskReceiptId,
    canonicalMissionStateIdBeforeRouting: canonicalMissionStateId,
    canonicalMissionStateIdAfterRouting: canonicalMissionStateId,
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
    claimBoundary:
      'This slice proves deterministic synthetic seat snapshot, admission, route selection, and finite lease construction. It starts no execution, accepts no completion, imports no private evidence, mutates no mission state, and grants no authority.',
  };
  return { ...body, routingSliceId: digest('estatefabricroutingslice1', body) };
}

export function validateFabricRoutingSlice(slice) {
  exactKeys(slice, SLICE_KEYS, 'FABRIC_ROUTING_SLICE_INVALID', 'fabric routing slice');
  requireCondition(
    slice.schema === 'spectra-anchor-node-estate-fabric-routing-slice/1',
    'FABRIC_ROUTING_SLICE_SCHEMA_INVALID',
    'fabric routing slice schema is invalid',
  );
  for (const key of [
    'routingSliceId',
    'fabricProfileId',
    'fabricProfileValidationSha256',
    'sourceRunId',
    'sourceTaskReceiptId',
    'canonicalMissionStateIdBeforeRouting',
    'canonicalMissionStateIdAfterRouting',
    'claimBoundary',
  ]) {
    boundedString(slice[key], 'FABRIC_ROUTING_SLICE_INVALID', key, 4096);
  }
  requireCondition(
    SHA256.test(slice.fabricProfileValidationSha256),
    'FABRIC_ROUTING_SLICE_INVALID',
    'fabric profile validation digest is invalid',
  );
  requireCondition(
    slice.canonicalMissionStateIdBeforeRouting === slice.canonicalMissionStateIdAfterRouting,
    'FABRIC_ROUTING_STATE_MUTATION',
    'fabric routing mutated canonical mission state',
  );
  validateSeatSnapshot(slice.seatSnapshot);
  validateFabricWorkload(slice.workload);
  validateAdmissionDenominator(slice.admissions, slice.seatSnapshot, slice.workload);
  verifyRouteSelection(slice.routeSelection, slice.seatSnapshot, slice.workload, slice.admissions);
  verifyWorkerLease(slice.workerLease, slice.routeSelection);
  requireCondition(slice.acceptedRouteCount === 1, 'FABRIC_ROUTING_SLICE_INVALID', 'fabric routing must select exactly one route');
  requireCondition(
    slice.admittedSeatCount === slice.admissions.filter((row) => row.disposition === 'admit').length
      && slice.refusedSeatCount === slice.admissions.filter((row) => row.disposition === 'refuse').length,
    'FABRIC_ROUTING_SLICE_INVALID',
    'fabric routing admission counts differ',
  );
  requireCondition(
    slice.executionStarted === false
      && slice.completionAccepted === false
      && slice.externalServiceCalls === 0
      && slice.operationalCredentials === 0
      && slice.physicalEvidenceBodies === 0
      && slice.authority === false,
    'FABRIC_ROUTING_CLAIM_INVALID',
    'fabric routing slice invents execution, completion, private evidence, dependency, or authority',
  );
  exactIdentity(slice, 'estatefabricroutingslice1', 'routingSliceId', 'FABRIC_ROUTING_SLICE_ID_INVALID');
  return slice;
}

export function verifyFabricRoutingSlice(slice, { bundle, fabricProfile, registry }) {
  validateFabricRoutingSlice(slice);
  verifyVerticalSlice(bundle);
  validateFabricProfile(fabricProfile);
  verifySeatSnapshot(slice.seatSnapshot, registry);
  verifyFabricWorkload(slice.workload, bundle);
  const preferredSeatId = slice.routeSelection.selectionPolicy === 'explicit_admitted_seat'
    ? slice.routeSelection.selectedSeatId
    : null;
  const replayed = runFabricRoutingSlice({
    bundle,
    fabricProfile,
    registry,
    preferredSeatId,
    leaseGeneration: slice.workerLease.generation,
    leaseIssuedAtStep: slice.workerLease.issuedAtStep,
    leaseDurationSteps: slice.workerLease.leaseDurationSteps,
  });
  requireCondition(
    canonicalJson(slice) === canonicalJson(replayed),
    'FABRIC_ROUTING_REPLAY_MISMATCH',
    'fabric routing slice does not replay',
  );
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
    claimBoundary:
      'This receipt proves deterministic replay of the synthetic routing slice only. It grants no execution success, physical, operator, field, evaluator, mission, or command authority.',
  };
  return { ...body, verificationId: digest('estatefabricverification1', body) };
}

async function writeJson(path, value) {
  await mkdir(dirname(path), { recursive: true });
  await writeFile(path, `${JSON.stringify(value, null, 2)}\n`, 'utf8');
}

async function loadDefaults() {
  const [fabricProfile, registry] = await Promise.all([
    readFile(DEFAULT_PROFILE, 'utf8').then(JSON.parse),
    readFile(DEFAULT_REGISTRY, 'utf8').then(JSON.parse),
  ]);
  return { fabricProfile, registry };
}

async function main(argv) {
  const command = argv[2];
  if (command === 'run') {
    const bundlePath = resolve(argv[3]);
    const outputPath = resolve(argv[4]);
    const bundle = JSON.parse(await readFile(bundlePath, 'utf8'));
    const { fabricProfile, registry } = await loadDefaults();
    const slice = runFabricRoutingSlice({ bundle, fabricProfile, registry });
    await writeJson(outputPath, slice);
    process.stdout.write(`${JSON.stringify({
      status: 'PASS',
      routingSliceId: slice.routingSliceId,
      seatSnapshotId: slice.seatSnapshot.snapshotId,
      selectedSeatId: slice.routeSelection.selectedSeatId,
      leaseId: slice.workerLease.leaseId,
      outputPath,
    }, null, 2)}\n`);
    return;
  }
  if (command === 'verify') {
    const bundlePath = resolve(argv[3]);
    const slicePath = resolve(argv[4]);
    const outputPath = resolve(argv[5]);
    const [bundle, slice, defaults] = await Promise.all([
      readFile(bundlePath, 'utf8').then(JSON.parse),
      readFile(slicePath, 'utf8').then(JSON.parse),
      loadDefaults(),
    ]);
    const verification = verifyFabricRoutingSlice(slice, {
      bundle,
      fabricProfile: defaults.fabricProfile,
      registry: defaults.registry,
    });
    await writeJson(outputPath, verification);
    process.stdout.write(`${JSON.stringify(verification, null, 2)}\n`);
    return;
  }
  throw new FabricRuntimeError(
    'COMMAND_INVALID',
    'usage: fabric_runtime.mjs run <vertical-slice.json> <routing-slice.json> | verify <vertical-slice.json> <routing-slice.json> <verification.json>',
  );
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  main(process.argv).catch((error) => {
    const code = error instanceof FabricRuntimeError ? error.code : 'UNEXPECTED_ERROR';
    process.stderr.write(`${code}: ${error.message}\n`);
    process.exitCode = 1;
  });
}

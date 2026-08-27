import { createHash } from 'node:crypto';
import { canonicalJson } from '../semantic/authority_sidecar.mjs';
import {
  createWorkerLease,
  selectRoute,
  validateFabricRoutingSlice,
  validateRouteSelection,
} from './fabric_runtime.mjs';

export const MAX_STEP = 1_000_000_000;
export const MAX_CANDIDATES = 64;
export const OUTPUT_PREFIX = 'anchorlocalartifact1';
export const REFUSAL_REASONS = new Set([
  'LEASE_EXPIRED',
  'STALE_LEASE_GENERATION',
  'OUTPUT_DIGEST_MISMATCH',
  'INDEPENDENT_VERIFIER_MISMATCH',
  'VERIFIER_OUTPUT_BINDING_MISMATCH',
  'OUTPUT_UNVERIFIABLE',
  'TERMINAL_ALREADY_ACCEPTED',
]);
export const VERIFICATION_STATES = new Set(['pass', 'fail', 'unverifiable']);

export const KEYS = Object.freeze({
  loss: [
    'schema',
    'lossEvidenceId',
    'routingSliceId',
    'routeSelectionId',
    'leaseId',
    'seatId',
    'leaseGeneration',
    'observedAtStep',
    'observedState',
    'evidenceClass',
    'reassignmentPermitted',
    'leaseReleased',
    'authority',
    'claimBoundary',
  ],
  verifier: [
    'schema',
    'verificationEvidenceId',
    'verifierIdentity',
    'verificationState',
    'observedOutputDigest',
    'expectedOutputDigest',
    'routeBindingDigest',
    'evidenceClass',
    'authority',
    'claimBoundary',
  ],
  candidate: [
    'schema',
    'candidateId',
    'submissionId',
    'routingSliceId',
    'routeSelectionId',
    'leaseId',
    'workloadId',
    'seatId',
    'leaseGeneration',
    'submittedAtStep',
    'completedAtStep',
    'leaseStateAtCompletion',
    'modelOrExecutableDigest',
    'invocationContractDigest',
    'contextAndKvContractDigest',
    'effectClass',
    'output',
    'outputDigest',
    'expectedOutputDigest',
    'verificationEvidence',
    'status',
    'authority',
    'claimBoundary',
  ],
  refusal: [
    'schema',
    'refusalId',
    'candidateId',
    'routingSliceId',
    'routeSelectionId',
    'leaseId',
    'seatId',
    'leaseGeneration',
    'evaluatedAtStep',
    'reasons',
    'observedOutputDigest',
    'expectedOutputDigest',
    'acceptedCandidateIdAtEvaluation',
    'terminalStateBeforeEvaluation',
    'authority',
    'claimBoundary',
  ],
  disposition: [
    'candidateId',
    'disposition',
    'refusalId',
    'acceptedOutputDigest',
    'evaluatedAtStep',
  ],
  run: [
    'schema',
    'fabricRunId',
    'sourceRoutingSliceId',
    'sourceRunId',
    'sourceTaskReceiptId',
    'workloadId',
    'canonicalMissionStateIdBeforeExecution',
    'canonicalMissionStateIdAfterExecution',
    'primaryRouteSelection',
    'primaryWorkerLease',
    'primarySeatLossEvidence',
    'fallbackRouteSelection',
    'fallbackWorkerLease',
    'candidateDenominator',
    'candidates',
    'refusals',
    'dispositions',
    'acceptedCandidateId',
    'acceptedOutputDigest',
    'acceptedCompletionCount',
    'refusedCompletionCount',
    'pendingCompletionCount',
    'terminalState',
    'jobCustodyPreserved',
    'canonicalStateUnchanged',
    'memoryAggregationUsed',
    'optionalSeatRequiredForContinuity',
    'executionEffect',
    'externalServiceCalls',
    'operationalCredentials',
    'physicalEvidenceBodies',
    'authority',
    'claimBoundary',
  ],
  verification: [
    'schema',
    'verificationId',
    'fabricRunId',
    'sourceRoutingSliceId',
    'status',
    'candidateDenominatorVerified',
    'refusalDenominatorVerified',
    'primaryLossVerified',
    'fallbackReassignmentVerified',
    'stalePrimaryRefused',
    'latePrimaryRefused',
    'wrongOutputRefused',
    'unverifiableOutputRefused',
    'duplicateTerminalRefused',
    'acceptedCompletionCount',
    'canonicalStateUnchanged',
    'jobCustodyPreserved',
    'memoryAggregationUsed',
    'physicalQualification',
    'representativeOperatorQualification',
    'externalServiceCalls',
    'operationalCredentials',
    'authority',
    'claimBoundary',
  ],
  projection: [
    'schema',
    'projectionId',
    'fabricRunId',
    'sourceRoutingSliceId',
    'routes',
    'leases',
    'candidateSummary',
    'refusalSummary',
    'acceptedCompletion',
    'canonicalStateUnchanged',
    'jobCustodyPreserved',
    'authority',
    'claimBoundary',
  ],
});

export class FabricExecutionError extends Error {
  constructor(code, message) {
    super(message);
    this.name = 'FabricExecutionError';
    this.code = code;
  }
}

export function requireCondition(condition, code, message) {
  if (!condition) throw new FabricExecutionError(code, message);
}

export function isRecord(value) {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) return false;
  const prototype = Object.getPrototypeOf(value);
  return prototype === Object.prototype || prototype === null;
}

export function exactKeys(value, expected, code, label) {
  requireCondition(isRecord(value), code, `${label} must be an object`);
  requireCondition(
    canonicalJson(Object.keys(value).sort()) === canonicalJson([...expected].sort()),
    code,
    `${label} fields differ`,
  );
}

export function boundedString(value, code, label, max = 4096) {
  requireCondition(typeof value === 'string', code, `${label} must be a string`);
  const normalized = value.trim();
  requireCondition(normalized.length > 0 && normalized.length <= max, code, `${label} is empty or unbounded`);
  return normalized;
}

export function safeInteger(value, min, max, code, label) {
  requireCondition(Number.isSafeInteger(value) && value >= min && value <= max, code, `${label} is outside ${min}..${max}`);
  return value;
}

export function uniqueStrings(values, code, label, allowEmpty = false) {
  requireCondition(Array.isArray(values), code, `${label} must be an array`);
  requireCondition(allowEmpty || values.length > 0, code, `${label} must be non-empty`);
  requireCondition(
    values.every((value) => typeof value === 'string' && value.trim().length > 0),
    code,
    `${label} contains an invalid value`,
  );
  requireCondition(new Set(values).size === values.length, code, `${label} contains duplicates`);
}

export function digest(prefix, value) {
  return `${prefix}_${createHash('sha256').update(canonicalJson(value), 'utf8').digest('hex')}`;
}

export function bodyWithoutId(value, idKey) {
  const copy = structuredClone(value);
  delete copy[idKey];
  return copy;
}

export function assertIdentity(value, prefix, idKey, code) {
  requireCondition(value[idKey] === digest(prefix, bodyWithoutId(value, idKey)), code, `${idKey} differs from content identity`);
}

export function exactObject(value, expected, code, label) {
  requireCondition(canonicalJson(value) === canonicalJson(expected), code, `${label} differs`);
}

export function outputDigest(output) {
  return digest(OUTPUT_PREFIX, output);
}

export function routeBindingDigest(route) {
  return digest('estatefabricroutebinding1', {
    routeSelectionId: route.routeSelectionId,
    selectedSeatId: route.selectedSeatId,
    workloadId: route.workloadId,
    endpointIdentity: route.endpointIdentity,
    runtimeVersion: route.runtimeVersion,
    adapterVersion: route.adapterVersion,
    modelOrExecutableDigest: route.modelOrExecutableDigest,
    invocationContract: route.invocationContract,
    contextAndKvContract: route.contextAndKvContract,
    acceptancePredicate: route.acceptancePredicate,
    independentVerifierIdentity: route.independentVerifierIdentity,
  });
}

export function invocationDigest(route) {
  return digest('estatefabricinvocationbinding1', route.invocationContract);
}

export function contextDigest(route) {
  return digest('estatefabriccontextbinding1', route.contextAndKvContract);
}

export function createPrimarySeatLossEvidence({ routingSlice, observedAtStep = 22 }) {
  validateFabricRoutingSlice(routingSlice);
  safeInteger(observedAtStep, 0, MAX_STEP, 'SEAT_LOSS_EVIDENCE_INVALID', 'observedAtStep');
  const lease = routingSlice.workerLease;
  requireCondition(
    observedAtStep >= lease.issuedAtStep && observedAtStep <= lease.expiresAtStep,
    'SEAT_LOSS_EVIDENCE_INVALID',
    'seat loss must be observed while the primary lease is still active',
  );
  const body = {
    schema: 'estate-fabric-seat-loss-evidence/1',
    routingSliceId: routingSlice.routingSliceId,
    routeSelectionId: routingSlice.routeSelection.routeSelectionId,
    leaseId: lease.leaseId,
    seatId: lease.seatId,
    leaseGeneration: lease.generation,
    observedAtStep,
    observedState: 'inaccessible',
    evidenceClass: 'synthetic_injected_fault',
    reassignmentPermitted: true,
    leaseReleased: false,
    authority: false,
    claimBoundary:
      'Synthetic evidence that the selected primary seat became inaccessible. It permits bounded reassignment but does not prove process death, release a lock, accept completion, mutate mission state, or grant authority.',
  };
  return { ...body, lossEvidenceId: digest('estatefabricseatlossevidence1', body) };
}

export function validatePrimarySeatLossEvidence(loss, routingSlice) {
  exactKeys(loss, KEYS.loss, 'SEAT_LOSS_EVIDENCE_INVALID', 'seat-loss evidence');
  requireCondition(loss.schema === 'estate-fabric-seat-loss-evidence/1', 'SEAT_LOSS_EVIDENCE_SCHEMA_INVALID', 'seat-loss evidence schema differs');
  safeInteger(loss.leaseGeneration, 1, MAX_STEP, 'SEAT_LOSS_EVIDENCE_INVALID', 'leaseGeneration');
  safeInteger(loss.observedAtStep, 0, MAX_STEP, 'SEAT_LOSS_EVIDENCE_INVALID', 'observedAtStep');
  requireCondition(
    loss.observedState === 'inaccessible' &&
      loss.evidenceClass === 'synthetic_injected_fault' &&
      loss.reassignmentPermitted === true &&
      loss.leaseReleased === false &&
      loss.authority === false,
    'SEAT_LOSS_EVIDENCE_INVALID',
    'seat-loss evidence widens its claim',
  );
  assertIdentity(loss, 'estatefabricseatlossevidence1', 'lossEvidenceId', 'SEAT_LOSS_EVIDENCE_ID_INVALID');
  if (routingSlice !== undefined) {
    validateFabricRoutingSlice(routingSlice);
    requireCondition(
      loss.routingSliceId === routingSlice.routingSliceId &&
        loss.routeSelectionId === routingSlice.routeSelection.routeSelectionId &&
        loss.leaseId === routingSlice.workerLease.leaseId &&
        loss.seatId === routingSlice.workerLease.seatId &&
        loss.leaseGeneration === routingSlice.workerLease.generation,
      'SEAT_LOSS_EVIDENCE_BINDING_INVALID',
      'seat-loss evidence belongs to another route, lease, generation, or seat',
    );
    exactObject(
      loss,
      createPrimarySeatLossEvidence({ routingSlice, observedAtStep: loss.observedAtStep }),
      'SEAT_LOSS_EVIDENCE_REPLAY_MISMATCH',
      'seat-loss evidence replay',
    );
  }
  return loss;
}

function admittedFallbackSeatId(routingSlice) {
  const primarySeatId = routingSlice.routeSelection.selectedSeatId;
  const admitted = routingSlice.admissions.filter(
    (row) => row.disposition === 'admit' && row.seatId !== primarySeatId,
  );
  requireCondition(admitted.length > 0, 'FALLBACK_ROUTE_UNAVAILABLE', 'no admitted fallback seat exists');
  const roleRank = new Map([
    ['fallback', 0],
    ['resident', 1],
    ['optional', 2],
  ]);
  return [...admitted].sort(
    (a, b) => (roleRank.get(a.seatRole) ?? 9) - (roleRank.get(b.seatRole) ?? 9) || a.seatId.localeCompare(b.seatId),
  )[0].seatId;
}

export function createFallbackRouteAndLease({
  routingSlice,
  lossEvidence,
  leaseDurationSteps = 6,
}) {
  validateFabricRoutingSlice(routingSlice);
  validatePrimarySeatLossEvidence(lossEvidence, routingSlice);
  const fallbackSeatId = admittedFallbackSeatId(routingSlice);
  const fallbackRouteSelection = selectRoute({
    snapshot: routingSlice.seatSnapshot,
    workload: routingSlice.workload,
    admissions: routingSlice.admissions,
    preferredSeatId: fallbackSeatId,
  });
  const fallbackWorkerLease = createWorkerLease({
    routeSelection: fallbackRouteSelection,
    generation: routingSlice.workerLease.generation + 1,
    issuedAtStep: lossEvidence.observedAtStep + 1,
    leaseDurationSteps,
  });
  return { fallbackRouteSelection, fallbackWorkerLease };
}

export function createIndependentVerifierEvidence({
  routeSelection,
  outputDigest: observedOutputDigest,
  verificationState = 'pass',
  verifierIdentity = routeSelection.independentVerifierIdentity,
}) {
  validateRouteSelection(routeSelection);
  requireCondition(VERIFICATION_STATES.has(verificationState), 'VERIFIER_EVIDENCE_INVALID', 'verification state differs');
  boundedString(verifierIdentity, 'VERIFIER_EVIDENCE_INVALID', 'verifierIdentity');
  boundedString(observedOutputDigest, 'VERIFIER_EVIDENCE_INVALID', 'observedOutputDigest');
  const body = {
    schema: 'estate-independent-output-verification-evidence/1',
    verifierIdentity,
    verificationState,
    observedOutputDigest,
    expectedOutputDigest: routeSelection.outputDigest,
    routeBindingDigest: routeBindingDigest(routeSelection),
    evidenceClass: 'synthetic_independent_replay',
    authority: false,
    claimBoundary:
      'Synthetic independent output-verification evidence. A pass may satisfy the route acceptance predicate but does not grant mission, command, evaluator, field, or hardware authority.',
  };
  return { ...body, verificationEvidenceId: digest('estateindependentverificationevidence1', body) };
}

export function validateIndependentVerifierEvidence(evidence, routeSelection) {
  exactKeys(evidence, KEYS.verifier, 'VERIFIER_EVIDENCE_INVALID', 'verifier evidence');
  requireCondition(
    evidence.schema === 'estate-independent-output-verification-evidence/1',
    'VERIFIER_EVIDENCE_SCHEMA_INVALID',
    'verifier evidence schema differs',
  );
  requireCondition(VERIFICATION_STATES.has(evidence.verificationState), 'VERIFIER_EVIDENCE_INVALID', 'verification state differs');
  requireCondition(evidence.evidenceClass === 'synthetic_independent_replay' && evidence.authority === false, 'VERIFIER_EVIDENCE_AUTHORITY_INVALID', 'verifier evidence widens its claim');
  assertIdentity(
    evidence,
    'estateindependentverificationevidence1',
    'verificationEvidenceId',
    'VERIFIER_EVIDENCE_ID_INVALID',
  );
  if (routeSelection !== undefined) {
    validateRouteSelection(routeSelection);
    requireCondition(
      evidence.expectedOutputDigest === routeSelection.outputDigest &&
        evidence.routeBindingDigest === routeBindingDigest(routeSelection),
      'VERIFIER_EVIDENCE_BINDING_INVALID',
      'verifier evidence belongs to another route or expected output',
    );
  }
  return evidence;
}

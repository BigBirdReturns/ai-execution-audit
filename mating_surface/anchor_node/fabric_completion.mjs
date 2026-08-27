import {
  KEYS,
  MAX_STEP,
  REFUSAL_REASONS,
  FabricExecutionError,
  assertIdentity,
  boundedString,
  contextDigest,
  digest,
  exactKeys,
  exactObject,
  isRecord,
  invocationDigest,
  outputDigest,
  requireCondition,
  safeInteger,
  uniqueStrings,
  createIndependentVerifierEvidence,
  validateIndependentVerifierEvidence,
} from './fabric_execution_support.mjs';
import {
  validateFabricRoutingSlice,
  validateRouteSelection,
  validateWorkerLease,
  verifyRouteSelection,
  verifyWorkerLease,
  workerLeaseStateAt,
} from './fabric_runtime.mjs';

export function createCompletionCandidate({
  routingSlice,
  routeSelection,
  workerLease,
  submissionId,
  output,
  submittedAtStep,
  completedAtStep,
  verificationState = 'pass',
  verifierIdentity = routeSelection.independentVerifierIdentity,
}) {
  validateFabricRoutingSlice(routingSlice);
  verifyRouteSelection(
    routeSelection,
    routingSlice.seatSnapshot,
    routingSlice.workload,
    routingSlice.admissions,
  );
  verifyWorkerLease(workerLease, routeSelection);
  boundedString(submissionId, 'COMPLETION_CANDIDATE_INVALID', 'submissionId');
  requireCondition(submissionId.startsWith('SYN-CANDIDATE-'), 'COMPLETION_CANDIDATE_INVALID', 'submission identity is not synthetic');
  safeInteger(submittedAtStep, 0, MAX_STEP, 'COMPLETION_CANDIDATE_INVALID', 'submittedAtStep');
  safeInteger(completedAtStep, 0, MAX_STEP, 'COMPLETION_CANDIDATE_INVALID', 'completedAtStep');
  requireCondition(completedAtStep >= submittedAtStep && submittedAtStep >= workerLease.issuedAtStep, 'COMPLETION_CANDIDATE_INVALID', 'candidate timing is invalid');
  requireCondition(isRecord(output), 'COMPLETION_CANDIDATE_INVALID', 'candidate output must be an object');
  const observedDigest = outputDigest(output);
  const verificationEvidence = createIndependentVerifierEvidence({
    routeSelection,
    outputDigest: observedDigest,
    verificationState,
    verifierIdentity,
  });
  const body = {
    schema: 'estate-completion-candidate/1',
    submissionId,
    routingSliceId: routingSlice.routingSliceId,
    routeSelectionId: routeSelection.routeSelectionId,
    leaseId: workerLease.leaseId,
    workloadId: routeSelection.workloadId,
    seatId: workerLease.seatId,
    leaseGeneration: workerLease.generation,
    submittedAtStep,
    completedAtStep,
    leaseStateAtCompletion: workerLeaseStateAt(workerLease, completedAtStep),
    modelOrExecutableDigest: routeSelection.modelOrExecutableDigest,
    invocationContractDigest: invocationDigest(routeSelection),
    contextAndKvContractDigest: contextDigest(routeSelection),
    effectClass: 'local_artifact_only',
    output: structuredClone(output),
    outputDigest: observedDigest,
    expectedOutputDigest: routeSelection.outputDigest,
    verificationEvidence,
    status: 'candidate_pending_terminal_disposition',
    authority: false,
    claimBoundary:
      'Synthetic bounded completion candidate for one local-artifact-only route. It is neither accepted completion nor mission, command, field, evaluator, model, or hardware authority.',
  };
  return { ...body, candidateId: digest('estatecompletioncandidate1', body) };
}

export function validateCompletionCandidate(candidate, { routingSlice, routeSelection, workerLease } = {}) {
  exactKeys(candidate, KEYS.candidate, 'COMPLETION_CANDIDATE_INVALID', 'completion candidate');
  requireCondition(candidate.schema === 'estate-completion-candidate/1', 'COMPLETION_CANDIDATE_SCHEMA_INVALID', 'completion candidate schema differs');
  boundedString(candidate.submissionId, 'COMPLETION_CANDIDATE_INVALID', 'submissionId');
  safeInteger(candidate.leaseGeneration, 1, MAX_STEP, 'COMPLETION_CANDIDATE_INVALID', 'leaseGeneration');
  safeInteger(candidate.submittedAtStep, 0, MAX_STEP, 'COMPLETION_CANDIDATE_INVALID', 'submittedAtStep');
  safeInteger(candidate.completedAtStep, 0, MAX_STEP, 'COMPLETION_CANDIDATE_INVALID', 'completedAtStep');
  requireCondition(candidate.completedAtStep >= candidate.submittedAtStep, 'COMPLETION_CANDIDATE_INVALID', 'candidate completes before submission');
  requireCondition(['active', 'expired'].includes(candidate.leaseStateAtCompletion), 'COMPLETION_CANDIDATE_INVALID', 'lease state differs');
  requireCondition(candidate.effectClass === 'local_artifact_only' && candidate.status === 'candidate_pending_terminal_disposition' && candidate.authority === false, 'COMPLETION_CANDIDATE_CLAIM_INVALID', 'candidate widens its claim');
  requireCondition(isRecord(candidate.output), 'COMPLETION_CANDIDATE_INVALID', 'candidate output must be an object');
  requireCondition(candidate.outputDigest === outputDigest(candidate.output), 'COMPLETION_CANDIDATE_OUTPUT_ID_INVALID', 'candidate output digest differs from output');
  validateIndependentVerifierEvidence(candidate.verificationEvidence, routeSelection);
  requireCondition(candidate.verificationEvidence.observedOutputDigest === candidate.outputDigest, 'COMPLETION_CANDIDATE_VERIFIER_BINDING_INVALID', 'verifier observed another output');
  assertIdentity(candidate, 'estatecompletioncandidate1', 'candidateId', 'COMPLETION_CANDIDATE_ID_INVALID');
  if (routingSlice !== undefined) {
    validateFabricRoutingSlice(routingSlice);
    requireCondition(candidate.routingSliceId === routingSlice.routingSliceId && candidate.workloadId === routingSlice.workload.workloadId, 'COMPLETION_CANDIDATE_BINDING_INVALID', 'candidate belongs to another routing slice or workload');
  }
  if (routeSelection !== undefined) {
    validateRouteSelection(routeSelection);
    requireCondition(
      candidate.routeSelectionId === routeSelection.routeSelectionId &&
        candidate.seatId === routeSelection.selectedSeatId &&
        candidate.modelOrExecutableDigest === routeSelection.modelOrExecutableDigest &&
        candidate.invocationContractDigest === invocationDigest(routeSelection) &&
        candidate.contextAndKvContractDigest === contextDigest(routeSelection) &&
        candidate.expectedOutputDigest === routeSelection.outputDigest,
      'COMPLETION_CANDIDATE_BINDING_INVALID',
      'candidate route identity differs',
    );
  }
  if (workerLease !== undefined) {
    validateWorkerLease(workerLease);
    requireCondition(
      candidate.leaseId === workerLease.leaseId &&
        candidate.seatId === workerLease.seatId &&
        candidate.leaseGeneration === workerLease.generation &&
        candidate.submittedAtStep >= workerLease.issuedAtStep &&
        candidate.leaseStateAtCompletion === workerLeaseStateAt(workerLease, candidate.completedAtStep),
      'COMPLETION_CANDIDATE_LEASE_INVALID',
      'candidate lease identity or timing differs',
    );
  }
  return candidate;
}

export function completionRefusalReasons(candidate, { activeGeneration, acceptedCandidateId, routeSelection }) {
  const reasons = [];
  if (candidate.leaseStateAtCompletion === 'expired') reasons.push('LEASE_EXPIRED');
  if (candidate.leaseGeneration < activeGeneration) reasons.push('STALE_LEASE_GENERATION');
  if (candidate.outputDigest !== candidate.expectedOutputDigest) reasons.push('OUTPUT_DIGEST_MISMATCH');
  if (candidate.verificationEvidence.verifierIdentity !== routeSelection.independentVerifierIdentity) {
    reasons.push('INDEPENDENT_VERIFIER_MISMATCH');
  }
  if (candidate.verificationEvidence.observedOutputDigest !== candidate.outputDigest) {
    reasons.push('VERIFIER_OUTPUT_BINDING_MISMATCH');
  }
  if (candidate.verificationEvidence.verificationState !== 'pass') reasons.push('OUTPUT_UNVERIFIABLE');
  if (acceptedCandidateId !== null) reasons.push('TERMINAL_ALREADY_ACCEPTED');
  return [...new Set(reasons)];
}

export function createCompletionRefusal({
  candidate,
  routeSelection,
  workerLease,
  activeGeneration,
  acceptedCandidateId,
  evaluatedAtStep,
}) {
  validateCompletionCandidate(candidate, { routeSelection, workerLease });
  safeInteger(activeGeneration, 1, MAX_STEP, 'COMPLETION_REFUSAL_INVALID', 'activeGeneration');
  safeInteger(evaluatedAtStep, 0, MAX_STEP, 'COMPLETION_REFUSAL_INVALID', 'evaluatedAtStep');
  requireCondition(evaluatedAtStep >= candidate.completedAtStep, 'COMPLETION_REFUSAL_INVALID', 'refusal precedes candidate completion');
  const reasons = completionRefusalReasons(candidate, { activeGeneration, acceptedCandidateId, routeSelection });
  requireCondition(reasons.length > 0, 'COMPLETION_REFUSAL_INVALID', 'candidate has no refusal reason');
  const body = {
    schema: 'estate-completion-refusal/1',
    candidateId: candidate.candidateId,
    routingSliceId: candidate.routingSliceId,
    routeSelectionId: candidate.routeSelectionId,
    leaseId: candidate.leaseId,
    seatId: candidate.seatId,
    leaseGeneration: candidate.leaseGeneration,
    evaluatedAtStep,
    reasons,
    observedOutputDigest: candidate.outputDigest,
    expectedOutputDigest: candidate.expectedOutputDigest,
    acceptedCandidateIdAtEvaluation: acceptedCandidateId,
    terminalStateBeforeEvaluation: acceptedCandidateId === null ? 'open' : 'completed',
    authority: false,
    claimBoundary:
      'Terminal refusal for one synthetic completion candidate. It preserves rejected-candidate custody and grants no mission, command, field, evaluator, model, hardware, or lock-release authority.',
  };
  return { ...body, refusalId: digest('estatecompletionrefusal1', body) };
}

export function validateCompletionRefusal(refusal, context = {}) {
  exactKeys(refusal, KEYS.refusal, 'COMPLETION_REFUSAL_INVALID', 'completion refusal');
  requireCondition(refusal.schema === 'estate-completion-refusal/1', 'COMPLETION_REFUSAL_SCHEMA_INVALID', 'completion refusal schema differs');
  safeInteger(refusal.leaseGeneration, 1, MAX_STEP, 'COMPLETION_REFUSAL_INVALID', 'leaseGeneration');
  safeInteger(refusal.evaluatedAtStep, 0, MAX_STEP, 'COMPLETION_REFUSAL_INVALID', 'evaluatedAtStep');
  uniqueStrings(refusal.reasons, 'COMPLETION_REFUSAL_INVALID', 'refusal reasons');
  requireCondition(refusal.reasons.every((reason) => REFUSAL_REASONS.has(reason)), 'COMPLETION_REFUSAL_INVALID', 'unsupported refusal reason');
  requireCondition(['open', 'completed'].includes(refusal.terminalStateBeforeEvaluation) && refusal.authority === false, 'COMPLETION_REFUSAL_CLAIM_INVALID', 'refusal widens its claim');
  assertIdentity(refusal, 'estatecompletionrefusal1', 'refusalId', 'COMPLETION_REFUSAL_ID_INVALID');
  if (context.candidate !== undefined) {
    const replayed = createCompletionRefusal({
      candidate: context.candidate,
      routeSelection: context.routeSelection,
      workerLease: context.workerLease,
      activeGeneration: context.activeGeneration,
      acceptedCandidateId: context.acceptedCandidateId,
      evaluatedAtStep: refusal.evaluatedAtStep,
    });
    exactObject(refusal, replayed, 'COMPLETION_REFUSAL_REPLAY_MISMATCH', 'completion refusal replay');
  }
  return refusal;
}

function createWrongOutput(expectedOutput) {
  const changed = structuredClone(expectedOutput);
  if (Array.isArray(changed.checklist)) {
    changed.checklist = [...changed.checklist, 'synthetic wrong-output marker'];
  } else {
    changed.syntheticWrongOutput = true;
  }
  return changed;
}

export function createDefaultTerminalCandidateSet({ bundle, routingSlice, fallbackRouteSelection, fallbackWorkerLease }) {
  const expectedOutput = bundle.taskReceipt.output;
  const primaryRoute = routingSlice.routeSelection;
  const primaryLease = routingSlice.workerLease;
  return [
    createCompletionCandidate({
      routingSlice,
      routeSelection: primaryRoute,
      workerLease: primaryLease,
      submissionId: 'SYN-CANDIDATE-PRIMARY-STALE-01',
      output: expectedOutput,
      submittedAtStep: 24,
      completedAtStep: 24,
    }),
    createCompletionCandidate({
      routingSlice,
      routeSelection: fallbackRouteSelection,
      workerLease: fallbackWorkerLease,
      submissionId: 'SYN-CANDIDATE-FALLBACK-WRONG-02',
      output: createWrongOutput(expectedOutput),
      submittedAtStep: 24,
      completedAtStep: 24,
      verificationState: 'fail',
    }),
    createCompletionCandidate({
      routingSlice,
      routeSelection: fallbackRouteSelection,
      workerLease: fallbackWorkerLease,
      submissionId: 'SYN-CANDIDATE-FALLBACK-UNVERIFIABLE-03',
      output: expectedOutput,
      submittedAtStep: 25,
      completedAtStep: 25,
      verificationState: 'unverifiable',
    }),
    createCompletionCandidate({
      routingSlice,
      routeSelection: fallbackRouteSelection,
      workerLease: fallbackWorkerLease,
      submissionId: 'SYN-CANDIDATE-FALLBACK-ACCEPTED-04',
      output: expectedOutput,
      submittedAtStep: 26,
      completedAtStep: 26,
      verificationState: 'pass',
    }),
    createCompletionCandidate({
      routingSlice,
      routeSelection: primaryRoute,
      workerLease: primaryLease,
      submissionId: 'SYN-CANDIDATE-PRIMARY-LATE-05',
      output: expectedOutput,
      submittedAtStep: primaryLease.expiresAtStep + 1,
      completedAtStep: primaryLease.expiresAtStep + 1,
      verificationState: 'pass',
    }),
    createCompletionCandidate({
      routingSlice,
      routeSelection: fallbackRouteSelection,
      workerLease: fallbackWorkerLease,
      submissionId: 'SYN-CANDIDATE-FALLBACK-DUPLICATE-06',
      output: expectedOutput,
      submittedAtStep: 27,
      completedAtStep: 27,
      verificationState: 'pass',
    }),
  ];
}

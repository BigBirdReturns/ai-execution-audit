import {
  MAX_STEP,
  requireCondition,
  createFallbackRouteAndLease as createFallbackRouteAndLeaseLegacy,
  createPrimarySeatLossEvidence as createPrimarySeatLossEvidenceLegacy,
  validatePrimarySeatLossEvidence,
} from './fabric_execution_support.mjs';
import { createCompletionCandidate } from './fabric_completion.mjs';
import {
  validateFabricRoutingSlice,
  validateWorkerLease,
} from './fabric_runtime.mjs';

export function deriveTerminalCampaignSchedule(primaryWorkerLease) {
  validateWorkerLease(primaryWorkerLease);
  requireCondition(
    primaryWorkerLease.expiresAtStep < MAX_STEP,
    'TERMINAL_SCHEDULE_HEADROOM_INVALID',
    'terminal campaign requires at least one representable step after primary lease expiry',
  );
  const lossAtStep =
    primaryWorkerLease.issuedAtStep + Math.floor(primaryWorkerLease.leaseDurationSteps / 2);
  const fallbackLeaseIssuedAtStep = lossAtStep + 1;
  const stalePrimaryAtStep = Math.min(
    fallbackLeaseIssuedAtStep + 1,
    primaryWorkerLease.expiresAtStep,
  );
  const wrongOutputAtStep = fallbackLeaseIssuedAtStep + 1;
  const unverifiableAtStep = fallbackLeaseIssuedAtStep + 2;
  const acceptedAtStep = fallbackLeaseIssuedAtStep + 3;
  const latePrimaryAtStep = Math.max(primaryWorkerLease.expiresAtStep + 1, acceptedAtStep);
  const duplicateAtStep = Math.max(acceptedAtStep + 1, latePrimaryAtStep + 1);
  requireCondition(
    duplicateAtStep <= MAX_STEP,
    'TERMINAL_SCHEDULE_HEADROOM_INVALID',
    'terminal campaign schedule exceeds the bounded step domain',
  );
  const fallbackLeaseDurationSteps = Math.max(
    6,
    duplicateAtStep - fallbackLeaseIssuedAtStep,
  );
  requireCondition(
    fallbackLeaseIssuedAtStep + fallbackLeaseDurationSteps <= MAX_STEP,
    'TERMINAL_SCHEDULE_HEADROOM_INVALID',
    'fallback lease exceeds the bounded step domain',
  );
  return {
    lossAtStep,
    fallbackLeaseIssuedAtStep,
    fallbackLeaseDurationSteps,
    stalePrimaryAtStep,
    wrongOutputAtStep,
    unverifiableAtStep,
    acceptedAtStep,
    latePrimaryAtStep,
    duplicateAtStep,
  };
}

export function createPrimarySeatLossEvidence({ routingSlice, observedAtStep = undefined }) {
  validateFabricRoutingSlice(routingSlice);
  const schedule = deriveTerminalCampaignSchedule(routingSlice.workerLease);
  return createPrimarySeatLossEvidenceLegacy({
    routingSlice,
    observedAtStep: observedAtStep ?? schedule.lossAtStep,
  });
}

export function createFallbackRouteAndLease({
  routingSlice,
  lossEvidence,
  leaseDurationSteps = undefined,
}) {
  validateFabricRoutingSlice(routingSlice);
  validatePrimarySeatLossEvidence(lossEvidence, routingSlice);
  const schedule = deriveTerminalCampaignSchedule(routingSlice.workerLease);
  requireCondition(
    lossEvidence.observedAtStep === schedule.lossAtStep,
    'TERMINAL_SCHEDULE_LOSS_MISMATCH',
    'fallback route requires the derived primary-loss step',
  );
  return createFallbackRouteAndLeaseLegacy({
    routingSlice,
    lossEvidence,
    leaseDurationSteps: leaseDurationSteps ?? schedule.fallbackLeaseDurationSteps,
  });
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

export function createDefaultTerminalCandidateSet({
  bundle,
  routingSlice,
  fallbackRouteSelection,
  fallbackWorkerLease,
  schedule = deriveTerminalCampaignSchedule(routingSlice.workerLease),
}) {
  const expectedOutput = bundle.taskReceipt.output;
  const primaryRoute = routingSlice.routeSelection;
  const primaryLease = routingSlice.workerLease;
  requireCondition(
    fallbackWorkerLease.issuedAtStep === schedule.fallbackLeaseIssuedAtStep &&
      fallbackWorkerLease.expiresAtStep >= schedule.duplicateAtStep,
    'TERMINAL_SCHEDULE_FALLBACK_LEASE_INVALID',
    'fallback lease does not cover the derived terminal campaign schedule',
  );
  return [
    createCompletionCandidate({
      routingSlice,
      routeSelection: primaryRoute,
      workerLease: primaryLease,
      submissionId: 'SYN-CANDIDATE-PRIMARY-STALE-01',
      output: expectedOutput,
      submittedAtStep: schedule.stalePrimaryAtStep,
      completedAtStep: schedule.stalePrimaryAtStep,
    }),
    createCompletionCandidate({
      routingSlice,
      routeSelection: fallbackRouteSelection,
      workerLease: fallbackWorkerLease,
      submissionId: 'SYN-CANDIDATE-FALLBACK-WRONG-02',
      output: createWrongOutput(expectedOutput),
      submittedAtStep: schedule.wrongOutputAtStep,
      completedAtStep: schedule.wrongOutputAtStep,
      verificationState: 'fail',
    }),
    createCompletionCandidate({
      routingSlice,
      routeSelection: fallbackRouteSelection,
      workerLease: fallbackWorkerLease,
      submissionId: 'SYN-CANDIDATE-FALLBACK-UNVERIFIABLE-03',
      output: expectedOutput,
      submittedAtStep: schedule.unverifiableAtStep,
      completedAtStep: schedule.unverifiableAtStep,
      verificationState: 'unverifiable',
    }),
    createCompletionCandidate({
      routingSlice,
      routeSelection: fallbackRouteSelection,
      workerLease: fallbackWorkerLease,
      submissionId: 'SYN-CANDIDATE-FALLBACK-ACCEPTED-04',
      output: expectedOutput,
      submittedAtStep: schedule.acceptedAtStep,
      completedAtStep: schedule.acceptedAtStep,
      verificationState: 'pass',
    }),
    createCompletionCandidate({
      routingSlice,
      routeSelection: primaryRoute,
      workerLease: primaryLease,
      submissionId: 'SYN-CANDIDATE-PRIMARY-LATE-05',
      output: expectedOutput,
      submittedAtStep: schedule.latePrimaryAtStep,
      completedAtStep: schedule.latePrimaryAtStep,
      verificationState: 'pass',
    }),
    createCompletionCandidate({
      routingSlice,
      routeSelection: fallbackRouteSelection,
      workerLease: fallbackWorkerLease,
      submissionId: 'SYN-CANDIDATE-FALLBACK-DUPLICATE-06',
      output: expectedOutput,
      submittedAtStep: schedule.duplicateAtStep,
      completedAtStep: schedule.duplicateAtStep,
      verificationState: 'pass',
    }),
  ];
}

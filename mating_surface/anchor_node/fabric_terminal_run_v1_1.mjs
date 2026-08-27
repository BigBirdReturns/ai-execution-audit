import { canonicalJson } from '../semantic/authority_sidecar.mjs';
import {
  KEYS,
  digest,
  exactKeys,
  requireCondition,
  safeInteger,
} from './fabric_execution_support.mjs';
import {
  completionRefusalReasons,
  createCompletionRefusal,
  validateCompletionCandidate,
} from './fabric_completion.mjs';
import {
  verifyFabricRoutingSlice,
} from './fabric_runtime.mjs';
import { verifyVerticalSlice } from './vertical_slice.mjs';
import {
  createDefaultTerminalCandidateSet,
  createFallbackRouteAndLease,
  createPrimarySeatLossEvidence,
  deriveTerminalCampaignSchedule,
} from './fabric_terminal_schedule_v1_1.mjs';

export function candidateContext(candidate, routingSlice, fallbackRouteSelection, fallbackWorkerLease) {
  if (candidate.routeSelectionId === routingSlice.routeSelection.routeSelectionId) {
    return {
      routeSelection: routingSlice.routeSelection,
      workerLease: routingSlice.workerLease,
    };
  }
  requireCondition(
    candidate.routeSelectionId === fallbackRouteSelection.routeSelectionId,
    'FABRIC_RUN_CANDIDATE_ROUTE_INVALID',
    'candidate belongs to an undeclared route',
  );
  return {
    routeSelection: fallbackRouteSelection,
    workerLease: fallbackWorkerLease,
  };
}

export function runFabricExecutionCampaign({ bundle, routingSlice, fabricProfile, registry }) {
  verifyVerticalSlice(bundle);
  verifyFabricRoutingSlice(routingSlice, { bundle, fabricProfile, registry });
  const schedule = deriveTerminalCampaignSchedule(routingSlice.workerLease);
  const lossEvidence = createPrimarySeatLossEvidence({
    routingSlice,
    observedAtStep: schedule.lossAtStep,
  });
  const { fallbackRouteSelection, fallbackWorkerLease } = createFallbackRouteAndLease({
    routingSlice,
    lossEvidence,
    leaseDurationSteps: schedule.fallbackLeaseDurationSteps,
  });
  const candidates = createDefaultTerminalCandidateSet({
    bundle,
    routingSlice,
    fallbackRouteSelection,
    fallbackWorkerLease,
    schedule,
  });

  let acceptedCandidateId = null;
  let acceptedOutputDigest = null;
  const refusals = [];
  const dispositions = [];
  for (const candidate of candidates) {
    const context = candidateContext(
      candidate,
      routingSlice,
      fallbackRouteSelection,
      fallbackWorkerLease,
    );
    validateCompletionCandidate(candidate, {
      routingSlice,
      ...context,
    });
    const reasons = completionRefusalReasons(candidate, {
      activeGeneration: fallbackWorkerLease.generation,
      acceptedCandidateId,
      routeSelection: context.routeSelection,
    });
    if (reasons.length === 0) {
      acceptedCandidateId = candidate.candidateId;
      acceptedOutputDigest = candidate.outputDigest;
      dispositions.push({
        candidateId: candidate.candidateId,
        disposition: 'accept',
        refusalId: null,
        acceptedOutputDigest: candidate.outputDigest,
        evaluatedAtStep: candidate.completedAtStep,
      });
      continue;
    }
    const refusal = createCompletionRefusal({
      candidate,
      routeSelection: context.routeSelection,
      workerLease: context.workerLease,
      activeGeneration: fallbackWorkerLease.generation,
      acceptedCandidateId,
      evaluatedAtStep: candidate.completedAtStep,
    });
    refusals.push(refusal);
    dispositions.push({
      candidateId: candidate.candidateId,
      disposition: 'refuse',
      refusalId: refusal.refusalId,
      acceptedOutputDigest: null,
      evaluatedAtStep: refusal.evaluatedAtStep,
    });
  }

  requireCondition(acceptedCandidateId !== null, 'FABRIC_RUN_NO_ACCEPTED_COMPLETION', 'campaign accepted no completion');
  const stateId = routingSlice.canonicalMissionStateIdAfterRouting;
  const body = {
    schema: 'estate-fabric-run/1',
    sourceRoutingSliceId: routingSlice.routingSliceId,
    sourceRunId: routingSlice.sourceRunId,
    sourceTaskReceiptId: routingSlice.sourceTaskReceiptId,
    workloadId: routingSlice.workload.workloadId,
    canonicalMissionStateIdBeforeExecution: stateId,
    canonicalMissionStateIdAfterExecution: stateId,
    primaryRouteSelection: structuredClone(routingSlice.routeSelection),
    primaryWorkerLease: structuredClone(routingSlice.workerLease),
    primarySeatLossEvidence: lossEvidence,
    fallbackRouteSelection,
    fallbackWorkerLease,
    candidateDenominator: candidates.map((candidate) => candidate.candidateId),
    candidates,
    refusals,
    dispositions,
    acceptedCandidateId,
    acceptedOutputDigest,
    acceptedCompletionCount: 1,
    refusedCompletionCount: refusals.length,
    pendingCompletionCount: 0,
    terminalState: 'completed_exactly_once',
    jobCustodyPreserved: true,
    canonicalStateUnchanged: true,
    memoryAggregationUsed: false,
    optionalSeatRequiredForContinuity: false,
    executionEffect: 'local_artifact_only',
    externalServiceCalls: 0,
    operationalCredentials: 0,
    physicalEvidenceBodies: 0,
    authority: false,
    claimBoundary:
      'Complete synthetic Estate fabric terminal campaign. It proves bounded local-artifact execution custody, refusal, reassignment, verification, and exactly-once completion without physical, representative-operator, field, operational-C2, mission, command, targeting, engagement, effector, or weapons authority.',
  };
  return { ...body, fabricRunId: digest('estatefabricrun1', body) };
}

export function validateDispositionRows(run) {
  requireCondition(Array.isArray(run.dispositions) && run.dispositions.length === run.candidates.length, 'FABRIC_RUN_DISPOSITION_DENOMINATOR_INVALID', 'disposition denominator differs');
  const candidateIds = run.candidates.map((row) => row.candidateId);
  requireCondition(
    canonicalJson(run.dispositions.map((row) => row.candidateId)) === canonicalJson(candidateIds),
    'FABRIC_RUN_DISPOSITION_DENOMINATOR_INVALID',
    'dispositions do not preserve candidate order and denominator',
  );
  for (const row of run.dispositions) {
    exactKeys(row, KEYS.disposition, 'FABRIC_RUN_DISPOSITION_INVALID', 'candidate disposition');
    requireCondition(['accept', 'refuse'].includes(row.disposition), 'FABRIC_RUN_DISPOSITION_INVALID', 'candidate disposition differs');
    safeInteger(row.evaluatedAtStep, 0, MAX_STEP, 'FABRIC_RUN_DISPOSITION_INVALID', 'evaluatedAtStep');
    if (row.disposition === 'accept') {
      requireCondition(row.refusalId === null && row.acceptedOutputDigest !== null, 'FABRIC_RUN_DISPOSITION_INVALID', 'accepted disposition lacks output or carries refusal');
    } else {
      requireCondition(typeof row.refusalId === 'string' && row.acceptedOutputDigest === null, 'FABRIC_RUN_DISPOSITION_INVALID', 'refused disposition lacks refusal or carries accepted output');
    }
  }
}

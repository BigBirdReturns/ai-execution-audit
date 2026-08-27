import { canonicalJson } from '../semantic/authority_sidecar.mjs';
import {
  KEYS,
  MAX_CANDIDATES,
  assertIdentity,
  digest,
  exactKeys,
  exactObject,
  requireCondition,
  uniqueStrings,
} from './fabric_execution_support.mjs';
import {
  completionRefusalReasons,
  validateCompletionCandidate,
  validateCompletionRefusal,
} from './fabric_completion.mjs';
import {
  validateFabricRoutingSlice,
  validateRouteSelection,
  validateWorkerLease,
  verifyFabricRoutingSlice,
  verifyWorkerLease,
} from './fabric_runtime.mjs';
import { verifyVerticalSlice } from './vertical_slice.mjs';
import { validatePrimarySeatLossEvidence } from './fabric_execution_support.mjs';
import {
  runFabricExecutionCampaign,
  validateDispositionRows,
} from './fabric_terminal_run_v1_1.mjs';

export function validateFabricRun(run, { routingSlice } = {}) {
  exactKeys(run, KEYS.run, 'FABRIC_RUN_INVALID', 'fabric run');
  requireCondition(run.schema === 'estate-fabric-run/1', 'FABRIC_RUN_SCHEMA_INVALID', 'fabric run schema differs');
  if (routingSlice !== undefined) {
    validateFabricRoutingSlice(routingSlice);
    requireCondition(
      run.sourceRoutingSliceId === routingSlice.routingSliceId &&
        run.sourceRunId === routingSlice.sourceRunId &&
        run.sourceTaskReceiptId === routingSlice.sourceTaskReceiptId &&
        run.workloadId === routingSlice.workload.workloadId &&
        run.canonicalMissionStateIdBeforeExecution === routingSlice.canonicalMissionStateIdAfterRouting,
      'FABRIC_RUN_SOURCE_BINDING_INVALID',
      'fabric run belongs to another routing slice, source run, task, workload, or mission state',
    );
  }
  requireCondition(run.canonicalMissionStateIdBeforeExecution === run.canonicalMissionStateIdAfterExecution && run.canonicalStateUnchanged === true, 'FABRIC_RUN_STATE_MUTATION', 'fabric run mutates canonical state');
  requireCondition(Array.isArray(run.candidates) && run.candidates.length > 0 && run.candidates.length <= MAX_CANDIDATES, 'FABRIC_RUN_CANDIDATE_DENOMINATOR_INVALID', 'candidate denominator is invalid');
  uniqueStrings(run.candidateDenominator, 'FABRIC_RUN_CANDIDATE_DENOMINATOR_INVALID', 'candidateDenominator');
  requireCondition(canonicalJson(run.candidateDenominator) === canonicalJson(run.candidates.map((row) => row.candidateId)), 'FABRIC_RUN_CANDIDATE_DENOMINATOR_INVALID', 'candidate denominator differs from candidates');
  requireCondition(new Set(run.candidates.map((row) => row.candidateId)).size === run.candidates.length, 'FABRIC_RUN_CANDIDATE_DENOMINATOR_INVALID', 'candidate identities are duplicated');
  validateRouteSelection(run.primaryRouteSelection);
  validateWorkerLease(run.primaryWorkerLease);
  verifyWorkerLease(run.primaryWorkerLease, run.primaryRouteSelection);
  validatePrimarySeatLossEvidence(run.primarySeatLossEvidence, routingSlice);
  requireCondition(
    run.primarySeatLossEvidence.routeSelectionId === run.primaryRouteSelection.routeSelectionId &&
      run.primarySeatLossEvidence.leaseId === run.primaryWorkerLease.leaseId,
    'FABRIC_RUN_PRIMARY_BINDING_INVALID',
    'primary loss evidence differs from embedded primary route or lease',
  );
  if (routingSlice !== undefined) {
    requireCondition(
      canonicalJson(run.primaryRouteSelection) === canonicalJson(routingSlice.routeSelection) &&
        canonicalJson(run.primaryWorkerLease) === canonicalJson(routingSlice.workerLease),
      'FABRIC_RUN_PRIMARY_BINDING_INVALID',
      'embedded primary route or lease differs from routing slice',
    );
  }
  validateRouteSelection(run.fallbackRouteSelection);
  validateWorkerLease(run.fallbackWorkerLease);
  requireCondition(run.fallbackWorkerLease.generation === run.primarySeatLossEvidence.leaseGeneration + 1, 'FABRIC_RUN_FALLBACK_GENERATION_INVALID', 'fallback lease is not the next generation');
  requireCondition(run.fallbackWorkerLease.seatId !== run.primarySeatLossEvidence.seatId, 'FABRIC_RUN_FALLBACK_SEAT_INVALID', 'fallback lease remains on lost primary seat');
  verifyWorkerLease(run.fallbackWorkerLease, run.fallbackRouteSelection);
  validateDispositionRows(run);

  const candidateMap = new Map(run.candidates.map((row) => [row.candidateId, row]));
  const refusalMap = new Map();
  for (const refusal of run.refusals) {
    validateCompletionRefusal(refusal);
    requireCondition(!refusalMap.has(refusal.refusalId), 'FABRIC_RUN_REFUSAL_DENOMINATOR_INVALID', 'duplicate refusal identity');
    refusalMap.set(refusal.refusalId, refusal);
  }
  requireCondition(run.refusedCompletionCount === run.refusals.length, 'FABRIC_RUN_REFUSAL_DENOMINATOR_INVALID', 'refusal count differs');
  requireCondition(run.acceptedCompletionCount === 1 && run.pendingCompletionCount === 0, 'FABRIC_RUN_TERMINAL_COUNT_INVALID', 'fabric run does not have exactly one accepted completion and zero pending');
  requireCondition(candidateMap.has(run.acceptedCandidateId), 'FABRIC_RUN_ACCEPTED_CANDIDATE_INVALID', 'accepted candidate is absent');
  const acceptedCandidate = candidateMap.get(run.acceptedCandidateId);
  requireCondition(acceptedCandidate.outputDigest === run.acceptedOutputDigest, 'FABRIC_RUN_ACCEPTED_OUTPUT_INVALID', 'accepted output differs');
  requireCondition(acceptedCandidate.routeSelectionId === run.fallbackRouteSelection.routeSelectionId && acceptedCandidate.leaseId === run.fallbackWorkerLease.leaseId, 'FABRIC_RUN_ACCEPTED_ROUTE_INVALID', 'accepted completion did not come from fallback route and lease');

  let acceptedSeen = false;
  let acceptedCandidateId = null;
  for (const [index, candidate] of run.candidates.entries()) {
    const routeSelection = candidate.routeSelectionId === run.fallbackRouteSelection.routeSelectionId
      ? run.fallbackRouteSelection
      : run.primaryRouteSelection;
    const workerLease = candidate.leaseId === run.fallbackWorkerLease.leaseId
      ? run.fallbackWorkerLease
      : run.primaryWorkerLease;
    requireCondition(routeSelection !== undefined && workerLease !== undefined, 'FABRIC_RUN_CANDIDATE_ROUTE_INVALID', 'candidate route or lease is unavailable');
    validateCompletionCandidate(candidate, { routingSlice, routeSelection, workerLease });
    const disposition = run.dispositions[index];
    const reasons = completionRefusalReasons(candidate, {
      activeGeneration: run.fallbackWorkerLease.generation,
      acceptedCandidateId,
      routeSelection,
    });
    if (reasons.length === 0) {
      requireCondition(!acceptedSeen && disposition.disposition === 'accept' && disposition.candidateId === candidate.candidateId && disposition.refusalId === null && disposition.acceptedOutputDigest === candidate.outputDigest, 'FABRIC_RUN_ACCEPTED_DISPOSITION_INVALID', 'accepted disposition differs');
      acceptedSeen = true;
      acceptedCandidateId = candidate.candidateId;
      continue;
    }
    requireCondition(disposition.disposition === 'refuse' && disposition.candidateId === candidate.candidateId, 'FABRIC_RUN_REFUSED_DISPOSITION_INVALID', 'refused disposition differs');
    const refusal = refusalMap.get(disposition.refusalId);
    requireCondition(refusal !== undefined, 'FABRIC_RUN_REFUSAL_DENOMINATOR_INVALID', 'refusal referenced by disposition is absent');
    validateCompletionRefusal(refusal, {
      candidate,
      routeSelection,
      workerLease,
      activeGeneration: run.fallbackWorkerLease.generation,
      acceptedCandidateId,
    });
  }
  requireCondition(acceptedSeen && acceptedCandidateId === run.acceptedCandidateId, 'FABRIC_RUN_ACCEPTED_CANDIDATE_INVALID', 'accepted candidate order or identity differs');
  requireCondition(new Set(run.dispositions.filter((row) => row.disposition === 'refuse').map((row) => row.refusalId)).size === run.refusals.length, 'FABRIC_RUN_REFUSAL_DENOMINATOR_INVALID', 'refusal denominator contains unused or duplicate rows');
  requireCondition(
    run.terminalState === 'completed_exactly_once' &&
      run.jobCustodyPreserved === true &&
      run.memoryAggregationUsed === false &&
      run.optionalSeatRequiredForContinuity === false &&
      run.executionEffect === 'local_artifact_only' &&
      run.externalServiceCalls === 0 &&
      run.operationalCredentials === 0 &&
      run.physicalEvidenceBodies === 0 &&
      run.authority === false,
    'FABRIC_RUN_CLAIM_INVALID',
    'fabric run widens its claim or loses custody',
  );
  assertIdentity(run, 'estatefabricrun1', 'fabricRunId', 'FABRIC_RUN_ID_INVALID');
  return run;
}

export function verifyFabricRun(run, { bundle, routingSlice, fabricProfile, registry }) {
  validateFabricRun(run, { routingSlice });
  verifyVerticalSlice(bundle);
  verifyFabricRoutingSlice(routingSlice, { bundle, fabricProfile, registry });
  const replayed = runFabricExecutionCampaign({ bundle, routingSlice, fabricProfile, registry });
  exactObject(run, replayed, 'FABRIC_RUN_REPLAY_MISMATCH', 'fabric run replay');
  const refusalReasonsFlat = run.refusals.flatMap((row) => row.reasons);
  const body = {
    schema: 'estate-fabric-verification/1',
    fabricRunId: run.fabricRunId,
    sourceRoutingSliceId: run.sourceRoutingSliceId,
    status: 'PASS',
    candidateDenominatorVerified: true,
    refusalDenominatorVerified: true,
    primaryLossVerified: true,
    fallbackReassignmentVerified: true,
    stalePrimaryRefused: refusalReasonsFlat.includes('STALE_LEASE_GENERATION'),
    latePrimaryRefused: refusalReasonsFlat.includes('LEASE_EXPIRED'),
    wrongOutputRefused: refusalReasonsFlat.includes('OUTPUT_DIGEST_MISMATCH'),
    unverifiableOutputRefused: refusalReasonsFlat.includes('OUTPUT_UNVERIFIABLE'),
    duplicateTerminalRefused: refusalReasonsFlat.includes('TERMINAL_ALREADY_ACCEPTED'),
    acceptedCompletionCount: run.acceptedCompletionCount,
    canonicalStateUnchanged: run.canonicalStateUnchanged,
    jobCustodyPreserved: run.jobCustodyPreserved,
    memoryAggregationUsed: run.memoryAggregationUsed,
    physicalQualification: false,
    representativeOperatorQualification: false,
    externalServiceCalls: 0,
    operationalCredentials: 0,
    authority: 'none',
    claimBoundary:
      'Detached verification of the complete synthetic Estate fabric terminal campaign. It grants no physical, operator, field, evaluator, operational-C2, mission, command, targeting, engagement, effector, or weapons authority.',
  };
  requireCondition(
    body.stalePrimaryRefused &&
      body.latePrimaryRefused &&
      body.wrongOutputRefused &&
      body.unverifiableOutputRefused &&
      body.duplicateTerminalRefused &&
      body.acceptedCompletionCount === 1,
    'FABRIC_RUN_HOSTILE_DENOMINATOR_INCOMPLETE',
    'terminal hostile denominator is incomplete',
  );
  return { ...body, verificationId: digest('estatefabricterminalverification1', body) };
}

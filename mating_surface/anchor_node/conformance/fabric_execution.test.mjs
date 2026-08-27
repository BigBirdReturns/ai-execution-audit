import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';
import {
  FabricExecutionError,
  buildFabricExecutionProjection,
  createCompletionCandidate,
  createCompletionRefusal,
  createFallbackRouteAndLease,
  createIndependentVerifierEvidence,
  createPrimarySeatLossEvidence,
  renderFabricExecutionHtml,
  runFabricExecutionCampaign,
  validateCompletionCandidate,
  validateCompletionRefusal,
  validateFabricExecutionProjection,
  validateFabricRun,
  validateIndependentVerifierEvidence,
  validatePrimarySeatLossEvidence,
  verifyFabricRun,
} from '../fabric_execution.mjs';
import {
  createWorkerLease,
  runFabricRoutingSlice,
  selectRoute,
} from '../fabric_runtime.mjs';
import { runVerticalSlice } from '../vertical_slice.mjs';

const HERE = dirname(fileURLToPath(import.meta.url));
const REGISTRY_PATH = resolve(HERE, '../fixtures/mp01-invented-seat-registry.json');
const PROFILE_PATH = resolve(HERE, '../fabric-profile-01.json');
const OBSERVATION_PATH = resolve(HERE, '../fixtures/mp01-observation-package.json');

async function fixtures() {
  const [registry, fabricProfile, sourcePackage] = await Promise.all([
    readFile(REGISTRY_PATH, 'utf8').then(JSON.parse),
    readFile(PROFILE_PATH, 'utf8').then(JSON.parse),
    readFile(OBSERVATION_PATH, 'utf8').then(JSON.parse),
  ]);
  const bundle = runVerticalSlice(sourcePackage);
  const routingSlice = runFabricRoutingSlice({ bundle, fabricProfile, registry });
  return { registry, fabricProfile, sourcePackage, bundle, routingSlice };
}

async function campaignFixture() {
  const source = await fixtures();
  const run = runFabricExecutionCampaign(source);
  return { ...source, run };
}

function assertCode(fn, code) {
  assert.throws(fn, (error) => error instanceof FabricExecutionError && error.code === code);
}

function refusalByReason(run, reason) {
  return run.refusals.find((row) => row.reasons.includes(reason));
}

test('complete terminal campaign accepts exactly one fallback completion', async () => {
  const { routingSlice, run } = await campaignFixture();
  assert.equal(validateFabricRun(run, { routingSlice }), run);
  assert.equal(run.acceptedCompletionCount, 1);
  assert.equal(run.refusedCompletionCount, 5);
  assert.equal(run.pendingCompletionCount, 0);
  assert.equal(run.candidates.length, 6);
  assert.equal(run.candidateDenominator.length, 6);
  assert.equal(run.terminalState, 'completed_exactly_once');
  assert.equal(run.jobCustodyPreserved, true);
});

test('primary loss evidence is content-addressed and does not release the lease', async () => {
  const { routingSlice } = await fixtures();
  const loss = createPrimarySeatLossEvidence({ routingSlice });
  assert.equal(validatePrimarySeatLossEvidence(loss, routingSlice), loss);
  assert.equal(loss.seatId, routingSlice.workerLease.seatId);
  assert.equal(loss.observedState, 'inaccessible');
  assert.equal(loss.reassignmentPermitted, true);
  assert.equal(loss.leaseReleased, false);
  assert.equal(loss.authority, false);
});

test('fallback route is independently admitted and receives generation two', async () => {
  const { routingSlice } = await fixtures();
  const lossEvidence = createPrimarySeatLossEvidence({ routingSlice });
  const { fallbackRouteSelection, fallbackWorkerLease } = createFallbackRouteAndLease({
    routingSlice,
    lossEvidence,
  });
  assert.equal(fallbackRouteSelection.selectedSeatId, 'SYN-SEAT-FALLBACK-B');
  assert.equal(fallbackRouteSelection.selectionPolicy, 'explicit_admitted_seat');
  assert.equal(fallbackWorkerLease.generation, 2);
  assert.equal(fallbackWorkerLease.seatId, fallbackRouteSelection.selectedSeatId);
  assert.equal(fallbackWorkerLease.issuedAtStep, lossEvidence.observedAtStep + 1);
});

test('stale primary completion is retained and refused', async () => {
  const { run } = await campaignFixture();
  const refusal = refusalByReason(run, 'STALE_LEASE_GENERATION');
  assert.ok(refusal);
  assert.equal(refusal.seatId, run.primaryWorkerLease.seatId);
  assert.equal(refusal.leaseGeneration, 1);
});

test('late primary completion is refused after finite lease expiry', async () => {
  const { run } = await campaignFixture();
  const refusal = refusalByReason(run, 'LEASE_EXPIRED');
  assert.ok(refusal);
  const candidate = run.candidates.find((row) => row.candidateId === refusal.candidateId);
  assert.equal(candidate.leaseStateAtCompletion, 'expired');
});

test('wrong output candidate is refused', async () => {
  const { run } = await campaignFixture();
  const refusal = refusalByReason(run, 'OUTPUT_DIGEST_MISMATCH');
  assert.ok(refusal);
  assert.notEqual(refusal.observedOutputDigest, refusal.expectedOutputDigest);
});

test('unverifiable output candidate is refused', async () => {
  const { run } = await campaignFixture();
  const refusal = refusalByReason(run, 'OUTPUT_UNVERIFIABLE');
  assert.ok(refusal);
  const candidate = run.candidates.find((row) => row.candidateId === refusal.candidateId);
  assert.notEqual(candidate.verificationEvidence.verificationState, 'pass');
});

test('post-terminal duplicate completion is refused', async () => {
  const { run } = await campaignFixture();
  const refusal = refusalByReason(run, 'TERMINAL_ALREADY_ACCEPTED');
  assert.ok(refusal);
  assert.equal(refusal.terminalStateBeforeEvaluation, 'completed');
  assert.equal(refusal.acceptedCandidateIdAtEvaluation, run.acceptedCandidateId);
});

test('accepted completion binds the fallback route, lease, output, and verifier', async () => {
  const { run } = await campaignFixture();
  const accepted = run.candidates.find((row) => row.candidateId === run.acceptedCandidateId);
  assert.equal(accepted.routeSelectionId, run.fallbackRouteSelection.routeSelectionId);
  assert.equal(accepted.leaseId, run.fallbackWorkerLease.leaseId);
  assert.equal(accepted.leaseGeneration, 2);
  assert.equal(accepted.outputDigest, accepted.expectedOutputDigest);
  assert.equal(accepted.verificationEvidence.verificationState, 'pass');
  assert.equal(
    accepted.verificationEvidence.verifierIdentity,
    run.fallbackRouteSelection.independentVerifierIdentity,
  );
});

test('detached terminal verification closes every hostile condition', async () => {
  const { registry, fabricProfile, bundle, routingSlice, run } = await campaignFixture();
  const verification = verifyFabricRun(run, {
    registry,
    fabricProfile,
    bundle,
    routingSlice,
  });
  assert.equal(verification.status, 'PASS');
  assert.equal(verification.stalePrimaryRefused, true);
  assert.equal(verification.latePrimaryRefused, true);
  assert.equal(verification.wrongOutputRefused, true);
  assert.equal(verification.unverifiableOutputRefused, true);
  assert.equal(verification.duplicateTerminalRefused, true);
  assert.equal(verification.acceptedCompletionCount, 1);
  assert.equal(verification.authority, 'none');
});

test('repeated terminal campaigns are byte-equivalent', async () => {
  const source = await fixtures();
  const first = runFabricExecutionCampaign(source);
  const second = runFabricExecutionCampaign(source);
  assert.deepEqual(first, second);
  assert.equal(first.fabricRunId, second.fabricRunId);
});

test('receipt-only projection rebuilds deterministically from the fabric run', async () => {
  const { run } = await campaignFixture();
  const first = buildFabricExecutionProjection(run);
  const second = buildFabricExecutionProjection(run);
  assert.deepEqual(first, second);
  assert.equal(validateFabricExecutionProjection(first, run), first);
  assert.equal(first.authority, 'none');
  assert.equal(first.candidateSummary.length, run.candidates.length);
  assert.equal(first.refusalSummary.length, run.refusals.length);
});

test('receipt-only review HTML is static and contains terminal custody', async () => {
  const { run } = await campaignFixture();
  const projection = buildFabricExecutionProjection(run);
  const html = renderFabricExecutionHtml(projection);
  assert.match(html, /MP01 Estate Fabric Terminal Receipt/);
  assert.match(html, new RegExp(run.acceptedCandidateId));
  assert.match(html, /Canonical state unchanged: true/);
  assert.doesNotMatch(html, /<script/i);
  assert.doesNotMatch(html, /fetch\s*\(/i);
});

test('candidate denominator cannot silently shrink', async () => {
  const { run } = await campaignFixture();
  const changed = structuredClone(run);
  changed.candidates.pop();
  assertCode(() => validateFabricRun(changed), 'FABRIC_RUN_CANDIDATE_DENOMINATOR_INVALID');
});

test('refusal denominator cannot silently shrink', async () => {
  const { run } = await campaignFixture();
  const changed = structuredClone(run);
  changed.refusals.pop();
  assertCode(() => validateFabricRun(changed), 'FABRIC_RUN_REFUSAL_DENOMINATOR_INVALID');
});

test('accepted completion count cannot inflate', async () => {
  const { run } = await campaignFixture();
  const changed = structuredClone(run);
  changed.acceptedCompletionCount = 2;
  assertCode(() => validateFabricRun(changed), 'FABRIC_RUN_TERMINAL_COUNT_INVALID');
});

test('terminal execution cannot mutate canonical MP01 state', async () => {
  const { run } = await campaignFixture();
  const changed = structuredClone(run);
  changed.canonicalMissionStateIdAfterExecution = 'different-state';
  assertCode(() => validateFabricRun(changed), 'FABRIC_RUN_STATE_MUTATION');
});

test('terminal execution cannot claim pooled memory', async () => {
  const { run } = await campaignFixture();
  const changed = structuredClone(run);
  changed.memoryAggregationUsed = true;
  assertCode(() => validateFabricRun(changed), 'FABRIC_RUN_CLAIM_INVALID');
});

test('terminal execution cannot claim external service use or authority', async () => {
  for (const [key, value] of [['externalServiceCalls', 1], ['authority', true]]) {
    const { run } = await campaignFixture();
    run[key] = value;
    assertCode(() => validateFabricRun(run), 'FABRIC_RUN_CLAIM_INVALID');
  }
});

test('completion output tampering breaks candidate identity before acceptance', async () => {
  const { run } = await campaignFixture();
  const candidate = structuredClone(run.candidates[0]);
  candidate.output.checklist.push('tampered');
  assertCode(() => validateCompletionCandidate(candidate), 'COMPLETION_CANDIDATE_OUTPUT_ID_INVALID');
});

test('completion candidate identity cannot be rewritten', async () => {
  const { run } = await campaignFixture();
  const candidate = structuredClone(run.candidates[0]);
  candidate.candidateId = 'estatecompletioncandidate1_' + '0'.repeat(64);
  assertCode(() => validateCompletionCandidate(candidate), 'COMPLETION_CANDIDATE_ID_INVALID');
});

test('independent verifier evidence identity cannot be rewritten', async () => {
  const { run } = await campaignFixture();
  const accepted = run.candidates.find((row) => row.candidateId === run.acceptedCandidateId);
  const evidence = structuredClone(accepted.verificationEvidence);
  evidence.verificationEvidenceId = 'estateindependentverificationevidence1_' + '0'.repeat(64);
  assertCode(
    () => validateIndependentVerifierEvidence(evidence, run.fallbackRouteSelection),
    'VERIFIER_EVIDENCE_ID_INVALID',
  );
});

test('primary loss evidence cannot migrate to another seat', async () => {
  const { routingSlice } = await fixtures();
  const loss = createPrimarySeatLossEvidence({ routingSlice });
  loss.seatId = 'SYN-SEAT-FALLBACK-B';
  assertCode(
    () => validatePrimarySeatLossEvidence(loss, routingSlice),
    'SEAT_LOSS_EVIDENCE_ID_INVALID',
  );
});

test('fallback lease must be exactly the next generation', async () => {
  const { run } = await campaignFixture();
  const changed = structuredClone(run);
  changed.fallbackWorkerLease = createWorkerLease({
    routeSelection: changed.fallbackRouteSelection,
    generation: 3,
    issuedAtStep: changed.fallbackWorkerLease.issuedAtStep,
    leaseDurationSteps: changed.fallbackWorkerLease.leaseDurationSteps,
  });
  assertCode(() => validateFabricRun(changed), 'FABRIC_RUN_FALLBACK_GENERATION_INVALID');
});

test('fallback lease cannot remain on the lost primary seat', async () => {
  const { routingSlice, run } = await campaignFixture();
  const changed = structuredClone(run);
  const sameSeatRoute = selectRoute({
    snapshot: routingSlice.seatSnapshot,
    workload: routingSlice.workload,
    admissions: routingSlice.admissions,
    preferredSeatId: routingSlice.routeSelection.selectedSeatId,
  });
  changed.fallbackRouteSelection = sameSeatRoute;
  changed.fallbackWorkerLease = createWorkerLease({
    routeSelection: sameSeatRoute,
    generation: 2,
    issuedAtStep: run.fallbackWorkerLease.issuedAtStep,
    leaseDurationSteps: run.fallbackWorkerLease.leaseDurationSteps,
  });
  assertCode(() => validateFabricRun(changed), 'FABRIC_RUN_FALLBACK_SEAT_INVALID');
});

test('wrong verifier identity creates an explicit completion refusal', async () => {
  const { routingSlice, bundle } = await fixtures();
  const loss = createPrimarySeatLossEvidence({ routingSlice });
  const { fallbackRouteSelection, fallbackWorkerLease } = createFallbackRouteAndLease({
    routingSlice,
    lossEvidence: loss,
  });
  const candidate = createCompletionCandidate({
    routingSlice,
    routeSelection: fallbackRouteSelection,
    workerLease: fallbackWorkerLease,
    submissionId: 'SYN-CANDIDATE-WRONG-VERIFIER-TEST',
    output: bundle.taskReceipt.output,
    submittedAtStep: 24,
    completedAtStep: 24,
    verifierIdentity: 'SYN-VERIFIER-WRONG-99',
  });
  const refusal = createCompletionRefusal({
    candidate,
    routeSelection: fallbackRouteSelection,
    workerLease: fallbackWorkerLease,
    activeGeneration: fallbackWorkerLease.generation,
    acceptedCandidateId: null,
    evaluatedAtStep: candidate.completedAtStep,
  });
  assert.equal(refusal.reasons.includes('INDEPENDENT_VERIFIER_MISMATCH'), true);
  assert.equal(validateCompletionRefusal(refusal, {
    candidate,
    routeSelection: fallbackRouteSelection,
    workerLease: fallbackWorkerLease,
    activeGeneration: fallbackWorkerLease.generation,
    acceptedCandidateId: null,
  }), refusal);
});

test('verifier evidence is route-bound and non-authoritative', async () => {
  const { run } = await campaignFixture();
  const evidence = createIndependentVerifierEvidence({
    routeSelection: run.fallbackRouteSelection,
    outputDigest: run.acceptedOutputDigest,
  });
  assert.equal(validateIndependentVerifierEvidence(evidence, run.fallbackRouteSelection), evidence);
  assert.equal(evidence.authority, false);
  assert.equal(evidence.verificationState, 'pass');
});

test('removing the optional seat does not disturb resident-floor continuity', async () => {
  const { registry, fabricProfile, bundle } = await fixtures();
  registry.seats = registry.seats.filter((row) => row.role !== 'optional');
  const routingSlice = runFabricRoutingSlice({ bundle, fabricProfile, registry });
  const run = runFabricExecutionCampaign({ bundle, routingSlice, fabricProfile, registry });
  assert.equal(run.acceptedCompletionCount, 1);
  assert.equal(run.optionalSeatRequiredForContinuity, false);
  assert.equal(run.candidates.find((row) => row.candidateId === run.acceptedCandidateId).seatId, 'SYN-SEAT-FALLBACK-B');
});

test('projection tampering breaks its content identity', async () => {
  const { run } = await campaignFixture();
  const projection = buildFabricExecutionProjection(run);
  projection.jobCustodyPreserved = false;
  assertCode(
    () => validateFabricExecutionProjection(projection),
    'FABRIC_EXECUTION_PROJECTION_CLAIM_INVALID',
  );
});

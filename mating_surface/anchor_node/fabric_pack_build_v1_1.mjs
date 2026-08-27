import { writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import {
  FILES,
  OBSERVATION_PATH,
  PACK_FILE_NAMES,
  PROFILE_PATH,
  REGISTRY_PATH,
  digest,
  manifestEntry,
  readJson,
  requireCondition,
  writeJson,
} from './fabric_pack_common_v1_1.mjs';
import { bindSourceCommit } from './fabric_pack_checkout_v1_1.mjs';
import {
  buildSourceClosure,
  preparePackOutputDirectory,
} from './fabric_pack_storage_v1_1.mjs';
import {
  runVerticalSlice,
  verifyVerticalSlice,
} from './vertical_slice.mjs';
import {
  runFabricRoutingSlice,
  verifyFabricRoutingSlice,
} from './fabric_runtime.mjs';
import {
  buildFabricExecutionProjection,
  renderFabricExecutionHtml,
  runFabricExecutionCampaign,
  verifyFabricRun,
} from './fabric_execution.mjs';

export function sixQuestionAnswer({ routingSlice, run, terminalVerification }) {
  const accepted = run.candidates.find((row) => row.candidateId === run.acceptedCandidateId);
  requireCondition(accepted !== undefined, 'SIX_QUESTION_ANSWER_INVALID', 'accepted candidate is absent');
  return {
    schema: 'spectra-anchor-node-estate-fabric-six-question-answer/1',
    questions: {
      whatRan: {
        answer:
          'One synthetic local-artifact reconstruction workload derived from the admitted MP01 task receipt. The primary route lost accessibility, work was reassigned under generation two, and one fallback completion was accepted.',
        workloadId: run.workloadId,
        fabricRunId: run.fabricRunId,
        executionEffect: run.executionEffect,
      },
      whereItRan: {
        answer:
          'The accepted completion ran on the selected invented fallback seat under the generation-two worker lease. The primary seat produced no accepted terminal result.',
        acceptedSeatId: accepted.seatId,
        routeSelectionId: accepted.routeSelectionId,
        leaseId: accepted.leaseId,
        leaseGeneration: accepted.leaseGeneration,
      },
      whyTheSeatQualified: {
        answer:
          'The fallback seat appeared in the exact seat snapshot, passed every seat-specific admission check, satisfied independent memory fit, and matched the required runtime, adapter, model or executable, workload class, and verifier.',
        seatSnapshotId: routingSlice.seatSnapshot.snapshotId,
        admissionId: routingSlice.admissions.find((row) => row.seatId === accepted.seatId)?.admissionId ?? null,
        routeSelectionId: run.fallbackRouteSelection.routeSelectionId,
        memoryAggregationUsed: false,
      },
      whatProvedCompletion: {
        answer:
          'The content-addressed completion candidate matched the expected output digest, the route-bound independent verifier returned pass, exactly one terminal disposition accepted it, and detached terminal verification replayed the full candidate and refusal denominator.',
        candidateId: accepted.candidateId,
        outputDigest: accepted.outputDigest,
        verifierEvidenceId: accepted.verificationEvidence.verificationEvidenceId,
        terminalVerificationId: terminalVerification.verificationId,
      },
      whatWasRefused: {
        answer:
          'The ledger retains the stale primary completion, wrong-output fallback candidate, unverifiable fallback candidate, expired primary completion, and post-terminal duplicate completion as explicit refusals.',
        refusalIds: run.refusals.map((row) => row.refusalId),
        reasons: [...new Set(run.refusals.flatMap((row) => row.reasons))],
      },
      whatRemainsUnresolved: {
        answer:
          'No physical Estate host, representative operator, field network, operational C2 environment, production Lattice membrane, targeting chain, engagement path, effector, or weapons capability has been qualified by this pack.',
        physicalEstateQualified: false,
        representativeOperatorQualified: false,
        productionLatticeQualified: false,
        safeNext:
          'Prepare a separately authorized private Tier-3 physical-flight packet that binds real seat evidence by digest without importing private evidence bodies into the public repository.',
      },
    },
    status: 'complete_for_synthetic_terminal_qualification',
    authority: 'none',
    claimBoundary:
      'This answer supports cold-successor reconstruction of one synthetic terminal fabric campaign. It is not physical, representative-operator, field, operational-C2, mission, command, targeting, engagement, effector, or weapons authority.',
  };
}

async function loadInputs() {
  const [profile, registry, observations] = await Promise.all([
    readJson(PROFILE_PATH),
    readJson(REGISTRY_PATH),
    readJson(OBSERVATION_PATH),
  ]);
  return { profile, registry, observations };
}

export async function buildFabricExecutionColdSuccessorPack(outDir, { sourceCommit }) {
  const boundCommit = await bindSourceCommit(sourceCommit);
  const [sourceClosure, inputs] = await Promise.all([
    buildSourceClosure(boundCommit),
    loadInputs(),
  ]);
  const resolvedOutDir = await preparePackOutputDirectory(outDir);
  const { profile, registry, observations } = inputs;
  const verticalSlice = runVerticalSlice(observations);
  verifyVerticalSlice(verticalSlice);
  const routingSlice = runFabricRoutingSlice({
    bundle: verticalSlice,
    fabricProfile: profile,
    registry,
  });
  const routingVerification = verifyFabricRoutingSlice(routingSlice, {
    bundle: verticalSlice,
    fabricProfile: profile,
    registry,
  });
  const fabricRun = runFabricExecutionCampaign({
    bundle: verticalSlice,
    routingSlice,
    fabricProfile: profile,
    registry,
  });
  const terminalVerification = verifyFabricRun(fabricRun, {
    bundle: verticalSlice,
    routingSlice,
    fabricProfile: profile,
    registry,
  });
  const projection = buildFabricExecutionProjection(fabricRun);
  const reviewHtml = renderFabricExecutionHtml(projection);
  const sixQuestions = sixQuestionAnswer({
    routingSlice,
    run: fabricRun,
    terminalVerification,
  });

  const objects = new Map([
    [FILES.sourceClosure, sourceClosure],
    [FILES.profile, profile],
    [FILES.registry, registry],
    [FILES.observations, observations],
    [FILES.verticalSlice, verticalSlice],
    [FILES.routingSlice, routingSlice],
    [FILES.routingVerification, routingVerification],
    [FILES.fabricRun, fabricRun],
    [FILES.terminalVerification, terminalVerification],
    [FILES.projection, projection],
    [FILES.sixQuestions, sixQuestions],
  ]);
  for (const [fileName, value] of objects) {
    await writeJson(join(resolvedOutDir, fileName), value);
  }
  await writeFile(join(resolvedOutDir, FILES.reviewHtml), reviewHtml, 'utf8');

  const entries = [];
  for (const fileName of PACK_FILE_NAMES) entries.push(await manifestEntry(resolvedOutDir, fileName));
  const manifestBody = {
    schema: 'spectra-anchor-node-estate-fabric-terminal-pack-manifest/1',
    sourceRepository: 'BigBirdReturns/ai-execution-audit',
    sourceCommit: boundCommit,
    sourceClosureId: sourceClosure.sourceClosureId,
    classification: 'invented_unclassified_synthetic_only',
    sourceRoutingSliceId: routingSlice.routingSliceId,
    fabricRunId: fabricRun.fabricRunId,
    terminalVerificationId: terminalVerification.verificationId,
    files: entries,
    fileCount: entries.length,
    candidateCount: fabricRun.candidates.length,
    refusalCount: fabricRun.refusals.length,
    acceptedCompletionCount: fabricRun.acceptedCompletionCount,
    canonicalStateUnchanged: fabricRun.canonicalStateUnchanged,
    jobCustodyPreserved: fabricRun.jobCustodyPreserved,
    externalServiceCalls: 0,
    operationalCredentials: 0,
    physicalEvidenceBodies: 0,
    authority: 'none',
    claimBoundary:
      'Checkout-bound and source-byte-closed cold-successor extension for one synthetic Estate fabric terminal campaign. It does not establish physical, operator, field, operational-C2, production-Lattice, mission, command, targeting, engagement, effector, or weapons authority.',
  };
  const manifest = {
    ...manifestBody,
    packId: digest('estatefabricterminalpack1', manifestBody),
  };
  await writeJson(join(resolvedOutDir, 'manifest.json'), manifest);
  return manifest;
}

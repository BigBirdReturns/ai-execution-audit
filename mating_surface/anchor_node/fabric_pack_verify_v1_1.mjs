import { readFile } from 'node:fs/promises';
import { join, resolve } from 'node:path';
import { canonicalJson } from '../semantic/authority_sidecar.mjs';
import {
  FILES,
  PACK_FILE_NAMES,
  digest,
  digestBytes,
  readJson,
  requireCondition,
  validateSourceCommitSyntax,
} from './fabric_pack_common_v1_1.mjs';
import { bindSourceCommit } from './fabric_pack_checkout_v1_1.mjs';
import {
  validateOutputMarker,
  verifySourceClosure,
} from './fabric_pack_storage_v1_1.mjs';
import { sixQuestionAnswer } from './fabric_pack_build_v1_1.mjs';
import {
  runVerticalSlice,
  verifyVerticalSlice,
} from './vertical_slice.mjs';
import {
  runFabricRoutingSlice,
  verifyFabricRoutingSlice,
} from './fabric_runtime.mjs';
import {
  renderFabricExecutionHtml,
  runFabricExecutionCampaign,
  validateFabricExecutionProjection,
  verifyFabricRun,
} from './fabric_execution.mjs';

function validateManifestShape(manifest) {
  const expected = [
    'schema',
    'packId',
    'sourceRepository',
    'sourceCommit',
    'sourceClosureId',
    'classification',
    'sourceRoutingSliceId',
    'fabricRunId',
    'terminalVerificationId',
    'files',
    'fileCount',
    'candidateCount',
    'refusalCount',
    'acceptedCompletionCount',
    'canonicalStateUnchanged',
    'jobCustodyPreserved',
    'externalServiceCalls',
    'operationalCredentials',
    'physicalEvidenceBodies',
    'authority',
    'claimBoundary',
  ];
  requireCondition(
    manifest !== null && typeof manifest === 'object' && !Array.isArray(manifest),
    'PACK_MANIFEST_INVALID',
    'manifest must be an object',
  );
  requireCondition(
    canonicalJson(Object.keys(manifest).sort()) === canonicalJson(expected.sort()),
    'PACK_MANIFEST_INVALID',
    'manifest fields differ',
  );
  requireCondition(
    manifest.schema === 'spectra-anchor-node-estate-fabric-terminal-pack-manifest/1',
    'PACK_MANIFEST_SCHEMA_INVALID',
    'manifest schema differs',
  );
  validateSourceCommitSyntax(manifest.sourceCommit);
  requireCondition(manifest.sourceRepository === 'BigBirdReturns/ai-execution-audit', 'PACK_MANIFEST_INVALID', 'source repository differs');
  requireCondition(manifest.classification === 'invented_unclassified_synthetic_only', 'PACK_MANIFEST_INVALID', 'classification differs');
  requireCondition(Array.isArray(manifest.files) && manifest.files.length === PACK_FILE_NAMES.length && manifest.fileCount === manifest.files.length, 'PACK_FILE_DENOMINATOR_INVALID', 'manifest file denominator differs');
  requireCondition(canonicalJson(manifest.files.map((row) => row.path)) === canonicalJson(PACK_FILE_NAMES), 'PACK_FILE_DENOMINATOR_INVALID', 'manifest file order or names differ');
  requireCondition(manifest.acceptedCompletionCount === 1 && manifest.canonicalStateUnchanged === true && manifest.jobCustodyPreserved === true, 'PACK_TERMINAL_STATE_INVALID', 'manifest terminal state differs');
  requireCondition(manifest.externalServiceCalls === 0 && manifest.operationalCredentials === 0 && manifest.physicalEvidenceBodies === 0 && manifest.authority === 'none', 'PACK_CLAIM_INVALID', 'manifest widens its claim');
  const body = structuredClone(manifest);
  delete body.packId;
  requireCondition(manifest.packId === digest('estatefabricterminalpack1', body), 'PACK_MANIFEST_ID_INVALID', 'pack identity differs');
  return manifest;
}

async function verifyManifestFiles(outDir, manifest) {
  for (const row of manifest.files) {
    requireCondition(
      row !== null &&
        typeof row === 'object' &&
        !Array.isArray(row) &&
        canonicalJson(Object.keys(row).sort()) === canonicalJson(['bytes', 'path', 'sha256']),
      'PACK_FILE_ENTRY_INVALID',
      'manifest file entry differs',
    );
    const bytes = await readFile(join(outDir, row.path));
    requireCondition(bytes.length === row.bytes, 'PACK_FILE_SIZE_MISMATCH', `file size differs: ${row.path}`);
    requireCondition(digestBytes(bytes) === row.sha256, 'PACK_FILE_HASH_MISMATCH', `file hash differs: ${row.path}`);
  }
}

export async function verifyFabricExecutionColdSuccessorPack(outDir) {
  const resolvedOutDir = resolve(outDir);
  const manifest = await readJson(join(resolvedOutDir, 'manifest.json'));
  validateManifestShape(manifest);
  await bindSourceCommit(manifest.sourceCommit);
  await verifyManifestFiles(resolvedOutDir, manifest);
  const [sourceClosure, profile, registry, observations, verticalSlice, routingSlice, routingVerification, fabricRun, terminalVerification, projection, sixQuestions, reviewHtml] = await Promise.all([
    readJson(join(resolvedOutDir, FILES.sourceClosure)),
    readJson(join(resolvedOutDir, FILES.profile)),
    readJson(join(resolvedOutDir, FILES.registry)),
    readJson(join(resolvedOutDir, FILES.observations)),
    readJson(join(resolvedOutDir, FILES.verticalSlice)),
    readJson(join(resolvedOutDir, FILES.routingSlice)),
    readJson(join(resolvedOutDir, FILES.routingVerification)),
    readJson(join(resolvedOutDir, FILES.fabricRun)),
    readJson(join(resolvedOutDir, FILES.terminalVerification)),
    readJson(join(resolvedOutDir, FILES.projection)),
    readJson(join(resolvedOutDir, FILES.sixQuestions)),
    readFile(join(resolvedOutDir, FILES.reviewHtml), 'utf8'),
  ]);
  validateOutputMarker(await readJson(join(resolvedOutDir, FILES.outputMarker)));
  await verifySourceClosure(sourceClosure);
  requireCondition(sourceClosure.sourceClosureId === manifest.sourceClosureId, 'PACK_SOURCE_CLOSURE_BINDING_INVALID', 'manifest names another source closure');

  const expectedVertical = runVerticalSlice(observations);
  requireCondition(canonicalJson(verticalSlice) === canonicalJson(expectedVertical), 'PACK_VERTICAL_REPLAY_MISMATCH', 'vertical slice differs from source replay');
  const replayVerification = verifyVerticalSlice(verticalSlice);
  requireCondition(replayVerification.status === 'PASS', 'PACK_VERTICAL_REPLAY_MISMATCH', 'vertical slice detached replay failed');
  const expectedRouting = runFabricRoutingSlice({
    bundle: verticalSlice,
    fabricProfile: profile,
    registry,
  });
  requireCondition(canonicalJson(routingSlice) === canonicalJson(expectedRouting), 'PACK_ROUTING_REPLAY_MISMATCH', 'routing slice differs from source replay');
  const replayedRoutingVerification = verifyFabricRoutingSlice(routingSlice, {
    bundle: verticalSlice,
    fabricProfile: profile,
    registry,
  });
  requireCondition(canonicalJson(routingVerification) === canonicalJson(replayedRoutingVerification), 'PACK_ROUTING_VERIFICATION_MISMATCH', 'routing verification differs');
  const replayedRun = runFabricExecutionCampaign({
    bundle: verticalSlice,
    routingSlice,
    fabricProfile: profile,
    registry,
  });
  requireCondition(canonicalJson(fabricRun) === canonicalJson(replayedRun), 'PACK_FABRIC_RUN_REPLAY_MISMATCH', 'fabric run differs from source replay');
  const replayedTerminalVerification = verifyFabricRun(fabricRun, {
    bundle: verticalSlice,
    routingSlice,
    fabricProfile: profile,
    registry,
  });
  requireCondition(canonicalJson(terminalVerification) === canonicalJson(replayedTerminalVerification), 'PACK_TERMINAL_VERIFICATION_MISMATCH', 'terminal verification differs');
  validateFabricExecutionProjection(projection, fabricRun);
  requireCondition(reviewHtml === renderFabricExecutionHtml(projection), 'PACK_REVIEW_SURFACE_MISMATCH', 'receipt-only review surface differs');
  requireCondition(canonicalJson(sixQuestions) === canonicalJson(sixQuestionAnswer({ routingSlice, run: fabricRun, terminalVerification })), 'PACK_SIX_QUESTION_MISMATCH', 'six-question answer differs');
  requireCondition(manifest.sourceRoutingSliceId === routingSlice.routingSliceId && manifest.fabricRunId === fabricRun.fabricRunId && manifest.terminalVerificationId === terminalVerification.verificationId, 'PACK_OBJECT_BINDING_INVALID', 'manifest object identities differ');
  requireCondition(manifest.candidateCount === fabricRun.candidates.length && manifest.refusalCount === fabricRun.refusals.length && manifest.acceptedCompletionCount === fabricRun.acceptedCompletionCount, 'PACK_TERMINAL_STATE_INVALID', 'manifest terminal counts differ');

  const body = {
    schema: 'spectra-anchor-node-estate-fabric-terminal-pack-verification/1',
    packId: manifest.packId,
    sourceCommit: manifest.sourceCommit,
    sourceClosureId: sourceClosure.sourceClosureId,
    status: 'PASS',
    fileCount: manifest.fileCount,
    candidateCount: manifest.candidateCount,
    refusalCount: manifest.refusalCount,
    acceptedCompletionCount: manifest.acceptedCompletionCount,
    sixQuestionStatus: sixQuestions.status,
    checkoutCommitBound: true,
    sourceClosureVerified: true,
    deterministicReconstruction: true,
    receiptOnlyReviewSurface: true,
    canonicalStateUnchanged: true,
    jobCustodyPreserved: true,
    externalServiceCalls: 0,
    operationalCredentials: 0,
    physicalEvidenceBodies: 0,
    authority: 'none',
    claimBoundary:
      'Detached verification of one checkout-bound and source-byte-closed synthetic Estate fabric terminal cold-successor pack. It grants no physical, operator, field, operational-C2, production-Lattice, mission, command, targeting, engagement, effector, or weapons authority.',
  };
  return {
    ...body,
    verificationId: digest('estatefabricterminalpackverification1', body),
  };
}

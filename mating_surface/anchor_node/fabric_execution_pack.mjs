import { createHash } from 'node:crypto';
import { mkdir, readFile, rm, writeFile } from 'node:fs/promises';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { canonicalJson } from '../semantic/authority_sidecar.mjs';
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
  validateFabricExecutionProjection,
  verifyFabricRun,
} from './fabric_execution.mjs';

const HERE = dirname(fileURLToPath(import.meta.url));
const PROFILE_PATH = resolve(HERE, 'fabric-profile-01.json');
const REGISTRY_PATH = resolve(HERE, 'fixtures/mp01-invented-seat-registry.json');
const OBSERVATION_PATH = resolve(HERE, 'fixtures/mp01-observation-package.json');

const FILES = Object.freeze({
  profile: 'fabric-profile.json',
  registry: 'invented-seat-registry.json',
  observations: 'synthetic-observations.json',
  verticalSlice: 'vertical-slice.json',
  routingSlice: 'routing-slice.json',
  routingVerification: 'routing-verification.json',
  fabricRun: 'fabric-run.json',
  terminalVerification: 'terminal-verification.json',
  projection: 'receipt-only-projection.json',
  reviewHtml: 'receipt-only-review.html',
  sixQuestions: 'six-question-answer.json',
});
const PACK_FILE_NAMES = Object.values(FILES);

export class FabricExecutionPackError extends Error {
  constructor(code, message) {
    super(message);
    this.name = 'FabricExecutionPackError';
    this.code = code;
  }
}

function requireCondition(condition, code, message) {
  if (!condition) throw new FabricExecutionPackError(code, message);
}

function digest(prefix, value) {
  return `${prefix}_${createHash('sha256').update(canonicalJson(value), 'utf8').digest('hex')}`;
}

function digestBytes(bytes) {
  return createHash('sha256').update(bytes).digest('hex');
}

function canonicalPretty(value) {
  return `${JSON.stringify(value, null, 2)}\n`;
}

async function readJson(path) {
  return JSON.parse(await readFile(path, 'utf8'));
}

async function writeJson(path, value) {
  const content = canonicalPretty(value);
  await writeFile(path, content, 'utf8');
  return Buffer.from(content, 'utf8');
}

function validateSourceCommit(sourceCommit) {
  requireCondition(
    /^[0-9a-f]{40}$/.test(sourceCommit),
    'SOURCE_COMMIT_INVALID',
    'source commit must be a full lowercase Git SHA-1',
  );
  return sourceCommit;
}

function sixQuestionAnswer({ routingSlice, run, terminalVerification }) {
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

async function manifestEntry(outDir, fileName) {
  const bytes = await readFile(join(outDir, fileName));
  return {
    path: fileName,
    bytes: bytes.length,
    sha256: digestBytes(bytes),
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
  validateSourceCommit(sourceCommit);
  await rm(outDir, { recursive: true, force: true });
  await mkdir(outDir, { recursive: true });
  const { profile, registry, observations } = await loadInputs();
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
    await writeJson(join(outDir, fileName), value);
  }
  await writeFile(join(outDir, FILES.reviewHtml), reviewHtml, 'utf8');

  const entries = [];
  for (const fileName of PACK_FILE_NAMES) entries.push(await manifestEntry(outDir, fileName));
  const manifestBody = {
    schema: 'spectra-anchor-node-estate-fabric-terminal-pack-manifest/1',
    sourceRepository: 'BigBirdReturns/ai-execution-audit',
    sourceCommit,
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
      'Source-pinned cold-successor extension for one synthetic Estate fabric terminal campaign. It does not establish physical, operator, field, operational-C2, production-Lattice, mission, command, targeting, engagement, effector, or weapons authority.',
  };
  const manifest = {
    ...manifestBody,
    packId: digest('estatefabricterminalpack1', manifestBody),
  };
  await writeJson(join(outDir, 'manifest.json'), manifest);
  return manifest;
}

function validateManifestShape(manifest) {
  const expected = [
    'schema',
    'packId',
    'sourceRepository',
    'sourceCommit',
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
  validateSourceCommit(manifest.sourceCommit);
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
  const manifest = await readJson(join(outDir, 'manifest.json'));
  validateManifestShape(manifest);
  await verifyManifestFiles(outDir, manifest);
  const [profile, registry, observations, verticalSlice, routingSlice, routingVerification, fabricRun, terminalVerification, projection, sixQuestions, reviewHtml] = await Promise.all([
    readJson(join(outDir, FILES.profile)),
    readJson(join(outDir, FILES.registry)),
    readJson(join(outDir, FILES.observations)),
    readJson(join(outDir, FILES.verticalSlice)),
    readJson(join(outDir, FILES.routingSlice)),
    readJson(join(outDir, FILES.routingVerification)),
    readJson(join(outDir, FILES.fabricRun)),
    readJson(join(outDir, FILES.terminalVerification)),
    readJson(join(outDir, FILES.projection)),
    readJson(join(outDir, FILES.sixQuestions)),
    readFile(join(outDir, FILES.reviewHtml), 'utf8'),
  ]);

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
    status: 'PASS',
    fileCount: manifest.fileCount,
    candidateCount: manifest.candidateCount,
    refusalCount: manifest.refusalCount,
    acceptedCompletionCount: manifest.acceptedCompletionCount,
    sixQuestionStatus: sixQuestions.status,
    deterministicReconstruction: true,
    receiptOnlyReviewSurface: true,
    canonicalStateUnchanged: true,
    jobCustodyPreserved: true,
    externalServiceCalls: 0,
    operationalCredentials: 0,
    physicalEvidenceBodies: 0,
    authority: 'none',
    claimBoundary:
      'Detached verification of one source-pinned synthetic Estate fabric terminal cold-successor pack. It grants no physical, operator, field, operational-C2, production-Lattice, mission, command, targeting, engagement, effector, or weapons authority.',
  };
  return {
    ...body,
    verificationId: digest('estatefabricterminalpackverification1', body),
  };
}

async function main(argv) {
  const command = argv[2];
  if (command === 'build') {
    const outDir = resolve(argv[3]);
    const manifest = await buildFabricExecutionColdSuccessorPack(outDir, {
      sourceCommit: argv[4],
    });
    process.stdout.write(`${JSON.stringify({ status: 'PASS', packId: manifest.packId, outDir }, null, 2)}\n`);
    return;
  }
  if (command === 'verify') {
    const outDir = resolve(argv[3]);
    const outputPath = resolve(argv[4]);
    const verification = await verifyFabricExecutionColdSuccessorPack(outDir);
    await writeJson(outputPath, verification);
    process.stdout.write(`${JSON.stringify(verification, null, 2)}\n`);
    return;
  }
  throw new FabricExecutionPackError(
    'COMMAND_INVALID',
    'usage: fabric_execution_pack.mjs build <out-dir> <source-commit> | verify <out-dir> <verification.json>',
  );
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  main(process.argv).catch((error) => {
    process.stderr.write(`${error instanceof FabricExecutionPackError ? error.code : 'UNEXPECTED_ERROR'}: ${error.message}\n`);
    process.exitCode = 1;
  });
}

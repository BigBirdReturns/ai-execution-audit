import { createHash } from 'node:crypto';
import { mkdir, readFile, rm, stat, writeFile } from 'node:fs/promises';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { canonicalJson } from '../semantic/authority_sidecar.mjs';
import { missionProfileReceipt, validateMissionProfile } from './validate_mission_profile.mjs';
import { runVerticalSlice, verifyVerticalSlice } from './vertical_slice.mjs';
import {
  projectVerticalSliceToLattice,
  reconcileInboundCandidate,
  verifyLatticeRemoval,
} from './lattice_membrane.mjs';
import {
  runFaultWorkerCampaign,
  verifyFaultWorkerCampaign,
} from './fault_worker_campaign.mjs';
import {
  runHostileRecoveryCampaign,
  verifyHostileRecoveryCampaign,
} from './hostile_recovery_campaign.mjs';

const HERE = dirname(fileURLToPath(import.meta.url));
const PROFILE_PATH = resolve(HERE, 'mission-profile-01.json');
const OBSERVATION_PATH = resolve(HERE, 'fixtures/mp01-observation-package.json');
const INBOUND_PATH = resolve(HERE, 'fixtures/mp01-lattice-inbound-candidate.json');

const FILES = Object.freeze({
  profile: 'mission-profile.json',
  profileValidation: 'mission-profile-validation.json',
  observations: 'synthetic-observations.json',
  verticalSlice: 'vertical-slice.json',
  replay: 'detached-replay-verification.json',
  latticeEnvelope: 'lattice-envelope.json',
  latticeRemoval: 'lattice-removal-verification.json',
  latticeInbound: 'lattice-inbound-candidate.json',
  latticeReconciliation: 'lattice-reconciliation.json',
  faultCampaign: 'fault-worker-campaign.json',
  faultVerification: 'fault-worker-verification.json',
  hostileCampaign: 'hostile-recovery-campaign.json',
  hostileVerification: 'hostile-recovery-verification.json',
  afterActionHtml: 'after-action.html',
  fiveQuestions: 'five-question-answer.json',
});
const PACK_FILE_NAMES = Object.values(FILES);

export class ColdSuccessorPackError extends Error {
  constructor(code, message) {
    super(message);
    this.name = 'ColdSuccessorPackError';
    this.code = code;
  }
}

function requireCondition(condition, code, message) {
  if (!condition) throw new ColdSuccessorPackError(code, message);
}

function digestBytes(bytes) {
  return createHash('sha256').update(bytes).digest('hex');
}

function digest(prefix, value) {
  return `${prefix}_${createHash('sha256').update(canonicalJson(value), 'utf8').digest('hex')}`;
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

function fiveQuestionAnswer({
  profile,
  bundle,
  replay,
  latticeRemoval,
  latticeReconciliation,
  faultCampaign,
  faultVerification,
  hostileCampaign,
  hostileVerification,
}) {
  const openObligations = [
    ...bundle.missionStateAfter.obligations
      .filter((row) => row.status === 'open')
      .map((row) => ({ obligationId: row.obligationId, type: row.obligationType })),
    {
      obligationId: latticeReconciliation.obligation.obligationId,
      type: latticeReconciliation.obligation.obligationType,
    },
    {
      obligationId: hostileCampaign.authorityConflict.reconciliation.reconciliationId,
      type: 'reconcile_conflicting_returning_authority',
    },
  ];
  return {
    schema: 'spectra-anchor-node-cold-successor-five-question-answer/1',
    profileId: profile.profileId,
    questions: {
      whatExists: {
        answer:
          'One invented synthetic Mission Profile 01 state, one bounded model proposal, one denied-communications authority decision, one admission ticket, one completed local-artifact-only task, one closed transport/worker fault campaign, and one hostile-recovery campaign.',
        objectIds: [
          bundle.missionStateAfter.missionStateId,
          bundle.modelProposal.proposalId,
          bundle.authorityDecision.decisionId,
          bundle.admissionTicket.ticketId,
          bundle.taskReceipt.taskReceiptId,
          faultCampaign.campaignId,
          hostileCampaign.campaignId,
        ],
      },
      whatProvesIt: {
        answer:
          'Exact package hashes plus deterministic detached replay, Lattice-removal continuity, transport/worker verification, hostile-recovery verification, and the bounded task receipt.',
        receiptIds: [
          replay.verificationId,
          latticeRemoval.removalVerificationId,
          faultVerification.verificationId,
          hostileVerification.verificationId,
          bundle.taskReceipt.taskReceiptId,
        ],
      },
      whoMayAct: {
        answer:
          'Only the bounded local authority runtime admitted the synthetic task while a local operator was present. The model, task receipt, Lattice membrane, worker campaign, after-action surface, and cold-successor pack carry no authority.',
        localOperatorPresent: bundle.authorityDecision.localOperatorPresent,
        authorityDecisionId: bundle.authorityDecision.decisionId,
        admissionTicketId: bundle.admissionTicket.ticketId,
        modelAuthority: bundle.modelProposal.authority,
      },
      whatIsUnresolved: {
        answer:
          'The candidate shared-corridor relationship, the external Lattice-shaped candidate, and the conflicting returning-authority state require explicit human review.',
        obligations: openObligations,
      },
      whatIsSafeNext: {
        answer:
          'Inspect the cited synthetic observations and retained receipts, then record human dispositions for the open relationship, external candidate, and authority conflict. Do not perform any external, kinetic, command, targeting, engagement, or effector action.',
        allowedEffect: 'local_review_only',
      },
    },
    status: 'complete_for_synthetic_qualification',
    authority: 'none',
    claimBoundary:
      'This answer supports cold-successor inspection of one synthetic qualification pack. It is not field readiness, operational C2, command authority, targeting, engagement, effector, or weapons capability.',
  };
}

async function manifestEntry(outDir, fileName) {
  const path = join(outDir, fileName);
  const bytes = await readFile(path);
  return {
    path: fileName,
    bytes: bytes.length,
    sha256: digestBytes(bytes),
  };
}

function validateSourceCommit(sourceCommit) {
  requireCondition(
    /^[0-9a-f]{40}$/.test(sourceCommit),
    'SOURCE_COMMIT_INVALID',
    'source commit must be a full lowercase Git SHA-1',
  );
  return sourceCommit;
}

export async function buildColdSuccessorPack(outDir, { sourceCommit }) {
  validateSourceCommit(sourceCommit);
  await rm(outDir, { recursive: true, force: true });
  await mkdir(outDir, { recursive: true });

  const profile = await readJson(PROFILE_PATH);
  validateMissionProfile(profile);
  const profileValidation = missionProfileReceipt(profile);
  const observations = await readJson(OBSERVATION_PATH);
  const inbound = await readJson(INBOUND_PATH);
  const bundle = runVerticalSlice(observations);
  const replay = verifyVerticalSlice(bundle);
  const latticeEnvelope = projectVerticalSliceToLattice(bundle);
  const latticeRemoval = verifyLatticeRemoval(bundle, latticeEnvelope);
  const latticeReconciliation = reconcileInboundCandidate(bundle.missionStateAfter, inbound);
  const faultCampaign = runFaultWorkerCampaign(bundle);
  const faultVerification = verifyFaultWorkerCampaign(faultCampaign, bundle);
  const hostile = runHostileRecoveryCampaign(bundle, faultCampaign);
  const hostileVerification = verifyHostileRecoveryCampaign(
    hostile.campaign,
    hostile.html,
    bundle,
    faultCampaign,
  );
  const fiveQuestions = fiveQuestionAnswer({
    profile,
    bundle,
    replay,
    latticeRemoval,
    latticeReconciliation,
    faultCampaign,
    faultVerification,
    hostileCampaign: hostile.campaign,
    hostileVerification,
  });

  const objects = new Map([
    [FILES.profile, profile],
    [FILES.profileValidation, profileValidation],
    [FILES.observations, observations],
    [FILES.verticalSlice, bundle],
    [FILES.replay, replay],
    [FILES.latticeEnvelope, latticeEnvelope],
    [FILES.latticeRemoval, latticeRemoval],
    [FILES.latticeInbound, inbound],
    [FILES.latticeReconciliation, latticeReconciliation],
    [FILES.faultCampaign, faultCampaign],
    [FILES.faultVerification, faultVerification],
    [FILES.hostileCampaign, hostile.campaign],
    [FILES.hostileVerification, hostileVerification],
    [FILES.fiveQuestions, fiveQuestions],
  ]);
  for (const [fileName, value] of objects) {
    await writeJson(join(outDir, fileName), value);
  }
  await writeFile(join(outDir, FILES.afterActionHtml), hostile.html, 'utf8');

  const entries = [];
  for (const fileName of PACK_FILE_NAMES) {
    entries.push(await manifestEntry(outDir, fileName));
  }
  const manifestBody = {
    schema: 'spectra-anchor-node-cold-successor-pack-manifest/1',
    profileId: profile.profileId,
    sourceRepository: 'BigBirdReturns/ai-execution-audit',
    sourceCommit,
    classification: 'invented_unclassified_synthetic_only',
    files: entries,
    fileCount: entries.length,
    externalServiceCalls: 0,
    operationalCredentials: 0,
    latticeRequired: false,
    authority: 'none',
    claimBoundary:
      'This manifest binds one synthetic, source-pinned runnable qualification pack. It does not establish field readiness, target hardware qualification, production Lattice integration, operational C2, command authority, targeting, engagement, effector, or weapons capability.',
  };
  const manifest = {
    ...manifestBody,
    packId: digest('anchorcoldsuccessorpack1', manifestBody),
  };
  await writeJson(join(outDir, 'manifest.json'), manifest);
  return manifest;
}

function assertFiveQuestionAnswer(answer) {
  requireCondition(
    answer?.schema === 'spectra-anchor-node-cold-successor-five-question-answer/1',
    'FIVE_QUESTION_INVALID',
    'five-question answer schema is invalid',
  );
  const keys = Object.keys(answer.questions ?? {}).sort();
  requireCondition(
    canonicalJson(keys)
      === canonicalJson(
        ['whatExists', 'whatIsUnresolved', 'whatIsSafeNext', 'whatProvesIt', 'whoMayAct'].sort(),
      ),
    'FIVE_QUESTION_INVALID',
    'five-question answer is incomplete',
  );
  requireCondition(
    answer.questions.whoMayAct.modelAuthority === false,
    'FIVE_QUESTION_INVALID',
    'model authority is not false',
  );
  requireCondition(
    answer.questions.whatIsSafeNext.allowedEffect === 'local_review_only',
    'FIVE_QUESTION_INVALID',
    'safe next effect is too broad',
  );
  requireCondition(
    Array.isArray(answer.questions.whatIsUnresolved.obligations)
      && answer.questions.whatIsUnresolved.obligations.length >= 3,
    'FIVE_QUESTION_INVALID',
    'unresolved obligations are incomplete',
  );
  requireCondition(
    answer.questions.whatProvesIt.receiptIds.length >= 5,
    'FIVE_QUESTION_INVALID',
    'proof receipt denominator is incomplete',
  );
  requireCondition(
    answer.authority === 'none',
    'FIVE_QUESTION_INVALID',
    'five-question answer cannot grant authority',
  );
}

export async function verifyColdSuccessorPack(outDir) {
  const manifest = await readJson(join(outDir, 'manifest.json'));
  requireCondition(
    manifest.schema === 'spectra-anchor-node-cold-successor-pack-manifest/1',
    'MANIFEST_INVALID',
    'manifest schema is invalid',
  );
  validateSourceCommit(manifest.sourceCommit);
  requireCondition(
    manifest.classification === 'invented_unclassified_synthetic_only',
    'MANIFEST_INVALID',
    'manifest classification is invalid',
  );
  requireCondition(
    manifest.externalServiceCalls === 0,
    'MANIFEST_INVALID',
    'manifest records external service calls',
  );
  requireCondition(
    manifest.operationalCredentials === 0,
    'MANIFEST_INVALID',
    'manifest records operational credentials',
  );
  requireCondition(
    manifest.latticeRequired === false,
    'MANIFEST_INVALID',
    'manifest makes Lattice required',
  );
  requireCondition(
    manifest.authority === 'none',
    'MANIFEST_INVALID',
    'manifest cannot grant authority',
  );
  requireCondition(
    Array.isArray(manifest.files) && manifest.files.length === PACK_FILE_NAMES.length,
    'MANIFEST_INVALID',
    'manifest file denominator differs',
  );
  requireCondition(
    manifest.fileCount === PACK_FILE_NAMES.length,
    'MANIFEST_INVALID',
    'manifest file count differs',
  );
  requireCondition(
    canonicalJson(manifest.files.map((row) => row.path)) === canonicalJson(PACK_FILE_NAMES),
    'MANIFEST_INVALID',
    'manifest path order or denominator differs',
  );

  for (const row of manifest.files) {
    const path = join(outDir, row.path);
    const fileStat = await stat(path).catch(() => null);
    requireCondition(fileStat?.isFile(), 'PACK_FILE_MISSING', `pack file missing: ${row.path}`);
    const bytes = await readFile(path);
    requireCondition(
      bytes.length === row.bytes,
      'PACK_FILE_SIZE_MISMATCH',
      `pack file size differs: ${row.path}`,
    );
    requireCondition(
      digestBytes(bytes) === row.sha256,
      'PACK_FILE_HASH_MISMATCH',
      `pack file hash differs: ${row.path}`,
    );
  }
  const manifestBody = structuredClone(manifest);
  delete manifestBody.packId;
  requireCondition(
    manifest.packId === digest('anchorcoldsuccessorpack1', manifestBody),
    'PACK_ID_INVALID',
    'pack identity is invalid',
  );

  const profile = await readJson(join(outDir, FILES.profile));
  validateMissionProfile(profile);
  const observations = await readJson(join(outDir, FILES.observations));
  const storedBundle = await readJson(join(outDir, FILES.verticalSlice));
  const replayedBundle = runVerticalSlice(observations);
  requireCondition(
    canonicalJson(storedBundle) === canonicalJson(replayedBundle),
    'PACK_REPLAY_MISMATCH',
    'vertical slice does not reconstruct',
  );
  const storedReplay = await readJson(join(outDir, FILES.replay));
  requireCondition(
    canonicalJson(storedReplay) === canonicalJson(verifyVerticalSlice(storedBundle)),
    'PACK_REPLAY_MISMATCH',
    'detached replay receipt does not reconstruct',
  );
  const storedLatticeEnvelope = await readJson(join(outDir, FILES.latticeEnvelope));
  requireCondition(
    canonicalJson(storedLatticeEnvelope)
      === canonicalJson(projectVerticalSliceToLattice(storedBundle)),
    'PACK_REPLAY_MISMATCH',
    'Lattice projection does not reconstruct',
  );
  const storedLatticeRemoval = await readJson(join(outDir, FILES.latticeRemoval));
  requireCondition(
    canonicalJson(storedLatticeRemoval)
      === canonicalJson(verifyLatticeRemoval(storedBundle, storedLatticeEnvelope)),
    'PACK_REPLAY_MISMATCH',
    'Lattice removal receipt does not reconstruct',
  );
  const inbound = await readJson(join(outDir, FILES.latticeInbound));
  const storedLatticeReconciliation = await readJson(
    join(outDir, FILES.latticeReconciliation),
  );
  requireCondition(
    canonicalJson(storedLatticeReconciliation)
      === canonicalJson(reconcileInboundCandidate(storedBundle.missionStateAfter, inbound)),
    'PACK_REPLAY_MISMATCH',
    'Lattice reconciliation receipt does not reconstruct',
  );
  const storedFaultCampaign = await readJson(join(outDir, FILES.faultCampaign));
  const replayedFaultCampaign = runFaultWorkerCampaign(storedBundle);
  requireCondition(
    canonicalJson(storedFaultCampaign) === canonicalJson(replayedFaultCampaign),
    'PACK_REPLAY_MISMATCH',
    'fault-worker campaign does not reconstruct',
  );
  const storedFaultVerification = await readJson(join(outDir, FILES.faultVerification));
  requireCondition(
    canonicalJson(storedFaultVerification)
      === canonicalJson(verifyFaultWorkerCampaign(storedFaultCampaign, storedBundle)),
    'PACK_REPLAY_MISMATCH',
    'fault-worker verification does not reconstruct',
  );
  const storedHostileCampaign = await readJson(join(outDir, FILES.hostileCampaign));
  const storedAfterActionHtml = await readFile(join(outDir, FILES.afterActionHtml), 'utf8');
  const replayedHostile = runHostileRecoveryCampaign(storedBundle, storedFaultCampaign);
  requireCondition(
    canonicalJson(storedHostileCampaign) === canonicalJson(replayedHostile.campaign),
    'PACK_REPLAY_MISMATCH',
    'hostile-recovery campaign does not reconstruct',
  );
  requireCondition(
    storedAfterActionHtml === replayedHostile.html,
    'PACK_REPLAY_MISMATCH',
    'after-action HTML does not reconstruct',
  );
  const storedHostileVerification = await readJson(join(outDir, FILES.hostileVerification));
  requireCondition(
    canonicalJson(storedHostileVerification)
      === canonicalJson(
        verifyHostileRecoveryCampaign(
          storedHostileCampaign,
          storedAfterActionHtml,
          storedBundle,
          storedFaultCampaign,
        ),
      ),
    'PACK_REPLAY_MISMATCH',
    'hostile-recovery verification does not reconstruct',
  );
  const answer = await readJson(join(outDir, FILES.fiveQuestions));
  assertFiveQuestionAnswer(answer);

  const receiptBody = {
    schema: 'spectra-anchor-node-cold-successor-verification/1',
    packId: manifest.packId,
    profileId: manifest.profileId,
    sourceCommit: manifest.sourceCommit,
    status: 'PASS',
    fileCount: manifest.fileCount,
    fiveQuestionStatus: 'PASS',
    faultWorkerStatus: storedFaultVerification.status,
    hostileRecoveryStatus: storedHostileVerification.status,
    afterActionReceiptOnly: storedHostileVerification.afterActionReceiptOnly,
    deterministicReconstruction: true,
    externalServiceCalls: 0,
    operationalCredentials: 0,
    latticeRequired: false,
    authority: 'none',
    claimBoundary:
      'This receipt proves exact bytes and deterministic reconstruction of one synthetic qualification pack. It grants no operational, field, evaluator, adoption, or command authority.',
  };
  return {
    ...receiptBody,
    verificationId: digest('anchorcoldsuccessorverification1', receiptBody),
  };
}

async function main(argv) {
  const command = argv[2];
  if (command === 'build') {
    const outDir = resolve(argv[3]);
    const sourceCommit = argv[4];
    const manifest = await buildColdSuccessorPack(outDir, { sourceCommit });
    process.stdout.write(
      `${JSON.stringify({ status: 'PASS', packId: manifest.packId, outDir }, null, 2)}\n`,
    );
    return;
  }
  if (command === 'verify') {
    const outDir = resolve(argv[3]);
    const outputPath = resolve(argv[4]);
    const receipt = await verifyColdSuccessorPack(outDir);
    await writeJson(outputPath, receipt);
    process.stdout.write(`${JSON.stringify(receipt, null, 2)}\n`);
    return;
  }
  throw new ColdSuccessorPackError('COMMAND_INVALID', `unknown command ${command}`);
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  main(process.argv).catch((error) => {
    const code = error instanceof ColdSuccessorPackError ? error.code : 'UNEXPECTED_ERROR';
    process.stderr.write(`${code}: ${error.message}\n`);
    process.exitCode = 1;
  });
}

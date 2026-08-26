import { createHash } from 'node:crypto';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  MessageAuthorityRuntime,
  canonicalJson,
  createDefaultRehearsalAuthorityProfile,
  verifyAdmissionTicket,
  verifyAuthorityDecision,
} from '../semantic/authority_sidecar.mjs';

const HERE = dirname(fileURLToPath(import.meta.url));
const DEFAULT_FIXTURE = resolve(HERE, 'fixtures/mp01-observation-package.json');

const OBSERVATION_PACKAGE_KEYS = new Set([
  'schema',
  'packageId',
  'classification',
  'capturedAt',
  'observations',
  'claimBoundary',
]);
const OBSERVATION_KEYS = new Set([
  'observationId',
  'kind',
  'source',
  'observedAtStep',
  'entityExternalId',
  'attributes',
  'uncertainty',
  'claimBoundary',
]);
const UNCERTAINTY_KEYS = new Set(['state', 'reason']);
const OBSERVATION_KINDS = new Set(['synthetic_airspace', 'synthetic_logistics']);
const UNCERTAINTY_STATES = new Set(['PROVEN', 'UNRESOLVED', 'UNMEASURED', 'STALE', 'CONFLICTED']);
const CLAIM_KINDS = new Set(['observation', 'inference', 'decision', 'grant', 'execution', 'result', 'verification', 'obligation']);

const AUTHORITY_BINDINGS = Object.freeze({
  artifactAdmissionId: 'anchor-node-mp01-synthetic-admission/1',
  artifactUseId: 'anchor-node-mp01-synthetic-use/1',
  catalogId: 'anchor-node-mp01-catalog/1',
});

export class AnchorNodeError extends Error {
  constructor(code, message) {
    super(message);
    this.name = 'AnchorNodeError';
    this.code = code;
  }
}

function requireCondition(condition, code, message) {
  if (!condition) throw new AnchorNodeError(code, message);
}

function isRecord(value) {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) return false;
  const prototype = Object.getPrototypeOf(value);
  return prototype === Object.prototype || prototype === null;
}

function exactKeys(value, expected, code, label) {
  requireCondition(isRecord(value), code, `${label} must be an object`);
  const actual = Object.keys(value).sort();
  const wanted = [...expected].sort();
  requireCondition(canonicalJson(actual) === canonicalJson(wanted), code, `${label} fields differ`);
}

function boundedString(value, code, label, max = 1024) {
  requireCondition(typeof value === 'string', code, `${label} must be a string`);
  const normalized = value.trim();
  requireCondition(normalized.length > 0 && normalized.length <= max, code, `${label} is empty or unbounded`);
  return normalized;
}

function safeStep(value, code, label) {
  requireCondition(Number.isSafeInteger(value) && value >= 0, code, `${label} must be a non-negative safe integer`);
  return value;
}

function digest(prefix, value) {
  return `${prefix}_${createHash('sha256').update(canonicalJson(value), 'utf8').digest('hex')}`;
}

function withoutKeys(value, keys) {
  const copy = structuredClone(value);
  for (const key of keys) delete copy[key];
  return copy;
}

function parseIso(value, code, label) {
  boundedString(value, code, label, 64);
  const parsed = Date.parse(value);
  requireCondition(Number.isFinite(parsed), code, `${label} must be an ISO timestamp`);
  return value;
}

export function validateSyntheticObservationPackage(input) {
  exactKeys(input, OBSERVATION_PACKAGE_KEYS, 'OBSERVATION_PACKAGE_INVALID', 'observation package');
  requireCondition(
    input.schema === 'spectra-anchor-node-synthetic-observation-package/1',
    'OBSERVATION_PACKAGE_SCHEMA_INVALID',
    'observation package schema is invalid',
  );
  boundedString(input.packageId, 'OBSERVATION_PACKAGE_INVALID', 'packageId');
  requireCondition(
    input.classification === 'invented_unclassified_synthetic_only',
    'OBSERVATION_CLASSIFICATION_INVALID',
    'observation package must remain invented, unclassified, and synthetic-only',
  );
  parseIso(input.capturedAt, 'OBSERVATION_PACKAGE_INVALID', 'capturedAt');
  boundedString(input.claimBoundary, 'OBSERVATION_PACKAGE_INVALID', 'claimBoundary', 2048);
  requireCondition(
    input.claimBoundary.toLowerCase().includes('no real'),
    'OBSERVATION_PACKAGE_INVALID',
    'package claim boundary must explicitly exclude real data',
  );
  requireCondition(Array.isArray(input.observations) && input.observations.length === 2, 'OBSERVATION_PACKAGE_INVALID', 'Mission Profile 01 requires exactly two synthetic observations');

  const ids = new Set();
  const kinds = new Set();
  for (const row of input.observations) {
    exactKeys(row, OBSERVATION_KEYS, 'OBSERVATION_INVALID', 'observation');
    boundedString(row.observationId, 'OBSERVATION_INVALID', 'observationId');
    requireCondition(!ids.has(row.observationId), 'OBSERVATION_INVALID', `duplicate observation ${row.observationId}`);
    ids.add(row.observationId);
    requireCondition(OBSERVATION_KINDS.has(row.kind), 'OBSERVATION_INVALID', `unsupported observation kind ${row.kind}`);
    kinds.add(row.kind);
    boundedString(row.source, 'OBSERVATION_INVALID', 'source');
    safeStep(row.observedAtStep, 'OBSERVATION_INVALID', 'observedAtStep');
    boundedString(row.entityExternalId, 'OBSERVATION_INVALID', 'entityExternalId');
    requireCondition(row.entityExternalId.startsWith('SYN-'), 'OBSERVATION_INVALID', 'synthetic entity ids must use the SYN- prefix');
    requireCondition(isRecord(row.attributes) && Object.keys(row.attributes).length > 0, 'OBSERVATION_INVALID', 'attributes must be a non-empty object');
    exactKeys(row.uncertainty, UNCERTAINTY_KEYS, 'OBSERVATION_INVALID', 'uncertainty');
    requireCondition(UNCERTAINTY_STATES.has(row.uncertainty.state), 'OBSERVATION_INVALID', 'uncertainty state is invalid');
    boundedString(row.uncertainty.reason, 'OBSERVATION_INVALID', 'uncertainty.reason');
    boundedString(row.claimBoundary, 'OBSERVATION_INVALID', 'observation claimBoundary', 2048);
    requireCondition(row.claimBoundary.toLowerCase().includes('invented'), 'OBSERVATION_INVALID', 'each observation must remain explicitly invented');
  }
  requireCondition(kinds.size === 2, 'OBSERVATION_PACKAGE_INVALID', 'the package must contain one airspace and one logistics observation');
  return input;
}

function observationClaim(row) {
  const body = {
    schema: 'spectra-anchor-node-claim/1',
    claimKind: 'observation',
    subject: row.entityExternalId,
    predicate: 'observed_as',
    object: row.kind,
    evidenceRef: row.observationId,
    uncertainty: row.uncertainty,
    authority: false,
    claimBoundary: row.claimBoundary,
  };
  return { ...body, claimId: digest('anchorclaim1', body) };
}

export function buildCanonicalMissionState(sourcePackage) {
  validateSyntheticObservationPackage(sourcePackage);
  const sourcePackageDigest = digest('anchorsourcepackage1', sourcePackage);
  const observations = sourcePackage.observations.map((row) => structuredClone(row));
  const entities = observations.map((row) => {
    const body = {
      schema: 'spectra-anchor-node-entity-state/1',
      entityId: `entity/${row.entityExternalId}`,
      externalId: row.entityExternalId,
      entityType: row.kind === 'synthetic_airspace' ? 'synthetic_track' : 'synthetic_logistics_node',
      attributes: structuredClone(row.attributes),
      sourceObservationIds: [row.observationId],
      uncertainty: structuredClone(row.uncertainty),
      canonical: true,
      claimBoundary: 'Canonical only within this invented Mission Profile 01 fixture. It is not a real-world track, unit, location, or operational object.',
    };
    return { ...body, entityStateId: digest('anchorentitystate1', body) };
  });

  const air = entities.find((row) => row.entityType === 'synthetic_track');
  const logistics = entities.find((row) => row.entityType === 'synthetic_logistics_node');
  const sameCorridor = air.attributes.corridor === logistics.attributes.corridor;
  const relationshipBody = {
    schema: 'spectra-anchor-node-relationship-state/1',
    relationshipType: 'candidate_shared_corridor',
    fromEntityId: air.entityId,
    toEntityId: logistics.entityId,
    state: sameCorridor ? 'candidate' : 'disproven',
    evidenceRefs: [...air.sourceObservationIds, ...logistics.sourceObservationIds],
    uncertainty: {
      state: sameCorridor ? 'UNRESOLVED' : 'DISPROVEN',
      reason: sameCorridor
        ? 'Matching fixture labels support a review obligation but do not prove a real interaction.'
        : 'Fixture corridor labels do not match.',
    },
    canonical: true,
    claimBoundary: 'This relationship is an invented analytical candidate. It is not targeting, threat identification, or operational correlation.',
  };
  const relationship = { ...relationshipBody, relationshipStateId: digest('anchorrelationshipstate1', relationshipBody) };

  const obligationBody = {
    schema: 'spectra-anchor-node-obligation/1',
    claimKind: 'obligation',
    obligationType: 'review_shared_corridor_context',
    status: sameCorridor ? 'open' : 'not_required',
    evidenceRefs: relationship.evidenceRefs,
    reason: relationship.uncertainty.reason,
    authority: false,
    claimBoundary: 'This obligation requests local review of synthetic fixture state only. It is not an operational tasking order.',
  };
  const obligation = { ...obligationBody, obligationId: digest('anchorobligation1', obligationBody) };

  const claims = observations.map(observationClaim);
  const stateBody = {
    schema: 'spectra-anchor-node-canonical-mission-state/1',
    profileId: 'spectra-anchor-node/disconnected-multisensor-coordination/0.1',
    sourcePackageId: sourcePackage.packageId,
    sourcePackageDigest,
    classification: sourcePackage.classification,
    entities,
    relationships: [relationship],
    claims,
    obligations: [obligation],
    taskStates: [],
    canonical: true,
    claimBoundary: 'This is the canonical local state for one invented, unclassified, synthetic-only qualification slice. It grants no field or command authority.',
  };
  return { ...stateBody, missionStateId: digest('anchormissionstate1', stateBody) };
}

export function createDeterministicModelProposal(missionState) {
  requireCondition(missionState?.schema === 'spectra-anchor-node-canonical-mission-state/1', 'MISSION_STATE_INVALID', 'mission state is invalid');
  const relationship = missionState.relationships[0];
  const logistics = missionState.entities.find((row) => row.entityType === 'synthetic_logistics_node');
  const body = {
    schema: 'spectra-anchor-node-model-proposal/1',
    claimKind: 'inference',
    modelId: 'bounded-local-model-simulator/1',
    modelQualified: false,
    authority: false,
    proposalType: 'prepare_local_logistics_crosscheck',
    targetEntityId: logistics.entityId,
    evidenceRefs: relationship.evidenceRefs,
    rationale:
      relationship.state === 'candidate'
        ? 'Two invented fixture observations share a corridor label; prepare a local review artifact before any later decision.'
        : 'No shared corridor candidate exists; retain a no-action proposal.',
    confidence: relationship.state === 'candidate' ? 0.72 : 0.05,
    requestedEffect: 'local_artifact_only',
    claimBoundary: 'This deterministic simulator exercises the model-proposal interface. It is not a qualified AI model, command recommendation, targeting output, or authority grant.',
  };
  return { ...body, proposalId: digest('anchormodelproposal1', body) };
}

function createSemanticTaskMessageReceipt(sourcePackage, proposal) {
  const payload = canonicalJson(proposal);
  const body = {
    schema: 'c2sim-semantic-message-receipt/1',
    messageReceiptId: '',
    artifactAdmissionId: AUTHORITY_BINDINGS.artifactAdmissionId,
    artifactUseId: AUTHORITY_BINDINGS.artifactUseId,
    artifactSha256: createHash('sha256').update('synthetic-anchor-node-mp01', 'utf8').digest('hex'),
    catalogId: AUTHORITY_BINDINGS.catalogId,
    standardId: 'siso-std-019-2020-c2sim',
    standardRevision: 'synthetic-interface-binding-only',
    fileName: 'mp01-local-proposal.json',
    payloadSha256: createHash('sha256').update(payload, 'utf8').digest('hex'),
    payloadBytes: Buffer.byteLength(payload, 'utf8'),
    messageId: `message/${proposal.proposalId}`,
    conversationId: `conversation/${sourcePackage.packageId}`,
    communicativeAct: 'request_local_review_artifact',
    fromSystem: 'spectra-anchor-node-local-model-interface',
    toSystem: 'spectra-anchor-node-local-authority-runtime',
    inReplyToMessageId: null,
    sentAt: sourcePackage.capturedAt,
    protocol: 'local-c2sim-rehearsal-binding',
    protocolVersion: '1',
    securityClassification: 'UNCLASSIFIED_SYNTHETIC_ONLY',
    messageClass: 'order',
    validation: {
      status: 'pass',
      validator: 'spectra-anchor-node-local-contract/1',
    },
    claimBoundary: 'This semantic receipt wraps one synthetic local proposal so the existing denied-communications authority runtime can be exercised. It is not an operational C2 message or command.',
  };
  body.messageReceiptId = digest('anchorsemanticmessagereceipt1', withoutKeys(body, ['messageReceiptId', 'claimBoundary']));
  return body;
}

function createTaskReceipt({ missionState, proposal, decision, ticket, taskStep }) {
  requireCondition(decision.disposition === 'allow', 'TASK_AUTHORITY_INVALID', 'task cannot execute without an allow decision');
  requireCondition(ticket !== null, 'TASK_AUTHORITY_INVALID', 'task cannot execute without an admission ticket');
  requireCondition(ticket.expiresAtStep === null || taskStep <= ticket.expiresAtStep, 'TASK_LEASE_EXPIRED', 'task step exceeds the authority lease');
  const output = {
    schema: 'spectra-anchor-node-local-review-artifact/1',
    artifactType: 'logistics_crosscheck_checklist',
    targetEntityId: proposal.targetEntityId,
    checklist: [
      'inspect the two cited synthetic observations',
      'preserve the unresolved relationship state',
      'record a human disposition before any later tasking',
    ],
    effectClass: 'local_artifact_only',
    claimBoundary: 'This output is a local synthetic review checklist. It performs no external, kinetic, command, targeting, engagement, or effector action.',
  };
  const outputDigest = digest('anchorlocalartifact1', output);
  const body = {
    schema: 'spectra-anchor-node-non-kinetic-task-receipt/1',
    claimKind: 'execution',
    taskType: proposal.proposalType,
    effectClass: 'local_artifact_only',
    proposalId: proposal.proposalId,
    decisionId: decision.decisionId,
    admissionTicketId: ticket.ticketId,
    preStateId: missionState.missionStateId,
    executedAtStep: taskStep,
    status: 'completed',
    output,
    outputDigest,
    authority: false,
    claimBoundary: 'This receipt proves deterministic creation of one local synthetic review artifact. It grants no operational or command authority and records no external effect.',
  };
  return { ...body, taskReceiptId: digest('anchornonkinetictaskreceipt1', body) };
}

function appendTaskState(missionState, taskReceipt) {
  const taskState = {
    schema: 'spectra-anchor-node-task-state/1',
    taskReceiptId: taskReceipt.taskReceiptId,
    taskType: taskReceipt.taskType,
    effectClass: taskReceipt.effectClass,
    terminalState: taskReceipt.status,
    outputDigest: taskReceipt.outputDigest,
    canonical: true,
    claimBoundary: taskReceipt.claimBoundary,
  };
  const body = {
    ...withoutKeys(missionState, ['missionStateId']),
    taskStates: [...missionState.taskStates, taskState],
  };
  return { ...body, missionStateId: digest('anchormissionstate1', body) };
}

export function runVerticalSlice(sourcePackage, options = {}) {
  validateSyntheticObservationPackage(sourcePackage);
  const localOperatorPresent = options.localOperatorPresent ?? true;
  const authorityEvaluationStep = options.authorityEvaluationStep ?? 2;
  const taskStep = options.taskStep ?? 3;
  requireCondition(typeof localOperatorPresent === 'boolean', 'LOCAL_OPERATOR_STATE_INVALID', 'localOperatorPresent must be boolean');
  safeStep(authorityEvaluationStep, 'STEP_INVALID', 'authorityEvaluationStep');
  safeStep(taskStep, 'STEP_INVALID', 'taskStep');
  requireCondition(taskStep >= authorityEvaluationStep, 'STEP_INVALID', 'task step cannot precede authority evaluation');

  const missionStateBefore = buildCanonicalMissionState(sourcePackage);
  const modelProposal = createDeterministicModelProposal(missionStateBefore);
  const semanticMessageReceipt = createSemanticTaskMessageReceipt(sourcePackage, modelProposal);
  const authorityProfile = createDefaultRehearsalAuthorityProfile({
    ...AUTHORITY_BINDINGS,
    authorityGeneration: 1,
    offlineLeaseSteps: 3,
  });
  const authorityRuntime = new MessageAuthorityRuntime(authorityProfile);
  authorityRuntime.setLinkState('headquarters_denied', 1);
  const { decision: authorityDecision, ticket: admissionTicket } = authorityRuntime.evaluateMessage(
    semanticMessageReceipt,
    { step: authorityEvaluationStep, localOperatorPresent },
  );
  verifyAuthorityDecision(authorityDecision, authorityProfile);
  if (authorityDecision.disposition !== 'allow') {
    throw new AnchorNodeError('AUTHORITY_NOT_GRANTED', `authority disposition ${authorityDecision.disposition}: ${authorityDecision.reason}`);
  }
  verifyAdmissionTicket(admissionTicket, authorityDecision, authorityProfile);
  const taskReceipt = createTaskReceipt({
    missionState: missionStateBefore,
    proposal: modelProposal,
    decision: authorityDecision,
    ticket: admissionTicket,
    taskStep,
  });
  const missionStateAfter = appendTaskState(missionStateBefore, taskReceipt);

  const transitions = [
    {
      step: 0,
      claimKind: 'observation',
      objectId: missionStateBefore.sourcePackageDigest,
      state: 'captured',
    },
    {
      step: 0,
      claimKind: 'verification',
      objectId: missionStateBefore.missionStateId,
      state: 'canonical_local_state_built',
    },
    {
      step: 1,
      claimKind: 'inference',
      objectId: modelProposal.proposalId,
      state: 'proposal_only_no_authority',
    },
    {
      step: authorityEvaluationStep,
      claimKind: 'decision',
      objectId: authorityDecision.decisionId,
      state: authorityDecision.disposition,
    },
    {
      step: authorityEvaluationStep,
      claimKind: 'grant',
      objectId: admissionTicket.ticketId,
      state: 'bounded_admission_ticket_issued',
    },
    {
      step: taskStep,
      claimKind: 'execution',
      objectId: taskReceipt.taskReceiptId,
      state: taskReceipt.status,
    },
    {
      step: taskStep,
      claimKind: 'result',
      objectId: taskReceipt.outputDigest,
      state: 'local_artifact_created',
    },
  ];
  for (const transition of transitions) {
    requireCondition(CLAIM_KINDS.has(transition.claimKind), 'CLAIM_KIND_INVALID', `unknown transition claim kind ${transition.claimKind}`);
  }

  const bundleBody = {
    schema: 'spectra-anchor-node-vertical-slice-bundle/1',
    profileId: 'spectra-anchor-node/disconnected-multisensor-coordination/0.1',
    classification: sourcePackage.classification,
    sourcePackage: structuredClone(sourcePackage),
    missionStateBefore,
    modelProposal,
    semanticMessageReceipt,
    authorityProfile,
    authorityDecision,
    admissionTicket,
    taskReceipt,
    missionStateAfter,
    materialTransitions: transitions,
    externalServiceCalls: 0,
    operationalCredentials: 0,
    latticeRequired: false,
    claimBoundary: 'This bundle proves one deterministic synthetic local vertical slice. It is not an operational C2 profile, field-network qualification, representative-operator result, targeting system, command grant, or weapons capability.',
  };
  return { ...bundleBody, runId: digest('anchorverticalslice1', bundleBody) };
}

function materialView(bundle) {
  return {
    profileId: bundle.profileId,
    classification: bundle.classification,
    sourcePackage: bundle.sourcePackage,
    missionStateBefore: bundle.missionStateBefore,
    modelProposal: bundle.modelProposal,
    semanticMessageReceipt: bundle.semanticMessageReceipt,
    authorityProfile: bundle.authorityProfile,
    authorityDecision: bundle.authorityDecision,
    admissionTicket: bundle.admissionTicket,
    taskReceipt: bundle.taskReceipt,
    missionStateAfter: bundle.missionStateAfter,
    materialTransitions: bundle.materialTransitions,
    externalServiceCalls: bundle.externalServiceCalls,
    operationalCredentials: bundle.operationalCredentials,
    latticeRequired: bundle.latticeRequired,
  };
}

export function verifyVerticalSlice(bundle) {
  requireCondition(isRecord(bundle), 'BUNDLE_INVALID', 'vertical slice bundle must be an object');
  requireCondition(bundle.schema === 'spectra-anchor-node-vertical-slice-bundle/1', 'BUNDLE_SCHEMA_INVALID', 'vertical slice bundle schema is invalid');
  requireCondition(bundle.classification === 'invented_unclassified_synthetic_only', 'BUNDLE_CLASSIFICATION_INVALID', 'bundle must remain synthetic-only');
  requireCondition(bundle.externalServiceCalls === 0, 'BUNDLE_EXTERNAL_DEPENDENCY_INVALID', 'bundle records external service calls');
  requireCondition(bundle.operationalCredentials === 0, 'BUNDLE_CREDENTIALS_INVALID', 'bundle records operational credentials');
  requireCondition(bundle.latticeRequired === false, 'BUNDLE_LATTICE_INVALID', 'Lattice cannot be required for local continuity');
  requireCondition(bundle.modelProposal.claimKind === 'inference', 'CLAIM_KIND_CROSS_CONVERSION', 'model proposal must remain an inference');
  requireCondition(bundle.modelProposal.authority === false, 'MODEL_AUTHORITY_INVALID', 'model proposal cannot carry authority');
  requireCondition(bundle.modelProposal.modelQualified === false, 'MODEL_QUALIFICATION_INVALID', 'fixture simulator cannot self-qualify');
  requireCondition(bundle.authorityDecision.disposition === 'allow', 'BUNDLE_AUTHORITY_INVALID', 'qualified bundle must contain an allow decision');
  requireCondition(bundle.taskReceipt.claimKind === 'execution', 'CLAIM_KIND_CROSS_CONVERSION', 'task receipt must remain an execution claim');
  requireCondition(bundle.taskReceipt.effectClass === 'local_artifact_only', 'TASK_EFFECT_INVALID', 'vertical slice task must remain local and non-kinetic');
  requireCondition(bundle.taskReceipt.authority === false, 'TASK_AUTHORITY_INVALID', 'task receipt cannot grant authority');
  requireCondition(bundle.taskReceipt.status === 'completed', 'TASK_STATUS_INVALID', 'task receipt is not complete');
  requireCondition(bundle.missionStateBefore.canonical === true && bundle.missionStateAfter.canonical === true, 'CANONICAL_STATE_INVALID', 'mission states must remain canonical');
  verifyAuthorityDecision(bundle.authorityDecision, bundle.authorityProfile);
  verifyAdmissionTicket(bundle.admissionTicket, bundle.authorityDecision, bundle.authorityProfile);

  const replayed = runVerticalSlice(bundle.sourcePackage, {
    localOperatorPresent: bundle.authorityDecision.localOperatorPresent,
    authorityEvaluationStep: bundle.authorityDecision.evaluatedAtStep,
    taskStep: bundle.taskReceipt.executedAtStep,
  });
  requireCondition(canonicalJson(materialView(replayed)) === canonicalJson(materialView(bundle)), 'DETACHED_REPLAY_MISMATCH', 'detached replay material state differs');
  requireCondition(bundle.runId === replayed.runId, 'RUN_ID_INVALID', 'run identity differs from deterministic replay');

  const receiptBody = {
    schema: 'spectra-anchor-node-detached-replay-verification/1',
    runId: bundle.runId,
    profileId: bundle.profileId,
    status: 'PASS',
    materialTransitionDigest: digest('anchortransitionledger1', bundle.materialTransitions),
    sourcePackageDigest: bundle.missionStateBefore.sourcePackageDigest,
    finalMissionStateId: bundle.missionStateAfter.missionStateId,
    externalServiceCalls: 0,
    latticeRequired: false,
    claimBoundary: 'This verification proves deterministic replay of the synthetic material transitions. It grants no field, operational, evaluator, or command authority.',
  };
  return { ...receiptBody, verificationId: digest('anchordetachedreplayverification1', receiptBody) };
}

async function writeJson(path, value) {
  await mkdir(dirname(path), { recursive: true });
  await writeFile(path, `${JSON.stringify(value, null, 2)}\n`, 'utf8');
}

async function main(argv) {
  const command = argv[2] ?? 'run';
  if (command === 'run') {
    const fixturePath = resolve(argv[3] ?? DEFAULT_FIXTURE);
    const outputPath = resolve(argv[4] ?? 'qualification/anchor-node-mp01/vertical-slice.json');
    const sourcePackage = JSON.parse(await readFile(fixturePath, 'utf8'));
    const bundle = runVerticalSlice(sourcePackage);
    await writeJson(outputPath, bundle);
    process.stdout.write(`${JSON.stringify({ status: 'PASS', runId: bundle.runId, outputPath }, null, 2)}\n`);
    return;
  }
  if (command === 'verify') {
    const bundlePath = resolve(argv[3]);
    const outputPath = resolve(argv[4] ?? 'qualification/anchor-node-mp01/detached-replay-verification.json');
    const bundle = JSON.parse(await readFile(bundlePath, 'utf8'));
    const receipt = verifyVerticalSlice(bundle);
    await writeJson(outputPath, receipt);
    process.stdout.write(`${JSON.stringify(receipt, null, 2)}\n`);
    return;
  }
  throw new AnchorNodeError('COMMAND_INVALID', `unknown command ${command}`);
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  main(process.argv).catch((error) => {
    const code = error instanceof AnchorNodeError ? error.code : 'UNEXPECTED_ERROR';
    process.stderr.write(`${code}: ${error.message}\n`);
    process.exitCode = 1;
  });
}

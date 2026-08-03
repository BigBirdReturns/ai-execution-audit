import { createHash } from 'node:crypto';

const QUALIFICATION_SCHEMA = 'standards-external-evidence-qualification/1';
const VERIFICATION_SCHEMA = 'standards-external-evidence-verification/1';
const SOURCE_TIERS = new Set([
  'private_digest_only',
  'public_exact_bytes',
  'synthetic_fixture',
]);
const CLAIM_RESULTS = new Set([
  'pass',
  'pass_within_harness',
  'pass_for_logged_sample',
  'partial',
  'fail',
  'incomplete',
  'not_run',
  'not_witnessed',
  'not_acquired',
]);
const DETACHED_REPLAY_STATES = new Set(['pass', 'fail', 'absent']);
const SIMPLE_VALUE_TYPES = new Set(['string', 'number', 'boolean']);

export class ExternalEvidenceError extends Error {
  constructor(code, message) {
    super(message);
    this.name = 'ExternalEvidenceError';
    this.code = code;
  }
}

function requireCondition(condition, code, message) {
  if (!condition) throw new ExternalEvidenceError(code, message);
}

function isRecord(value) {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) return false;
  const prototype = Object.getPrototypeOf(value);
  return prototype === Object.prototype || prototype === null;
}

function canonicalJson(value) {
  if (value === null) return 'null';
  if (Array.isArray(value)) return `[${value.map((item) => canonicalJson(item)).join(',')}]`;
  if (isRecord(value)) {
    return `{${Object.keys(value)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${canonicalJson(value[key])}`)
      .join(',')}}`;
  }
  return JSON.stringify(value);
}

function digest(prefix, value) {
  return `${prefix}_${createHash('sha256').update(canonicalJson(value), 'utf8').digest('hex')}`;
}

function exactKeys(value, allowed, required, code, label) {
  requireCondition(isRecord(value), code, `${label} must be an object`);
  const unexpected = Object.keys(value).filter((key) => !allowed.has(key)).sort();
  requireCondition(unexpected.length === 0, code, `${label} contains unsupported field ${unexpected[0]}`);
  const missing = [...required].filter((key) => !Object.hasOwn(value, key));
  requireCondition(missing.length === 0, code, `${label} is missing field ${missing[0]}`);
}

function boundedString(value, code, label, maximum = 2_000) {
  requireCondition(typeof value === 'string', code, `${label} must be a string`);
  const normalized = value.trim();
  requireCondition(normalized.length > 0 && normalized.length <= maximum, code, `${label} is empty or unbounded`);
  return normalized;
}

function optionalIdentity(value, code, label) {
  if (value === null) return null;
  return boundedString(value, code, label, 300);
}

function validateArtifact(artifact, index, sourceTier) {
  exactKeys(
    artifact,
    new Set(['artifactId', 'role', 'bytes', 'sha256']),
    new Set(['artifactId', 'role', 'bytes', 'sha256']),
    'EXTERNAL_ARTIFACT_INVALID',
    `source artifact ${index}`,
  );
  const normalized = {
    artifactId: boundedString(artifact.artifactId, 'EXTERNAL_ARTIFACT_INVALID', 'artifactId', 120),
    role: boundedString(artifact.role, 'EXTERNAL_ARTIFACT_INVALID', 'artifact role', 120),
    bytes: artifact.bytes,
    sha256: artifact.sha256,
  };
  requireCondition(
    Number.isSafeInteger(normalized.bytes) && normalized.bytes > 0,
    'EXTERNAL_ARTIFACT_INVALID',
    `${normalized.artifactId} bytes must be a positive integer`,
  );
  requireCondition(
    typeof normalized.sha256 === 'string' && /^[0-9a-f]{64}$/.test(normalized.sha256),
    'EXTERNAL_ARTIFACT_INVALID',
    `${normalized.artifactId} SHA-256 is invalid`,
  );
  requireCondition(
    !['path', 'filename', 'content', 'body', 'bytesBase64'].some((key) => Object.hasOwn(artifact, key)),
    'EXTERNAL_PRIVATE_BYTES_REFUSED',
    `${normalized.artifactId} attempts to retain source bytes or a source path`,
  );
  requireCondition(
    sourceTier !== 'private_digest_only' || !normalized.role.includes('published_bytes'),
    'EXTERNAL_PRIVATE_BYTES_REFUSED',
    'private digest-only evidence may not claim published source bytes',
  );
  return normalized;
}

function normalizeSource(source) {
  exactKeys(
    source,
    new Set([
      'evidenceTier',
      'classification',
      'rawSourceCommitted',
      'artifacts',
      'custodyStatement',
    ]),
    new Set([
      'evidenceTier',
      'classification',
      'rawSourceCommitted',
      'artifacts',
      'custodyStatement',
    ]),
    'EXTERNAL_SOURCE_INVALID',
    'source',
  );
  requireCondition(SOURCE_TIERS.has(source.evidenceTier), 'EXTERNAL_SOURCE_INVALID', 'unsupported evidence tier');
  requireCondition(typeof source.rawSourceCommitted === 'boolean', 'EXTERNAL_SOURCE_INVALID', 'rawSourceCommitted must be boolean');
  requireCondition(
    source.evidenceTier !== 'private_digest_only' || source.rawSourceCommitted === false,
    'EXTERNAL_PRIVATE_BYTES_REFUSED',
    'private digest-only evidence may not commit raw source bytes',
  );
  requireCondition(
    Array.isArray(source.artifacts) && source.artifacts.length > 0 && source.artifacts.length <= 20,
    'EXTERNAL_SOURCE_INVALID',
    'source artifacts are empty or unbounded',
  );
  const artifacts = source.artifacts.map((artifact, index) => validateArtifact(artifact, index, source.evidenceTier));
  const ids = new Set();
  for (const artifact of artifacts) {
    requireCondition(!ids.has(artifact.artifactId), 'EXTERNAL_ARTIFACT_DUPLICATE', `duplicate artifact ${artifact.artifactId}`);
    ids.add(artifact.artifactId);
  }
  return {
    evidenceTier: source.evidenceTier,
    classification: boundedString(source.classification, 'EXTERNAL_SOURCE_INVALID', 'classification', 160),
    rawSourceCommitted: source.rawSourceCommitted,
    artifacts,
    custodyStatement: boundedString(source.custodyStatement, 'EXTERNAL_SOURCE_INVALID', 'custodyStatement', 3_000),
  };
}

function normalizeTestContext(context) {
  exactKeys(
    context,
    new Set([
      'sessionLabel',
      'sourceMode',
      'testVenue',
      'canonicalRuntimeExecuted',
      'physicalNetworkPartitionTested',
      'signedAuthorityTested',
    ]),
    new Set([
      'sessionLabel',
      'sourceMode',
      'testVenue',
      'canonicalRuntimeExecuted',
      'physicalNetworkPartitionTested',
      'signedAuthorityTested',
    ]),
    'EXTERNAL_CONTEXT_INVALID',
    'testContext',
  );
  for (const key of [
    'canonicalRuntimeExecuted',
    'physicalNetworkPartitionTested',
    'signedAuthorityTested',
  ]) {
    requireCondition(typeof context[key] === 'boolean', 'EXTERNAL_CONTEXT_INVALID', `${key} must be boolean`);
  }
  return {
    sessionLabel: boundedString(context.sessionLabel, 'EXTERNAL_CONTEXT_INVALID', 'sessionLabel', 180),
    sourceMode: boundedString(context.sourceMode, 'EXTERNAL_CONTEXT_INVALID', 'sourceMode', 120),
    testVenue: boundedString(context.testVenue, 'EXTERNAL_CONTEXT_INVALID', 'testVenue', 240),
    canonicalRuntimeExecuted: context.canonicalRuntimeExecuted,
    physicalNetworkPartitionTested: context.physicalNetworkPartitionTested,
    signedAuthorityTested: context.signedAuthorityTested,
  };
}

function normalizeObservation(observation, index, artifactIds) {
  exactKeys(
    observation,
    new Set(['observationId', 'name', 'value', 'unit', 'sourceArtifactId', 'interpretation']),
    new Set(['observationId', 'name', 'value', 'unit', 'sourceArtifactId', 'interpretation']),
    'EXTERNAL_OBSERVATION_INVALID',
    `observation ${index}`,
  );
  requireCondition(
    observation.value === null || SIMPLE_VALUE_TYPES.has(typeof observation.value),
    'EXTERNAL_OBSERVATION_INVALID',
    `observation ${index} value must be scalar or null`,
  );
  if (typeof observation.value === 'number') {
    requireCondition(Number.isFinite(observation.value), 'EXTERNAL_OBSERVATION_INVALID', `observation ${index} number is not finite`);
  }
  const normalized = {
    observationId: boundedString(observation.observationId, 'EXTERNAL_OBSERVATION_INVALID', 'observationId', 140),
    name: boundedString(observation.name, 'EXTERNAL_OBSERVATION_INVALID', 'observation name', 240),
    value: observation.value,
    unit: boundedString(observation.unit, 'EXTERNAL_OBSERVATION_INVALID', 'observation unit', 80),
    sourceArtifactId: boundedString(observation.sourceArtifactId, 'EXTERNAL_OBSERVATION_INVALID', 'sourceArtifactId', 120),
    interpretation: boundedString(observation.interpretation, 'EXTERNAL_OBSERVATION_INVALID', 'observation interpretation', 2_000),
  };
  requireCondition(
    artifactIds.has(normalized.sourceArtifactId),
    'EXTERNAL_OBSERVATION_SOURCE_MISSING',
    `${normalized.observationId} cites unknown artifact ${normalized.sourceArtifactId}`,
  );
  return normalized;
}

function normalizeClaim(claim, index, observationIds) {
  exactKeys(
    claim,
    new Set([
      'claimId',
      'name',
      'result',
      'requiredForAcceptance',
      'evidenceObservationIds',
      'rationale',
      'nextEvidence',
    ]),
    new Set([
      'claimId',
      'name',
      'result',
      'requiredForAcceptance',
      'evidenceObservationIds',
      'rationale',
      'nextEvidence',
    ]),
    'EXTERNAL_CLAIM_INVALID',
    `claim ${index}`,
  );
  requireCondition(CLAIM_RESULTS.has(claim.result), 'EXTERNAL_CLAIM_INVALID', `unsupported claim result ${claim.result}`);
  requireCondition(typeof claim.requiredForAcceptance === 'boolean', 'EXTERNAL_CLAIM_INVALID', 'requiredForAcceptance must be boolean');
  requireCondition(
    Array.isArray(claim.evidenceObservationIds) && claim.evidenceObservationIds.length <= 50,
    'EXTERNAL_CLAIM_INVALID',
    'evidenceObservationIds must be a bounded array',
  );
  const cited = claim.evidenceObservationIds.map((value) => boundedString(value, 'EXTERNAL_CLAIM_INVALID', 'observation reference', 140));
  for (const id of cited) {
    requireCondition(observationIds.has(id), 'EXTERNAL_CLAIM_EVIDENCE_MISSING', `${claim.claimId} cites unknown observation ${id}`);
  }
  requireCondition(
    claim.result !== 'pass' || cited.length > 0,
    'EXTERNAL_CLAIM_EVIDENCE_MISSING',
    `${claim.claimId} cannot pass without an observation`,
  );
  return {
    claimId: boundedString(claim.claimId, 'EXTERNAL_CLAIM_INVALID', 'claimId', 140),
    name: boundedString(claim.name, 'EXTERNAL_CLAIM_INVALID', 'claim name', 300),
    result: claim.result,
    requiredForAcceptance: claim.requiredForAcceptance,
    evidenceObservationIds: [...new Set(cited)].sort(),
    rationale: boundedString(claim.rationale, 'EXTERNAL_CLAIM_INVALID', 'claim rationale', 3_000),
    nextEvidence: boundedString(claim.nextEvidence, 'EXTERNAL_CLAIM_INVALID', 'claim nextEvidence', 3_000),
  };
}

function normalizeClosure(closure) {
  exactKeys(
    closure,
    new Set([
      'sourceEvidenceSetId',
      'scenarioCatalogId',
      'scenarioDefinitionId',
      'sessionReceiptId',
      'sessionVerificationId',
      'detachedReplayStatus',
    ]),
    new Set([
      'sourceEvidenceSetId',
      'scenarioCatalogId',
      'scenarioDefinitionId',
      'sessionReceiptId',
      'sessionVerificationId',
      'detachedReplayStatus',
    ]),
    'EXTERNAL_CLOSURE_INVALID',
    'canonicalClosure',
  );
  requireCondition(
    DETACHED_REPLAY_STATES.has(closure.detachedReplayStatus),
    'EXTERNAL_CLOSURE_INVALID',
    'detachedReplayStatus is invalid',
  );
  return {
    sourceEvidenceSetId: optionalIdentity(closure.sourceEvidenceSetId, 'EXTERNAL_CLOSURE_INVALID', 'sourceEvidenceSetId'),
    scenarioCatalogId: optionalIdentity(closure.scenarioCatalogId, 'EXTERNAL_CLOSURE_INVALID', 'scenarioCatalogId'),
    scenarioDefinitionId: optionalIdentity(closure.scenarioDefinitionId, 'EXTERNAL_CLOSURE_INVALID', 'scenarioDefinitionId'),
    sessionReceiptId: optionalIdentity(closure.sessionReceiptId, 'EXTERNAL_CLOSURE_INVALID', 'sessionReceiptId'),
    sessionVerificationId: optionalIdentity(closure.sessionVerificationId, 'EXTERNAL_CLOSURE_INVALID', 'sessionVerificationId'),
    detachedReplayStatus: closure.detachedReplayStatus,
  };
}

function sourceEvidenceBody(source, testContext, observations) {
  return { source, testContext, observations };
}

function deriveAutomaticEvaluation(claims, closure, sourceEvidenceSetId) {
  const required = claims.filter((claim) => claim.requiredForAcceptance);
  const failClaims = required.filter((claim) => claim.result === 'fail');
  const passClaims = required.filter((claim) => claim.result === 'pass');
  const incompleteClaims = required.filter((claim) => claim.result !== 'pass' && claim.result !== 'fail');
  const closureIds = [
    closure.scenarioCatalogId,
    closure.scenarioDefinitionId,
    closure.sessionReceiptId,
    closure.sessionVerificationId,
  ];
  const canonicalClosureComplete = closure.sourceEvidenceSetId === sourceEvidenceSetId
    && closure.detachedReplayStatus === 'pass'
    && closureIds.every((value) => typeof value === 'string' && value.length > 0);
  const status = failClaims.length > 0
    ? 'fail'
    : required.length > 0
      && passClaims.length === required.length
      && canonicalClosureComplete
      ? 'pass'
      : 'incomplete';
  return {
    status,
    requiredClaimCount: required.length,
    requiredPassCount: passClaims.length,
    requiredIncompleteCount: incompleteClaims.length,
    requiredFailCount: failClaims.length,
    canonicalClosureComplete,
    acceptanceEligible: status === 'pass' && canonicalClosureComplete,
    controllingStatement: status === 'pass'
      ? 'The exact external evidence set is closed to a canonical replay-verified session and every required acceptance claim passed.'
      : status === 'fail'
        ? 'At least one required acceptance claim failed.'
        : 'Observed external evidence may qualify bounded behavior, but canonical end-to-end acceptance closure is incomplete.',
  };
}

function receiptBody(receipt) {
  const {
    schema: _schema,
    receiptId: _receiptId,
    claimBoundary: _claimBoundary,
    ...body
  } = receipt;
  return body;
}

export function createExternalEvidenceQualification(input) {
  exactKeys(
    input,
    new Set([
      'source',
      'testContext',
      'observations',
      'claimDispositions',
      'producerReportReview',
      'canonicalClosure',
      'nextEvidence',
    ]),
    new Set([
      'source',
      'testContext',
      'observations',
      'claimDispositions',
      'producerReportReview',
      'canonicalClosure',
      'nextEvidence',
    ]),
    'EXTERNAL_EVIDENCE_INVALID',
    'external evidence input',
  );
  const source = normalizeSource(input.source);
  const testContext = normalizeTestContext(input.testContext);
  requireCondition(
    Array.isArray(input.observations) && input.observations.length > 0 && input.observations.length <= 100,
    'EXTERNAL_OBSERVATION_INVALID',
    'observations are empty or unbounded',
  );
  const artifactIds = new Set(source.artifacts.map((artifact) => artifact.artifactId));
  const observations = input.observations.map((observation, index) => normalizeObservation(observation, index, artifactIds));
  const observationIds = new Set();
  for (const observation of observations) {
    requireCondition(!observationIds.has(observation.observationId), 'EXTERNAL_OBSERVATION_DUPLICATE', `duplicate observation ${observation.observationId}`);
    observationIds.add(observation.observationId);
  }
  requireCondition(
    Array.isArray(input.claimDispositions) && input.claimDispositions.length > 0 && input.claimDispositions.length <= 100,
    'EXTERNAL_CLAIM_INVALID',
    'claim dispositions are empty or unbounded',
  );
  const claimDispositions = input.claimDispositions.map((claim, index) => normalizeClaim(claim, index, observationIds));
  const claimIds = new Set();
  for (const claim of claimDispositions) {
    requireCondition(!claimIds.has(claim.claimId), 'EXTERNAL_CLAIM_DUPLICATE', `duplicate claim ${claim.claimId}`);
    claimIds.add(claim.claimId);
  }
  exactKeys(
    input.producerReportReview,
    new Set(['reviewed', 'sourceArtifactId', 'dispositionCounts', 'controllingCorrection']),
    new Set(['reviewed', 'sourceArtifactId', 'dispositionCounts', 'controllingCorrection']),
    'EXTERNAL_REPORT_REVIEW_INVALID',
    'producerReportReview',
  );
  requireCondition(input.producerReportReview.reviewed === true, 'EXTERNAL_REPORT_REVIEW_INVALID', 'producer report must be marked reviewed');
  requireCondition(artifactIds.has(input.producerReportReview.sourceArtifactId), 'EXTERNAL_REPORT_REVIEW_INVALID', 'producer report cites unknown artifact');
  requireCondition(isRecord(input.producerReportReview.dispositionCounts), 'EXTERNAL_REPORT_REVIEW_INVALID', 'dispositionCounts must be an object');
  requireCondition(
    Object.keys(input.producerReportReview.dispositionCounts).length > 0
      && Object.keys(input.producerReportReview.dispositionCounts).length <= 50,
    'EXTERNAL_REPORT_REVIEW_INVALID',
    'dispositionCounts is empty or unbounded',
  );
  const dispositionCounts = {};
  for (const key of Object.keys(input.producerReportReview.dispositionCounts).sort()) {
    boundedString(key, 'EXTERNAL_REPORT_REVIEW_INVALID', 'disposition label', 100);
    const value = input.producerReportReview.dispositionCounts[key];
    requireCondition(Number.isSafeInteger(value) && value >= 0, 'EXTERNAL_REPORT_REVIEW_INVALID', `invalid disposition count ${key}`);
    dispositionCounts[key] = value;
  }
  const producerReportReview = {
    reviewed: true,
    sourceArtifactId: input.producerReportReview.sourceArtifactId,
    dispositionCounts,
    controllingCorrection: boundedString(
      input.producerReportReview.controllingCorrection,
      'EXTERNAL_REPORT_REVIEW_INVALID',
      'controllingCorrection',
      4_000,
    ),
  };
  const canonicalClosure = normalizeClosure(input.canonicalClosure);
  requireCondition(
    Array.isArray(input.nextEvidence) && input.nextEvidence.length > 0 && input.nextEvidence.length <= 50,
    'EXTERNAL_NEXT_EVIDENCE_INVALID',
    'nextEvidence is empty or unbounded',
  );
  const nextEvidence = input.nextEvidence.map((item) => boundedString(item, 'EXTERNAL_NEXT_EVIDENCE_INVALID', 'next evidence item', 2_000));
  const sourceEvidenceSetId = digest('standardsexternalevidenceset1', sourceEvidenceBody(source, testContext, observations));
  const automaticEvaluation = deriveAutomaticEvaluation(claimDispositions, canonicalClosure, sourceEvidenceSetId);
  const receipt = {
    schema: QUALIFICATION_SCHEMA,
    receiptId: '',
    sourceEvidenceSetId,
    source,
    testContext,
    observations,
    claimDispositions,
    producerReportReview,
    canonicalClosure,
    automaticEvaluation,
    nextEvidence,
    claimBoundary:
      'This receipt qualifies bounded observations from an external test artifact. It does not import private source bytes, convert a producer report into independent evidence, inherit another session by analogy, or establish operational command, targeting, engagement, effector, execution, weapons, human-performance, accessibility, or program-acceptance authority.',
  };
  receipt.receiptId = digest('standardsexternalevidencequalification1', receiptBody(receipt));
  return receipt;
}

export function verifyExternalEvidenceQualification(receipt) {
  exactKeys(
    receipt,
    new Set([
      'schema',
      'receiptId',
      'sourceEvidenceSetId',
      'source',
      'testContext',
      'observations',
      'claimDispositions',
      'producerReportReview',
      'canonicalClosure',
      'automaticEvaluation',
      'nextEvidence',
      'claimBoundary',
    ]),
    new Set([
      'schema',
      'receiptId',
      'sourceEvidenceSetId',
      'source',
      'testContext',
      'observations',
      'claimDispositions',
      'producerReportReview',
      'canonicalClosure',
      'automaticEvaluation',
      'nextEvidence',
      'claimBoundary',
    ]),
    'EXTERNAL_EVIDENCE_INVALID',
    'receipt',
  );
  requireCondition(receipt.schema === QUALIFICATION_SCHEMA, 'EXTERNAL_SCHEMA_INVALID', 'receipt schema is invalid');
  const reconstructed = createExternalEvidenceQualification({
    source: receipt.source,
    testContext: receipt.testContext,
    observations: receipt.observations,
    claimDispositions: receipt.claimDispositions,
    producerReportReview: receipt.producerReportReview,
    canonicalClosure: receipt.canonicalClosure,
    nextEvidence: receipt.nextEvidence,
  });
  requireCondition(
    receipt.sourceEvidenceSetId === reconstructed.sourceEvidenceSetId,
    'EXTERNAL_EVIDENCE_SET_ID_MISMATCH',
    'source evidence set identity does not reconstruct',
  );
  requireCondition(
    canonicalJson(receipt.automaticEvaluation) === canonicalJson(reconstructed.automaticEvaluation),
    'EXTERNAL_AUTOMATIC_EVALUATION_MISMATCH',
    'automatic evaluation does not reconstruct',
  );
  requireCondition(
    receipt.receiptId === reconstructed.receiptId,
    'EXTERNAL_RECEIPT_ID_MISMATCH',
    'external evidence receipt identity does not reconstruct',
  );
  requireCondition(
    receipt.claimBoundary === reconstructed.claimBoundary,
    'EXTERNAL_CLAIM_BOUNDARY_MISMATCH',
    'external evidence claim boundary drifted',
  );
  const verificationBody = {
    receiptId: receipt.receiptId,
    sourceEvidenceSetId: receipt.sourceEvidenceSetId,
    automaticEvaluationStatus: receipt.automaticEvaluation.status,
    acceptanceEligible: receipt.automaticEvaluation.acceptanceEligible,
    privateSourceBytesCommitted: receipt.source.rawSourceCommitted,
  };
  return {
    schema: VERIFICATION_SCHEMA,
    verificationId: digest('standardsexternalevidenceverification1', verificationBody),
    status: 'pass',
    ...verificationBody,
    claimBoundary:
      'Verification establishes deterministic receipt integrity and admission-boundary consistency. It does not change the receipt automatic evaluation or grant acceptance authority.',
  };
}

import { createHash } from 'node:crypto';
import { createReadStream } from 'node:fs';
import { mkdir, readFile, stat, writeFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { canonicalJson } from '../semantic/authority_sidecar.mjs';

const HERE = dirname(fileURLToPath(import.meta.url));
const DEFAULT_PROFILE = resolve(HERE, 'stc-mary-physical-flight-profile-01.json');
const DEFAULT_FIXTURE = resolve(HERE, 'fixtures/stc-mary-physical-flight-synthetic-01.json');
const SHA256 = /^[0-9a-f]{64}$/;
const CONTENT_ID = /^[a-z0-9][a-z0-9_-]*_[0-9a-f]{64}$/;
const MAX_STRING = 8192;
const MAX_EVIDENCE_PER_STAGE = 64;
const MAX_EVIDENCE_BYTES = 8 * 1024 * 1024 * 1024;

export const STC_MARY_STAGES = Object.freeze([
  'VERIFY_INPUTS',
  'MOUNT_PERSONAL_FLOOR',
  'BIND_GRACE',
  'RUN_PERSONAL_FLOOR_BASELINE',
  'ATTACH_HALO3',
  'RUN_HALO3_ACCELERATED',
  'REMOVE_HALO3',
  'VERIFY_PERSONAL_FLOOR_CONTINUITY',
  'REMOVE_LATTICE',
  'VERIFY_LOCAL_CONTINUITY',
  'PARTITION_TWO_CELLS',
  'RESTORE_LINK_HOLD_CONFLICT',
  'REPLACE_HEAD',
  'REBUILD_PROJECTIONS',
  'COLD_SUCCESSOR_VERIFY',
  'SEAL_PRIVATE_EVIDENCE',
]);

export const REQUIRED_STAGE_TERMINALS = Object.freeze({
  VERIFY_INPUTS: 'PASS',
  MOUNT_PERSONAL_FLOOR: 'PASS',
  BIND_GRACE: 'PASS',
  RUN_PERSONAL_FLOOR_BASELINE: 'PASS',
  ATTACH_HALO3: 'PASS',
  RUN_HALO3_ACCELERATED: 'PASS',
  REMOVE_HALO3: 'PASS',
  VERIFY_PERSONAL_FLOOR_CONTINUITY: 'PASS',
  REMOVE_LATTICE: 'PASS',
  VERIFY_LOCAL_CONTINUITY: 'PASS',
  PARTITION_TWO_CELLS: 'PASS',
  RESTORE_LINK_HOLD_CONFLICT: 'HUMAN_REQUIRED',
  REPLACE_HEAD: 'PASS',
  REBUILD_PROJECTIONS: 'PASS',
  COLD_SUCCESSOR_VERIFY: 'PASS',
  SEAL_PRIVATE_EVIDENCE: 'PASS',
});

const TERMINAL_STATES = new Set(['PASS', 'REFUSED', 'HUMAN_REQUIRED']);
const PROHIBITED_SUCCESS_STATES = new Set([
  'PENDING',
  'INACCESSIBLE',
  'UNKNOWN',
  'UNVERIFIABLE',
  'INVALID',
]);
const FLIGHT_MODES = new Set(['synthetic_simulation', 'private_physical_attested']);
const EVIDENCE_CLASSES = new Set([
  'synthetic_deterministic_receipt',
  'private_local_attestation',
  'private_instrument_receipt',
  'private_operator_statement',
]);
const PROJECTION_KINDS = Object.freeze(['graph', 'query', 'cache', 'review']);

const KEYS = Object.freeze({
  profile: [
    'schema',
    'profileId',
    'issues',
    'status',
    'predecessor',
    'flightModes',
    'stageSequence',
    'stagePolicy',
    'substrateRoles',
    'authorityPolicy',
    'evidencePolicy',
    'acceptance',
    'claimBoundary',
  ],
  predecessor: ['repository', 'evidenceTier', 'requiredObjects'],
  predecessorObject: ['schema', 'objectId'],
  stagePolicy: [
    'requiredTerminalStates',
    'prohibitedSuccessStates',
    'previousReceiptChainingRequired',
    'completeDenominatorRequired',
    'canonicalMissionStateMutationAllowed',
    'unresolvedConflictMustRemainExplicit',
  ],
  substrateRoles: ['personalFloor', 'halo3', 'head', 'modelOrExecutable', 'lattice'],
  authorityPolicy: [
    'namedHumanBind',
    'humanBindRequired',
    'modelAuthority',
    'hardwareAuthority',
    'schedulerAuthority',
    'verifierAuthority',
    'returningConflictDisposition',
    'automaticConflictMergeAllowed',
  ],
  evidencePolicy: [
    'publicRepositoryMayContainPrivateEvidenceBodies',
    'publicDispositionDigestOnly',
    'privateBodyPathsMayAppearInPublicDisposition',
    'minimumEvidenceBodiesPerPhysicalStage',
    'contentAddressing',
    'syntheticModeCanClaimPhysicalFlight',
    'privateAttestationCanClaimRepresentativeOperatorQualification',
    'privateAttestationCanClaimFieldQualification',
  ],
  acceptance: ['requires', 'refuseIf'],
  profileClaim: [
    'syntheticHarnessCandidate',
    'privatePhysicalFlightExecuted',
    'physicalEstateQualified',
    'representativeOperatorQualified',
    'fieldNetworkQualified',
    'operationalC2Qualified',
    'productionLatticeQualified',
    'missionAuthorityGranted',
    'commandAuthorityGranted',
    'targetingEngagementEffectorOrWeaponsCapability',
  ],
  fixture: [
    'schema',
    'fixtureId',
    'classification',
    'flightMode',
    'profileId',
    'campaignLabel',
    'sourceObjects',
    'identities',
    'digests',
    'syntheticMetrics',
    'expectedConflict',
    'externalServiceCalls',
    'operationalCredentials',
    'physicalEvidenceBodies',
    'authority',
    'claimBoundary',
  ],
  fixtureIdentities: [
    'personalFloorSeatId',
    'halo3SeatId',
    'initialHeadId',
    'successorHeadId',
    'graceBindId',
    'latticeId',
    'cellIds',
  ],
  fixtureDigests: [
    'missionCartridge',
    'canonicalMissionState',
    'localFeed',
    'runtime',
    'modelOrExecutable',
    'verifier',
    'storageSubstrate',
    'residencyEvidence',
    'powerEvidence',
    'latticeMembrane',
    'projectionTemplate',
  ],
  syntheticMetrics: [
    'unit',
    'personalFloorBaseline',
    'halo3Accelerated',
    'personalFloorAfterHalo3Removal',
  ],
  expectedConflict: [
    'leftCellStateDigest',
    'rightCellStateDigest',
    'automaticMergeAllowed',
    'requiredDisposition',
  ],
  seed: [
    'schema',
    'campaignSeedId',
    'profileId',
    'sourceId',
    'flightMode',
    'stageSequenceDigest',
    'authority',
    'claimBoundary',
  ],
  evidence: [
    'schema',
    'evidenceId',
    'stage',
    'evidenceClass',
    'mediaType',
    'sha256',
    'bytes',
    'bodyPresent',
    'authority',
    'claimBoundary',
  ],
  stageReceipt: [
    'schema',
    'stageReceiptId',
    'campaignSeedId',
    'sequence',
    'stage',
    'terminalState',
    'previousStageReceiptId',
    'canonicalMissionStateIdBefore',
    'canonicalMissionStateIdAfter',
    'observation',
    'evidence',
    'unresolvedObligationIds',
    'effectClass',
    'authority',
    'claimBoundary',
  ],
  run: [
    'schema',
    'runId',
    'profileId',
    'sourceId',
    'flightMode',
    'campaignSeed',
    'stageDenominator',
    'stageReceipts',
    'stageCount',
    'successfulStageCount',
    'humanRequiredStageCount',
    'refusedStageCount',
    'pendingStageCount',
    'canonicalMissionStateIdBefore',
    'canonicalMissionStateIdAfter',
    'canonicalMissionStateUnchanged',
    'personalFloorBaselineVerified',
    'halo3AccelerationVerified',
    'halo3RequiredForContinuity',
    'latticeRequiredForContinuity',
    'partitionCellCount',
    'conflictDisposition',
    'headReplacementVerified',
    'projectionsRebuilt',
    'coldSuccessorVerified',
    'privatePhysicalFlightCompleted',
    'privatePhysicalEvidenceBodyCount',
    'publicEvidenceBodyCount',
    'externalServiceCalls',
    'operationalCredentials',
    'physicalEstateQualified',
    'representativeOperatorQualified',
    'fieldNetworkQualified',
    'operationalC2Qualified',
    'productionLatticeQualified',
    'authority',
    'claimBoundary',
  ],
  verification: [
    'schema',
    'verificationId',
    'runId',
    'status',
    'flightMode',
    'stageDenominatorVerified',
    'stageChainVerified',
    'stageIdentityVerified',
    'expectedTerminalStatesVerified',
    'evidenceDenominatorVerified',
    'canonicalMissionStateUnchanged',
    'personalFloorContinuityVerified',
    'halo3OptionalityVerified',
    'latticeOptionalityVerified',
    'partitionClosureVerified',
    'conflictHeldHumanRequired',
    'headReplacementVerified',
    'projectionsRebuilt',
    'coldSuccessorVerified',
    'privatePhysicalFlightCompleted',
    'publicDispositionBodyFree',
    'physicalEstateQualified',
    'representativeOperatorQualified',
    'fieldNetworkQualified',
    'operationalC2Qualified',
    'productionLatticeQualified',
    'authority',
    'claimBoundary',
  ],
  projection: [
    'schema',
    'projectionId',
    'runId',
    'flightMode',
    'stageSummary',
    'unresolvedObligations',
    'continuity',
    'coldSuccessor',
    'privatePhysicalFlightCompleted',
    'physicalEstateQualified',
    'authority',
    'claimBoundary',
  ],
  privateRequest: [
    'schema',
    'profileId',
    'flightMode',
    'campaignLabel',
    'sourceObjectDigests',
    'identityClasses',
    'canonicalMissionStateDigest',
    'stageAttestations',
    'externalServiceCalls',
    'operationalCredentials',
    'attestationBoundary',
  ],
  privateIdentityClasses: [
    'personalFloor',
    'halo3',
    'initialHead',
    'successorHead',
    'graceBind',
    'lattice',
    'leftCell',
    'rightCell',
  ],
  stageAttestation: [
    'stage',
    'terminalState',
    'canonicalMissionStateIdBefore',
    'canonicalMissionStateIdAfter',
    'observation',
    'evidenceBodies',
  ],
  evidenceBody: ['path', 'mediaType', 'evidenceClass'],
  disposition: [
    'schema',
    'dispositionId',
    'runId',
    'profileId',
    'flightMode',
    'stageReceiptIds',
    'stageCount',
    'successfulStageCount',
    'humanRequiredStageCount',
    'evidenceDigestRoot',
    'privatePhysicalEvidenceBodyCount',
    'publicEvidenceBodyCount',
    'privatePhysicalFlightCompleted',
    'selfAttestationOnly',
    'physicalEstateQualified',
    'representativeOperatorQualified',
    'fieldNetworkQualified',
    'operationalC2Qualified',
    'productionLatticeQualified',
    'authority',
    'claimBoundary',
  ],
});

export class StcMaryPhysicalFlightError extends Error {
  constructor(code, message) {
    super(message);
    this.name = 'StcMaryPhysicalFlightError';
    this.code = code;
  }
}

function requireCondition(condition, code, message) {
  if (!condition) throw new StcMaryPhysicalFlightError(code, message);
}

function isRecord(value) {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) return false;
  const prototype = Object.getPrototypeOf(value);
  return prototype === Object.prototype || prototype === null;
}

function exactKeys(value, expected, code, label) {
  requireCondition(isRecord(value), code, `${label} must be an object`);
  requireCondition(
    canonicalJson(Object.keys(value).sort()) === canonicalJson([...expected].sort()),
    code,
    `${label} fields differ`,
  );
}

function boundedString(value, code, label, max = MAX_STRING) {
  requireCondition(typeof value === 'string', code, `${label} must be a string`);
  const normalized = value.trim();
  requireCondition(normalized.length > 0 && normalized.length <= max, code, `${label} is empty or unbounded`);
  return normalized;
}

function safeInteger(value, min, max, code, label) {
  requireCondition(Number.isSafeInteger(value) && value >= min && value <= max, code, `${label} is outside ${min}..${max}`);
  return value;
}

function uniqueStrings(values, code, label, allowEmpty = false) {
  requireCondition(Array.isArray(values), code, `${label} must be an array`);
  requireCondition(allowEmpty || values.length > 0, code, `${label} must be non-empty`);
  requireCondition(values.every((value) => typeof value === 'string' && value.trim().length > 0), code, `${label} contains an invalid value`);
  requireCondition(new Set(values).size === values.length, code, `${label} contains duplicates`);
}

function digest(prefix, value) {
  return `${prefix}_${createHash('sha256').update(canonicalJson(value), 'utf8').digest('hex')}`;
}

function sha256Bytes(bytes) {
  return createHash('sha256').update(bytes).digest('hex');
}

function bodyWithoutId(value, idKey) {
  const copy = structuredClone(value);
  delete copy[idKey];
  return copy;
}

function assertIdentity(value, prefix, idKey, code) {
  requireCondition(value[idKey] === digest(prefix, bodyWithoutId(value, idKey)), code, `${idKey} differs from content identity`);
}

function exactObject(value, expected, code, label) {
  requireCondition(canonicalJson(value) === canonicalJson(expected), code, `${label} differs`);
}

function assertSha256(value, code, label) {
  requireCondition(typeof value === 'string' && SHA256.test(value), code, `${label} is not a lowercase SHA-256 digest`);
}

function assertContentId(value, code, label) {
  requireCondition(typeof value === 'string' && CONTENT_ID.test(value), code, `${label} is not a content identity`);
}

function assertNoPublicPrivateMaterial(value, code, label) {
  const encoded = canonicalJson(value);
  const forbidden = [
    /[A-Za-z]:\\\\/,
    /\/home\//,
    /ssh:\/\//i,
    /https?:\/\//i,
    /Authorization:\s*Bearer/i,
    /BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY/i,
    /OCTO-(W|L)[0-9]+/i,
  ];
  for (const pattern of forbidden) {
    requireCondition(!pattern.test(encoded), code, `${label} contains private, endpoint, credential, or key-shaped material`);
  }
}

function requiredState(stage) {
  return REQUIRED_STAGE_TERMINALS[stage];
}

function validateStringArray(values, expected, code, label) {
  uniqueStrings(values, code, label);
  requireCondition(canonicalJson(values) === canonicalJson(expected), code, `${label} differs`);
}

export function validateStcMaryPhysicalFlightProfile(profile) {
  exactKeys(profile, KEYS.profile, 'PHYSICAL_FLIGHT_PROFILE_INVALID', 'physical-flight profile');
  requireCondition(profile.schema === 'spectra-anchor-node-stc-mary-physical-flight-profile/1', 'PHYSICAL_FLIGHT_PROFILE_SCHEMA_INVALID', 'profile schema differs');
  requireCondition(profile.profileId === 'spectra-anchor-node/stc-mary-physical-flight/0.1', 'PHYSICAL_FLIGHT_PROFILE_INVALID', 'profile identity differs');
  requireCondition(canonicalJson(profile.issues) === canonicalJson([26, 29]), 'PHYSICAL_FLIGHT_PROFILE_INVALID', 'issue coordinates differ');
  requireCondition(profile.status === 'candidate_design_only', 'PHYSICAL_FLIGHT_PROFILE_INVALID', 'profile status differs');
  exactKeys(profile.predecessor, KEYS.predecessor, 'PHYSICAL_FLIGHT_PROFILE_INVALID', 'profile predecessor');
  requireCondition(profile.predecessor.repository === 'BigBirdReturns/ai-execution-audit' && profile.predecessor.evidenceTier === 'admitted_synthetic_terminal', 'PHYSICAL_FLIGHT_PROFILE_INVALID', 'predecessor repository or tier differs');
  requireCondition(Array.isArray(profile.predecessor.requiredObjects) && profile.predecessor.requiredObjects.length === 4, 'PHYSICAL_FLIGHT_PROFILE_INVALID', 'predecessor object denominator differs');
  const predecessorIds = new Set();
  for (const row of profile.predecessor.requiredObjects) {
    exactKeys(row, KEYS.predecessorObject, 'PHYSICAL_FLIGHT_PROFILE_INVALID', 'predecessor object');
    boundedString(row.schema, 'PHYSICAL_FLIGHT_PROFILE_INVALID', 'predecessor schema');
    assertContentId(row.objectId, 'PHYSICAL_FLIGHT_PROFILE_INVALID', 'predecessor objectId');
    requireCondition(!predecessorIds.has(row.objectId), 'PHYSICAL_FLIGHT_PROFILE_INVALID', 'predecessor object identity is duplicated');
    predecessorIds.add(row.objectId);
  }
  validateStringArray(profile.flightModes, [...FLIGHT_MODES], 'PHYSICAL_FLIGHT_PROFILE_INVALID', 'flight modes');
  validateStringArray(profile.stageSequence, STC_MARY_STAGES, 'PHYSICAL_FLIGHT_PROFILE_INVALID', 'stage sequence');
  exactKeys(profile.stagePolicy, KEYS.stagePolicy, 'PHYSICAL_FLIGHT_PROFILE_INVALID', 'stage policy');
  requireCondition(canonicalJson(profile.stagePolicy.requiredTerminalStates) === canonicalJson(REQUIRED_STAGE_TERMINALS), 'PHYSICAL_FLIGHT_PROFILE_INVALID', 'required terminal states differ');
  validateStringArray(profile.stagePolicy.prohibitedSuccessStates, [...PROHIBITED_SUCCESS_STATES], 'PHYSICAL_FLIGHT_PROFILE_INVALID', 'prohibited success states');
  requireCondition(
    profile.stagePolicy.previousReceiptChainingRequired === true &&
      profile.stagePolicy.completeDenominatorRequired === true &&
      profile.stagePolicy.canonicalMissionStateMutationAllowed === false &&
      profile.stagePolicy.unresolvedConflictMustRemainExplicit === true,
    'PHYSICAL_FLIGHT_PROFILE_INVALID',
    'stage policy widens custody or permits state mutation',
  );
  exactKeys(profile.substrateRoles, KEYS.substrateRoles, 'PHYSICAL_FLIGHT_PROFILE_INVALID', 'substrate roles');
  requireCondition(
    profile.substrateRoles.personalFloor.role === 'resident_mission_closed_floor' &&
      profile.substrateRoles.personalFloor.requiredForContinuity === true &&
      profile.substrateRoles.personalFloor.mustSurviveHalo3Removal === true &&
      profile.substrateRoles.personalFloor.mustSurviveLatticeRemoval === true,
    'PHYSICAL_FLIGHT_PROFILE_INVALID',
    'personal floor contract differs',
  );
  requireCondition(
    profile.substrateRoles.halo3.role === 'optional_high_bandwidth_accelerator' &&
      profile.substrateRoles.halo3.requiredForContinuity === false &&
      profile.substrateRoles.halo3.removalMayReducePerformanceOnly === true,
    'PHYSICAL_FLIGHT_PROFILE_INVALID',
    'HALO3 contract differs',
  );
  requireCondition(profile.substrateRoles.head.replaceable === true && profile.substrateRoles.head.canonicalStateOwner === false, 'PHYSICAL_FLIGHT_PROFILE_INVALID', 'HEAD contract differs');
  requireCondition(profile.substrateRoles.modelOrExecutable.replaceable === true && profile.substrateRoles.modelOrExecutable.authoritySource === false, 'PHYSICAL_FLIGHT_PROFILE_INVALID', 'model or executable contract differs');
  requireCondition(profile.substrateRoles.lattice.requiredForLocalContinuity === false && profile.substrateRoles.lattice.canonicalStateOwner === false, 'PHYSICAL_FLIGHT_PROFILE_INVALID', 'Lattice contract differs');
  exactKeys(profile.authorityPolicy, KEYS.authorityPolicy, 'PHYSICAL_FLIGHT_PROFILE_INVALID', 'authority policy');
  requireCondition(
    profile.authorityPolicy.namedHumanBind === 'GRACE' &&
      profile.authorityPolicy.humanBindRequired === true &&
      profile.authorityPolicy.modelAuthority === 'none' &&
      profile.authorityPolicy.hardwareAuthority === 'none' &&
      profile.authorityPolicy.schedulerAuthority === 'none' &&
      profile.authorityPolicy.verifierAuthority === 'none' &&
      profile.authorityPolicy.returningConflictDisposition === 'human_required' &&
      profile.authorityPolicy.automaticConflictMergeAllowed === false,
    'PHYSICAL_FLIGHT_PROFILE_INVALID',
    'authority policy differs',
  );
  exactKeys(profile.evidencePolicy, KEYS.evidencePolicy, 'PHYSICAL_FLIGHT_PROFILE_INVALID', 'evidence policy');
  requireCondition(
    profile.evidencePolicy.publicRepositoryMayContainPrivateEvidenceBodies === false &&
      profile.evidencePolicy.publicDispositionDigestOnly === true &&
      profile.evidencePolicy.privateBodyPathsMayAppearInPublicDisposition === false &&
      profile.evidencePolicy.minimumEvidenceBodiesPerPhysicalStage === 1 &&
      profile.evidencePolicy.contentAddressing === 'sha256' &&
      profile.evidencePolicy.syntheticModeCanClaimPhysicalFlight === false &&
      profile.evidencePolicy.privateAttestationCanClaimRepresentativeOperatorQualification === false &&
      profile.evidencePolicy.privateAttestationCanClaimFieldQualification === false,
    'PHYSICAL_FLIGHT_PROFILE_INVALID',
    'evidence policy differs',
  );
  exactKeys(profile.acceptance, KEYS.acceptance, 'PHYSICAL_FLIGHT_PROFILE_INVALID', 'acceptance policy');
  uniqueStrings(profile.acceptance.requires, 'PHYSICAL_FLIGHT_PROFILE_INVALID', 'acceptance requirements');
  uniqueStrings(profile.acceptance.refuseIf, 'PHYSICAL_FLIGHT_PROFILE_INVALID', 'acceptance refusals');
  exactKeys(profile.claimBoundary, KEYS.profileClaim, 'PHYSICAL_FLIGHT_PROFILE_INVALID', 'profile claim boundary');
  requireCondition(
    profile.claimBoundary.syntheticHarnessCandidate === true &&
      Object.entries(profile.claimBoundary).filter(([key]) => key !== 'syntheticHarnessCandidate').every(([, value]) => value === false),
    'PHYSICAL_FLIGHT_PROFILE_INVALID',
    'profile claim boundary widens authority or qualification',
  );
  assertNoPublicPrivateMaterial(profile, 'PHYSICAL_FLIGHT_PROFILE_PRIVATE_MATERIAL', 'physical-flight profile');
  return profile;
}

export function validateSyntheticPhysicalFlightFixture(fixture, profile = undefined) {
  exactKeys(fixture, KEYS.fixture, 'PHYSICAL_FLIGHT_FIXTURE_INVALID', 'physical-flight fixture');
  requireCondition(fixture.schema === 'spectra-anchor-node-stc-mary-physical-flight-fixture/1', 'PHYSICAL_FLIGHT_FIXTURE_SCHEMA_INVALID', 'fixture schema differs');
  requireCondition(fixture.fixtureId.startsWith('SYN-STC-MARY-'), 'PHYSICAL_FLIGHT_FIXTURE_INVALID', 'fixture identity is not synthetic');
  requireCondition(fixture.classification === 'invented_unclassified_synthetic_only' && fixture.flightMode === 'synthetic_simulation', 'PHYSICAL_FLIGHT_FIXTURE_INVALID', 'fixture classification or mode differs');
  if (profile !== undefined) {
    validateStcMaryPhysicalFlightProfile(profile);
    requireCondition(fixture.profileId === profile.profileId, 'PHYSICAL_FLIGHT_FIXTURE_INVALID', 'fixture belongs to another profile');
    const requiredIds = new Set(profile.predecessor.requiredObjects.map((row) => row.objectId));
    requireCondition(fixture.sourceObjects.every((row) => requiredIds.has(row)), 'PHYSICAL_FLIGHT_FIXTURE_INVALID', 'fixture names an undeclared predecessor');
  }
  boundedString(fixture.campaignLabel, 'PHYSICAL_FLIGHT_FIXTURE_INVALID', 'campaignLabel');
  uniqueStrings(fixture.sourceObjects, 'PHYSICAL_FLIGHT_FIXTURE_INVALID', 'sourceObjects');
  requireCondition(fixture.sourceObjects.length === 3 && fixture.sourceObjects.every((row) => CONTENT_ID.test(row)), 'PHYSICAL_FLIGHT_FIXTURE_INVALID', 'fixture source object denominator differs');
  exactKeys(fixture.identities, KEYS.fixtureIdentities, 'PHYSICAL_FLIGHT_FIXTURE_INVALID', 'fixture identities');
  for (const [key, value] of Object.entries(fixture.identities)) {
    if (key === 'cellIds') continue;
    requireCondition(typeof value === 'string' && value.startsWith('SYN-'), 'PHYSICAL_FLIGHT_FIXTURE_INVALID', `${key} is not synthetic`);
  }
  uniqueStrings(fixture.identities.cellIds, 'PHYSICAL_FLIGHT_FIXTURE_INVALID', 'cellIds');
  requireCondition(fixture.identities.cellIds.length === 2 && fixture.identities.cellIds.every((row) => row.startsWith('SYN-CELL-')), 'PHYSICAL_FLIGHT_FIXTURE_INVALID', 'cell identity denominator differs');
  exactKeys(fixture.digests, KEYS.fixtureDigests, 'PHYSICAL_FLIGHT_FIXTURE_INVALID', 'fixture digests');
  for (const [key, value] of Object.entries(fixture.digests)) assertSha256(value, 'PHYSICAL_FLIGHT_FIXTURE_INVALID', key);
  exactKeys(fixture.syntheticMetrics, KEYS.syntheticMetrics, 'PHYSICAL_FLIGHT_FIXTURE_INVALID', 'synthetic metrics');
  boundedString(fixture.syntheticMetrics.unit, 'PHYSICAL_FLIGHT_FIXTURE_INVALID', 'metric unit');
  safeInteger(fixture.syntheticMetrics.personalFloorBaseline, 1, 1_000_000, 'PHYSICAL_FLIGHT_FIXTURE_INVALID', 'personal floor baseline');
  safeInteger(fixture.syntheticMetrics.halo3Accelerated, 1, 1_000_000, 'PHYSICAL_FLIGHT_FIXTURE_INVALID', 'HALO3 accelerated metric');
  safeInteger(fixture.syntheticMetrics.personalFloorAfterHalo3Removal, 1, 1_000_000, 'PHYSICAL_FLIGHT_FIXTURE_INVALID', 'post-removal metric');
  requireCondition(
    fixture.syntheticMetrics.halo3Accelerated > fixture.syntheticMetrics.personalFloorBaseline &&
      fixture.syntheticMetrics.personalFloorAfterHalo3Removal === fixture.syntheticMetrics.personalFloorBaseline,
    'PHYSICAL_FLIGHT_FIXTURE_INVALID',
    'fixture does not prove acceleration and resident-floor continuity',
  );
  exactKeys(fixture.expectedConflict, KEYS.expectedConflict, 'PHYSICAL_FLIGHT_FIXTURE_INVALID', 'expected conflict');
  assertSha256(fixture.expectedConflict.leftCellStateDigest, 'PHYSICAL_FLIGHT_FIXTURE_INVALID', 'left cell state digest');
  assertSha256(fixture.expectedConflict.rightCellStateDigest, 'PHYSICAL_FLIGHT_FIXTURE_INVALID', 'right cell state digest');
  requireCondition(
    fixture.expectedConflict.leftCellStateDigest !== fixture.expectedConflict.rightCellStateDigest &&
      fixture.expectedConflict.automaticMergeAllowed === false &&
      fixture.expectedConflict.requiredDisposition === 'human_required',
    'PHYSICAL_FLIGHT_FIXTURE_INVALID',
    'fixture conflict contract differs',
  );
  requireCondition(
    fixture.externalServiceCalls === 0 &&
      fixture.operationalCredentials === 0 &&
      fixture.physicalEvidenceBodies === 0 &&
      fixture.authority === 'none',
    'PHYSICAL_FLIGHT_FIXTURE_CLAIM_INVALID',
    'fixture widens its dependency, evidence, or authority claim',
  );
  assertNoPublicPrivateMaterial(fixture, 'PHYSICAL_FLIGHT_FIXTURE_PRIVATE_MATERIAL', 'physical-flight fixture');
  return fixture;
}

export function createPhysicalFlightCampaignSeed({ profile, sourceId, flightMode }) {
  validateStcMaryPhysicalFlightProfile(profile);
  boundedString(sourceId, 'PHYSICAL_FLIGHT_SEED_INVALID', 'sourceId');
  requireCondition(FLIGHT_MODES.has(flightMode), 'PHYSICAL_FLIGHT_SEED_INVALID', 'flight mode differs');
  const body = {
    schema: 'stc-mary-physical-flight-campaign-seed/1',
    profileId: profile.profileId,
    sourceId,
    flightMode,
    stageSequenceDigest: digest('stcmarystagesequence1', profile.stageSequence),
    authority: 'none',
    claimBoundary: 'Content-addressed seed for one bounded STC and MARY physical-flight campaign. It grants no execution, physical, mission, command, targeting, engagement, effector, or weapons authority.',
  };
  return { ...body, campaignSeedId: digest('stcmaryphysicalflightseed1', body) };
}

export function validatePhysicalFlightCampaignSeed(seed, profile = undefined) {
  exactKeys(seed, KEYS.seed, 'PHYSICAL_FLIGHT_SEED_INVALID', 'campaign seed');
  requireCondition(seed.schema === 'stc-mary-physical-flight-campaign-seed/1', 'PHYSICAL_FLIGHT_SEED_SCHEMA_INVALID', 'campaign seed schema differs');
  requireCondition(FLIGHT_MODES.has(seed.flightMode) && seed.authority === 'none', 'PHYSICAL_FLIGHT_SEED_INVALID', 'campaign seed mode or authority differs');
  assertContentId(seed.stageSequenceDigest, 'PHYSICAL_FLIGHT_SEED_INVALID', 'stage sequence digest');
  assertIdentity(seed, 'stcmaryphysicalflightseed1', 'campaignSeedId', 'PHYSICAL_FLIGHT_SEED_ID_INVALID');
  if (profile !== undefined) {
    validateStcMaryPhysicalFlightProfile(profile);
    requireCondition(seed.profileId === profile.profileId && seed.stageSequenceDigest === digest('stcmarystagesequence1', profile.stageSequence), 'PHYSICAL_FLIGHT_SEED_BINDING_INVALID', 'campaign seed belongs to another profile or stage sequence');
  }
  return seed;
}

function createEvidenceDescriptor({ stage, evidenceClass, mediaType, sha256, bytes }) {
  requireCondition(STC_MARY_STAGES.includes(stage), 'PHYSICAL_FLIGHT_EVIDENCE_INVALID', 'evidence stage differs');
  requireCondition(EVIDENCE_CLASSES.has(evidenceClass), 'PHYSICAL_FLIGHT_EVIDENCE_INVALID', 'evidence class differs');
  boundedString(mediaType, 'PHYSICAL_FLIGHT_EVIDENCE_INVALID', 'mediaType', 256);
  assertSha256(sha256, 'PHYSICAL_FLIGHT_EVIDENCE_INVALID', 'evidence sha256');
  safeInteger(bytes, 1, MAX_EVIDENCE_BYTES, 'PHYSICAL_FLIGHT_EVIDENCE_INVALID', 'evidence bytes');
  const body = {
    schema: 'stc-mary-physical-flight-evidence-descriptor/1',
    stage,
    evidenceClass,
    mediaType,
    sha256,
    bytes,
    bodyPresent: false,
    authority: 'none',
    claimBoundary: 'Digest-only evidence descriptor. The evidence body remains outside this receipt and grants no mission, command, targeting, engagement, effector, or weapons authority.',
  };
  return { ...body, evidenceId: digest('stcmaryphysicalflightevidence1', body) };
}

export function validatePhysicalFlightEvidenceDescriptor(evidence, { stage, flightMode } = {}) {
  exactKeys(evidence, KEYS.evidence, 'PHYSICAL_FLIGHT_EVIDENCE_INVALID', 'evidence descriptor');
  requireCondition(evidence.schema === 'stc-mary-physical-flight-evidence-descriptor/1', 'PHYSICAL_FLIGHT_EVIDENCE_SCHEMA_INVALID', 'evidence descriptor schema differs');
  requireCondition(STC_MARY_STAGES.includes(evidence.stage), 'PHYSICAL_FLIGHT_EVIDENCE_INVALID', 'evidence stage differs');
  requireCondition(EVIDENCE_CLASSES.has(evidence.evidenceClass), 'PHYSICAL_FLIGHT_EVIDENCE_INVALID', 'evidence class differs');
  assertSha256(evidence.sha256, 'PHYSICAL_FLIGHT_EVIDENCE_INVALID', 'evidence sha256');
  safeInteger(evidence.bytes, 1, MAX_EVIDENCE_BYTES, 'PHYSICAL_FLIGHT_EVIDENCE_INVALID', 'evidence bytes');
  requireCondition(evidence.bodyPresent === false && evidence.authority === 'none', 'PHYSICAL_FLIGHT_EVIDENCE_CLAIM_INVALID', 'evidence descriptor embeds a body or authority');
  assertIdentity(evidence, 'stcmaryphysicalflightevidence1', 'evidenceId', 'PHYSICAL_FLIGHT_EVIDENCE_ID_INVALID');
  if (stage !== undefined) requireCondition(evidence.stage === stage, 'PHYSICAL_FLIGHT_EVIDENCE_BINDING_INVALID', 'evidence belongs to another stage');
  if (flightMode === 'synthetic_simulation') requireCondition(evidence.evidenceClass === 'synthetic_deterministic_receipt', 'PHYSICAL_FLIGHT_EVIDENCE_BINDING_INVALID', 'synthetic run carries private evidence');
  if (flightMode === 'private_physical_attested') requireCondition(evidence.evidenceClass !== 'synthetic_deterministic_receipt', 'PHYSICAL_FLIGHT_EVIDENCE_BINDING_INVALID', 'private flight carries synthetic evidence');
  return evidence;
}

function createSyntheticEvidence(stage, observation) {
  const bytes = Buffer.from(canonicalJson(observation), 'utf8');
  return createEvidenceDescriptor({
    stage,
    evidenceClass: 'synthetic_deterministic_receipt',
    mediaType: 'application/json',
    sha256: sha256Bytes(bytes),
    bytes: bytes.length,
  });
}

function validateObservation(stage, observation) {
  requireCondition(isRecord(observation), 'PHYSICAL_FLIGHT_OBSERVATION_INVALID', `${stage} observation must be an object`);
  switch (stage) {
    case 'VERIFY_INPUTS':
      exactKeys(observation, ['profileValidated', 'sourceObjectsVerified', 'inputDigestRoot'], 'PHYSICAL_FLIGHT_OBSERVATION_INVALID', stage);
      requireCondition(observation.profileValidated === true && observation.sourceObjectsVerified === true, 'PHYSICAL_FLIGHT_OBSERVATION_INVALID', `${stage} did not verify inputs`);
      assertContentId(observation.inputDigestRoot, 'PHYSICAL_FLIGHT_OBSERVATION_INVALID', 'inputDigestRoot');
      break;
    case 'MOUNT_PERSONAL_FLOOR':
      exactKeys(observation, ['personalFloorSeatIdentityClass', 'mounted', 'missionClosed'], 'PHYSICAL_FLIGHT_OBSERVATION_INVALID', stage);
      boundedString(observation.personalFloorSeatIdentityClass, 'PHYSICAL_FLIGHT_OBSERVATION_INVALID', 'personal floor identity class');
      requireCondition(observation.mounted === true && observation.missionClosed === true, 'PHYSICAL_FLIGHT_OBSERVATION_INVALID', `${stage} did not establish the resident floor`);
      break;
    case 'BIND_GRACE':
      exactKeys(observation, ['humanBindIdentityClass', 'bound', 'authoritySource'], 'PHYSICAL_FLIGHT_OBSERVATION_INVALID', stage);
      boundedString(observation.humanBindIdentityClass, 'PHYSICAL_FLIGHT_OBSERVATION_INVALID', 'human bind identity class');
      requireCondition(observation.bound === true && observation.authoritySource === 'named_human_bind', 'PHYSICAL_FLIGHT_OBSERVATION_INVALID', `${stage} did not preserve human authority`);
      break;
    case 'RUN_PERSONAL_FLOOR_BASELINE':
      exactKeys(observation, ['outputDigest', 'throughputUnits', 'verifierState'], 'PHYSICAL_FLIGHT_OBSERVATION_INVALID', stage);
      assertContentId(observation.outputDigest, 'PHYSICAL_FLIGHT_OBSERVATION_INVALID', 'baseline output digest');
      safeInteger(observation.throughputUnits, 1, 1_000_000_000, 'PHYSICAL_FLIGHT_OBSERVATION_INVALID', 'baseline throughput');
      requireCondition(observation.verifierState === 'pass', 'PHYSICAL_FLIGHT_OBSERVATION_INVALID', `${stage} verifier did not pass`);
      break;
    case 'ATTACH_HALO3':
      exactKeys(observation, ['halo3SeatIdentityClass', 'attached', 'optional'], 'PHYSICAL_FLIGHT_OBSERVATION_INVALID', stage);
      boundedString(observation.halo3SeatIdentityClass, 'PHYSICAL_FLIGHT_OBSERVATION_INVALID', 'HALO3 identity class');
      requireCondition(observation.attached === true && observation.optional === true, 'PHYSICAL_FLIGHT_OBSERVATION_INVALID', `${stage} changed HALO3 optionality`);
      break;
    case 'RUN_HALO3_ACCELERATED':
      exactKeys(observation, ['outputDigest', 'throughputUnits', 'verifierState', 'fasterThanBaseline'], 'PHYSICAL_FLIGHT_OBSERVATION_INVALID', stage);
      assertContentId(observation.outputDigest, 'PHYSICAL_FLIGHT_OBSERVATION_INVALID', 'accelerated output digest');
      safeInteger(observation.throughputUnits, 1, 1_000_000_000, 'PHYSICAL_FLIGHT_OBSERVATION_INVALID', 'accelerated throughput');
      requireCondition(observation.verifierState === 'pass' && observation.fasterThanBaseline === true, 'PHYSICAL_FLIGHT_OBSERVATION_INVALID', `${stage} did not prove acceleration`);
      break;
    case 'REMOVE_HALO3':
      exactKeys(observation, ['halo3SeatIdentityClass', 'attached', 'removalReceiptPresent'], 'PHYSICAL_FLIGHT_OBSERVATION_INVALID', stage);
      boundedString(observation.halo3SeatIdentityClass, 'PHYSICAL_FLIGHT_OBSERVATION_INVALID', 'HALO3 identity class');
      requireCondition(observation.attached === false && observation.removalReceiptPresent === true, 'PHYSICAL_FLIGHT_OBSERVATION_INVALID', `${stage} did not prove removal`);
      break;
    case 'VERIFY_PERSONAL_FLOOR_CONTINUITY':
      exactKeys(observation, ['personalFloorAvailable', 'outputDigestMatches', 'halo3Required', 'throughputUnits'], 'PHYSICAL_FLIGHT_OBSERVATION_INVALID', stage);
      requireCondition(observation.personalFloorAvailable === true && observation.outputDigestMatches === true && observation.halo3Required === false, 'PHYSICAL_FLIGHT_OBSERVATION_INVALID', `${stage} lost resident-floor continuity`);
      safeInteger(observation.throughputUnits, 1, 1_000_000_000, 'PHYSICAL_FLIGHT_OBSERVATION_INVALID', 'post-removal throughput');
      break;
    case 'REMOVE_LATTICE':
      exactKeys(observation, ['latticeIdentityClass', 'present', 'removalReceiptPresent'], 'PHYSICAL_FLIGHT_OBSERVATION_INVALID', stage);
      boundedString(observation.latticeIdentityClass, 'PHYSICAL_FLIGHT_OBSERVATION_INVALID', 'Lattice identity class');
      requireCondition(observation.present === false && observation.removalReceiptPresent === true, 'PHYSICAL_FLIGHT_OBSERVATION_INVALID', `${stage} did not prove membrane removal`);
      break;
    case 'VERIFY_LOCAL_CONTINUITY':
      exactKeys(observation, ['localStateAvailable', 'latticeRequired', 'canonicalStateRecovered'], 'PHYSICAL_FLIGHT_OBSERVATION_INVALID', stage);
      requireCondition(observation.localStateAvailable === true && observation.latticeRequired === false && observation.canonicalStateRecovered === true, 'PHYSICAL_FLIGHT_OBSERVATION_INVALID', `${stage} lost local continuity`);
      break;
    case 'PARTITION_TWO_CELLS':
      exactKeys(observation, ['cellCount', 'cellIdentityClasses', 'eachCellLocallyValid', 'authorityWidened'], 'PHYSICAL_FLIGHT_OBSERVATION_INVALID', stage);
      safeInteger(observation.cellCount, 2, 2, 'PHYSICAL_FLIGHT_OBSERVATION_INVALID', 'cell count');
      uniqueStrings(observation.cellIdentityClasses, 'PHYSICAL_FLIGHT_OBSERVATION_INVALID', 'cell identity classes');
      requireCondition(observation.cellIdentityClasses.length === 2 && observation.eachCellLocallyValid === true && observation.authorityWidened === false, 'PHYSICAL_FLIGHT_OBSERVATION_INVALID', `${stage} did not create two bounded cells`);
      break;
    case 'RESTORE_LINK_HOLD_CONFLICT':
      exactKeys(observation, ['linkRestored', 'conflictDetected', 'automaticMerge', 'resolution', 'leftStateDigest', 'rightStateDigest'], 'PHYSICAL_FLIGHT_OBSERVATION_INVALID', stage);
      assertSha256(observation.leftStateDigest, 'PHYSICAL_FLIGHT_OBSERVATION_INVALID', 'left state digest');
      assertSha256(observation.rightStateDigest, 'PHYSICAL_FLIGHT_OBSERVATION_INVALID', 'right state digest');
      requireCondition(observation.leftStateDigest !== observation.rightStateDigest && observation.linkRestored === true && observation.conflictDetected === true && observation.automaticMerge === false && observation.resolution === 'human_required', 'PHYSICAL_FLIGHT_OBSERVATION_INVALID', `${stage} did not retain conflict`);
      break;
    case 'REPLACE_HEAD':
      exactKeys(observation, ['oldHeadIdentityClass', 'newHeadIdentityClass', 'replacementAccepted', 'canonicalStateCopiedByDigest', 'authorityTransferred'], 'PHYSICAL_FLIGHT_OBSERVATION_INVALID', stage);
      boundedString(observation.oldHeadIdentityClass, 'PHYSICAL_FLIGHT_OBSERVATION_INVALID', 'old HEAD identity class');
      boundedString(observation.newHeadIdentityClass, 'PHYSICAL_FLIGHT_OBSERVATION_INVALID', 'new HEAD identity class');
      requireCondition(observation.oldHeadIdentityClass !== observation.newHeadIdentityClass && observation.replacementAccepted === true && observation.canonicalStateCopiedByDigest === true && observation.authorityTransferred === false, 'PHYSICAL_FLIGHT_OBSERVATION_INVALID', `${stage} did not preserve replaceable-carrier semantics`);
      break;
    case 'REBUILD_PROJECTIONS':
      exactKeys(observation, ['projectionKinds', 'rebuiltFromCanonicalReceipts', 'projectionDigestRoot'], 'PHYSICAL_FLIGHT_OBSERVATION_INVALID', stage);
      validateStringArray(observation.projectionKinds, PROJECTION_KINDS, 'PHYSICAL_FLIGHT_OBSERVATION_INVALID', 'projection kinds');
      requireCondition(observation.rebuiltFromCanonicalReceipts === true, 'PHYSICAL_FLIGHT_OBSERVATION_INVALID', `${stage} did not rebuild from receipts`);
      assertContentId(observation.projectionDigestRoot, 'PHYSICAL_FLIGHT_OBSERVATION_INVALID', 'projection digest root');
      break;
    case 'COLD_SUCCESSOR_VERIFY':
      exactKeys(observation, ['successorHeadIdentityClass', 'recoveredCartridge', 'recoveredAuthorityBoundary', 'recoveredObligations', 'verificationState'], 'PHYSICAL_FLIGHT_OBSERVATION_INVALID', stage);
      boundedString(observation.successorHeadIdentityClass, 'PHYSICAL_FLIGHT_OBSERVATION_INVALID', 'successor HEAD identity class');
      requireCondition(observation.recoveredCartridge === true && observation.recoveredAuthorityBoundary === true && observation.recoveredObligations === true && observation.verificationState === 'pass', 'PHYSICAL_FLIGHT_OBSERVATION_INVALID', `${stage} did not reconstruct the operating state`);
      break;
    case 'SEAL_PRIVATE_EVIDENCE':
      exactKeys(observation, ['sealedEvidenceClass', 'evidenceDescriptorCount', 'publicDispositionBodyFree', 'privateEvidenceBodiesCommittedToGit'], 'PHYSICAL_FLIGHT_OBSERVATION_INVALID', stage);
      requireCondition(['synthetic_simulation', 'private_physical_attested'].includes(observation.sealedEvidenceClass), 'PHYSICAL_FLIGHT_OBSERVATION_INVALID', 'sealed evidence class differs');
      safeInteger(observation.evidenceDescriptorCount, 1, STC_MARY_STAGES.length * MAX_EVIDENCE_PER_STAGE, 'PHYSICAL_FLIGHT_OBSERVATION_INVALID', 'evidence descriptor count');
      requireCondition(observation.publicDispositionBodyFree === true && observation.privateEvidenceBodiesCommittedToGit === false, 'PHYSICAL_FLIGHT_OBSERVATION_INVALID', `${stage} leaked private evidence`);
      break;
    default:
      throw new StcMaryPhysicalFlightError('PHYSICAL_FLIGHT_OBSERVATION_INVALID', `unsupported stage ${stage}`);
  }
  return observation;
}

function createStageReceipt({
  seed,
  sequence,
  stage,
  terminalState,
  previousStageReceiptId,
  canonicalMissionStateIdBefore,
  canonicalMissionStateIdAfter,
  observation,
  evidence,
  unresolvedObligationIds,
}) {
  validatePhysicalFlightCampaignSeed(seed);
  safeInteger(sequence, 1, STC_MARY_STAGES.length, 'PHYSICAL_FLIGHT_STAGE_INVALID', 'stage sequence');
  requireCondition(STC_MARY_STAGES[sequence - 1] === stage, 'PHYSICAL_FLIGHT_STAGE_INVALID', 'stage order differs');
  requireCondition(TERMINAL_STATES.has(terminalState) && terminalState === requiredState(stage), 'PHYSICAL_FLIGHT_STAGE_INVALID', 'stage terminal state differs');
  if (sequence === 1) requireCondition(previousStageReceiptId === null, 'PHYSICAL_FLIGHT_STAGE_INVALID', 'first stage carries a predecessor');
  else assertContentId(previousStageReceiptId, 'PHYSICAL_FLIGHT_STAGE_INVALID', 'previousStageReceiptId');
  assertSha256(canonicalMissionStateIdBefore, 'PHYSICAL_FLIGHT_STAGE_INVALID', 'canonical state before');
  assertSha256(canonicalMissionStateIdAfter, 'PHYSICAL_FLIGHT_STAGE_INVALID', 'canonical state after');
  requireCondition(canonicalMissionStateIdBefore === canonicalMissionStateIdAfter, 'PHYSICAL_FLIGHT_STAGE_STATE_MUTATION', 'stage mutates canonical mission state');
  validateObservation(stage, observation);
  requireCondition(Array.isArray(evidence) && evidence.length > 0 && evidence.length <= MAX_EVIDENCE_PER_STAGE, 'PHYSICAL_FLIGHT_STAGE_EVIDENCE_INVALID', 'stage evidence denominator differs');
  for (const row of evidence) validatePhysicalFlightEvidenceDescriptor(row, { stage, flightMode: seed.flightMode });
  uniqueStrings(unresolvedObligationIds, 'PHYSICAL_FLIGHT_STAGE_INVALID', 'unresolved obligations', true);
  const body = {
    schema: 'stc-mary-physical-flight-stage-receipt/1',
    campaignSeedId: seed.campaignSeedId,
    sequence,
    stage,
    terminalState,
    previousStageReceiptId,
    canonicalMissionStateIdBefore,
    canonicalMissionStateIdAfter,
    observation: structuredClone(observation),
    evidence: structuredClone(evidence),
    unresolvedObligationIds: [...unresolvedObligationIds],
    effectClass: 'local_artifact_and_state_continuity_only',
    authority: 'none',
    claimBoundary: `Terminal receipt for ${stage}. It grants no mission, command, targeting, engagement, effector, weapons, model, hardware, scheduler, or verifier authority.`,
  };
  return { ...body, stageReceiptId: digest('stcmaryphysicalflightstage1', body) };
}

export function validatePhysicalFlightStageReceipt(receipt, { seed, sequence, previousStageReceiptId, obligationId } = {}) {
  exactKeys(receipt, KEYS.stageReceipt, 'PHYSICAL_FLIGHT_STAGE_INVALID', 'stage receipt');
  requireCondition(receipt.schema === 'stc-mary-physical-flight-stage-receipt/1', 'PHYSICAL_FLIGHT_STAGE_SCHEMA_INVALID', 'stage receipt schema differs');
  safeInteger(receipt.sequence, 1, STC_MARY_STAGES.length, 'PHYSICAL_FLIGHT_STAGE_INVALID', 'stage sequence');
  requireCondition(receipt.stage === STC_MARY_STAGES[receipt.sequence - 1], 'PHYSICAL_FLIGHT_STAGE_INVALID', 'stage order differs');
  requireCondition(TERMINAL_STATES.has(receipt.terminalState) && receipt.terminalState === requiredState(receipt.stage), 'PHYSICAL_FLIGHT_STAGE_TERMINAL_INVALID', 'stage terminal state differs');
  requireCondition(!PROHIBITED_SUCCESS_STATES.has(receipt.terminalState), 'PHYSICAL_FLIGHT_STAGE_TERMINAL_INVALID', 'prohibited state counted as terminal success');
  if (receipt.sequence === 1) requireCondition(receipt.previousStageReceiptId === null, 'PHYSICAL_FLIGHT_STAGE_CHAIN_INVALID', 'first stage carries a predecessor');
  else assertContentId(receipt.previousStageReceiptId, 'PHYSICAL_FLIGHT_STAGE_CHAIN_INVALID', 'previousStageReceiptId');
  assertSha256(receipt.canonicalMissionStateIdBefore, 'PHYSICAL_FLIGHT_STAGE_INVALID', 'canonical state before');
  assertSha256(receipt.canonicalMissionStateIdAfter, 'PHYSICAL_FLIGHT_STAGE_INVALID', 'canonical state after');
  requireCondition(receipt.canonicalMissionStateIdBefore === receipt.canonicalMissionStateIdAfter, 'PHYSICAL_FLIGHT_STAGE_STATE_MUTATION', 'stage mutates canonical mission state');
  validateObservation(receipt.stage, receipt.observation);
  requireCondition(Array.isArray(receipt.evidence) && receipt.evidence.length > 0 && receipt.evidence.length <= MAX_EVIDENCE_PER_STAGE, 'PHYSICAL_FLIGHT_STAGE_EVIDENCE_INVALID', 'stage evidence denominator differs');
  for (const row of receipt.evidence) validatePhysicalFlightEvidenceDescriptor(row, { stage: receipt.stage, flightMode: seed?.flightMode });
  uniqueStrings(receipt.unresolvedObligationIds, 'PHYSICAL_FLIGHT_STAGE_INVALID', 'unresolved obligations', true);
  const conflictIndex = STC_MARY_STAGES.indexOf('RESTORE_LINK_HOLD_CONFLICT') + 1;
  if (receipt.sequence < conflictIndex) requireCondition(receipt.unresolvedObligationIds.length === 0, 'PHYSICAL_FLIGHT_STAGE_OBLIGATION_INVALID', 'obligation appears before conflict');
  if (receipt.sequence >= conflictIndex && obligationId !== undefined) requireCondition(canonicalJson(receipt.unresolvedObligationIds) === canonicalJson([obligationId]), 'PHYSICAL_FLIGHT_STAGE_OBLIGATION_INVALID', 'conflict obligation was lost or replaced');
  requireCondition(receipt.effectClass === 'local_artifact_and_state_continuity_only' && receipt.authority === 'none', 'PHYSICAL_FLIGHT_STAGE_CLAIM_INVALID', 'stage widens its effect or authority');
  assertIdentity(receipt, 'stcmaryphysicalflightstage1', 'stageReceiptId', 'PHYSICAL_FLIGHT_STAGE_ID_INVALID');
  if (seed !== undefined) requireCondition(receipt.campaignSeedId === seed.campaignSeedId, 'PHYSICAL_FLIGHT_STAGE_BINDING_INVALID', 'stage belongs to another campaign seed');
  if (sequence !== undefined) requireCondition(receipt.sequence === sequence, 'PHYSICAL_FLIGHT_STAGE_BINDING_INVALID', 'stage sequence differs');
  if (previousStageReceiptId !== undefined) requireCondition(receipt.previousStageReceiptId === previousStageReceiptId, 'PHYSICAL_FLIGHT_STAGE_CHAIN_INVALID', 'stage chain differs');
  return receipt;
}

function syntheticOutputDigest(fixture) {
  return digest('stcmarymissionoutput1', {
    missionCartridge: fixture.digests.missionCartridge,
    localFeed: fixture.digests.localFeed,
    canonicalMissionState: fixture.digests.canonicalMissionState,
  });
}

function syntheticInputRoot(fixture) {
  return digest('stcmaryphysicalflightinputroot1', {
    sourceObjects: fixture.sourceObjects,
    digests: fixture.digests,
  });
}

function syntheticObservation(stage, { fixture, receipts, obligationId }) {
  const outputDigest = syntheticOutputDigest(fixture);
  switch (stage) {
    case 'VERIFY_INPUTS':
      return { profileValidated: true, sourceObjectsVerified: true, inputDigestRoot: syntheticInputRoot(fixture) };
    case 'MOUNT_PERSONAL_FLOOR':
      return { personalFloorSeatIdentityClass: fixture.identities.personalFloorSeatId, mounted: true, missionClosed: true };
    case 'BIND_GRACE':
      return { humanBindIdentityClass: fixture.identities.graceBindId, bound: true, authoritySource: 'named_human_bind' };
    case 'RUN_PERSONAL_FLOOR_BASELINE':
      return { outputDigest, throughputUnits: fixture.syntheticMetrics.personalFloorBaseline, verifierState: 'pass' };
    case 'ATTACH_HALO3':
      return { halo3SeatIdentityClass: fixture.identities.halo3SeatId, attached: true, optional: true };
    case 'RUN_HALO3_ACCELERATED':
      return { outputDigest, throughputUnits: fixture.syntheticMetrics.halo3Accelerated, verifierState: 'pass', fasterThanBaseline: true };
    case 'REMOVE_HALO3':
      return { halo3SeatIdentityClass: fixture.identities.halo3SeatId, attached: false, removalReceiptPresent: true };
    case 'VERIFY_PERSONAL_FLOOR_CONTINUITY':
      return { personalFloorAvailable: true, outputDigestMatches: true, halo3Required: false, throughputUnits: fixture.syntheticMetrics.personalFloorAfterHalo3Removal };
    case 'REMOVE_LATTICE':
      return { latticeIdentityClass: fixture.identities.latticeId, present: false, removalReceiptPresent: true };
    case 'VERIFY_LOCAL_CONTINUITY':
      return { localStateAvailable: true, latticeRequired: false, canonicalStateRecovered: true };
    case 'PARTITION_TWO_CELLS':
      return { cellCount: 2, cellIdentityClasses: fixture.identities.cellIds, eachCellLocallyValid: true, authorityWidened: false };
    case 'RESTORE_LINK_HOLD_CONFLICT':
      return {
        linkRestored: true,
        conflictDetected: true,
        automaticMerge: false,
        resolution: 'human_required',
        leftStateDigest: fixture.expectedConflict.leftCellStateDigest,
        rightStateDigest: fixture.expectedConflict.rightCellStateDigest,
      };
    case 'REPLACE_HEAD':
      return {
        oldHeadIdentityClass: fixture.identities.initialHeadId,
        newHeadIdentityClass: fixture.identities.successorHeadId,
        replacementAccepted: true,
        canonicalStateCopiedByDigest: true,
        authorityTransferred: false,
      };
    case 'REBUILD_PROJECTIONS':
      return {
        projectionKinds: PROJECTION_KINDS,
        rebuiltFromCanonicalReceipts: true,
        projectionDigestRoot: digest('stcmaryprojectionroot1', receipts.map((row) => row.stageReceiptId)),
      };
    case 'COLD_SUCCESSOR_VERIFY':
      return {
        successorHeadIdentityClass: fixture.identities.successorHeadId,
        recoveredCartridge: true,
        recoveredAuthorityBoundary: true,
        recoveredObligations: obligationId !== null,
        verificationState: 'pass',
      };
    case 'SEAL_PRIVATE_EVIDENCE':
      return {
        sealedEvidenceClass: 'synthetic_simulation',
        evidenceDescriptorCount: receipts.flatMap((row) => row.evidence).length + 1,
        publicDispositionBodyFree: true,
        privateEvidenceBodiesCommittedToGit: false,
      };
    default:
      throw new StcMaryPhysicalFlightError('PHYSICAL_FLIGHT_STAGE_INVALID', `unsupported stage ${stage}`);
  }
}

function buildRunBody({ profile, sourceId, flightMode, seed, receipts, privatePhysicalEvidenceBodyCount }) {
  const conflict = receipts.find((row) => row.stage === 'RESTORE_LINK_HOLD_CONFLICT');
  const baseline = receipts.find((row) => row.stage === 'RUN_PERSONAL_FLOOR_BASELINE');
  const accelerated = receipts.find((row) => row.stage === 'RUN_HALO3_ACCELERATED');
  const continuity = receipts.find((row) => row.stage === 'VERIFY_PERSONAL_FLOOR_CONTINUITY');
  const successfulStageCount = receipts.filter((row) => row.terminalState === 'PASS').length;
  const humanRequiredStageCount = receipts.filter((row) => row.terminalState === 'HUMAN_REQUIRED').length;
  const refusedStageCount = receipts.filter((row) => row.terminalState === 'REFUSED').length;
  const body = {
    schema: 'stc-mary-physical-flight-run/1',
    profileId: profile.profileId,
    sourceId,
    flightMode,
    campaignSeed: seed,
    stageDenominator: [...STC_MARY_STAGES],
    stageReceipts: receipts,
    stageCount: receipts.length,
    successfulStageCount,
    humanRequiredStageCount,
    refusedStageCount,
    pendingStageCount: 0,
    canonicalMissionStateIdBefore: receipts[0].canonicalMissionStateIdBefore,
    canonicalMissionStateIdAfter: receipts.at(-1).canonicalMissionStateIdAfter,
    canonicalMissionStateUnchanged: receipts.every((row) => row.canonicalMissionStateIdBefore === row.canonicalMissionStateIdAfter) && receipts[0].canonicalMissionStateIdBefore === receipts.at(-1).canonicalMissionStateIdAfter,
    personalFloorBaselineVerified: baseline.terminalState === 'PASS' && baseline.observation.verifierState === 'pass',
    halo3AccelerationVerified: accelerated.terminalState === 'PASS' && accelerated.observation.outputDigest === baseline.observation.outputDigest && accelerated.observation.throughputUnits > baseline.observation.throughputUnits,
    halo3RequiredForContinuity: !continuity.observation.personalFloorAvailable || continuity.observation.halo3Required,
    latticeRequiredForContinuity: receipts.find((row) => row.stage === 'VERIFY_LOCAL_CONTINUITY').observation.latticeRequired,
    partitionCellCount: receipts.find((row) => row.stage === 'PARTITION_TWO_CELLS').observation.cellCount,
    conflictDisposition: conflict.observation.resolution,
    headReplacementVerified: receipts.find((row) => row.stage === 'REPLACE_HEAD').observation.replacementAccepted,
    projectionsRebuilt: receipts.find((row) => row.stage === 'REBUILD_PROJECTIONS').observation.rebuiltFromCanonicalReceipts,
    coldSuccessorVerified: receipts.find((row) => row.stage === 'COLD_SUCCESSOR_VERIFY').observation.verificationState === 'pass',
    privatePhysicalFlightCompleted: flightMode === 'private_physical_attested',
    privatePhysicalEvidenceBodyCount,
    publicEvidenceBodyCount: 0,
    externalServiceCalls: 0,
    operationalCredentials: 0,
    physicalEstateQualified: false,
    representativeOperatorQualified: false,
    fieldNetworkQualified: false,
    operationalC2Qualified: false,
    productionLatticeQualified: false,
    authority: 'none',
    claimBoundary: flightMode === 'private_physical_attested'
      ? 'Complete digest-only private physical-flight self-attestation. It records a local flight but does not independently qualify the Estate, representative operators, field networking, operational C2, production Lattice, mission authority, command authority, targeting, engagement, effectors, or weapons.'
      : 'Complete invented synthetic STC and MARY physical-flight harness simulation. It does not establish a physical flight, physical Estate qualification, representative-operator qualification, field networking, operational C2, production Lattice, mission authority, command authority, targeting, engagement, effectors, or weapons.',
  };
  return body;
}

export function runSyntheticStcMaryPhysicalFlight({ profile, fixture }) {
  validateStcMaryPhysicalFlightProfile(profile);
  validateSyntheticPhysicalFlightFixture(fixture, profile);
  const sourceId = digest('stcmarysyntheticflightsource1', fixture);
  const seed = createPhysicalFlightCampaignSeed({ profile, sourceId, flightMode: fixture.flightMode });
  const receipts = [];
  let previousStageReceiptId = null;
  let obligationId = null;
  for (const [index, stage] of STC_MARY_STAGES.entries()) {
    if (stage === 'RESTORE_LINK_HOLD_CONFLICT') {
      obligationId = digest('stcmaryconflictobligation1', {
        campaignSeedId: seed.campaignSeedId,
        leftStateDigest: fixture.expectedConflict.leftCellStateDigest,
        rightStateDigest: fixture.expectedConflict.rightCellStateDigest,
        disposition: 'human_required',
      });
    }
    const observation = syntheticObservation(stage, { fixture, receipts, obligationId });
    const evidence = [createSyntheticEvidence(stage, observation)];
    const unresolvedObligationIds = obligationId === null ? [] : [obligationId];
    const receipt = createStageReceipt({
      seed,
      sequence: index + 1,
      stage,
      terminalState: requiredState(stage),
      previousStageReceiptId,
      canonicalMissionStateIdBefore: fixture.digests.canonicalMissionState,
      canonicalMissionStateIdAfter: fixture.digests.canonicalMissionState,
      observation,
      evidence,
      unresolvedObligationIds,
    });
    receipts.push(receipt);
    previousStageReceiptId = receipt.stageReceiptId;
  }
  const body = buildRunBody({
    profile,
    sourceId,
    flightMode: fixture.flightMode,
    seed,
    receipts,
    privatePhysicalEvidenceBodyCount: 0,
  });
  return { ...body, runId: digest('stcmaryphysicalflightrun1', body) };
}

export function validateStcMaryPhysicalFlightRun(run, profile = undefined) {
  exactKeys(run, KEYS.run, 'PHYSICAL_FLIGHT_RUN_INVALID', 'physical-flight run');
  requireCondition(run.schema === 'stc-mary-physical-flight-run/1', 'PHYSICAL_FLIGHT_RUN_SCHEMA_INVALID', 'run schema differs');
  requireCondition(FLIGHT_MODES.has(run.flightMode), 'PHYSICAL_FLIGHT_RUN_INVALID', 'run mode differs');
  if (profile !== undefined) {
    validateStcMaryPhysicalFlightProfile(profile);
    requireCondition(run.profileId === profile.profileId, 'PHYSICAL_FLIGHT_RUN_BINDING_INVALID', 'run belongs to another profile');
  }
  validatePhysicalFlightCampaignSeed(run.campaignSeed, profile);
  requireCondition(run.sourceId === run.campaignSeed.sourceId && run.flightMode === run.campaignSeed.flightMode, 'PHYSICAL_FLIGHT_RUN_BINDING_INVALID', 'run source or mode differs from campaign seed');
  validateStringArray(run.stageDenominator, STC_MARY_STAGES, 'PHYSICAL_FLIGHT_RUN_DENOMINATOR_INVALID', 'stage denominator');
  requireCondition(Array.isArray(run.stageReceipts) && run.stageReceipts.length === STC_MARY_STAGES.length && run.stageCount === STC_MARY_STAGES.length, 'PHYSICAL_FLIGHT_RUN_DENOMINATOR_INVALID', 'stage receipt denominator differs');
  requireCondition(new Set(run.stageReceipts.map((row) => row.stageReceiptId)).size === run.stageReceipts.length, 'PHYSICAL_FLIGHT_RUN_DENOMINATOR_INVALID', 'stage receipt identities are duplicated');
  let previousStageReceiptId = null;
  let obligationId;
  for (const [index, receipt] of run.stageReceipts.entries()) {
    if (receipt.stage === 'RESTORE_LINK_HOLD_CONFLICT') {
      requireCondition(receipt.unresolvedObligationIds.length === 1, 'PHYSICAL_FLIGHT_STAGE_OBLIGATION_INVALID', 'conflict stage lacks its obligation');
      obligationId = receipt.unresolvedObligationIds[0];
    }
    validatePhysicalFlightStageReceipt(receipt, {
      seed: run.campaignSeed,
      sequence: index + 1,
      previousStageReceiptId,
      obligationId,
    });
    previousStageReceiptId = receipt.stageReceiptId;
  }
  requireCondition(obligationId !== undefined, 'PHYSICAL_FLIGHT_STAGE_OBLIGATION_INVALID', 'run contains no conflict obligation');
  const successful = run.stageReceipts.filter((row) => row.terminalState === 'PASS').length;
  const humanRequired = run.stageReceipts.filter((row) => row.terminalState === 'HUMAN_REQUIRED').length;
  const refused = run.stageReceipts.filter((row) => row.terminalState === 'REFUSED').length;
  requireCondition(run.successfulStageCount === successful && run.humanRequiredStageCount === humanRequired && run.refusedStageCount === refused && run.pendingStageCount === 0, 'PHYSICAL_FLIGHT_RUN_COUNT_INVALID', 'run terminal counts differ');
  requireCondition(successful === 15 && humanRequired === 1 && refused === 0, 'PHYSICAL_FLIGHT_RUN_TERMINAL_INVALID', 'run terminal state denominator differs');
  requireCondition(run.canonicalMissionStateIdBefore === run.canonicalMissionStateIdAfter && run.canonicalMissionStateUnchanged === true, 'PHYSICAL_FLIGHT_RUN_STATE_MUTATION', 'run mutates canonical mission state');
  requireCondition(
    run.personalFloorBaselineVerified === true &&
      run.halo3AccelerationVerified === true &&
      run.halo3RequiredForContinuity === false &&
      run.latticeRequiredForContinuity === false &&
      run.partitionCellCount === 2 &&
      run.conflictDisposition === 'human_required' &&
      run.headReplacementVerified === true &&
      run.projectionsRebuilt === true &&
      run.coldSuccessorVerified === true,
    'PHYSICAL_FLIGHT_RUN_CONTINUITY_INVALID',
    'run does not preserve the required continuity and conflict mechanisms',
  );
  if (run.flightMode === 'synthetic_simulation') {
    requireCondition(run.privatePhysicalFlightCompleted === false && run.privatePhysicalEvidenceBodyCount === 0, 'PHYSICAL_FLIGHT_RUN_CLAIM_INVALID', 'synthetic run claims a physical flight');
  } else {
    requireCondition(run.privatePhysicalFlightCompleted === true && run.privatePhysicalEvidenceBodyCount >= STC_MARY_STAGES.length, 'PHYSICAL_FLIGHT_RUN_CLAIM_INVALID', 'private run lacks a complete physical evidence denominator');
  }
  requireCondition(
    run.publicEvidenceBodyCount === 0 &&
      run.externalServiceCalls === 0 &&
      run.operationalCredentials === 0 &&
      run.physicalEstateQualified === false &&
      run.representativeOperatorQualified === false &&
      run.fieldNetworkQualified === false &&
      run.operationalC2Qualified === false &&
      run.productionLatticeQualified === false &&
      run.authority === 'none',
    'PHYSICAL_FLIGHT_RUN_CLAIM_INVALID',
    'run widens its evidence, dependency, qualification, or authority claim',
  );
  assertIdentity(run, 'stcmaryphysicalflightrun1', 'runId', 'PHYSICAL_FLIGHT_RUN_ID_INVALID');
  return run;
}

function verificationBody(run) {
  const evidenceCount = run.stageReceipts.reduce((sum, row) => sum + row.evidence.length, 0);
  return {
    schema: 'stc-mary-physical-flight-verification/1',
    runId: run.runId,
    status: 'PASS',
    flightMode: run.flightMode,
    stageDenominatorVerified: true,
    stageChainVerified: true,
    stageIdentityVerified: true,
    expectedTerminalStatesVerified: true,
    evidenceDenominatorVerified: evidenceCount >= STC_MARY_STAGES.length,
    canonicalMissionStateUnchanged: run.canonicalMissionStateUnchanged,
    personalFloorContinuityVerified: run.personalFloorBaselineVerified && !run.halo3RequiredForContinuity,
    halo3OptionalityVerified: run.halo3AccelerationVerified && !run.halo3RequiredForContinuity,
    latticeOptionalityVerified: !run.latticeRequiredForContinuity,
    partitionClosureVerified: run.partitionCellCount === 2,
    conflictHeldHumanRequired: run.conflictDisposition === 'human_required',
    headReplacementVerified: run.headReplacementVerified,
    projectionsRebuilt: run.projectionsRebuilt,
    coldSuccessorVerified: run.coldSuccessorVerified,
    privatePhysicalFlightCompleted: run.privatePhysicalFlightCompleted,
    publicDispositionBodyFree: run.publicEvidenceBodyCount === 0,
    physicalEstateQualified: false,
    representativeOperatorQualified: false,
    fieldNetworkQualified: false,
    operationalC2Qualified: false,
    productionLatticeQualified: false,
    authority: 'none',
    claimBoundary: 'Detached verification of one complete STC and MARY physical-flight receipt chain. It does not grant independent physical qualification, representative-operator qualification, field networking, operational C2, production Lattice, mission authority, command authority, targeting, engagement, effector, or weapons capability.',
  };
}

export function verifyStcMaryPhysicalFlightRun(run, { profile, fixture } = {}) {
  validateStcMaryPhysicalFlightRun(run, profile);
  if (run.flightMode === 'synthetic_simulation') {
    requireCondition(fixture !== undefined, 'PHYSICAL_FLIGHT_RUN_REPLAY_INPUT_MISSING', 'synthetic verification requires the source fixture');
    const replayed = runSyntheticStcMaryPhysicalFlight({ profile, fixture });
    exactObject(run, replayed, 'PHYSICAL_FLIGHT_RUN_REPLAY_MISMATCH', 'synthetic physical-flight replay');
  }
  const body = verificationBody(run);
  requireCondition(
    body.evidenceDenominatorVerified &&
      body.personalFloorContinuityVerified &&
      body.halo3OptionalityVerified &&
      body.latticeOptionalityVerified &&
      body.partitionClosureVerified &&
      body.conflictHeldHumanRequired &&
      body.headReplacementVerified &&
      body.projectionsRebuilt &&
      body.coldSuccessorVerified &&
      body.publicDispositionBodyFree,
    'PHYSICAL_FLIGHT_VERIFICATION_INCOMPLETE',
    'physical-flight verification denominator is incomplete',
  );
  return { ...body, verificationId: digest('stcmaryphysicalflightverification1', body) };
}

export function buildStcMaryPhysicalFlightProjection(run) {
  validateStcMaryPhysicalFlightRun(run);
  const unresolvedObligations = [...new Set(run.stageReceipts.flatMap((row) => row.unresolvedObligationIds))];
  const body = {
    schema: 'stc-mary-physical-flight-receipt-projection/1',
    runId: run.runId,
    flightMode: run.flightMode,
    stageSummary: run.stageReceipts.map((row) => ({
      sequence: row.sequence,
      stage: row.stage,
      terminalState: row.terminalState,
      stageReceiptId: row.stageReceiptId,
      evidenceCount: row.evidence.length,
    })),
    unresolvedObligations,
    continuity: {
      canonicalMissionStateUnchanged: run.canonicalMissionStateUnchanged,
      personalFloorBaselineVerified: run.personalFloorBaselineVerified,
      halo3RequiredForContinuity: run.halo3RequiredForContinuity,
      latticeRequiredForContinuity: run.latticeRequiredForContinuity,
      partitionCellCount: run.partitionCellCount,
      conflictDisposition: run.conflictDisposition,
    },
    coldSuccessor: {
      headReplacementVerified: run.headReplacementVerified,
      projectionsRebuilt: run.projectionsRebuilt,
      coldSuccessorVerified: run.coldSuccessorVerified,
    },
    privatePhysicalFlightCompleted: run.privatePhysicalFlightCompleted,
    physicalEstateQualified: false,
    authority: 'none',
    claimBoundary: 'Destructible receipt-only projection of the STC and MARY physical-flight chain. It is not canonical state, a private evidence body, physical qualification, or an authority surface.',
  };
  return { ...body, projectionId: digest('stcmaryphysicalflightprojection1', body) };
}

export function validateStcMaryPhysicalFlightProjection(projection, run = undefined) {
  exactKeys(projection, KEYS.projection, 'PHYSICAL_FLIGHT_PROJECTION_INVALID', 'physical-flight projection');
  requireCondition(projection.schema === 'stc-mary-physical-flight-receipt-projection/1', 'PHYSICAL_FLIGHT_PROJECTION_SCHEMA_INVALID', 'projection schema differs');
  requireCondition(Array.isArray(projection.stageSummary) && projection.stageSummary.length === STC_MARY_STAGES.length, 'PHYSICAL_FLIGHT_PROJECTION_INVALID', 'projection stage denominator differs');
  uniqueStrings(projection.unresolvedObligations, 'PHYSICAL_FLIGHT_PROJECTION_INVALID', 'projection obligations');
  requireCondition(projection.physicalEstateQualified === false && projection.authority === 'none', 'PHYSICAL_FLIGHT_PROJECTION_CLAIM_INVALID', 'projection widens qualification or authority');
  assertIdentity(projection, 'stcmaryphysicalflightprojection1', 'projectionId', 'PHYSICAL_FLIGHT_PROJECTION_ID_INVALID');
  if (run !== undefined) exactObject(projection, buildStcMaryPhysicalFlightProjection(run), 'PHYSICAL_FLIGHT_PROJECTION_REPLAY_MISMATCH', 'physical-flight projection replay');
  return projection;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

export function renderStcMaryPhysicalFlightHtml(projection) {
  validateStcMaryPhysicalFlightProjection(projection);
  const rows = projection.stageSummary.map((row) => `<tr><td>${row.sequence}</td><td>${escapeHtml(row.stage)}</td><td>${escapeHtml(row.terminalState)}</td><td><code>${escapeHtml(row.stageReceiptId)}</code></td><td>${row.evidenceCount}</td></tr>`).join('');
  const obligations = projection.unresolvedObligations.map((row) => `<li><code>${escapeHtml(row)}</code></li>`).join('');
  return `<!doctype html>\n<html lang="en"><head><meta charset="utf-8"><title>STC MARY Physical-Flight Receipt</title></head><body><main><h1>STC MARY Physical-Flight Receipt</h1><p>Run: <code>${escapeHtml(projection.runId)}</code></p><p>Mode: ${escapeHtml(projection.flightMode)}</p><p>Private physical flight completed: ${projection.privatePhysicalFlightCompleted}</p><p>Physical Estate qualified: ${projection.physicalEstateQualified}</p><h2>Stage denominator</h2><table><thead><tr><th>#</th><th>Stage</th><th>Terminal</th><th>Receipt</th><th>Evidence</th></tr></thead><tbody>${rows}</tbody></table><h2>Unresolved obligations</h2><ul>${obligations}</ul><p>${escapeHtml(projection.claimBoundary)}</p></main></body></html>\n`;
}

function genericTemplateObservation(stage) {
  const genericOutput = digest('stcmarytemplateoutput1', { stage: 'mission-output' });
  switch (stage) {
    case 'VERIFY_INPUTS': return { profileValidated: true, sourceObjectsVerified: true, inputDigestRoot: digest('stcmarytemplateinput1', {}) };
    case 'MOUNT_PERSONAL_FLOOR': return { personalFloorSeatIdentityClass: 'private_resident_execution_seat', mounted: true, missionClosed: true };
    case 'BIND_GRACE': return { humanBindIdentityClass: 'named_human_operator', bound: true, authoritySource: 'named_human_bind' };
    case 'RUN_PERSONAL_FLOOR_BASELINE': return { outputDigest: genericOutput, throughputUnits: 1, verifierState: 'pass' };
    case 'ATTACH_HALO3': return { halo3SeatIdentityClass: 'private_optional_accelerator', attached: true, optional: true };
    case 'RUN_HALO3_ACCELERATED': return { outputDigest: genericOutput, throughputUnits: 2, verifierState: 'pass', fasterThanBaseline: true };
    case 'REMOVE_HALO3': return { halo3SeatIdentityClass: 'private_optional_accelerator', attached: false, removalReceiptPresent: true };
    case 'VERIFY_PERSONAL_FLOOR_CONTINUITY': return { personalFloorAvailable: true, outputDigestMatches: true, halo3Required: false, throughputUnits: 1 };
    case 'REMOVE_LATTICE': return { latticeIdentityClass: 'private_optional_interoperability_membrane', present: false, removalReceiptPresent: true };
    case 'VERIFY_LOCAL_CONTINUITY': return { localStateAvailable: true, latticeRequired: false, canonicalStateRecovered: true };
    case 'PARTITION_TWO_CELLS': return { cellCount: 2, cellIdentityClasses: ['private_cell_left', 'private_cell_right'], eachCellLocallyValid: true, authorityWidened: false };
    case 'RESTORE_LINK_HOLD_CONFLICT': return { linkRestored: true, conflictDetected: true, automaticMerge: false, resolution: 'human_required', leftStateDigest: '1'.repeat(64), rightStateDigest: '2'.repeat(64) };
    case 'REPLACE_HEAD': return { oldHeadIdentityClass: 'private_initial_head', newHeadIdentityClass: 'private_successor_head', replacementAccepted: true, canonicalStateCopiedByDigest: true, authorityTransferred: false };
    case 'REBUILD_PROJECTIONS': return { projectionKinds: PROJECTION_KINDS, rebuiltFromCanonicalReceipts: true, projectionDigestRoot: digest('stcmarytemplateprojection1', {}) };
    case 'COLD_SUCCESSOR_VERIFY': return { successorHeadIdentityClass: 'private_successor_head', recoveredCartridge: true, recoveredAuthorityBoundary: true, recoveredObligations: true, verificationState: 'pass' };
    case 'SEAL_PRIVATE_EVIDENCE': return { sealedEvidenceClass: 'private_physical_attested', evidenceDescriptorCount: STC_MARY_STAGES.length, publicDispositionBodyFree: true, privateEvidenceBodiesCommittedToGit: false };
    default: throw new StcMaryPhysicalFlightError('PHYSICAL_FLIGHT_STAGE_INVALID', `unsupported stage ${stage}`);
  }
}

export function createPrivatePhysicalFlightTemplate(profile) {
  validateStcMaryPhysicalFlightProfile(profile);
  const canonicalState = '0'.repeat(64);
  return {
    schema: 'stc-mary-private-physical-flight-attestation-request/1',
    profileId: profile.profileId,
    flightMode: 'private_physical_attested',
    campaignLabel: 'REPLACE_WITH_PRIVATE_CAMPAIGN_LABEL',
    sourceObjectDigests: ['0'.repeat(64)],
    identityClasses: {
      personalFloor: 'private_resident_execution_seat',
      halo3: 'private_optional_accelerator',
      initialHead: 'private_initial_head',
      successorHead: 'private_successor_head',
      graceBind: 'named_human_operator',
      lattice: 'private_optional_interoperability_membrane',
      leftCell: 'private_partition_cell_left',
      rightCell: 'private_partition_cell_right',
    },
    canonicalMissionStateDigest: canonicalState,
    stageAttestations: STC_MARY_STAGES.map((stage) => ({
      stage,
      terminalState: requiredState(stage),
      canonicalMissionStateIdBefore: canonicalState,
      canonicalMissionStateIdAfter: canonicalState,
      observation: genericTemplateObservation(stage),
      evidenceBodies: [{
        path: `REPLACE_WITH_PRIVATE_EVIDENCE_PATH_FOR_${stage}`,
        mediaType: 'application/octet-stream',
        evidenceClass: 'private_local_attestation',
      }],
    })),
    externalServiceCalls: 0,
    operationalCredentials: 0,
    attestationBoundary: 'Private local self-attestation request. Evidence paths and bodies remain local and must never be committed to the public repository.',
  };
}

export function validatePrivatePhysicalFlightRequest(request, profile) {
  validateStcMaryPhysicalFlightProfile(profile);
  exactKeys(request, KEYS.privateRequest, 'PRIVATE_PHYSICAL_FLIGHT_REQUEST_INVALID', 'private physical-flight request');
  requireCondition(request.schema === 'stc-mary-private-physical-flight-attestation-request/1', 'PRIVATE_PHYSICAL_FLIGHT_REQUEST_SCHEMA_INVALID', 'private request schema differs');
  requireCondition(request.profileId === profile.profileId && request.flightMode === 'private_physical_attested', 'PRIVATE_PHYSICAL_FLIGHT_REQUEST_INVALID', 'private request profile or mode differs');
  boundedString(request.campaignLabel, 'PRIVATE_PHYSICAL_FLIGHT_REQUEST_INVALID', 'campaign label');
  requireCondition(!request.campaignLabel.startsWith('REPLACE_WITH_'), 'PRIVATE_PHYSICAL_FLIGHT_REQUEST_INCOMPLETE', 'campaign label remains a template placeholder');
  uniqueStrings(request.sourceObjectDigests, 'PRIVATE_PHYSICAL_FLIGHT_REQUEST_INVALID', 'source object digests');
  request.sourceObjectDigests.forEach((row) => assertSha256(row, 'PRIVATE_PHYSICAL_FLIGHT_REQUEST_INVALID', 'source object digest'));
  exactKeys(request.identityClasses, KEYS.privateIdentityClasses, 'PRIVATE_PHYSICAL_FLIGHT_REQUEST_INVALID', 'identity classes');
  for (const [key, value] of Object.entries(request.identityClasses)) {
    boundedString(value, 'PRIVATE_PHYSICAL_FLIGHT_REQUEST_INVALID', key, 256);
    requireCondition(!value.startsWith('REPLACE_WITH_'), 'PRIVATE_PHYSICAL_FLIGHT_REQUEST_INCOMPLETE', `${key} remains a template placeholder`);
  }
  assertSha256(request.canonicalMissionStateDigest, 'PRIVATE_PHYSICAL_FLIGHT_REQUEST_INVALID', 'canonical mission state digest');
  requireCondition(Array.isArray(request.stageAttestations) && request.stageAttestations.length === STC_MARY_STAGES.length, 'PRIVATE_PHYSICAL_FLIGHT_REQUEST_DENOMINATOR_INVALID', 'stage attestation denominator differs');
  for (const [index, row] of request.stageAttestations.entries()) {
    exactKeys(row, KEYS.stageAttestation, 'PRIVATE_PHYSICAL_FLIGHT_REQUEST_INVALID', 'stage attestation');
    requireCondition(row.stage === STC_MARY_STAGES[index] && row.terminalState === requiredState(row.stage), 'PRIVATE_PHYSICAL_FLIGHT_REQUEST_DENOMINATOR_INVALID', 'stage attestation order or terminal state differs');
    assertSha256(row.canonicalMissionStateIdBefore, 'PRIVATE_PHYSICAL_FLIGHT_REQUEST_INVALID', 'canonical state before');
    assertSha256(row.canonicalMissionStateIdAfter, 'PRIVATE_PHYSICAL_FLIGHT_REQUEST_INVALID', 'canonical state after');
    requireCondition(row.canonicalMissionStateIdBefore === request.canonicalMissionStateDigest && row.canonicalMissionStateIdAfter === request.canonicalMissionStateDigest, 'PRIVATE_PHYSICAL_FLIGHT_REQUEST_STATE_MUTATION', 'stage attestation changes canonical mission state');
    validateObservation(row.stage, row.observation);
    requireCondition(Array.isArray(row.evidenceBodies) && row.evidenceBodies.length >= profile.evidencePolicy.minimumEvidenceBodiesPerPhysicalStage && row.evidenceBodies.length <= MAX_EVIDENCE_PER_STAGE, 'PRIVATE_PHYSICAL_FLIGHT_REQUEST_EVIDENCE_INVALID', 'stage evidence-body denominator differs');
    for (const evidenceBody of row.evidenceBodies) {
      exactKeys(evidenceBody, KEYS.evidenceBody, 'PRIVATE_PHYSICAL_FLIGHT_REQUEST_EVIDENCE_INVALID', 'evidence body reference');
      boundedString(evidenceBody.path, 'PRIVATE_PHYSICAL_FLIGHT_REQUEST_EVIDENCE_INVALID', 'evidence path');
      requireCondition(!evidenceBody.path.startsWith('REPLACE_WITH_'), 'PRIVATE_PHYSICAL_FLIGHT_REQUEST_INCOMPLETE', 'evidence path remains a template placeholder');
      boundedString(evidenceBody.mediaType, 'PRIVATE_PHYSICAL_FLIGHT_REQUEST_EVIDENCE_INVALID', 'evidence media type', 256);
      requireCondition(EVIDENCE_CLASSES.has(evidenceBody.evidenceClass) && evidenceBody.evidenceClass !== 'synthetic_deterministic_receipt', 'PRIVATE_PHYSICAL_FLIGHT_REQUEST_EVIDENCE_INVALID', 'private request carries an invalid evidence class');
    }
  }
  requireCondition(request.externalServiceCalls === 0 && request.operationalCredentials === 0, 'PRIVATE_PHYSICAL_FLIGHT_REQUEST_CLAIM_INVALID', 'private request requires external services or operational credentials');
  boundedString(request.attestationBoundary, 'PRIVATE_PHYSICAL_FLIGHT_REQUEST_INVALID', 'attestation boundary');
  return request;
}

async function hashEvidenceFile(path) {
  const metadata = await stat(path);
  requireCondition(metadata.isFile(), 'PRIVATE_PHYSICAL_FLIGHT_EVIDENCE_INVALID', 'evidence path is not a regular file');
  safeInteger(metadata.size, 1, MAX_EVIDENCE_BYTES, 'PRIVATE_PHYSICAL_FLIGHT_EVIDENCE_INVALID', 'evidence file size');
  const hash = createHash('sha256');
  let bytes = 0;
  for await (const chunk of createReadStream(path)) {
    bytes += chunk.length;
    hash.update(chunk);
  }
  requireCondition(bytes === metadata.size, 'PRIVATE_PHYSICAL_FLIGHT_EVIDENCE_INVALID', 'evidence file changed while hashing');
  return { sha256: hash.digest('hex'), bytes };
}

function sanitizedPrivateSourceId({ profile, request, stageEvidence }) {
  return digest('stcmaryprivatephysicalflightsource1', {
    profileId: profile.profileId,
    campaignLabel: request.campaignLabel,
    sourceObjectDigests: request.sourceObjectDigests,
    identityClasses: request.identityClasses,
    canonicalMissionStateDigest: request.canonicalMissionStateDigest,
    stageEvidence: stageEvidence.map((row) => ({ stage: row.stage, evidence: row.evidence })),
  });
}

export async function sealPrivateStcMaryPhysicalFlight({ profile, request }) {
  validatePrivatePhysicalFlightRequest(request, profile);
  const stageEvidence = [];
  let evidenceBodyCount = 0;
  for (const attestation of request.stageAttestations) {
    const evidence = [];
    for (const body of attestation.evidenceBodies) {
      const hashed = await hashEvidenceFile(resolve(body.path));
      evidence.push(createEvidenceDescriptor({
        stage: attestation.stage,
        evidenceClass: body.evidenceClass,
        mediaType: body.mediaType,
        sha256: hashed.sha256,
        bytes: hashed.bytes,
      }));
      evidenceBodyCount += 1;
    }
    stageEvidence.push({ stage: attestation.stage, evidence });
  }
  const sourceId = sanitizedPrivateSourceId({ profile, request, stageEvidence });
  const seed = createPhysicalFlightCampaignSeed({ profile, sourceId, flightMode: request.flightMode });
  const receipts = [];
  let previousStageReceiptId = null;
  let obligationId = null;
  for (const [index, attestation] of request.stageAttestations.entries()) {
    if (attestation.stage === 'RESTORE_LINK_HOLD_CONFLICT') {
      obligationId = digest('stcmaryconflictobligation1', {
        campaignSeedId: seed.campaignSeedId,
        leftStateDigest: attestation.observation.leftStateDigest,
        rightStateDigest: attestation.observation.rightStateDigest,
        disposition: 'human_required',
      });
    }
    const observation = structuredClone(attestation.observation);
    if (attestation.stage === 'VERIFY_INPUTS') observation.inputDigestRoot = digest('stcmaryprivateinputroot1', { sourceObjectDigests: request.sourceObjectDigests, stageEvidence });
    if (attestation.stage === 'SEAL_PRIVATE_EVIDENCE') {
      observation.sealedEvidenceClass = 'private_physical_attested';
      observation.evidenceDescriptorCount = evidenceBodyCount;
      observation.publicDispositionBodyFree = true;
      observation.privateEvidenceBodiesCommittedToGit = false;
    }
    const receipt = createStageReceipt({
      seed,
      sequence: index + 1,
      stage: attestation.stage,
      terminalState: attestation.terminalState,
      previousStageReceiptId,
      canonicalMissionStateIdBefore: attestation.canonicalMissionStateIdBefore,
      canonicalMissionStateIdAfter: attestation.canonicalMissionStateIdAfter,
      observation,
      evidence: stageEvidence[index].evidence,
      unresolvedObligationIds: obligationId === null ? [] : [obligationId],
    });
    receipts.push(receipt);
    previousStageReceiptId = receipt.stageReceiptId;
  }
  const body = buildRunBody({
    profile,
    sourceId,
    flightMode: request.flightMode,
    seed,
    receipts,
    privatePhysicalEvidenceBodyCount: evidenceBodyCount,
  });
  const run = { ...body, runId: digest('stcmaryphysicalflightrun1', body) };
  validateStcMaryPhysicalFlightRun(run, profile);
  const disposition = buildPublicPhysicalFlightDisposition(run);
  return { run, disposition };
}

export function buildPublicPhysicalFlightDisposition(run) {
  validateStcMaryPhysicalFlightRun(run);
  const evidenceIds = run.stageReceipts.flatMap((row) => row.evidence.map((evidence) => evidence.evidenceId));
  const body = {
    schema: 'stc-mary-public-physical-flight-disposition/1',
    runId: run.runId,
    profileId: run.profileId,
    flightMode: run.flightMode,
    stageReceiptIds: run.stageReceipts.map((row) => row.stageReceiptId),
    stageCount: run.stageCount,
    successfulStageCount: run.successfulStageCount,
    humanRequiredStageCount: run.humanRequiredStageCount,
    evidenceDigestRoot: digest('stcmarypublicevidenceroot1', evidenceIds),
    privatePhysicalEvidenceBodyCount: run.privatePhysicalEvidenceBodyCount,
    publicEvidenceBodyCount: 0,
    privatePhysicalFlightCompleted: run.privatePhysicalFlightCompleted,
    selfAttestationOnly: run.flightMode === 'private_physical_attested',
    physicalEstateQualified: false,
    representativeOperatorQualified: false,
    fieldNetworkQualified: false,
    operationalC2Qualified: false,
    productionLatticeQualified: false,
    authority: 'none',
    claimBoundary: 'Body-free public disposition for one STC and MARY physical-flight receipt chain. It exposes content identities and counts only, and grants no independent physical qualification, representative-operator qualification, field networking, operational C2, production Lattice, mission authority, command authority, targeting, engagement, effector, or weapons capability.',
  };
  const disposition = { ...body, dispositionId: digest('stcmarypublicphysicalflightdisposition1', body) };
  validatePublicPhysicalFlightDisposition(disposition, run);
  return disposition;
}

export function validatePublicPhysicalFlightDisposition(disposition, run = undefined) {
  exactKeys(disposition, KEYS.disposition, 'PUBLIC_PHYSICAL_FLIGHT_DISPOSITION_INVALID', 'public physical-flight disposition');
  requireCondition(disposition.schema === 'stc-mary-public-physical-flight-disposition/1', 'PUBLIC_PHYSICAL_FLIGHT_DISPOSITION_SCHEMA_INVALID', 'public disposition schema differs');
  uniqueStrings(disposition.stageReceiptIds, 'PUBLIC_PHYSICAL_FLIGHT_DISPOSITION_INVALID', 'stage receipt IDs');
  requireCondition(disposition.stageReceiptIds.length === STC_MARY_STAGES.length && disposition.stageCount === STC_MARY_STAGES.length, 'PUBLIC_PHYSICAL_FLIGHT_DISPOSITION_INVALID', 'public disposition stage denominator differs');
  assertContentId(disposition.evidenceDigestRoot, 'PUBLIC_PHYSICAL_FLIGHT_DISPOSITION_INVALID', 'evidence digest root');
  requireCondition(
    disposition.successfulStageCount === 15 &&
      disposition.humanRequiredStageCount === 1 &&
      disposition.publicEvidenceBodyCount === 0 &&
      disposition.physicalEstateQualified === false &&
      disposition.representativeOperatorQualified === false &&
      disposition.fieldNetworkQualified === false &&
      disposition.operationalC2Qualified === false &&
      disposition.productionLatticeQualified === false &&
      disposition.authority === 'none',
    'PUBLIC_PHYSICAL_FLIGHT_DISPOSITION_CLAIM_INVALID',
    'public disposition widens evidence, qualification, or authority',
  );
  assertNoPublicPrivateMaterial(disposition, 'PUBLIC_PHYSICAL_FLIGHT_DISPOSITION_PRIVATE_MATERIAL', 'public disposition');
  assertIdentity(disposition, 'stcmarypublicphysicalflightdisposition1', 'dispositionId', 'PUBLIC_PHYSICAL_FLIGHT_DISPOSITION_ID_INVALID');
  if (run !== undefined) exactObject(disposition, buildPublicPhysicalFlightDisposition(run), 'PUBLIC_PHYSICAL_FLIGHT_DISPOSITION_REPLAY_MISMATCH', 'public disposition replay');
  return disposition;
}

async function readJson(path) {
  return JSON.parse(await readFile(path, 'utf8'));
}

async function writeJson(path, value) {
  await mkdir(dirname(path), { recursive: true });
  await writeFile(path, `${JSON.stringify(value, null, 2)}\n`, 'utf8');
}

async function loadDefaults() {
  const [profile, fixture] = await Promise.all([readJson(DEFAULT_PROFILE), readJson(DEFAULT_FIXTURE)]);
  return { profile, fixture };
}

export async function runStcMaryPhysicalFlightCli(argv) {
  const command = argv[2];
  if (command === 'simulate') {
    const { profile, fixture } = await loadDefaults();
    const run = runSyntheticStcMaryPhysicalFlight({ profile, fixture });
    const verification = verifyStcMaryPhysicalFlightRun(run, { profile, fixture });
    const projection = buildStcMaryPhysicalFlightProjection(run);
    const runPath = resolve(argv[3]);
    const verificationPath = resolve(argv[4]);
    const reviewPath = resolve(argv[5]);
    await writeJson(runPath, run);
    await writeJson(verificationPath, verification);
    await mkdir(dirname(reviewPath), { recursive: true });
    await writeFile(reviewPath, renderStcMaryPhysicalFlightHtml(projection), 'utf8');
    process.stdout.write(`${JSON.stringify({ status: 'PASS', runId: run.runId, verificationId: verification.verificationId, runPath, verificationPath, reviewPath }, null, 2)}\n`);
    return;
  }
  if (command === 'verify') {
    const { profile, fixture } = await loadDefaults();
    const run = await readJson(resolve(argv[3]));
    const verification = verifyStcMaryPhysicalFlightRun(run, { profile, fixture: run.flightMode === 'synthetic_simulation' ? fixture : undefined });
    await writeJson(resolve(argv[4]), verification);
    process.stdout.write(`${JSON.stringify(verification, null, 2)}\n`);
    return;
  }
  if (command === 'template-private') {
    const { profile } = await loadDefaults();
    const outputPath = resolve(argv[3]);
    await writeJson(outputPath, createPrivatePhysicalFlightTemplate(profile));
    process.stdout.write(`${JSON.stringify({ status: 'TEMPLATE_CREATED', outputPath }, null, 2)}\n`);
    return;
  }
  if (command === 'seal-private') {
    const { profile } = await loadDefaults();
    const request = await readJson(resolve(argv[3]));
    const { run, disposition } = await sealPrivateStcMaryPhysicalFlight({ profile, request });
    const verification = verifyStcMaryPhysicalFlightRun(run, { profile });
    const projection = buildStcMaryPhysicalFlightProjection(run);
    const runPath = resolve(argv[4]);
    const dispositionPath = resolve(argv[5]);
    const verificationPath = resolve(argv[6]);
    const reviewPath = resolve(argv[7]);
    await writeJson(runPath, run);
    await writeJson(dispositionPath, disposition);
    await writeJson(verificationPath, verification);
    await mkdir(dirname(reviewPath), { recursive: true });
    await writeFile(reviewPath, renderStcMaryPhysicalFlightHtml(projection), 'utf8');
    process.stdout.write(`${JSON.stringify({ status: 'PASS', runId: run.runId, dispositionId: disposition.dispositionId, verificationId: verification.verificationId }, null, 2)}\n`);
    return;
  }
  throw new StcMaryPhysicalFlightError(
    'COMMAND_INVALID',
    'usage: stc_mary_physical_flight.mjs simulate <run.json> <verification.json> <review.html> | verify <run.json> <verification.json> | template-private <request.json> | seal-private <request.json> <private-run.json> <public-disposition.json> <verification.json> <review.html>',
  );
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  runStcMaryPhysicalFlightCli(process.argv).catch((error) => {
    process.stderr.write(`${error instanceof StcMaryPhysicalFlightError ? error.code : 'UNEXPECTED_ERROR'}: ${error.message}\n`);
    process.exitCode = 1;
  });
}

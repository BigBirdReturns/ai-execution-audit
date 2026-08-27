import { createHash } from 'node:crypto';
import { homedir } from 'node:os';
import {
  mkdir,
  readFile,
  readdir,
  stat,
  writeFile,
} from 'node:fs/promises';
import {
  basename,
  dirname,
  isAbsolute,
  join,
  relative,
  resolve,
  sep,
} from 'node:path';
import { fileURLToPath } from 'node:url';
import { canonicalJson } from '../semantic/authority_sidecar.mjs';
import {
  REQUIRED_STAGE_TERMINALS,
  STC_MARY_STAGES,
  buildStcMaryPhysicalFlightProjection,
  createPrivatePhysicalFlightTemplate,
  renderStcMaryPhysicalFlightHtml,
  sealPrivateStcMaryPhysicalFlight,
  validatePhysicalFlightObservation,
  validatePrivatePhysicalFlightRequest,
  validatePublicPhysicalFlightDisposition,
  validateStcMaryPhysicalFlightRun,
  validateStcMaryPhysicalFlightProfile,
  verifyStcMaryPhysicalFlightRun,
} from './stc_mary_physical_flight.mjs';

const HERE = dirname(fileURLToPath(import.meta.url));
const REPOSITORY_ROOT = resolve(HERE, '../..');
const PACKET_PROFILE_PATH = resolve(HERE, 'stc-mary-private-flight-packet-profile-01.json');
const PHYSICAL_PROFILE_PATH = resolve(HERE, 'stc-mary-physical-flight-profile-01.json');
const PACKET_DIRECTORY = /^stc-mary-private-flight-[a-z0-9][a-z0-9._-]*$/i;
const SEALED_DIRECTORY = /^stc-mary-private-flight-sealed-[a-z0-9][a-z0-9._-]*$/i;
const SHA256 = /^[0-9a-f]{64}$/;
const CONTENT_ID = /^[a-z0-9][a-z0-9_-]*_[0-9a-f]{64}$/;
const PRIVATE_EVIDENCE_CLASSES = new Set([
  'private_local_attestation',
  'private_instrument_receipt',
  'private_operator_statement',
]);
const MAX_EVIDENCE_BYTES = 8 * 1024 * 1024 * 1024;
const MAX_EVIDENCE_FILES = 64;

const FILES = Object.freeze({
  marker: 'PACKET-ROOT.json',
  state: 'packet-state.json',
  config: 'flight-config.json',
  request: 'private-request.local.json',
  sealedMarker: 'SEALED-ROOT.json',
  sealedRun: 'private-flight-run.json',
  publicDisposition: 'public-disposition.json',
  verification: 'verification.json',
  review: 'review.html',
  manifest: 'manifest.json',
});

export class StcMaryPrivateFlightPacketError extends Error {
  constructor(code, message) {
    super(message);
    this.name = 'StcMaryPrivateFlightPacketError';
    this.code = code;
  }
}

function requireCondition(condition, code, message) {
  if (!condition) throw new StcMaryPrivateFlightPacketError(code, message);
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

function boundedString(value, code, label, max = 8192) {
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
  requireCondition(values.every((row) => typeof row === 'string' && row.trim().length > 0), code, `${label} contains an invalid value`);
  requireCondition(new Set(values).size === values.length, code, `${label} contains duplicates`);
}

function digest(prefix, value) {
  return `${prefix}_${createHash('sha256').update(canonicalJson(value), 'utf8').digest('hex')}`;
}

function digestBytes(bytes) {
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

async function pathState(path) {
  try {
    return await stat(path);
  } catch (error) {
    if (error?.code === 'ENOENT') return null;
    throw error;
  }
}

async function readJson(path) {
  return JSON.parse(await readFile(path, 'utf8'));
}

async function writeJson(path, value) {
  await mkdir(dirname(path), { recursive: true });
  await writeFile(path, `${JSON.stringify(value, null, 2)}\n`, 'utf8');
}

function isInside(ancestor, target) {
  const relation = relative(ancestor, target);
  return relation === '' || (!relation.startsWith(`..${sep}`) && relation !== '..' && !isAbsolute(relation));
}

async function validateNewOutputDirectory(path, pattern, code, label) {
  const resolved = resolve(path);
  requireCondition(pattern.test(basename(resolved)), code, `${label} must use its dedicated name pattern`);
  requireCondition(!isInside(REPOSITORY_ROOT, resolved), code, `${label} must remain outside the public repository`);
  const forbiddenExact = new Set([
    resolve('/'),
    resolve(homedir()),
    resolve(process.cwd()),
    REPOSITORY_ROOT,
    HERE,
  ]);
  requireCondition(!forbiddenExact.has(resolved), code, `${label} is a protected path`);
  const parent = dirname(resolved);
  const parentState = await pathState(parent);
  requireCondition(parentState?.isDirectory(), code, `${label} parent must already exist`);
  requireCondition((await pathState(resolved)) === null, code, `${label} already exists`);
  return resolved;
}

function stageDirectoryName(sequence, stage) {
  return `${String(sequence).padStart(2, '0')}-${stage}`;
}

function packetIdFor(packetProfile, physicalProfile, campaignLabel) {
  return digest('stcmaryprivateflightpacket1', {
    packetProfileId: packetProfile.profileId,
    physicalProfileId: physicalProfile.profileId,
    campaignLabel,
    stageSequence: STC_MARY_STAGES,
  });
}

function packetMarker({ packetProfile, physicalProfile, campaignLabel }) {
  const body = {
    schema: 'stc-mary-private-flight-packet-root/1',
    packetProfileId: packetProfile.profileId,
    physicalProfileId: physicalProfile.profileId,
    campaignLabel,
    packetId: packetIdFor(packetProfile, physicalProfile, campaignLabel),
    authority: 'none',
    claimBoundary: 'Marker for one local private-flight packet outside the public repository. It grants no deletion, physical, mission, command, targeting, engagement, effector, or weapons authority.',
  };
  return { ...body, markerId: digest('stcmaryprivateflightpacketroot1', body) };
}

function validatePacketMarker(marker, packetProfile, physicalProfile) {
  exactKeys(marker, [
    'schema', 'markerId', 'packetProfileId', 'physicalProfileId', 'campaignLabel',
    'packetId', 'authority', 'claimBoundary',
  ], 'PRIVATE_FLIGHT_PACKET_MARKER_INVALID', 'packet marker');
  requireCondition(marker.schema === 'stc-mary-private-flight-packet-root/1', 'PRIVATE_FLIGHT_PACKET_MARKER_INVALID', 'packet marker schema differs');
  boundedString(marker.campaignLabel, 'PRIVATE_FLIGHT_PACKET_MARKER_INVALID', 'campaign label');
  requireCondition(
    marker.packetProfileId === packetProfile.profileId &&
      marker.physicalProfileId === physicalProfile.profileId &&
      marker.packetId === packetIdFor(packetProfile, physicalProfile, marker.campaignLabel) &&
      marker.authority === 'none',
    'PRIVATE_FLIGHT_PACKET_MARKER_INVALID',
    'packet marker binding or authority differs',
  );
  assertIdentity(marker, 'stcmaryprivateflightpacketroot1', 'markerId', 'PRIVATE_FLIGHT_PACKET_MARKER_ID_INVALID');
  return marker;
}

function stageStateRows() {
  return STC_MARY_STAGES.map((stage, index) => ({
    sequence: index + 1,
    stage,
    status: 'unrecorded',
    draftPath: join(stageDirectoryName(index + 1, stage), 'stage-attestation.json').replaceAll('\\', '/'),
    evidenceDirectory: join(stageDirectoryName(index + 1, stage), 'evidence').replaceAll('\\', '/'),
    evidenceCount: 0,
    recordDigest: null,
  }));
}

function createPacketState({ marker, configurationState = 'unconfigured', stages = stageStateRows(), sealed = false, sealedDispositionId = null }) {
  const completedStageCount = stages.filter((row) => row.status === 'recorded').length;
  const nextStage = stages.find((row) => row.status === 'unrecorded')?.stage ?? null;
  const body = {
    schema: 'stc-mary-private-flight-packet-state/1',
    packetId: marker.packetId,
    campaignLabel: marker.campaignLabel,
    packetProfileId: marker.packetProfileId,
    physicalProfileId: marker.physicalProfileId,
    configurationState,
    stageDenominator: [...STC_MARY_STAGES],
    stages,
    completedStageCount,
    nextStage,
    sealed,
    sealedDispositionId,
    authority: 'none',
    claimBoundary: 'Local packet state. It records preparation and receipt custody only and grants no physical, mission, command, targeting, engagement, effector, or weapons authority.',
  };
  return { ...body, stateId: digest('stcmaryprivateflightpacketstate1', body) };
}

function validatePacketState(state, marker) {
  exactKeys(state, [
    'schema', 'stateId', 'packetId', 'campaignLabel', 'packetProfileId', 'physicalProfileId',
    'configurationState', 'stageDenominator', 'stages', 'completedStageCount', 'nextStage',
    'sealed', 'sealedDispositionId', 'authority', 'claimBoundary',
  ], 'PRIVATE_FLIGHT_PACKET_STATE_INVALID', 'packet state');
  requireCondition(state.schema === 'stc-mary-private-flight-packet-state/1', 'PRIVATE_FLIGHT_PACKET_STATE_INVALID', 'packet state schema differs');
  requireCondition(
    state.packetId === marker.packetId &&
      state.campaignLabel === marker.campaignLabel &&
      state.packetProfileId === marker.packetProfileId &&
      state.physicalProfileId === marker.physicalProfileId,
    'PRIVATE_FLIGHT_PACKET_STATE_INVALID',
    'packet state belongs to another marker',
  );
  requireCondition(['unconfigured', 'configured'].includes(state.configurationState), 'PRIVATE_FLIGHT_PACKET_STATE_INVALID', 'configuration state differs');
  requireCondition(canonicalJson(state.stageDenominator) === canonicalJson(STC_MARY_STAGES), 'PRIVATE_FLIGHT_PACKET_STATE_INVALID', 'stage denominator differs');
  requireCondition(Array.isArray(state.stages) && state.stages.length === STC_MARY_STAGES.length, 'PRIVATE_FLIGHT_PACKET_STATE_INVALID', 'stage state denominator differs');
  for (const [index, row] of state.stages.entries()) {
    exactKeys(row, ['sequence', 'stage', 'status', 'draftPath', 'evidenceDirectory', 'evidenceCount', 'recordDigest'], 'PRIVATE_FLIGHT_PACKET_STATE_INVALID', 'stage state');
    requireCondition(row.sequence === index + 1 && row.stage === STC_MARY_STAGES[index], 'PRIVATE_FLIGHT_PACKET_STATE_INVALID', 'stage state order differs');
    requireCondition(['unrecorded', 'recorded'].includes(row.status), 'PRIVATE_FLIGHT_PACKET_STATE_INVALID', 'stage status differs');
    boundedString(row.draftPath, 'PRIVATE_FLIGHT_PACKET_STATE_INVALID', 'draft path');
    boundedString(row.evidenceDirectory, 'PRIVATE_FLIGHT_PACKET_STATE_INVALID', 'evidence directory');
    safeInteger(row.evidenceCount, 0, MAX_EVIDENCE_FILES, 'PRIVATE_FLIGHT_PACKET_STATE_INVALID', 'evidence count');
    if (row.status === 'recorded') assertContentId(row.recordDigest, 'PRIVATE_FLIGHT_PACKET_STATE_INVALID', 'record digest');
    else requireCondition(row.recordDigest === null && row.evidenceCount === 0, 'PRIVATE_FLIGHT_PACKET_STATE_INVALID', 'unrecorded stage carries evidence state');
  }
  const completed = state.stages.filter((row) => row.status === 'recorded').length;
  requireCondition(state.completedStageCount === completed, 'PRIVATE_FLIGHT_PACKET_STATE_INVALID', 'completed stage count differs');
  const expectedNext = state.stages.find((row) => row.status === 'unrecorded')?.stage ?? null;
  requireCondition(state.nextStage === expectedNext, 'PRIVATE_FLIGHT_PACKET_STATE_INVALID', 'next stage differs');
  requireCondition(typeof state.sealed === 'boolean' && state.authority === 'none', 'PRIVATE_FLIGHT_PACKET_STATE_INVALID', 'packet state seal or authority differs');
  if (state.sealed) assertContentId(state.sealedDispositionId, 'PRIVATE_FLIGHT_PACKET_STATE_INVALID', 'sealed disposition ID');
  else requireCondition(state.sealedDispositionId === null, 'PRIVATE_FLIGHT_PACKET_STATE_INVALID', 'unsealed packet names a disposition');
  assertIdentity(state, 'stcmaryprivateflightpacketstate1', 'stateId', 'PRIVATE_FLIGHT_PACKET_STATE_ID_INVALID');
  return state;
}

export function validatePrivateFlightPacketProfile(profile, physicalProfile) {
  exactKeys(profile, [
    'schema', 'profileId', 'physicalFlightProfileId', 'status', 'packetDirectoryPattern',
    'sealedDirectoryPattern', 'repositoryOutputAllowed', 'networkRequired', 'externalServiceCalls',
    'operationalCredentials', 'stageSequence', 'stages', 'claimBoundary',
  ], 'PRIVATE_FLIGHT_PACKET_PROFILE_INVALID', 'packet profile');
  requireCondition(profile.schema === 'stc-mary-private-flight-packet-profile/1', 'PRIVATE_FLIGHT_PACKET_PROFILE_INVALID', 'packet profile schema differs');
  requireCondition(
    profile.profileId === 'stc-mary/private-flight-packet/0.1' &&
      profile.physicalFlightProfileId === physicalProfile.profileId &&
      profile.status === 'candidate_design_only',
    'PRIVATE_FLIGHT_PACKET_PROFILE_INVALID',
    'packet profile identity, predecessor, or status differs',
  );
  requireCondition(
    profile.packetDirectoryPattern === PACKET_DIRECTORY.source &&
      profile.sealedDirectoryPattern === SEALED_DIRECTORY.source,
    'PRIVATE_FLIGHT_PACKET_PROFILE_INVALID',
    'packet directory patterns differ',
  );
  requireCondition(
    profile.repositoryOutputAllowed === false &&
      profile.networkRequired === false &&
      profile.externalServiceCalls === 0 &&
      profile.operationalCredentials === 0,
    'PRIVATE_FLIGHT_PACKET_PROFILE_INVALID',
    'packet profile widens output, network, service, or credential requirements',
  );
  requireCondition(canonicalJson(profile.stageSequence) === canonicalJson(STC_MARY_STAGES), 'PRIVATE_FLIGHT_PACKET_PROFILE_INVALID', 'packet stage sequence differs');
  exactKeys(profile.stages, STC_MARY_STAGES, 'PRIVATE_FLIGHT_PACKET_PROFILE_INVALID', 'stage instructions');
  for (const stage of STC_MARY_STAGES) {
    const row = profile.stages[stage];
    exactKeys(row, ['operatorAction', 'requiredEvidence', 'controlQuestion'], 'PRIVATE_FLIGHT_PACKET_PROFILE_INVALID', `${stage} instructions`);
    boundedString(row.operatorAction, 'PRIVATE_FLIGHT_PACKET_PROFILE_INVALID', `${stage} operator action`);
    uniqueStrings(row.requiredEvidence, 'PRIVATE_FLIGHT_PACKET_PROFILE_INVALID', `${stage} required evidence`);
    boundedString(row.controlQuestion, 'PRIVATE_FLIGHT_PACKET_PROFILE_INVALID', `${stage} control question`);
  }
  return profile;
}

async function loadProfiles() {
  const [packetProfile, physicalProfile] = await Promise.all([
    readJson(PACKET_PROFILE_PATH),
    readJson(PHYSICAL_PROFILE_PATH),
  ]);
  validateStcMaryPhysicalFlightProfile(physicalProfile);
  validatePrivateFlightPacketProfile(packetProfile, physicalProfile);
  return { packetProfile, physicalProfile };
}

function initialConfig(marker, template) {
  return {
    schema: 'stc-mary-private-flight-packet-config/1',
    campaignLabel: marker.campaignLabel,
    sourceObjectDigests: [],
    identityClasses: structuredClone(template.identityClasses),
    canonicalMissionStateDigest: null,
    authority: 'none',
    claimBoundary: 'Local private-flight configuration. Replace every incomplete field before recording a stage. This file remains outside the public repository.',
  };
}

export function validatePrivateFlightPacketConfig(config, marker) {
  exactKeys(config, [
    'schema', 'campaignLabel', 'sourceObjectDigests', 'identityClasses',
    'canonicalMissionStateDigest', 'authority', 'claimBoundary',
  ], 'PRIVATE_FLIGHT_PACKET_CONFIG_INVALID', 'packet configuration');
  requireCondition(config.schema === 'stc-mary-private-flight-packet-config/1', 'PRIVATE_FLIGHT_PACKET_CONFIG_INVALID', 'packet configuration schema differs');
  requireCondition(config.campaignLabel === marker.campaignLabel && !config.campaignLabel.startsWith('REPLACE_WITH_'), 'PRIVATE_FLIGHT_PACKET_CONFIG_INVALID', 'campaign label differs or remains incomplete');
  uniqueStrings(config.sourceObjectDigests, 'PRIVATE_FLIGHT_PACKET_CONFIG_INVALID', 'source object digests');
  config.sourceObjectDigests.forEach((row) => assertSha256(row, 'PRIVATE_FLIGHT_PACKET_CONFIG_INVALID', 'source object digest'));
  exactKeys(config.identityClasses, [
    'personalFloor', 'halo3', 'initialHead', 'successorHead', 'graceBind',
    'lattice', 'leftCell', 'rightCell',
  ], 'PRIVATE_FLIGHT_PACKET_CONFIG_INVALID', 'identity classes');
  for (const [key, value] of Object.entries(config.identityClasses)) {
    boundedString(value, 'PRIVATE_FLIGHT_PACKET_CONFIG_INVALID', key, 256);
    requireCondition(!value.startsWith('REPLACE_WITH_'), 'PRIVATE_FLIGHT_PACKET_CONFIG_INVALID', `${key} remains incomplete`);
  }
  assertSha256(config.canonicalMissionStateDigest, 'PRIVATE_FLIGHT_PACKET_CONFIG_INVALID', 'canonical mission state digest');
  requireCondition(config.authority === 'none', 'PRIVATE_FLIGHT_PACKET_CONFIG_INVALID', 'packet configuration carries authority');
  return config;
}

function createStageDraft(stage, sequence, templateStage) {
  return {
    schema: 'stc-mary-private-flight-stage-draft/1',
    sequence,
    stage,
    terminalState: REQUIRED_STAGE_TERMINALS[stage],
    canonicalMissionStateIdBefore: null,
    canonicalMissionStateIdAfter: null,
    observation: structuredClone(templateStage.observation),
    operatorConfirmed: false,
    evidenceClass: 'private_local_attestation',
    mediaType: 'application/octet-stream',
    notes: '',
  };
}

function validateStageDraft(draft, stage, sequence, config) {
  exactKeys(draft, [
    'schema', 'sequence', 'stage', 'terminalState', 'canonicalMissionStateIdBefore',
    'canonicalMissionStateIdAfter', 'observation', 'operatorConfirmed', 'evidenceClass',
    'mediaType', 'notes',
  ], 'PRIVATE_FLIGHT_STAGE_DRAFT_INVALID', 'stage draft');
  requireCondition(
    draft.schema === 'stc-mary-private-flight-stage-draft/1' &&
      draft.sequence === sequence &&
      draft.stage === stage &&
      draft.terminalState === REQUIRED_STAGE_TERMINALS[stage],
    'PRIVATE_FLIGHT_STAGE_DRAFT_INVALID',
    'stage draft identity, order, or terminal state differs',
  );
  requireCondition(
    draft.canonicalMissionStateIdBefore === config.canonicalMissionStateDigest &&
      draft.canonicalMissionStateIdAfter === config.canonicalMissionStateDigest,
    'PRIVATE_FLIGHT_STAGE_DRAFT_INVALID',
    'stage draft canonical state differs from configuration',
  );
  validatePhysicalFlightObservation(stage, draft.observation);
  requireCondition(draft.operatorConfirmed === true, 'PRIVATE_FLIGHT_STAGE_DRAFT_UNCONFIRMED', 'stage draft lacks explicit operator confirmation');
  requireCondition(PRIVATE_EVIDENCE_CLASSES.has(draft.evidenceClass), 'PRIVATE_FLIGHT_STAGE_DRAFT_INVALID', 'stage evidence class differs');
  boundedString(draft.mediaType, 'PRIVATE_FLIGHT_STAGE_DRAFT_INVALID', 'stage media type', 256);
  requireCondition(typeof draft.notes === 'string' && draft.notes.length <= 16384, 'PRIVATE_FLIGHT_STAGE_DRAFT_INVALID', 'stage notes are invalid or unbounded');
  return draft;
}

function applyIdentityClasses(stage, observation, identityClasses) {
  const changed = structuredClone(observation);
  switch (stage) {
    case 'MOUNT_PERSONAL_FLOOR':
      changed.personalFloorSeatIdentityClass = identityClasses.personalFloor;
      break;
    case 'BIND_GRACE':
      changed.humanBindIdentityClass = identityClasses.graceBind;
      break;
    case 'ATTACH_HALO3':
    case 'REMOVE_HALO3':
      changed.halo3SeatIdentityClass = identityClasses.halo3;
      break;
    case 'REMOVE_LATTICE':
      changed.latticeIdentityClass = identityClasses.lattice;
      break;
    case 'PARTITION_TWO_CELLS':
      changed.cellIdentityClasses = [identityClasses.leftCell, identityClasses.rightCell];
      break;
    case 'REPLACE_HEAD':
      changed.oldHeadIdentityClass = identityClasses.initialHead;
      changed.newHeadIdentityClass = identityClasses.successorHead;
      break;
    case 'COLD_SUCCESSOR_VERIFY':
      changed.successorHeadIdentityClass = identityClasses.successorHead;
      break;
    default:
      break;
  }
  return changed;
}

function renderStageInstructions(packetProfile, stage, sequence) {
  const row = packetProfile.stages[stage];
  return `# ${String(sequence).padStart(2, '0')} ${stage}\n\n${row.operatorAction}\n\n## Required evidence\n\n${row.requiredEvidence.map((value) => `- ${value}`).join('\n')}\n\n## Control question\n\n${row.controlQuestion}\n\nPlace every local evidence body in the \`evidence\` directory. Edit \`stage-attestation.json\` with the measured observation, set \`operatorConfirmed\` to \`true\`, then record the stage in sequence. Evidence bodies and paths remain local and must never be committed to the public repository.\n`;
}

export async function initializePrivateFlightPacket(packetDirectory, campaignLabel) {
  const { packetProfile, physicalProfile } = await loadProfiles();
  boundedString(campaignLabel, 'PRIVATE_FLIGHT_PACKET_INIT_INVALID', 'campaign label', 256);
  requireCondition(!campaignLabel.startsWith('REPLACE_WITH_'), 'PRIVATE_FLIGHT_PACKET_INIT_INVALID', 'campaign label remains incomplete');
  const resolved = await validateNewOutputDirectory(packetDirectory, PACKET_DIRECTORY, 'PRIVATE_FLIGHT_PACKET_OUTPUT_UNSAFE', 'packet directory');
  await mkdir(resolved);
  const marker = packetMarker({ packetProfile, physicalProfile, campaignLabel });
  const template = createPrivatePhysicalFlightTemplate(physicalProfile);
  await writeJson(join(resolved, FILES.marker), marker);
  await writeJson(join(resolved, FILES.config), initialConfig(marker, template));
  for (const [index, stage] of STC_MARY_STAGES.entries()) {
    const directory = join(resolved, stageDirectoryName(index + 1, stage));
    await mkdir(join(directory, 'evidence'), { recursive: true });
    await writeJson(join(directory, 'stage-attestation.json'), createStageDraft(stage, index + 1, template.stageAttestations[index]));
    await writeFile(join(directory, 'INSTRUCTIONS.md'), renderStageInstructions(packetProfile, stage, index + 1), 'utf8');
  }
  const state = createPacketState({ marker });
  await writeJson(join(resolved, FILES.state), state);
  return { packetDirectory: resolved, marker, state };
}

async function loadPacket(packetDirectory) {
  const resolved = resolve(packetDirectory);
  requireCondition(isInside(REPOSITORY_ROOT, resolved) === false, 'PRIVATE_FLIGHT_PACKET_OUTPUT_UNSAFE', 'packet directory must remain outside the public repository');
  const { packetProfile, physicalProfile } = await loadProfiles();
  const [marker, state] = await Promise.all([
    readJson(join(resolved, FILES.marker)),
    readJson(join(resolved, FILES.state)),
  ]);
  validatePacketMarker(marker, packetProfile, physicalProfile);
  validatePacketState(state, marker);
  return { resolved, packetProfile, physicalProfile, marker, state };
}

export async function configurePrivateFlightPacket(packetDirectory, configPath) {
  const packet = await loadPacket(packetDirectory);
  requireCondition(packet.state.sealed === false, 'PRIVATE_FLIGHT_PACKET_ALREADY_SEALED', 'sealed packet cannot be reconfigured');
  const config = await readJson(resolve(configPath));
  validatePrivateFlightPacketConfig(config, packet.marker);
  await writeJson(join(packet.resolved, FILES.config), config);
  for (const [index, stage] of STC_MARY_STAGES.entries()) {
    const stageState = packet.state.stages[index];
    requireCondition(stageState.status === 'unrecorded', 'PRIVATE_FLIGHT_PACKET_CONFIGURATION_LOCKED', 'recorded stages prevent reconfiguration');
    const draftPath = join(packet.resolved, stageState.draftPath);
    const draft = await readJson(draftPath);
    draft.canonicalMissionStateIdBefore = config.canonicalMissionStateDigest;
    draft.canonicalMissionStateIdAfter = config.canonicalMissionStateDigest;
    draft.observation = applyIdentityClasses(stage, draft.observation, config.identityClasses);
    await writeJson(draftPath, draft);
  }
  const state = createPacketState({
    marker: packet.marker,
    configurationState: 'configured',
    stages: packet.state.stages,
    sealed: false,
    sealedDispositionId: null,
  });
  await writeJson(join(packet.resolved, FILES.state), state);
  return state;
}

async function hashEvidenceFile(path) {
  const bytes = await readFile(path);
  requireCondition(bytes.length > 0 && bytes.length <= MAX_EVIDENCE_BYTES, 'PRIVATE_FLIGHT_STAGE_EVIDENCE_INVALID', 'evidence file is empty or unbounded');
  return { sha256: digestBytes(bytes), bytes: bytes.length };
}

async function evidenceFilesForStage(packet, stageState, draft) {
  const evidenceDirectory = join(packet.resolved, stageState.evidenceDirectory);
  const names = (await readdir(evidenceDirectory)).sort((a, b) => a.localeCompare(b));
  requireCondition(names.length > 0 && names.length <= MAX_EVIDENCE_FILES, 'PRIVATE_FLIGHT_STAGE_EVIDENCE_INVALID', 'evidence file denominator is empty or unbounded');
  const rows = [];
  for (const name of names) {
    const path = join(evidenceDirectory, name);
    const metadata = await pathState(path);
    requireCondition(metadata?.isFile(), 'PRIVATE_FLIGHT_STAGE_EVIDENCE_INVALID', `evidence entry is not a regular file: ${name}`);
    const hashed = await hashEvidenceFile(path);
    rows.push({
      relativePath: relative(packet.resolved, path).replaceAll('\\', '/'),
      sha256: hashed.sha256,
      bytes: hashed.bytes,
      mediaType: draft.mediaType,
      evidenceClass: draft.evidenceClass,
    });
  }
  return rows;
}

function createStageRecord({ packet, draft, evidenceFiles }) {
  const body = {
    schema: 'stc-mary-private-flight-stage-record/1',
    packetId: packet.marker.packetId,
    sequence: draft.sequence,
    stage: draft.stage,
    terminalState: draft.terminalState,
    canonicalMissionStateIdBefore: draft.canonicalMissionStateIdBefore,
    canonicalMissionStateIdAfter: draft.canonicalMissionStateIdAfter,
    observation: structuredClone(draft.observation),
    evidenceFiles,
    operatorConfirmed: true,
    notes: draft.notes,
    authority: 'none',
    claimBoundary: 'Local stage record with relative evidence references. It remains outside the public repository and grants no physical, mission, command, targeting, engagement, effector, or weapons authority.',
  };
  return { ...body, recordDigest: digest('stcmaryprivateflightstagerecord1', body) };
}

function validateStageRecord(record, packet, stageState) {
  exactKeys(record, [
    'schema', 'recordDigest', 'packetId', 'sequence', 'stage', 'terminalState',
    'canonicalMissionStateIdBefore', 'canonicalMissionStateIdAfter', 'observation',
    'evidenceFiles', 'operatorConfirmed', 'notes', 'authority', 'claimBoundary',
  ], 'PRIVATE_FLIGHT_STAGE_RECORD_INVALID', 'stage record');
  requireCondition(
    record.schema === 'stc-mary-private-flight-stage-record/1' &&
      record.packetId === packet.marker.packetId &&
      record.sequence === stageState.sequence &&
      record.stage === stageState.stage &&
      record.terminalState === REQUIRED_STAGE_TERMINALS[record.stage],
    'PRIVATE_FLIGHT_STAGE_RECORD_INVALID',
    'stage record binding, order, or terminal state differs',
  );
  assertSha256(record.canonicalMissionStateIdBefore, 'PRIVATE_FLIGHT_STAGE_RECORD_INVALID', 'canonical state before');
  requireCondition(record.canonicalMissionStateIdBefore === record.canonicalMissionStateIdAfter, 'PRIVATE_FLIGHT_STAGE_RECORD_INVALID', 'stage record mutates canonical mission state');
  validatePhysicalFlightObservation(record.stage, record.observation);
  requireCondition(Array.isArray(record.evidenceFiles) && record.evidenceFiles.length > 0 && record.evidenceFiles.length <= MAX_EVIDENCE_FILES, 'PRIVATE_FLIGHT_STAGE_RECORD_INVALID', 'stage record evidence denominator differs');
  for (const row of record.evidenceFiles) {
    exactKeys(row, ['relativePath', 'sha256', 'bytes', 'mediaType', 'evidenceClass'], 'PRIVATE_FLIGHT_STAGE_RECORD_INVALID', 'stage evidence row');
    boundedString(row.relativePath, 'PRIVATE_FLIGHT_STAGE_RECORD_INVALID', 'relative evidence path');
    requireCondition(!isAbsolute(row.relativePath) && !row.relativePath.startsWith('..'), 'PRIVATE_FLIGHT_STAGE_RECORD_INVALID', 'evidence path escapes the packet');
    assertSha256(row.sha256, 'PRIVATE_FLIGHT_STAGE_RECORD_INVALID', 'evidence sha256');
    safeInteger(row.bytes, 1, MAX_EVIDENCE_BYTES, 'PRIVATE_FLIGHT_STAGE_RECORD_INVALID', 'evidence bytes');
    boundedString(row.mediaType, 'PRIVATE_FLIGHT_STAGE_RECORD_INVALID', 'media type', 256);
    requireCondition(PRIVATE_EVIDENCE_CLASSES.has(row.evidenceClass), 'PRIVATE_FLIGHT_STAGE_RECORD_INVALID', 'evidence class differs');
  }
  requireCondition(record.operatorConfirmed === true && record.authority === 'none', 'PRIVATE_FLIGHT_STAGE_RECORD_INVALID', 'stage record lacks operator confirmation or carries authority');
  assertIdentity(record, 'stcmaryprivateflightstagerecord1', 'recordDigest', 'PRIVATE_FLIGHT_STAGE_RECORD_ID_INVALID');
  return record;
}

export async function recordPrivateFlightStage(packetDirectory, stage) {
  const packet = await loadPacket(packetDirectory);
  requireCondition(packet.state.configurationState === 'configured', 'PRIVATE_FLIGHT_PACKET_NOT_CONFIGURED', 'packet must be configured before recording stages');
  requireCondition(packet.state.sealed === false, 'PRIVATE_FLIGHT_PACKET_ALREADY_SEALED', 'sealed packet cannot record another stage');
  requireCondition(STC_MARY_STAGES.includes(stage), 'PRIVATE_FLIGHT_STAGE_INVALID', 'stage is not in the closed denominator');
  requireCondition(packet.state.nextStage === stage, 'PRIVATE_FLIGHT_STAGE_OUT_OF_ORDER', `next stage is ${packet.state.nextStage}`);
  const stageState = packet.state.stages.find((row) => row.stage === stage);
  const config = await readJson(join(packet.resolved, FILES.config));
  validatePrivateFlightPacketConfig(config, packet.marker);
  const draft = await readJson(join(packet.resolved, stageState.draftPath));
  validateStageDraft(draft, stage, stageState.sequence, config);
  const evidenceFiles = await evidenceFilesForStage(packet, stageState, draft);
  const record = createStageRecord({ packet, draft, evidenceFiles });
  validateStageRecord(record, packet, stageState);
  const stageDirectory = dirname(join(packet.resolved, stageState.draftPath));
  await writeJson(join(stageDirectory, 'stage-record.json'), record);
  const stages = packet.state.stages.map((row) => row.stage === stage
    ? { ...row, status: 'recorded', evidenceCount: evidenceFiles.length, recordDigest: record.recordDigest }
    : row);
  const state = createPacketState({
    marker: packet.marker,
    configurationState: 'configured',
    stages,
    sealed: false,
    sealedDispositionId: null,
  });
  await writeJson(join(packet.resolved, FILES.state), state);
  return { record, state };
}

async function buildPrivateRequest(packet) {
  requireCondition(packet.state.configurationState === 'configured', 'PRIVATE_FLIGHT_PACKET_NOT_CONFIGURED', 'packet is not configured');
  requireCondition(packet.state.completedStageCount === STC_MARY_STAGES.length && packet.state.nextStage === null, 'PRIVATE_FLIGHT_PACKET_INCOMPLETE', 'all sixteen stages must be recorded before sealing');
  const config = await readJson(join(packet.resolved, FILES.config));
  validatePrivateFlightPacketConfig(config, packet.marker);
  const request = createPrivatePhysicalFlightTemplate(packet.physicalProfile);
  request.campaignLabel = config.campaignLabel;
  request.sourceObjectDigests = [...config.sourceObjectDigests];
  request.identityClasses = structuredClone(config.identityClasses);
  request.canonicalMissionStateDigest = config.canonicalMissionStateDigest;
  request.stageAttestations = [];
  for (const stageState of packet.state.stages) {
    const record = await readJson(join(dirname(join(packet.resolved, stageState.draftPath)), 'stage-record.json'));
    validateStageRecord(record, packet, stageState);
    const evidenceBodies = [];
    for (const evidence of record.evidenceFiles) {
      const absolutePath = resolve(packet.resolved, evidence.relativePath);
      requireCondition(isInside(packet.resolved, absolutePath), 'PRIVATE_FLIGHT_STAGE_EVIDENCE_INVALID', 'evidence path escapes the packet');
      const hashed = await hashEvidenceFile(absolutePath);
      requireCondition(hashed.sha256 === evidence.sha256 && hashed.bytes === evidence.bytes, 'PRIVATE_FLIGHT_STAGE_EVIDENCE_DRIFT', `evidence changed after recording: ${evidence.relativePath}`);
      evidenceBodies.push({
        path: absolutePath,
        mediaType: evidence.mediaType,
        evidenceClass: evidence.evidenceClass,
      });
    }
    request.stageAttestations.push({
      stage: record.stage,
      terminalState: record.terminalState,
      canonicalMissionStateIdBefore: record.canonicalMissionStateIdBefore,
      canonicalMissionStateIdAfter: record.canonicalMissionStateIdAfter,
      observation: structuredClone(record.observation),
      evidenceBodies,
    });
  }
  validatePrivatePhysicalFlightRequest(request, packet.physicalProfile);
  await writeJson(join(packet.resolved, FILES.request), request);
  return request;
}

function sealedMarker(run, disposition) {
  const body = {
    schema: 'stc-mary-private-flight-sealed-root/1',
    runId: run.runId,
    dispositionId: disposition.dispositionId,
    flightMode: run.flightMode,
    publicEvidenceBodyCount: 0,
    authority: 'none',
    claimBoundary: 'Marker for one local digest-only sealed flight result. Private evidence bodies remain in the packet and this directory grants no independent qualification or authority.',
  };
  return { ...body, markerId: digest('stcmaryprivateflightsealedroot1', body) };
}

function validateSealedMarker(marker) {
  exactKeys(marker, [
    'schema', 'markerId', 'runId', 'dispositionId', 'flightMode',
    'publicEvidenceBodyCount', 'authority', 'claimBoundary',
  ], 'PRIVATE_FLIGHT_SEALED_MARKER_INVALID', 'sealed marker');
  requireCondition(marker.schema === 'stc-mary-private-flight-sealed-root/1' && marker.flightMode === 'private_physical_attested', 'PRIVATE_FLIGHT_SEALED_MARKER_INVALID', 'sealed marker schema or mode differs');
  assertContentId(marker.runId, 'PRIVATE_FLIGHT_SEALED_MARKER_INVALID', 'run ID');
  assertContentId(marker.dispositionId, 'PRIVATE_FLIGHT_SEALED_MARKER_INVALID', 'disposition ID');
  requireCondition(marker.publicEvidenceBodyCount === 0 && marker.authority === 'none', 'PRIVATE_FLIGHT_SEALED_MARKER_INVALID', 'sealed marker widens evidence or authority');
  assertIdentity(marker, 'stcmaryprivateflightsealedroot1', 'markerId', 'PRIVATE_FLIGHT_SEALED_MARKER_ID_INVALID');
  return marker;
}

async function manifestEntry(directory, fileName) {
  const bytes = await readFile(join(directory, fileName));
  return { path: fileName, bytes: bytes.length, sha256: digestBytes(bytes) };
}

function validateSealedManifest(manifest, marker) {
  exactKeys(manifest, [
    'schema', 'manifestId', 'runId', 'dispositionId', 'files', 'fileCount',
    'publicEvidenceBodyCount', 'authority', 'claimBoundary',
  ], 'PRIVATE_FLIGHT_SEALED_MANIFEST_INVALID', 'sealed manifest');
  requireCondition(manifest.schema === 'stc-mary-private-flight-sealed-manifest/1', 'PRIVATE_FLIGHT_SEALED_MANIFEST_INVALID', 'sealed manifest schema differs');
  requireCondition(manifest.runId === marker.runId && manifest.dispositionId === marker.dispositionId, 'PRIVATE_FLIGHT_SEALED_MANIFEST_INVALID', 'sealed manifest belongs to another marker');
  requireCondition(Array.isArray(manifest.files) && manifest.files.length === manifest.fileCount && manifest.files.length === 5, 'PRIVATE_FLIGHT_SEALED_MANIFEST_INVALID', 'sealed manifest file denominator differs');
  requireCondition(manifest.publicEvidenceBodyCount === 0 && manifest.authority === 'none', 'PRIVATE_FLIGHT_SEALED_MANIFEST_INVALID', 'sealed manifest widens evidence or authority');
  assertIdentity(manifest, 'stcmaryprivateflightsealedmanifest1', 'manifestId', 'PRIVATE_FLIGHT_SEALED_MANIFEST_ID_INVALID');
  return manifest;
}

export async function sealPrivateFlightPacket(packetDirectory, sealedDirectory) {
  const packet = await loadPacket(packetDirectory);
  requireCondition(packet.state.sealed === false, 'PRIVATE_FLIGHT_PACKET_ALREADY_SEALED', 'packet is already sealed');
  const resolvedSealed = await validateNewOutputDirectory(sealedDirectory, SEALED_DIRECTORY, 'PRIVATE_FLIGHT_SEALED_OUTPUT_UNSAFE', 'sealed directory');
  const request = await buildPrivateRequest(packet);
  const { run, disposition } = await sealPrivateStcMaryPhysicalFlight({ profile: packet.physicalProfile, request });
  validateStcMaryPhysicalFlightRun(run, packet.physicalProfile);
  validatePublicPhysicalFlightDisposition(disposition, run);
  const verification = verifyStcMaryPhysicalFlightRun(run, { profile: packet.physicalProfile });
  const projection = buildStcMaryPhysicalFlightProjection(run);
  const review = renderStcMaryPhysicalFlightHtml(projection);
  const marker = sealedMarker(run, disposition);
  await mkdir(resolvedSealed);
  await writeJson(join(resolvedSealed, FILES.sealedMarker), marker);
  await writeJson(join(resolvedSealed, FILES.sealedRun), run);
  await writeJson(join(resolvedSealed, FILES.publicDisposition), disposition);
  await writeJson(join(resolvedSealed, FILES.verification), verification);
  await writeFile(join(resolvedSealed, FILES.review), review, 'utf8');
  const fileNames = [FILES.sealedMarker, FILES.sealedRun, FILES.publicDisposition, FILES.verification, FILES.review];
  const entries = [];
  for (const fileName of fileNames) entries.push(await manifestEntry(resolvedSealed, fileName));
  const manifestBody = {
    schema: 'stc-mary-private-flight-sealed-manifest/1',
    runId: run.runId,
    dispositionId: disposition.dispositionId,
    files: entries,
    fileCount: entries.length,
    publicEvidenceBodyCount: 0,
    authority: 'none',
    claimBoundary: 'Digest manifest for one local sealed flight result. It contains no private evidence bodies or paths and grants no independent qualification or authority.',
  };
  const manifest = { ...manifestBody, manifestId: digest('stcmaryprivateflightsealedmanifest1', manifestBody) };
  await writeJson(join(resolvedSealed, FILES.manifest), manifest);
  const state = createPacketState({
    marker: packet.marker,
    configurationState: 'configured',
    stages: packet.state.stages,
    sealed: true,
    sealedDispositionId: disposition.dispositionId,
  });
  await writeJson(join(packet.resolved, FILES.state), state);
  return { sealedDirectory: resolvedSealed, run, disposition, verification, manifest, state };
}

export async function verifySealedPrivateFlightPacket(sealedDirectory) {
  const resolved = resolve(sealedDirectory);
  requireCondition(!isInside(REPOSITORY_ROOT, resolved), 'PRIVATE_FLIGHT_SEALED_OUTPUT_UNSAFE', 'sealed directory must remain outside the public repository');
  const { physicalProfile } = await loadProfiles();
  const [marker, manifest, run, disposition, verification, review] = await Promise.all([
    readJson(join(resolved, FILES.sealedMarker)),
    readJson(join(resolved, FILES.manifest)),
    readJson(join(resolved, FILES.sealedRun)),
    readJson(join(resolved, FILES.publicDisposition)),
    readJson(join(resolved, FILES.verification)),
    readFile(join(resolved, FILES.review), 'utf8'),
  ]);
  validateSealedMarker(marker);
  validateSealedManifest(manifest, marker);
  for (const row of manifest.files) {
    exactKeys(row, ['path', 'bytes', 'sha256'], 'PRIVATE_FLIGHT_SEALED_MANIFEST_INVALID', 'sealed manifest file');
    const bytes = await readFile(join(resolved, row.path));
    requireCondition(bytes.length === row.bytes && digestBytes(bytes) === row.sha256, 'PRIVATE_FLIGHT_SEALED_FILE_MISMATCH', `sealed file differs: ${row.path}`);
  }
  validateStcMaryPhysicalFlightRun(run, physicalProfile);
  validatePublicPhysicalFlightDisposition(disposition, run);
  const replayedVerification = verifyStcMaryPhysicalFlightRun(run, { profile: physicalProfile });
  exactObject(verification, replayedVerification, 'PRIVATE_FLIGHT_SEALED_VERIFICATION_MISMATCH', 'sealed verification replay');
  exactObject(review, renderStcMaryPhysicalFlightHtml(buildStcMaryPhysicalFlightProjection(run)), 'PRIVATE_FLIGHT_SEALED_REVIEW_MISMATCH', 'sealed review replay');
  requireCondition(marker.runId === run.runId && marker.dispositionId === disposition.dispositionId, 'PRIVATE_FLIGHT_SEALED_BINDING_INVALID', 'sealed marker names another run or disposition');
  const body = {
    schema: 'stc-mary-private-flight-sealed-verification/1',
    runId: run.runId,
    dispositionId: disposition.dispositionId,
    status: 'PASS',
    fileCount: manifest.fileCount,
    stageCount: run.stageCount,
    privatePhysicalEvidenceBodyCount: run.privatePhysicalEvidenceBodyCount,
    publicEvidenceBodyCount: 0,
    bodyFreePublicDisposition: true,
    deterministicReceiptReplay: true,
    physicalEstateQualified: false,
    representativeOperatorQualified: false,
    fieldNetworkQualified: false,
    operationalC2Qualified: false,
    productionLatticeQualified: false,
    authority: 'none',
    claimBoundary: 'Detached verification of one local sealed self-attestation package. It grants no independent physical, operator, field, operational, mission, command, targeting, engagement, effector, or weapons qualification or authority.',
  };
  return { ...body, verificationId: digest('stcmaryprivateflightsealedverification1', body) };
}

export async function privateFlightPacketStatus(packetDirectory) {
  const packet = await loadPacket(packetDirectory);
  return {
    schema: 'stc-mary-private-flight-packet-status/1',
    packetId: packet.marker.packetId,
    campaignLabel: packet.marker.campaignLabel,
    configurationState: packet.state.configurationState,
    completedStageCount: packet.state.completedStageCount,
    stageCount: STC_MARY_STAGES.length,
    nextStage: packet.state.nextStage,
    sealed: packet.state.sealed,
    sealedDispositionId: packet.state.sealedDispositionId,
    authority: 'none',
  };
}

export async function runStcMaryPrivateFlightPacketCli(argv) {
  const command = argv[2];
  if (command === 'init') {
    const result = await initializePrivateFlightPacket(resolve(argv[3]), argv[4]);
    process.stdout.write(`${JSON.stringify({ status: 'INITIALIZED', packetId: result.marker.packetId, packetDirectory: result.packetDirectory, nextStage: result.state.nextStage }, null, 2)}\n`);
    return;
  }
  if (command === 'configure') {
    const state = await configurePrivateFlightPacket(resolve(argv[3]), resolve(argv[4]));
    process.stdout.write(`${JSON.stringify({ status: 'CONFIGURED', stateId: state.stateId, nextStage: state.nextStage }, null, 2)}\n`);
    return;
  }
  if (command === 'record') {
    const result = await recordPrivateFlightStage(resolve(argv[3]), argv[4]);
    process.stdout.write(`${JSON.stringify({ status: 'RECORDED', stage: result.record.stage, recordDigest: result.record.recordDigest, nextStage: result.state.nextStage }, null, 2)}\n`);
    return;
  }
  if (command === 'status') {
    process.stdout.write(`${JSON.stringify(await privateFlightPacketStatus(resolve(argv[3])), null, 2)}\n`);
    return;
  }
  if (command === 'seal') {
    const result = await sealPrivateFlightPacket(resolve(argv[3]), resolve(argv[4]));
    process.stdout.write(`${JSON.stringify({ status: 'SEALED', runId: result.run.runId, dispositionId: result.disposition.dispositionId, sealedDirectory: result.sealedDirectory }, null, 2)}\n`);
    return;
  }
  if (command === 'verify-sealed') {
    const verification = await verifySealedPrivateFlightPacket(resolve(argv[3]));
    if (argv[4] !== undefined) await writeJson(resolve(argv[4]), verification);
    process.stdout.write(`${JSON.stringify(verification, null, 2)}\n`);
    return;
  }
  throw new StcMaryPrivateFlightPacketError(
    'COMMAND_INVALID',
    'usage: stc_mary_private_flight_packet.mjs init <packet-dir> <campaign-label> | configure <packet-dir> <config.json> | record <packet-dir> <stage> | status <packet-dir> | seal <packet-dir> <sealed-dir> | verify-sealed <sealed-dir> [verification.json]',
  );
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  runStcMaryPrivateFlightPacketCli(process.argv).catch((error) => {
    process.stderr.write(`${error instanceof StcMaryPrivateFlightPacketError ? error.code : 'UNEXPECTED_ERROR'}: ${error.message}\n`);
    process.exitCode = 1;
  });
}

import { createHash } from 'node:crypto';
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';
import { canonicalJson } from '../semantic/authority_sidecar.mjs';

const HERE = dirname(fileURLToPath(import.meta.url));
const DEFAULT_PROFILE = resolve(HERE, 'mission-profile-01.json');

const TOP_LEVEL_KEYS = new Set([
  'schema',
  'profileId',
  'issue',
  'status',
  'authority',
  'graphEffect',
  'fieldEffect',
  'publicationEffect',
  'adoptionEffect',
  'sourceBase',
  'purpose',
  'missionProfile',
  'canonicalObjects',
  'claimKinds',
  'invariants',
  'existingPrimitiveMap',
  'optionalLatticeMembrane',
  'firstVerticalSlice',
  'hostileQualification',
  'acceptance',
  'claimBoundary',
]);

const OPERATING_LOOP = [
  'INGEST',
  'NORMALIZE',
  'CORRELATE',
  'UNDERSTAND',
  'PLAN',
  'AUTHORIZE',
  'REHEARSE_OR_EXECUTE_ONE_NON_KINETIC_LOCAL_TASK',
  'RECEIPT',
  'REPLAY',
  'RECONCILE',
];

const CLAIM_KINDS = [
  'observation',
  'inference',
  'decision',
  'grant',
  'execution',
  'result',
  'verification',
  'obligation',
];

const CANONICAL_OBJECTS = [
  'source_observation',
  'entity_state',
  'relationship_state',
  'uncertainty_state',
  'model_proposal',
  'authority_state',
  'policy_decision',
  'task_request',
  'execution_state',
  'verification_state',
  'reconciliation_obligation',
  'receipt',
];

const VERTICAL_SLICE = [
  'synthetic_observation',
  'local_entity_state',
  'local_model_proposal',
  'authority_decision',
  'one_non_kinetic_task_receipt',
  'detached_replay',
];

const PRIMITIVE_COMMITS = new Map([
  ['message-authority-runtime', '36b50c7b0a1a6043502291e0a1a5ddb18b9d1cf7'],
  ['evaluator-disposition', '7e31be460d1346d5c74730d5acfee00361e9bd4f'],
  ['c2sim-semantic-rehearsal', '4bedf63cfcc6d09e3d0a950f0039ff89507a7b32'],
  ['transport-fault-machine', 'b40a8794504b6a3c919d7be136ba425e36e57ba1'],
  ['operator-console', '893731334572ab7654f26fea14b5afb09794ae33'],
]);

const HOSTILE_SCENARIOS = [
  'start_without_WAN_or_Lattice',
  'ingest_synthetic_multisensor_and_logistics_feeds',
  'preserve_typed_uncertainty',
  'propose_one_bounded_non_kinetic_task',
  'partition_headquarters_communications',
  'exercise_local_authority_lease_limits',
  'inject_duplicate_and_delayed_messages',
  'kill_one_admitted_compute_worker_and_recover_without_false_completion',
  'trigger_interface_drift_refusal',
  'restore_conflicting_returning_authority_and_require_reconciliation',
  'export_complete_after_action_package',
  'destroy_and_rebuild_graph_query_and_cache_projections',
  'complete_cold_successor_five_question_test',
  'exercise_and_remove_optional_Lattice_contract_simulator',
];

const REQUIRED_INVARIANT_FRAGMENTS = [
  'local canonical mission state is independent',
  'claim kinds do not cross-convert',
  'models may propose and explain',
  'lost communications do not imply unlimited local authority',
  'returning authority does not silently overwrite local state',
  'automatic pass does not create evaluator acceptance',
  'failed or inaccessible workers cannot manufacture success',
  'destructible projections',
  'interface drift refuses rather than improvises',
  'real mode never falls back to or mixes synthetic custody',
  'cold successor must answer',
];

const CLAIM_BOUNDARY_KEYS = new Set([
  'operationalC2Profile',
  'fieldNetworkQualification',
  'representativeOperatorReadiness',
  'targetHardwareRuggedization',
  'LatticeProductionIntegration',
  'weaponsOrEffectorCapability',
  'commandAuthorityGranted',
  'syntheticMissionContinuitySubstrate',
]);

export class MissionProfileError extends Error {
  constructor(code, message) {
    super(message);
    this.name = 'MissionProfileError';
    this.code = code;
  }
}

function requireCondition(condition, code, message) {
  if (!condition) throw new MissionProfileError(code, message);
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

function exactArray(actual, expected, code, label) {
  requireCondition(Array.isArray(actual), code, `${label} must be an array`);
  requireCondition(canonicalJson(actual) === canonicalJson(expected), code, `${label} differs from the frozen contract`);
}

function uniqueStrings(values, code, label) {
  requireCondition(Array.isArray(values), code, `${label} must be an array`);
  requireCondition(values.every((value) => typeof value === 'string' && value.trim().length > 0), code, `${label} must contain bounded strings`);
  requireCondition(new Set(values).size === values.length, code, `${label} contains duplicates`);
}

function containsFragment(values, fragment) {
  return values.some((value) => value.includes(fragment));
}

export function validateMissionProfile(profile) {
  exactKeys(profile, TOP_LEVEL_KEYS, 'PROFILE_FIELDS_INVALID', 'mission profile');
  requireCondition(profile.schema === 'spectra-anchor-node-mission-profile/1', 'PROFILE_SCHEMA_INVALID', 'mission profile schema is invalid');
  requireCondition(profile.profileId === 'spectra-anchor-node/disconnected-multisensor-coordination/0.1', 'PROFILE_ID_INVALID', 'profileId is not the frozen Mission Profile 01 identifier');
  requireCondition(profile.issue === 26, 'PROFILE_ISSUE_INVALID', 'mission profile must remain bound to issue 26');
  requireCondition(profile.status === 'candidate_design_only', 'PROFILE_STATUS_INVALID', 'candidate contract cannot self-promote');
  for (const key of ['authority', 'graphEffect', 'fieldEffect', 'publicationEffect', 'adoptionEffect']) {
    requireCondition(profile[key] === 'none', 'PROFILE_EFFECT_INVALID', `${key} must remain none`);
  }
  requireCondition(typeof profile.purpose === 'string' && profile.purpose.length >= 120, 'PROFILE_PURPOSE_INVALID', 'purpose is missing or under-bounded');

  exactKeys(profile.sourceBase, new Set(['repository', 'commit']), 'SOURCE_BASE_INVALID', 'sourceBase');
  requireCondition(profile.sourceBase.repository === 'BigBirdReturns/ai-execution-audit', 'SOURCE_BASE_INVALID', 'source repository differs');
  requireCondition(profile.sourceBase.commit === '699017462401c2569287803741044f291480f191', 'SOURCE_BASE_INVALID', 'source base commit differs');

  exactKeys(profile.missionProfile, new Set(['name', 'classification', 'operatingLoop', 'scenario']), 'MISSION_PROFILE_INVALID', 'missionProfile');
  requireCondition(profile.missionProfile.name === 'Disconnected Multi-Sensor Coordination', 'MISSION_PROFILE_INVALID', 'mission profile name differs');
  requireCondition(profile.missionProfile.classification === 'invented_unclassified_synthetic_only', 'MISSION_CLASSIFICATION_INVALID', 'mission profile must remain synthetic-only');
  exactArray(profile.missionProfile.operatingLoop, OPERATING_LOOP, 'OPERATING_LOOP_INVALID', 'operatingLoop');
  requireCondition(typeof profile.missionProfile.scenario === 'string' && profile.missionProfile.scenario.includes('synthetic'), 'MISSION_SCENARIO_INVALID', 'mission scenario must remain explicitly synthetic');

  exactArray(profile.canonicalObjects, CANONICAL_OBJECTS, 'CANONICAL_OBJECTS_INVALID', 'canonicalObjects');
  exactArray(profile.claimKinds, CLAIM_KINDS, 'CLAIM_KINDS_INVALID', 'claimKinds');
  uniqueStrings(profile.invariants, 'INVARIANTS_INVALID', 'invariants');
  for (const fragment of REQUIRED_INVARIANT_FRAGMENTS) {
    requireCondition(containsFragment(profile.invariants, fragment), 'INVARIANTS_INVALID', `missing invariant fragment: ${fragment}`);
  }

  requireCondition(Array.isArray(profile.existingPrimitiveMap), 'PRIMITIVE_MAP_INVALID', 'existingPrimitiveMap must be an array');
  requireCondition(profile.existingPrimitiveMap.length === PRIMITIVE_COMMITS.size, 'PRIMITIVE_MAP_INVALID', 'primitive map size differs');
  const seenPrimitiveIds = new Set();
  for (const row of profile.existingPrimitiveMap) {
    exactKeys(row, new Set(['id', 'repository', 'commit', 'role', 'admission']), 'PRIMITIVE_MAP_INVALID', 'primitive row');
    requireCondition(PRIMITIVE_COMMITS.has(row.id), 'PRIMITIVE_MAP_INVALID', `unknown primitive ${row.id}`);
    requireCondition(!seenPrimitiveIds.has(row.id), 'PRIMITIVE_MAP_INVALID', `duplicate primitive ${row.id}`);
    seenPrimitiveIds.add(row.id);
    requireCondition(row.commit === PRIMITIVE_COMMITS.get(row.id), 'PRIMITIVE_MAP_INVALID', `primitive ${row.id} commit differs`);
    requireCondition(/^[0-9a-f]{40}$/.test(row.commit), 'PRIMITIVE_MAP_INVALID', `primitive ${row.id} commit is malformed`);
    requireCondition(typeof row.repository === 'string' && row.repository.startsWith('BigBirdReturns/'), 'PRIMITIVE_MAP_INVALID', `primitive ${row.id} repository is invalid`);
    requireCondition(typeof row.role === 'string' && row.role.length >= 24, 'PRIMITIVE_MAP_INVALID', `primitive ${row.id} role is under-specified`);
    requireCondition(['existing_repository_evidence', 'cross_repository_candidate_dependency'].includes(row.admission), 'PRIMITIVE_MAP_INVALID', `primitive ${row.id} admission is invalid`);
  }

  exactKeys(profile.optionalLatticeMembrane, new Set(['status', 'canonicalStateOwner', 'primitives', 'requiredBehavior', 'operationalCredentialsRequired']), 'LATTICE_MEMBRANE_INVALID', 'optionalLatticeMembrane');
  requireCondition(profile.optionalLatticeMembrane.status === 'contract_simulator_only', 'LATTICE_MEMBRANE_INVALID', 'Lattice membrane status is invalid');
  requireCondition(profile.optionalLatticeMembrane.canonicalStateOwner === false, 'LATTICE_MEMBRANE_INVALID', 'Lattice membrane cannot own canonical state');
  exactArray(profile.optionalLatticeMembrane.primitives, ['entity', 'task', 'object'], 'LATTICE_MEMBRANE_INVALID', 'Lattice primitives');
  requireCondition(profile.optionalLatticeMembrane.operationalCredentialsRequired === false, 'LATTICE_MEMBRANE_INVALID', 'Mission Profile 01 cannot require operational credentials');
  uniqueStrings(profile.optionalLatticeMembrane.requiredBehavior, 'LATTICE_MEMBRANE_INVALID', 'Lattice requiredBehavior');
  requireCondition(containsFragment(profile.optionalLatticeMembrane.requiredBehavior, 'continue local mission state'), 'LATTICE_MEMBRANE_INVALID', 'Lattice removal continuity behavior is missing');

  exactKeys(profile.firstVerticalSlice, new Set(['sequence', 'externalServices', 'operationalCredentials', 'targetHardwareQualification', 'fieldAuthority']), 'VERTICAL_SLICE_INVALID', 'firstVerticalSlice');
  exactArray(profile.firstVerticalSlice.sequence, VERTICAL_SLICE, 'VERTICAL_SLICE_INVALID', 'vertical slice sequence');
  requireCondition(profile.firstVerticalSlice.externalServices === 0, 'VERTICAL_SLICE_INVALID', 'vertical slice must use zero external services');
  requireCondition(profile.firstVerticalSlice.operationalCredentials === 0, 'VERTICAL_SLICE_INVALID', 'vertical slice must use zero operational credentials');
  requireCondition(profile.firstVerticalSlice.targetHardwareQualification === false, 'VERTICAL_SLICE_INVALID', 'vertical slice cannot qualify target hardware');
  requireCondition(profile.firstVerticalSlice.fieldAuthority === false, 'VERTICAL_SLICE_INVALID', 'vertical slice cannot grant field authority');

  exactArray(profile.hostileQualification, HOSTILE_SCENARIOS, 'HOSTILE_SCENARIOS_INVALID', 'hostileQualification');
  exactKeys(profile.acceptance, new Set(['requires', 'refuseIf']), 'ACCEPTANCE_INVALID', 'acceptance');
  uniqueStrings(profile.acceptance.requires, 'ACCEPTANCE_INVALID', 'acceptance.requires');
  uniqueStrings(profile.acceptance.refuseIf, 'ACCEPTANCE_INVALID', 'acceptance.refuseIf');
  for (const fragment of ['zero external-service dependency', 'exact synthetic-only custody', 'detached replay', 'cold successor', 'excluded operational claims']) {
    requireCondition(containsFragment(profile.acceptance.requires, fragment), 'ACCEPTANCE_INVALID', `missing acceptance requirement: ${fragment}`);
  }
  for (const fragment of ['synthetic and real custody are mixed', 'model output is serialized as authority', 'projection state becomes canonical state', 'Lattice adapter becomes required', 'weapons']) {
    requireCondition(containsFragment(profile.acceptance.refuseIf, fragment), 'ACCEPTANCE_INVALID', `missing refusal condition: ${fragment}`);
  }

  exactKeys(profile.claimBoundary, CLAIM_BOUNDARY_KEYS, 'CLAIM_BOUNDARY_INVALID', 'claimBoundary');
  for (const key of CLAIM_BOUNDARY_KEYS) {
    if (key === 'syntheticMissionContinuitySubstrate') continue;
    requireCondition(profile.claimBoundary[key] === false, 'CLAIM_BOUNDARY_INVALID', `${key} must remain false`);
  }
  requireCondition(profile.claimBoundary.syntheticMissionContinuitySubstrate === 'candidate', 'CLAIM_BOUNDARY_INVALID', 'synthetic substrate must remain candidate');

  const encoded = canonicalJson(profile).toLowerCase();
  for (const forbidden of ['"operationalc2profile":true', '"fieldnetworkqualification":true', '"weaponsoreffectorcapability":true', '"commandauthoritygranted":true']) {
    requireCondition(!encoded.includes(forbidden), 'CLAIM_BOUNDARY_INVALID', `forbidden claim generated: ${forbidden}`);
  }

  return profile;
}

export function missionProfileReceipt(profile) {
  validateMissionProfile(profile);
  const canonical = canonicalJson(profile);
  return {
    schema: 'spectra-anchor-node-mission-profile-validation/1',
    profileId: profile.profileId,
    status: 'PASS',
    sha256: createHash('sha256').update(canonical, 'utf8').digest('hex'),
    authority: 'none',
    claimBoundary: 'Validation proves contract shape and frozen boundaries only. It grants no runtime, field, publication, adoption, or command authority.',
  };
}

async function main(argv) {
  const path = resolve(argv[2] ?? DEFAULT_PROFILE);
  const profile = JSON.parse(await readFile(path, 'utf8'));
  process.stdout.write(`${JSON.stringify(missionProfileReceipt(profile), null, 2)}\n`);
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  main(process.argv).catch((error) => {
    const code = error instanceof MissionProfileError ? error.code : 'UNEXPECTED_ERROR';
    process.stderr.write(`${code}: ${error.message}\n`);
    process.exitCode = 1;
  });
}

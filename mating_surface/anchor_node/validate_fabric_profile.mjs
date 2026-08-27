import { createHash } from 'node:crypto';
import { readFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { canonicalJson } from '../semantic/authority_sidecar.mjs';

const HERE = dirname(fileURLToPath(import.meta.url));
const DEFAULT_PROFILE = resolve(HERE, 'fabric-profile-01.json');
const SHA40 = /^[0-9a-f]{40}$/;

const TOP_LEVEL_KEYS = new Set([
  'schema',
  'profileId',
  'issue',
  'status',
  'authority',
  'missionStateEffect',
  'fieldEffect',
  'publicationEffect',
  'adoptionEffect',
  'predecessors',
  'purpose',
  'publicFixturePolicy',
  'contractObjects',
  'seatSemantics',
  'routeBinding',
  'firstVerticalSlice',
  'hostileQualification',
  'evidenceTiers',
  'acceptance',
  'claimBoundary',
]);

const CONTRACT_OBJECTS = [
  'estate-seat-snapshot/1',
  'estate-seat-admission/1',
  'estate-route-selection/1',
  'estate-worker-lease/1',
  'estate-completion-candidate/1',
  'estate-completion-refusal/1',
  'estate-fabric-run/1',
  'estate-fabric-verification/1',
];

const ROUTE_BINDING = [
  'seat_identity',
  'seat_snapshot_digest',
  'host_identity_class',
  'accelerator_identity_class',
  'endpoint_identity',
  'runtime_version',
  'adapter_version',
  'model_or_executable_digest',
  'invocation_contract',
  'context_and_kv_contract',
  'workload_class',
  'acceptance_predicate',
  'residency_evidence',
  'power_state_evidence_when_claimed',
  'independent_verifier_identity',
  'output_digest',
  'terminal_receipt',
];

const VERTICAL_SLICE = [
  'admitted_mp01_local_artifact_job',
  'exact_estate_seat_snapshot',
  'seat_admission',
  'qualified_route_selection',
  'finite_worker_lease',
  'bounded_execution_candidate',
  'independent_output_verification',
  'exactly_one_terminal_completion_receipt',
  'detached_replay',
];

const HOSTILE_SCENARIOS = [
  'refuse_seat_absent_from_exact_snapshot',
  'refuse_unqualified_accelerator_or_runtime_class',
  'refuse_independent_seat_memory_pooling',
  'refuse_endpoint_model_template_context_or_verifier_drift',
  'expire_worker_lease_and_refuse_late_completion',
  'make_primary_seat_inaccessible',
  'reassign_under_new_lease_generation',
  'refuse_stale_primary_completion',
  'accept_exactly_one_verified_fallback_completion',
  'refuse_duplicate_terminal_completion',
  'refuse_wrong_or_unverifiable_output',
  'preserve_job_custody_and_canonical_mp01_state',
  'remove_optional_seat_without_resident_floor_disruption',
  'destroy_and_rebuild_route_query_and_ui_projections',
  'extend_source_pinned_cold_successor_pack',
];

const EVIDENCE_TIERS = [
  {
    tier: 1,
    name: 'contract',
    status: 'candidate',
    scope: 'schemas_validators_synthetic_fixtures_and_deterministic_replay',
  },
  {
    tier: 2,
    name: 'ci_synthetic',
    status: 'not_yet_run',
    scope: 'complete_hostile_campaign_on_invented_seats',
  },
  {
    tier: 3,
    name: 'physical_host',
    status: 'not_admitted',
    scope: 'private_digest_referenced_seat_and_telemetry_flights',
  },
  {
    tier: 4,
    name: 'representative_operator',
    status: 'not_authorized',
    scope: 'separately_authorized_human_operation_against_physical_fabric',
  },
];

const CLAIM_BOUNDARY_KEYS = new Set([
  'missionProfilePredecessorAdmitted',
  'fabricContractCandidate',
  'syntheticFabricQualified',
  'physicalEstateQualified',
  'representativeOperatorQualified',
  'missionAuthorityFromHardware',
  'commandAuthorityGranted',
  'operationalC2Claim',
  'fieldNetworkClaim',
  'weaponsOrEffectorCapability',
]);

export class FabricProfileError extends Error {
  constructor(code, message) {
    super(message);
    this.name = 'FabricProfileError';
    this.code = code;
  }
}

function requireCondition(condition, code, message) {
  if (!condition) throw new FabricProfileError(code, message);
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
  requireCondition(
    canonicalJson(actual) === canonicalJson(wanted),
    code,
    `${label} fields differ`,
  );
}

function exactArray(actual, expected, code, label) {
  requireCondition(Array.isArray(actual), code, `${label} must be an array`);
  requireCondition(
    canonicalJson(actual) === canonicalJson(expected),
    code,
    `${label} differs from the frozen contract`,
  );
}

function boundedString(value, code, label, min = 1, max = 4096) {
  requireCondition(typeof value === 'string', code, `${label} must be a string`);
  const normalized = value.trim();
  requireCondition(
    normalized.length >= min && normalized.length <= max,
    code,
    `${label} is empty or unbounded`,
  );
  return normalized;
}

function uniqueStrings(values, code, label) {
  requireCondition(Array.isArray(values), code, `${label} must be an array`);
  requireCondition(
    values.every((value) => typeof value === 'string' && value.trim().length > 0),
    code,
    `${label} must contain bounded strings`,
  );
  requireCondition(new Set(values).size === values.length, code, `${label} contains duplicates`);
}

function containsFragment(values, fragment) {
  return values.some((value) => value.includes(fragment));
}

export function validateFabricProfile(profile) {
  exactKeys(profile, TOP_LEVEL_KEYS, 'FABRIC_PROFILE_FIELDS_INVALID', 'fabric profile');
  requireCondition(
    profile.schema === 'spectra-anchor-node-estate-fabric-profile/1',
    'FABRIC_PROFILE_SCHEMA_INVALID',
    'fabric profile schema is invalid',
  );
  requireCondition(
    profile.profileId === 'spectra-anchor-node/estate-fabric/0.1',
    'FABRIC_PROFILE_ID_INVALID',
    'fabric profile identifier differs',
  );
  requireCondition(profile.issue === 29, 'FABRIC_PROFILE_ISSUE_INVALID', 'fabric profile must remain bound to issue 29');
  requireCondition(
    profile.status === 'candidate_design_only',
    'FABRIC_PROFILE_STATUS_INVALID',
    'fabric contract cannot self-promote',
  );
  for (const key of [
    'authority',
    'missionStateEffect',
    'fieldEffect',
    'publicationEffect',
    'adoptionEffect',
  ]) {
    requireCondition(profile[key] === 'none', 'FABRIC_PROFILE_EFFECT_INVALID', `${key} must remain none`);
  }
  boundedString(profile.purpose, 'FABRIC_PROFILE_PURPOSE_INVALID', 'purpose', 160);

  exactKeys(
    profile.predecessors,
    new Set(['missionProfile', 'estateAuthority']),
    'FABRIC_PREDECESSOR_INVALID',
    'predecessors',
  );
  exactKeys(
    profile.predecessors.missionProfile,
    new Set(['repository', 'commit', 'profileId', 'admission']),
    'FABRIC_PREDECESSOR_INVALID',
    'missionProfile predecessor',
  );
  requireCondition(
    profile.predecessors.missionProfile.repository === 'BigBirdReturns/ai-execution-audit',
    'FABRIC_PREDECESSOR_INVALID',
    'mission predecessor repository differs',
  );
  requireCondition(
    profile.predecessors.missionProfile.commit === 'f70645a70f40ad0cbe6bad1e4e665116ad4230b1',
    'FABRIC_PREDECESSOR_INVALID',
    'mission predecessor commit differs',
  );
  requireCondition(
    profile.predecessors.missionProfile.profileId
      === 'spectra-anchor-node/disconnected-multisensor-coordination/0.1',
    'FABRIC_PREDECESSOR_INVALID',
    'mission predecessor profile differs',
  );
  requireCondition(
    profile.predecessors.missionProfile.admission === 'admitted_main',
    'FABRIC_PREDECESSOR_INVALID',
    'mission predecessor is not admitted main',
  );
  requireCondition(
    SHA40.test(profile.predecessors.missionProfile.commit),
    'FABRIC_PREDECESSOR_INVALID',
    'mission predecessor commit is malformed',
  );

  exactKeys(
    profile.predecessors.estateAuthority,
    new Set(['sourceClass', 'commit', 'evidenceBodies']),
    'FABRIC_PREDECESSOR_INVALID',
    'Estate predecessor',
  );
  requireCondition(
    profile.predecessors.estateAuthority.sourceClass === 'private_authority_coordinate',
    'FABRIC_PREDECESSOR_INVALID',
    'Estate predecessor source class differs',
  );
  requireCondition(
    profile.predecessors.estateAuthority.commit === '819e17d6a49b38855fb417dabcbe900b62798747',
    'FABRIC_PREDECESSOR_INVALID',
    'Estate predecessor commit differs',
  );
  requireCondition(
    SHA40.test(profile.predecessors.estateAuthority.commit),
    'FABRIC_PREDECESSOR_INVALID',
    'Estate predecessor commit is malformed',
  );
  requireCondition(
    profile.predecessors.estateAuthority.evidenceBodies === 'private_digest_reference_only',
    'FABRIC_PREDECESSOR_INVALID',
    'Estate evidence-body custody differs',
  );

  exactKeys(
    profile.publicFixturePolicy,
    new Set([
      'identityClass',
      'privateEvidenceBodiesAllowed',
      'privateHostnamesAllowed',
      'privatePathsAllowed',
      'operationalCredentialsRequired',
      'physicalEvidenceReference',
    ]),
    'PUBLIC_FIXTURE_POLICY_INVALID',
    'publicFixturePolicy',
  );
  requireCondition(
    profile.publicFixturePolicy.identityClass === 'invented_unclassified_synthetic_only',
    'PUBLIC_FIXTURE_POLICY_INVALID',
    'public fixtures must remain invented and synthetic-only',
  );
  for (const key of [
    'privateEvidenceBodiesAllowed',
    'privateHostnamesAllowed',
    'privatePathsAllowed',
    'operationalCredentialsRequired',
  ]) {
    requireCondition(profile.publicFixturePolicy[key] === false, 'PUBLIC_FIXTURE_POLICY_INVALID', `${key} must remain false`);
  }
  requireCondition(
    profile.publicFixturePolicy.physicalEvidenceReference
      === 'digest_evidence_class_and_claim_boundary_only',
    'PUBLIC_FIXTURE_POLICY_INVALID',
    'physical evidence reference boundary differs',
  );

  exactArray(profile.contractObjects, CONTRACT_OBJECTS, 'FABRIC_CONTRACT_OBJECTS_INVALID', 'contractObjects');

  exactKeys(
    profile.seatSemantics,
    new Set([
      'addressability',
      'memoryAggregation',
      'splitModelException',
      'topologyRole',
      'gpuPresenceImpliesAdmission',
      'optionalSeatRequiredForResidentContinuity',
    ]),
    'SEAT_SEMANTICS_INVALID',
    'seatSemantics',
  );
  requireCondition(
    profile.seatSemantics.addressability === 'independent_execution_boundary',
    'SEAT_SEMANTICS_INVALID',
    'seat addressability differs',
  );
  requireCondition(
    profile.seatSemantics.memoryAggregation === 'forbidden_across_independent_seats',
    'SEAT_SEMANTICS_INVALID',
    'independent-seat memory may not be pooled',
  );
  requireCondition(
    profile.seatSemantics.splitModelException === 'separately_qualified_route_only',
    'SEAT_SEMANTICS_INVALID',
    'split-model exception is under-bounded',
  );
  requireCondition(
    profile.seatSemantics.topologyRole === 'observation_not_constitution',
    'SEAT_SEMANTICS_INVALID',
    'observed topology cannot become constitutional state',
  );
  requireCondition(
    profile.seatSemantics.gpuPresenceImpliesAdmission === false,
    'SEAT_SEMANTICS_INVALID',
    'GPU presence cannot imply seat admission',
  );
  requireCondition(
    profile.seatSemantics.optionalSeatRequiredForResidentContinuity === false,
    'SEAT_SEMANTICS_INVALID',
    'optional seat cannot become required for resident continuity',
  );

  exactArray(profile.routeBinding, ROUTE_BINDING, 'ROUTE_BINDING_INVALID', 'routeBinding');

  exactKeys(
    profile.firstVerticalSlice,
    new Set([
      'sequence',
      'executionEffect',
      'missionStateMutation',
      'externalServices',
      'operationalCredentials',
    ]),
    'FABRIC_VERTICAL_SLICE_INVALID',
    'firstVerticalSlice',
  );
  exactArray(
    profile.firstVerticalSlice.sequence,
    VERTICAL_SLICE,
    'FABRIC_VERTICAL_SLICE_INVALID',
    'fabric vertical slice sequence',
  );
  requireCondition(
    profile.firstVerticalSlice.executionEffect === 'local_artifact_only',
    'FABRIC_VERTICAL_SLICE_INVALID',
    'fabric execution effect is too broad',
  );
  requireCondition(
    profile.firstVerticalSlice.missionStateMutation === false,
    'FABRIC_VERTICAL_SLICE_INVALID',
    'fabric routing cannot mutate mission state',
  );
  requireCondition(
    profile.firstVerticalSlice.externalServices === 0,
    'FABRIC_VERTICAL_SLICE_INVALID',
    'fabric vertical slice must use zero external services',
  );
  requireCondition(
    profile.firstVerticalSlice.operationalCredentials === 0,
    'FABRIC_VERTICAL_SLICE_INVALID',
    'fabric vertical slice must use zero operational credentials',
  );

  exactArray(
    profile.hostileQualification,
    HOSTILE_SCENARIOS,
    'FABRIC_HOSTILE_SCENARIOS_INVALID',
    'hostileQualification',
  );

  requireCondition(
    Array.isArray(profile.evidenceTiers) && profile.evidenceTiers.length === EVIDENCE_TIERS.length,
    'EVIDENCE_TIERS_INVALID',
    'evidence tier denominator differs',
  );
  for (let index = 0; index < EVIDENCE_TIERS.length; index += 1) {
    const row = profile.evidenceTiers[index];
    exactKeys(row, new Set(['tier', 'name', 'status', 'scope']), 'EVIDENCE_TIERS_INVALID', `evidence tier ${index + 1}`);
    requireCondition(
      canonicalJson(row) === canonicalJson(EVIDENCE_TIERS[index]),
      'EVIDENCE_TIERS_INVALID',
      `evidence tier ${index + 1} differs`,
    );
  }

  exactKeys(profile.acceptance, new Set(['requires', 'refuseIf']), 'FABRIC_ACCEPTANCE_INVALID', 'acceptance');
  uniqueStrings(profile.acceptance.requires, 'FABRIC_ACCEPTANCE_INVALID', 'acceptance.requires');
  uniqueStrings(profile.acceptance.refuseIf, 'FABRIC_ACCEPTANCE_INVALID', 'acceptance.refuseIf');
  for (const fragment of [
    'exact predecessor commits',
    'seat-specific and independently verifiable',
    'never pooled for fit',
    'exactly one terminal completion',
    'canonical MP01 mission state remains unchanged',
    'detached replay',
    'cold successor',
    'remain non-authoritative',
  ]) {
    requireCondition(
      containsFragment(profile.acceptance.requires, fragment),
      'FABRIC_ACCEPTANCE_INVALID',
      `missing acceptance requirement: ${fragment}`,
    );
  }
  for (const fragment of [
    'permanent law',
    'private Estate evidence bodies',
    'GPU presence',
    'summed into one fit value',
    'grants mission authority',
    'released without evidence',
    'rejected candidate denominator is lost',
    'weapons',
  ]) {
    requireCondition(
      containsFragment(profile.acceptance.refuseIf, fragment),
      'FABRIC_ACCEPTANCE_INVALID',
      `missing refusal condition: ${fragment}`,
    );
  }

  exactKeys(profile.claimBoundary, CLAIM_BOUNDARY_KEYS, 'FABRIC_CLAIM_BOUNDARY_INVALID', 'claimBoundary');
  requireCondition(
    profile.claimBoundary.missionProfilePredecessorAdmitted === true,
    'FABRIC_CLAIM_BOUNDARY_INVALID',
    'admitted predecessor fact differs',
  );
  requireCondition(
    profile.claimBoundary.fabricContractCandidate === true,
    'FABRIC_CLAIM_BOUNDARY_INVALID',
    'fabric contract must remain candidate',
  );
  for (const key of CLAIM_BOUNDARY_KEYS) {
    if (['missionProfilePredecessorAdmitted', 'fabricContractCandidate'].includes(key)) continue;
    requireCondition(profile.claimBoundary[key] === false, 'FABRIC_CLAIM_BOUNDARY_INVALID', `${key} must remain false`);
  }

  const encoded = canonicalJson(profile).toLowerCase();
  for (const forbidden of [
    'octo-w01',
    'gpu-',
    'authorization: bearer',
    'begin private key',
    '"syntheticfabricqualified":true',
    '"physicalestatequalified":true',
    '"representativeoperatorqualified":true',
    '"missionauthorityfromhardware":true',
    '"commandauthoritygranted":true',
    '"operationalc2claim":true',
    '"fieldnetworkclaim":true',
    '"weaponsoreffectorcapability":true',
  ]) {
    requireCondition(!encoded.includes(forbidden), 'FABRIC_CLAIM_BOUNDARY_INVALID', `forbidden public or authority claim generated: ${forbidden}`);
  }

  return profile;
}

export function fabricProfileReceipt(profile) {
  validateFabricProfile(profile);
  const canonical = canonicalJson(profile);
  return {
    schema: 'spectra-anchor-node-estate-fabric-profile-validation/1',
    profileId: profile.profileId,
    issue: profile.issue,
    status: 'PASS',
    sha256: createHash('sha256').update(canonical, 'utf8').digest('hex'),
    predecessorCommit: profile.predecessors.missionProfile.commit,
    estateAuthorityCommit: profile.predecessors.estateAuthority.commit,
    contractObjectCount: profile.contractObjects.length,
    routeBindingCount: profile.routeBinding.length,
    hostileScenarioCount: profile.hostileQualification.length,
    evidenceTierCount: profile.evidenceTiers.length,
    authority: 'none',
    claimBoundary:
      'Validation proves only the closed synthetic fabric contract and predecessor bindings. It grants no physical, representative-operator, field, adoption, publication, mission, or command authority.',
  };
}

async function main(argv) {
  const path = resolve(argv[2] ?? DEFAULT_PROFILE);
  const profile = JSON.parse(await readFile(path, 'utf8'));
  process.stdout.write(`${JSON.stringify(fabricProfileReceipt(profile), null, 2)}\n`);
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  main(process.argv).catch((error) => {
    const code = error instanceof FabricProfileError ? error.code : 'UNEXPECTED_ERROR';
    process.stderr.write(`${code}: ${error.message}\n`);
    process.exitCode = 1;
  });
}

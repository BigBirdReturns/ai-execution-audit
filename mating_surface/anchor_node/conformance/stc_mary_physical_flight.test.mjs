import assert from 'node:assert/strict';
import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';
import {
  REQUIRED_STAGE_TERMINALS,
  STC_MARY_STAGES,
  StcMaryPhysicalFlightError,
  buildPublicPhysicalFlightDisposition,
  buildStcMaryPhysicalFlightProjection,
  createPhysicalFlightCampaignSeed,
  createPrivatePhysicalFlightTemplate,
  renderStcMaryPhysicalFlightHtml,
  runSyntheticStcMaryPhysicalFlight,
  sealPrivateStcMaryPhysicalFlight,
  validatePhysicalFlightCampaignSeed,
  validatePrivatePhysicalFlightRequest,
  validatePublicPhysicalFlightDisposition,
  validateStcMaryPhysicalFlightProfile,
  validateStcMaryPhysicalFlightProjection,
  validateStcMaryPhysicalFlightRun,
  validateSyntheticPhysicalFlightFixture,
  verifyStcMaryPhysicalFlightRun,
} from '../stc_mary_physical_flight.mjs';

const HERE = dirname(fileURLToPath(import.meta.url));
const PROFILE_PATH = resolve(HERE, '../stc-mary-physical-flight-profile-01.json');
const FIXTURE_PATH = resolve(HERE, '../fixtures/stc-mary-physical-flight-synthetic-01.json');

async function inputs() {
  const [profile, fixture] = await Promise.all([
    readFile(PROFILE_PATH, 'utf8').then(JSON.parse),
    readFile(FIXTURE_PATH, 'utf8').then(JSON.parse),
  ]);
  return { profile, fixture };
}

async function syntheticRun() {
  const source = await inputs();
  return { ...source, run: runSyntheticStcMaryPhysicalFlight(source) };
}

function assertCode(fn, code) {
  assert.throws(fn, (error) => error instanceof StcMaryPhysicalFlightError && error.code === code);
}

function assertRejectCode(promise, code) {
  return assert.rejects(promise, (error) => error instanceof StcMaryPhysicalFlightError && error.code === code);
}

async function completePrivateRequest(profile, root) {
  const request = createPrivatePhysicalFlightTemplate(profile);
  request.campaignLabel = 'PRIVATE-STC-MARY-FLIGHT-TEST-01';
  request.sourceObjectDigests = ['a'.repeat(64), 'b'.repeat(64)];
  request.canonicalMissionStateDigest = 'c'.repeat(64);
  for (const [index, row] of request.stageAttestations.entries()) {
    row.canonicalMissionStateIdBefore = request.canonicalMissionStateDigest;
    row.canonicalMissionStateIdAfter = request.canonicalMissionStateDigest;
    const path = join(root, `stage-${String(index + 1).padStart(2, '0')}.txt`);
    await writeFile(path, `private evidence for ${row.stage}\n`, 'utf8');
    row.evidenceBodies[0].path = path;
  }
  return request;
}

test('physical-flight profile validates as a closed non-authoritative candidate', async () => {
  const { profile } = await inputs();
  assert.equal(validateStcMaryPhysicalFlightProfile(profile), profile);
  assert.deepEqual(profile.stageSequence, STC_MARY_STAGES);
  assert.equal(profile.claimBoundary.physicalEstateQualified, false);
});

test('profile refuses a reordered stage denominator', async () => {
  const { profile } = await inputs();
  [profile.stageSequence[0], profile.stageSequence[1]] = [profile.stageSequence[1], profile.stageSequence[0]];
  assertCode(() => validateStcMaryPhysicalFlightProfile(profile), 'PHYSICAL_FLIGHT_PROFILE_INVALID');
});

test('profile refuses HALO3 as a resident-floor dependency', async () => {
  const { profile } = await inputs();
  profile.substrateRoles.halo3.requiredForContinuity = true;
  assertCode(() => validateStcMaryPhysicalFlightProfile(profile), 'PHYSICAL_FLIGHT_PROFILE_INVALID');
});

test('profile refuses model authority', async () => {
  const { profile } = await inputs();
  profile.authorityPolicy.modelAuthority = 'mission';
  assertCode(() => validateStcMaryPhysicalFlightProfile(profile), 'PHYSICAL_FLIGHT_PROFILE_INVALID');
});

test('invented physical-flight fixture validates without private evidence', async () => {
  const { profile, fixture } = await inputs();
  assert.equal(validateSyntheticPhysicalFlightFixture(fixture, profile), fixture);
  assert.equal(fixture.physicalEvidenceBodies, 0);
});

test('fixture refuses a non-synthetic seat identity', async () => {
  const { profile, fixture } = await inputs();
  fixture.identities.personalFloorSeatId = 'REAL-SEAT-A';
  assertCode(() => validateSyntheticPhysicalFlightFixture(fixture, profile), 'PHYSICAL_FLIGHT_FIXTURE_INVALID');
});

test('fixture refuses a physical evidence-body claim', async () => {
  const { profile, fixture } = await inputs();
  fixture.physicalEvidenceBodies = 1;
  assertCode(() => validateSyntheticPhysicalFlightFixture(fixture, profile), 'PHYSICAL_FLIGHT_FIXTURE_CLAIM_INVALID');
});

test('fixture refuses a non-accelerating HALO3 metric', async () => {
  const { profile, fixture } = await inputs();
  fixture.syntheticMetrics.halo3Accelerated = fixture.syntheticMetrics.personalFloorBaseline;
  assertCode(() => validateSyntheticPhysicalFlightFixture(fixture, profile), 'PHYSICAL_FLIGHT_FIXTURE_INVALID');
});

test('fixture refuses automatic conflict merge', async () => {
  const { profile, fixture } = await inputs();
  fixture.expectedConflict.automaticMergeAllowed = true;
  assertCode(() => validateSyntheticPhysicalFlightFixture(fixture, profile), 'PHYSICAL_FLIGHT_FIXTURE_INVALID');
});

test('campaign seed is deterministic and source-bound', async () => {
  const { profile } = await inputs();
  const first = createPhysicalFlightCampaignSeed({ profile, sourceId: 'source-a', flightMode: 'synthetic_simulation' });
  const second = createPhysicalFlightCampaignSeed({ profile, sourceId: 'source-a', flightMode: 'synthetic_simulation' });
  assert.deepEqual(first, second);
  assert.equal(validatePhysicalFlightCampaignSeed(first, profile), first);
});

test('campaign seed identity cannot be rewritten', async () => {
  const { profile } = await inputs();
  const seed = createPhysicalFlightCampaignSeed({ profile, sourceId: 'source-a', flightMode: 'synthetic_simulation' });
  seed.campaignSeedId = `stcmaryphysicalflightseed1_${'0'.repeat(64)}`;
  assertCode(() => validatePhysicalFlightCampaignSeed(seed, profile), 'PHYSICAL_FLIGHT_SEED_ID_INVALID');
});

test('synthetic campaign closes the complete sixteen-stage denominator', async () => {
  const { profile, run } = await syntheticRun();
  assert.equal(validateStcMaryPhysicalFlightRun(run, profile), run);
  assert.equal(run.stageCount, 16);
  assert.deepEqual(run.stageDenominator, STC_MARY_STAGES);
});

test('synthetic campaign records fifteen passes and one human-required terminal', async () => {
  const { run } = await syntheticRun();
  assert.equal(run.successfulStageCount, 15);
  assert.equal(run.humanRequiredStageCount, 1);
  assert.equal(run.refusedStageCount, 0);
  assert.deepEqual(Object.fromEntries(run.stageReceipts.map((row) => [row.stage, row.terminalState])), REQUIRED_STAGE_TERMINALS);
});

test('stage receipts form one exact predecessor chain', async () => {
  const { run } = await syntheticRun();
  assert.equal(run.stageReceipts[0].previousStageReceiptId, null);
  for (let index = 1; index < run.stageReceipts.length; index += 1) {
    assert.equal(run.stageReceipts[index].previousStageReceiptId, run.stageReceipts[index - 1].stageReceiptId);
  }
});

test('canonical mission state is unchanged across every stage', async () => {
  const { run } = await syntheticRun();
  assert.equal(run.canonicalMissionStateUnchanged, true);
  assert.equal(run.canonicalMissionStateIdBefore, run.canonicalMissionStateIdAfter);
  assert.equal(run.stageReceipts.every((row) => row.canonicalMissionStateIdBefore === row.canonicalMissionStateIdAfter), true);
});

test('personal floor completes a verified baseline before HALO3 attachment', async () => {
  const { run } = await syntheticRun();
  const baselineIndex = run.stageDenominator.indexOf('RUN_PERSONAL_FLOOR_BASELINE');
  const haloIndex = run.stageDenominator.indexOf('ATTACH_HALO3');
  assert.equal(baselineIndex < haloIndex, true);
  assert.equal(run.personalFloorBaselineVerified, true);
});

test('HALO3 accelerates the same verified mission output', async () => {
  const { run } = await syntheticRun();
  const baseline = run.stageReceipts.find((row) => row.stage === 'RUN_PERSONAL_FLOOR_BASELINE').observation;
  const accelerated = run.stageReceipts.find((row) => row.stage === 'RUN_HALO3_ACCELERATED').observation;
  assert.equal(accelerated.outputDigest, baseline.outputDigest);
  assert.equal(accelerated.throughputUnits > baseline.throughputUnits, true);
  assert.equal(run.halo3AccelerationVerified, true);
});

test('HALO3 removal preserves the personal floor', async () => {
  const { run } = await syntheticRun();
  const continuity = run.stageReceipts.find((row) => row.stage === 'VERIFY_PERSONAL_FLOOR_CONTINUITY').observation;
  assert.equal(continuity.personalFloorAvailable, true);
  assert.equal(continuity.halo3Required, false);
  assert.equal(run.halo3RequiredForContinuity, false);
});

test('Lattice removal preserves local continuity', async () => {
  const { run } = await syntheticRun();
  const continuity = run.stageReceipts.find((row) => row.stage === 'VERIFY_LOCAL_CONTINUITY').observation;
  assert.equal(continuity.localStateAvailable, true);
  assert.equal(continuity.latticeRequired, false);
  assert.equal(run.latticeRequiredForContinuity, false);
});

test('partition produces exactly two locally valid cells without authority widening', async () => {
  const { run } = await syntheticRun();
  const partition = run.stageReceipts.find((row) => row.stage === 'PARTITION_TWO_CELLS').observation;
  assert.equal(partition.cellCount, 2);
  assert.equal(partition.eachCellLocallyValid, true);
  assert.equal(partition.authorityWidened, false);
});

test('reconnection retains conflict as human-required', async () => {
  const { run } = await syntheticRun();
  const conflict = run.stageReceipts.find((row) => row.stage === 'RESTORE_LINK_HOLD_CONFLICT');
  assert.equal(conflict.terminalState, 'HUMAN_REQUIRED');
  assert.equal(conflict.observation.automaticMerge, false);
  assert.equal(conflict.unresolvedObligationIds.length, 1);
  assert.equal(run.conflictDisposition, 'human_required');
});

test('replacement HEAD receives state by digest without authority transfer', async () => {
  const { run } = await syntheticRun();
  const replacement = run.stageReceipts.find((row) => row.stage === 'REPLACE_HEAD').observation;
  assert.notEqual(replacement.oldHeadIdentityClass, replacement.newHeadIdentityClass);
  assert.equal(replacement.canonicalStateCopiedByDigest, true);
  assert.equal(replacement.authorityTransferred, false);
  assert.equal(run.headReplacementVerified, true);
});

test('graph query cache and review projections rebuild from receipts', async () => {
  const { run } = await syntheticRun();
  const rebuild = run.stageReceipts.find((row) => row.stage === 'REBUILD_PROJECTIONS').observation;
  assert.deepEqual(rebuild.projectionKinds, ['graph', 'query', 'cache', 'review']);
  assert.equal(rebuild.rebuiltFromCanonicalReceipts, true);
  assert.equal(run.projectionsRebuilt, true);
});

test('cold successor recovers the cartridge boundary and open obligation', async () => {
  const { run } = await syntheticRun();
  const successor = run.stageReceipts.find((row) => row.stage === 'COLD_SUCCESSOR_VERIFY').observation;
  assert.equal(successor.recoveredCartridge, true);
  assert.equal(successor.recoveredAuthorityBoundary, true);
  assert.equal(successor.recoveredObligations, true);
  assert.equal(run.coldSuccessorVerified, true);
});

test('synthetic evidence descriptors are body-free and non-authoritative', async () => {
  const { run } = await syntheticRun();
  const evidence = run.stageReceipts.flatMap((row) => row.evidence);
  assert.equal(evidence.length, 16);
  assert.equal(evidence.every((row) => row.evidenceClass === 'synthetic_deterministic_receipt'), true);
  assert.equal(evidence.every((row) => row.bodyPresent === false && row.authority === 'none'), true);
  assert.equal(run.publicEvidenceBodyCount, 0);
});

test('detached verification closes every physical-flight mechanism', async () => {
  const { profile, fixture, run } = await syntheticRun();
  const verification = verifyStcMaryPhysicalFlightRun(run, { profile, fixture });
  assert.equal(verification.status, 'PASS');
  assert.equal(verification.stageDenominatorVerified, true);
  assert.equal(verification.conflictHeldHumanRequired, true);
  assert.equal(verification.coldSuccessorVerified, true);
  assert.equal(verification.physicalEstateQualified, false);
});

test('repeated synthetic campaigns are byte-equivalent', async () => {
  const source = await inputs();
  const first = runSyntheticStcMaryPhysicalFlight(source);
  const second = runSyntheticStcMaryPhysicalFlight(source);
  assert.deepEqual(first, second);
  assert.equal(first.runId, second.runId);
});

test('stage denominator cannot silently shrink', async () => {
  const { profile, run } = await syntheticRun();
  run.stageDenominator.pop();
  assertCode(() => validateStcMaryPhysicalFlightRun(run, profile), 'PHYSICAL_FLIGHT_RUN_DENOMINATOR_INVALID');
});

test('stage denominator cannot reorder', async () => {
  const { profile, run } = await syntheticRun();
  [run.stageDenominator[0], run.stageDenominator[1]] = [run.stageDenominator[1], run.stageDenominator[0]];
  assertCode(() => validateStcMaryPhysicalFlightRun(run, profile), 'PHYSICAL_FLIGHT_RUN_DENOMINATOR_INVALID');
});

test('stage receipt identities cannot duplicate', async () => {
  const { profile, run } = await syntheticRun();
  run.stageReceipts[1].stageReceiptId = run.stageReceipts[0].stageReceiptId;
  assertCode(() => validateStcMaryPhysicalFlightRun(run, profile), 'PHYSICAL_FLIGHT_RUN_DENOMINATOR_INVALID');
});

test('pending state cannot serialize as a successful terminal stage', async () => {
  const { profile, run } = await syntheticRun();
  run.stageReceipts[0].terminalState = 'PENDING';
  assertCode(() => validateStcMaryPhysicalFlightRun(run, profile), 'PHYSICAL_FLIGHT_STAGE_TERMINAL_INVALID');
});

test('stage receipt cannot mutate canonical mission state', async () => {
  const { profile, run } = await syntheticRun();
  run.stageReceipts[4].canonicalMissionStateIdAfter = 'd'.repeat(64);
  assertCode(() => validateStcMaryPhysicalFlightRun(run, profile), 'PHYSICAL_FLIGHT_STAGE_STATE_MUTATION');
});

test('run cannot make HALO3 necessary for continuity', async () => {
  const { profile, run } = await syntheticRun();
  run.halo3RequiredForContinuity = true;
  assertCode(() => validateStcMaryPhysicalFlightRun(run, profile), 'PHYSICAL_FLIGHT_RUN_CONTINUITY_INVALID');
});

test('synthetic run cannot claim completion of a private physical flight', async () => {
  const { profile, run } = await syntheticRun();
  run.privatePhysicalFlightCompleted = true;
  run.privatePhysicalEvidenceBodyCount = 16;
  assertCode(() => validateStcMaryPhysicalFlightRun(run, profile), 'PHYSICAL_FLIGHT_RUN_CLAIM_INVALID');
});

test('run cannot claim external service use or authority', async () => {
  for (const [key, value] of [['externalServiceCalls', 1], ['authority', 'mission']]) {
    const { profile, run } = await syntheticRun();
    run[key] = value;
    assertCode(() => validateStcMaryPhysicalFlightRun(run, profile), 'PHYSICAL_FLIGHT_RUN_CLAIM_INVALID');
  }
});

test('receipt-only projection and HTML rebuild deterministically and remain static', async () => {
  const { run } = await syntheticRun();
  const first = buildStcMaryPhysicalFlightProjection(run);
  const second = buildStcMaryPhysicalFlightProjection(run);
  assert.deepEqual(first, second);
  assert.equal(validateStcMaryPhysicalFlightProjection(first, run), first);
  const html = renderStcMaryPhysicalFlightHtml(first);
  assert.match(html, /STC MARY Physical-Flight Receipt/);
  assert.doesNotMatch(html, /<script/i);
  assert.doesNotMatch(html, /https?:\/\//i);
});

test('private flight template is deliberately incomplete until local evidence paths are supplied', async () => {
  const { profile } = await inputs();
  const template = createPrivatePhysicalFlightTemplate(profile);
  assert.equal(template.stageAttestations.length, 16);
  assertCode(() => validatePrivatePhysicalFlightRequest(template, profile), 'PRIVATE_PHYSICAL_FLIGHT_REQUEST_INCOMPLETE');
});

test('private evidence seals into a local run and body-free public disposition without qualification inflation', async () => {
  const { profile } = await inputs();
  const root = await mkdtemp(join(tmpdir(), 'stc-mary-private-flight-'));
  try {
    const request = await completePrivateRequest(profile, root);
    assert.equal(validatePrivatePhysicalFlightRequest(request, profile), request);
    const { run, disposition } = await sealPrivateStcMaryPhysicalFlight({ profile, request });
    assert.equal(run.flightMode, 'private_physical_attested');
    assert.equal(run.privatePhysicalFlightCompleted, true);
    assert.equal(run.privatePhysicalEvidenceBodyCount, 16);
    assert.equal(run.physicalEstateQualified, false);
    assert.equal(validateStcMaryPhysicalFlightRun(run, profile), run);
    assert.deepEqual(disposition, buildPublicPhysicalFlightDisposition(run));
    assert.equal(validatePublicPhysicalFlightDisposition(disposition, run), disposition);
    assert.equal(disposition.publicEvidenceBodyCount, 0);
    assert.equal(disposition.selfAttestationOnly, true);
    assert.equal(disposition.physicalEstateQualified, false);
    const encoded = JSON.stringify(disposition);
    assert.doesNotMatch(encoded, new RegExp(root.replaceAll('\\', '\\\\')));
    disposition.claimBoundary = 'C:\\private\\evidence';
    assertCode(() => validatePublicPhysicalFlightDisposition(disposition), 'PUBLIC_PHYSICAL_FLIGHT_DISPOSITION_PRIVATE_MATERIAL');
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

import assert from 'node:assert/strict';
import {
  mkdtemp,
  readFile,
  readdir,
  rm,
  writeFile,
} from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';
import {
  STC_MARY_STAGES,
  validateStcMaryPhysicalFlightProfile,
} from '../stc_mary_physical_flight.mjs';
import {
  StcMaryPrivateFlightPacketError,
  configurePrivateFlightPacket,
  initializePrivateFlightPacket,
  privateFlightPacketStatus,
  recordPrivateFlightStage,
  sealPrivateFlightPacket,
  validatePrivateFlightPacketConfig,
  validatePrivateFlightPacketProfile,
  verifySealedPrivateFlightPacket,
} from '../stc_mary_private_flight_packet.mjs';

const HERE = dirname(fileURLToPath(import.meta.url));
const REPOSITORY_ROOT = resolve(HERE, '../../..');
const PACKET_PROFILE_PATH = resolve(HERE, '../stc-mary-private-flight-packet-profile-01.json');
const PHYSICAL_PROFILE_PATH = resolve(HERE, '../stc-mary-physical-flight-profile-01.json');

async function profiles() {
  const [packetProfile, physicalProfile] = await Promise.all([
    readFile(PACKET_PROFILE_PATH, 'utf8').then(JSON.parse),
    readFile(PHYSICAL_PROFILE_PATH, 'utf8').then(JSON.parse),
  ]);
  return { packetProfile, physicalProfile };
}

function stageDirectory(packetDirectory, index, stage) {
  return join(packetDirectory, `${String(index + 1).padStart(2, '0')}-${stage}`);
}

async function packetFixture(label = 'PRIVATE-FLIGHT-PACKET-TEST-01') {
  const root = await mkdtemp(join(tmpdir(), 'stc-mary-private-packet-'));
  const packetDirectory = join(root, 'stc-mary-private-flight-test');
  await initializePrivateFlightPacket(packetDirectory, label);
  return { root, packetDirectory, label };
}

async function validConfig(packetDirectory, label) {
  const config = JSON.parse(await readFile(join(packetDirectory, 'flight-config.json'), 'utf8'));
  config.campaignLabel = label;
  config.sourceObjectDigests = ['a'.repeat(64), 'b'.repeat(64)];
  config.canonicalMissionStateDigest = 'c'.repeat(64);
  config.identityClasses = {
    personalFloor: 'private_resident_execution_seat',
    halo3: 'private_optional_accelerator',
    initialHead: 'private_initial_head',
    successorHead: 'private_successor_head',
    graceBind: 'named_human_operator',
    lattice: 'private_optional_interoperability_membrane',
    leftCell: 'private_partition_cell_left',
    rightCell: 'private_partition_cell_right',
  };
  config.authority = 'none';
  return config;
}

async function configureFixture(packetDirectory, label) {
  const config = await validConfig(packetDirectory, label);
  const configPath = join(dirname(packetDirectory), 'valid-config.json');
  await writeFile(configPath, `${JSON.stringify(config, null, 2)}\n`, 'utf8');
  await configurePrivateFlightPacket(packetDirectory, configPath);
  return { config, configPath };
}

async function prepareStage(packetDirectory, index, stage, { confirmed = true, evidence = true } = {}) {
  const directory = stageDirectory(packetDirectory, index, stage);
  const draftPath = join(directory, 'stage-attestation.json');
  const draft = JSON.parse(await readFile(draftPath, 'utf8'));
  draft.operatorConfirmed = confirmed;
  draft.notes = `Operator receipt for ${stage}`;
  await writeFile(draftPath, `${JSON.stringify(draft, null, 2)}\n`, 'utf8');
  if (evidence) {
    await writeFile(join(directory, 'evidence', `evidence-${String(index + 1).padStart(2, '0')}.txt`), `private evidence for ${stage}\n`, 'utf8');
  }
  return draft;
}

async function completePacket(packetDirectory, label) {
  await configureFixture(packetDirectory, label);
  for (const [index, stage] of STC_MARY_STAGES.entries()) {
    await prepareStage(packetDirectory, index, stage);
    await recordPrivateFlightStage(packetDirectory, stage);
  }
}

function assertCode(fn, code) {
  assert.throws(fn, (error) => error instanceof StcMaryPrivateFlightPacketError && error.code === code);
}

function assertRejectCode(promise, code) {
  return assert.rejects(promise, (error) => error instanceof StcMaryPrivateFlightPacketError && error.code === code);
}

test('private-flight packet profile validates against the admitted physical-flight profile', async () => {
  const { packetProfile, physicalProfile } = await profiles();
  assert.equal(validateStcMaryPhysicalFlightProfile(physicalProfile), physicalProfile);
  assert.equal(validatePrivateFlightPacketProfile(packetProfile, physicalProfile), packetProfile);
  assert.deepEqual(packetProfile.stageSequence, STC_MARY_STAGES);
});

test('packet initialization creates one marked local root and sixteen stage workspaces', async () => {
  const packet = await packetFixture();
  try {
    const entries = await readdir(packet.packetDirectory);
    assert.equal(entries.includes('PACKET-ROOT.json'), true);
    assert.equal(entries.includes('packet-state.json'), true);
    assert.equal(entries.includes('flight-config.json'), true);
    for (const [index, stage] of STC_MARY_STAGES.entries()) {
      const stageEntries = await readdir(stageDirectory(packet.packetDirectory, index, stage));
      assert.equal(stageEntries.includes('stage-attestation.json'), true);
      assert.equal(stageEntries.includes('INSTRUCTIONS.md'), true);
      assert.equal(stageEntries.includes('evidence'), true);
    }
    const status = await privateFlightPacketStatus(packet.packetDirectory);
    assert.equal(status.configurationState, 'unconfigured');
    assert.equal(status.completedStageCount, 0);
    assert.equal(status.nextStage, 'VERIFY_INPUTS');
  } finally {
    await rm(packet.root, { recursive: true, force: true });
  }
});

test('packet initialization refuses a destination inside the public repository', async () => {
  const target = join(REPOSITORY_ROOT, 'stc-mary-private-flight-unsafe');
  await assertRejectCode(
    initializePrivateFlightPacket(target, 'PRIVATE-FLIGHT-UNSAFE'),
    'PRIVATE_FLIGHT_PACKET_OUTPUT_UNSAFE',
  );
});

test('packet initialization refuses an unsafe basename', async () => {
  const root = await mkdtemp(join(tmpdir(), 'stc-mary-private-packet-name-'));
  try {
    await assertRejectCode(
      initializePrivateFlightPacket(join(root, 'packet'), 'PRIVATE-FLIGHT-UNSAFE-NAME'),
      'PRIVATE_FLIGHT_PACKET_OUTPUT_UNSAFE',
    );
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test('packet initialization refuses an existing destination without deleting it', async () => {
  const packet = await packetFixture();
  try {
    await writeFile(join(packet.packetDirectory, 'preserve.txt'), 'preserve me', 'utf8');
    await assertRejectCode(
      initializePrivateFlightPacket(packet.packetDirectory, packet.label),
      'PRIVATE_FLIGHT_PACKET_OUTPUT_UNSAFE',
    );
    assert.equal(await readFile(join(packet.packetDirectory, 'preserve.txt'), 'utf8'), 'preserve me');
  } finally {
    await rm(packet.root, { recursive: true, force: true });
  }
});

test('initial configuration remains deliberately incomplete', async () => {
  const packet = await packetFixture();
  try {
    const marker = JSON.parse(await readFile(join(packet.packetDirectory, 'PACKET-ROOT.json'), 'utf8'));
    const config = JSON.parse(await readFile(join(packet.packetDirectory, 'flight-config.json'), 'utf8'));
    assertCode(() => validatePrivateFlightPacketConfig(config, marker), 'PRIVATE_FLIGHT_PACKET_CONFIG_INVALID');
  } finally {
    await rm(packet.root, { recursive: true, force: true });
  }
});

test('valid configuration binds source digests, identity classes, and one canonical state digest', async () => {
  const packet = await packetFixture();
  try {
    const { config } = await configureFixture(packet.packetDirectory, packet.label);
    const marker = JSON.parse(await readFile(join(packet.packetDirectory, 'PACKET-ROOT.json'), 'utf8'));
    assert.equal(validatePrivateFlightPacketConfig(config, marker), config);
    const status = await privateFlightPacketStatus(packet.packetDirectory);
    assert.equal(status.configurationState, 'configured');
    assert.equal(status.nextStage, 'VERIFY_INPUTS');
    for (const [index, stage] of STC_MARY_STAGES.entries()) {
      const draft = JSON.parse(await readFile(join(stageDirectory(packet.packetDirectory, index, stage), 'stage-attestation.json'), 'utf8'));
      assert.equal(draft.canonicalMissionStateIdBefore, config.canonicalMissionStateDigest);
      assert.equal(draft.canonicalMissionStateIdAfter, config.canonicalMissionStateDigest);
    }
  } finally {
    await rm(packet.root, { recursive: true, force: true });
  }
});

test('configuration refuses a campaign-label mismatch', async () => {
  const packet = await packetFixture();
  try {
    const config = await validConfig(packet.packetDirectory, 'ANOTHER-CAMPAIGN');
    const path = join(packet.root, 'bad-config.json');
    await writeFile(path, JSON.stringify(config), 'utf8');
    await assertRejectCode(
      configurePrivateFlightPacket(packet.packetDirectory, path),
      'PRIVATE_FLIGHT_PACKET_CONFIG_INVALID',
    );
  } finally {
    await rm(packet.root, { recursive: true, force: true });
  }
});

test('configuration refuses a malformed source-object digest', async () => {
  const packet = await packetFixture();
  try {
    const config = await validConfig(packet.packetDirectory, packet.label);
    config.sourceObjectDigests = ['bad'];
    const path = join(packet.root, 'bad-config.json');
    await writeFile(path, JSON.stringify(config), 'utf8');
    await assertRejectCode(
      configurePrivateFlightPacket(packet.packetDirectory, path),
      'PRIVATE_FLIGHT_PACKET_CONFIG_INVALID',
    );
  } finally {
    await rm(packet.root, { recursive: true, force: true });
  }
});

test('recording refuses an unconfigured packet', async () => {
  const packet = await packetFixture();
  try {
    await assertRejectCode(
      recordPrivateFlightStage(packet.packetDirectory, 'VERIFY_INPUTS'),
      'PRIVATE_FLIGHT_PACKET_NOT_CONFIGURED',
    );
  } finally {
    await rm(packet.root, { recursive: true, force: true });
  }
});

test('recording refuses a stage out of sequence', async () => {
  const packet = await packetFixture();
  try {
    await configureFixture(packet.packetDirectory, packet.label);
    await prepareStage(packet.packetDirectory, 1, 'MOUNT_PERSONAL_FLOOR');
    await assertRejectCode(
      recordPrivateFlightStage(packet.packetDirectory, 'MOUNT_PERSONAL_FLOOR'),
      'PRIVATE_FLIGHT_STAGE_OUT_OF_ORDER',
    );
  } finally {
    await rm(packet.root, { recursive: true, force: true });
  }
});

test('recording refuses an unconfirmed stage draft', async () => {
  const packet = await packetFixture();
  try {
    await configureFixture(packet.packetDirectory, packet.label);
    await prepareStage(packet.packetDirectory, 0, 'VERIFY_INPUTS', { confirmed: false });
    await assertRejectCode(
      recordPrivateFlightStage(packet.packetDirectory, 'VERIFY_INPUTS'),
      'PRIVATE_FLIGHT_STAGE_DRAFT_UNCONFIRMED',
    );
  } finally {
    await rm(packet.root, { recursive: true, force: true });
  }
});

test('recording refuses a stage with no evidence body', async () => {
  const packet = await packetFixture();
  try {
    await configureFixture(packet.packetDirectory, packet.label);
    await prepareStage(packet.packetDirectory, 0, 'VERIFY_INPUTS', { evidence: false });
    await assertRejectCode(
      recordPrivateFlightStage(packet.packetDirectory, 'VERIFY_INPUTS'),
      'PRIVATE_FLIGHT_STAGE_EVIDENCE_INVALID',
    );
  } finally {
    await rm(packet.root, { recursive: true, force: true });
  }
});

test('recording the first stage advances the exact denominator', async () => {
  const packet = await packetFixture();
  try {
    await configureFixture(packet.packetDirectory, packet.label);
    await prepareStage(packet.packetDirectory, 0, 'VERIFY_INPUTS');
    const result = await recordPrivateFlightStage(packet.packetDirectory, 'VERIFY_INPUTS');
    assert.equal(result.record.stage, 'VERIFY_INPUTS');
    assert.match(result.record.recordDigest, /^stcmaryprivateflightstagerecord1_[0-9a-f]{64}$/);
    assert.equal(result.state.completedStageCount, 1);
    assert.equal(result.state.nextStage, 'MOUNT_PERSONAL_FLOOR');
  } finally {
    await rm(packet.root, { recursive: true, force: true });
  }
});

test('sealing refuses an incomplete stage denominator', async () => {
  const packet = await packetFixture();
  try {
    await configureFixture(packet.packetDirectory, packet.label);
    const sealed = join(packet.root, 'stc-mary-private-flight-sealed-incomplete');
    await assertRejectCode(
      sealPrivateFlightPacket(packet.packetDirectory, sealed),
      'PRIVATE_FLIGHT_PACKET_INCOMPLETE',
    );
    await assert.rejects(readFile(join(sealed, 'manifest.json')));
  } finally {
    await rm(packet.root, { recursive: true, force: true });
  }
});

test('a complete packet reports sixteen recorded stages and no next stage', async () => {
  const packet = await packetFixture();
  try {
    await completePacket(packet.packetDirectory, packet.label);
    const status = await privateFlightPacketStatus(packet.packetDirectory);
    assert.equal(status.completedStageCount, 16);
    assert.equal(status.stageCount, 16);
    assert.equal(status.nextStage, null);
    assert.equal(status.sealed, false);
  } finally {
    await rm(packet.root, { recursive: true, force: true });
  }
});

test('evidence drift after recording is refused before sealing', async () => {
  const packet = await packetFixture();
  try {
    await completePacket(packet.packetDirectory, packet.label);
    const evidencePath = join(stageDirectory(packet.packetDirectory, 0, 'VERIFY_INPUTS'), 'evidence', 'evidence-01.txt');
    await writeFile(evidencePath, 'tampered evidence\n', 'utf8');
    await assertRejectCode(
      sealPrivateFlightPacket(packet.packetDirectory, join(packet.root, 'stc-mary-private-flight-sealed-drift')),
      'PRIVATE_FLIGHT_STAGE_EVIDENCE_DRIFT',
    );
  } finally {
    await rm(packet.root, { recursive: true, force: true });
  }
});

test('complete local evidence seals into one private run and one body-free public disposition', async () => {
  const packet = await packetFixture();
  try {
    await completePacket(packet.packetDirectory, packet.label);
    const sealed = join(packet.root, 'stc-mary-private-flight-sealed-complete');
    const result = await sealPrivateFlightPacket(packet.packetDirectory, sealed);
    assert.equal(result.run.flightMode, 'private_physical_attested');
    assert.equal(result.run.privatePhysicalFlightCompleted, true);
    assert.equal(result.run.privatePhysicalEvidenceBodyCount, 16);
    assert.equal(result.run.physicalEstateQualified, false);
    assert.equal(result.disposition.publicEvidenceBodyCount, 0);
    assert.equal(result.disposition.selfAttestationOnly, true);
    assert.equal(result.disposition.physicalEstateQualified, false);
    assert.equal(result.manifest.fileCount, 5);
    const status = await privateFlightPacketStatus(packet.packetDirectory);
    assert.equal(status.sealed, true);
    assert.equal(status.sealedDispositionId, result.disposition.dispositionId);
  } finally {
    await rm(packet.root, { recursive: true, force: true });
  }
});

test('sealed packet verifies every digest and deterministic receipt surface', async () => {
  const packet = await packetFixture();
  try {
    await completePacket(packet.packetDirectory, packet.label);
    const sealed = join(packet.root, 'stc-mary-private-flight-sealed-verify');
    const result = await sealPrivateFlightPacket(packet.packetDirectory, sealed);
    const verification = await verifySealedPrivateFlightPacket(sealed);
    assert.equal(verification.status, 'PASS');
    assert.equal(verification.runId, result.run.runId);
    assert.equal(verification.dispositionId, result.disposition.dispositionId);
    assert.equal(verification.stageCount, 16);
    assert.equal(verification.privatePhysicalEvidenceBodyCount, 16);
    assert.equal(verification.bodyFreePublicDisposition, true);
    assert.equal(verification.physicalEstateQualified, false);
  } finally {
    await rm(packet.root, { recursive: true, force: true });
  }
});

test('sealed public disposition and review contain no packet path or evidence filename', async () => {
  const packet = await packetFixture();
  try {
    await completePacket(packet.packetDirectory, packet.label);
    const sealed = join(packet.root, 'stc-mary-private-flight-sealed-body-free');
    await sealPrivateFlightPacket(packet.packetDirectory, sealed);
    const disposition = await readFile(join(sealed, 'public-disposition.json'), 'utf8');
    const review = await readFile(join(sealed, 'review.html'), 'utf8');
    assert.doesNotMatch(disposition, new RegExp(packet.root.replaceAll('\\', '\\\\')));
    assert.doesNotMatch(review, new RegExp(packet.root.replaceAll('\\', '\\\\')));
    assert.doesNotMatch(disposition, /evidence-01\.txt/);
    assert.doesNotMatch(review, /evidence-01\.txt/);
  } finally {
    await rm(packet.root, { recursive: true, force: true });
  }
});

test('recording is refused after a packet is sealed', async () => {
  const packet = await packetFixture();
  try {
    await completePacket(packet.packetDirectory, packet.label);
    await sealPrivateFlightPacket(packet.packetDirectory, join(packet.root, 'stc-mary-private-flight-sealed-lock'));
    await assertRejectCode(
      recordPrivateFlightStage(packet.packetDirectory, 'VERIFY_INPUTS'),
      'PRIVATE_FLIGHT_PACKET_ALREADY_SEALED',
    );
  } finally {
    await rm(packet.root, { recursive: true, force: true });
  }
});

test('tampered sealed file fails hash verification', async () => {
  const packet = await packetFixture();
  try {
    await completePacket(packet.packetDirectory, packet.label);
    const sealed = join(packet.root, 'stc-mary-private-flight-sealed-tamper');
    await sealPrivateFlightPacket(packet.packetDirectory, sealed);
    await writeFile(join(sealed, 'public-disposition.json'), '{}\n', 'utf8');
    await assertRejectCode(
      verifySealedPrivateFlightPacket(sealed),
      'PRIVATE_FLIGHT_SEALED_FILE_MISMATCH',
    );
  } finally {
    await rm(packet.root, { recursive: true, force: true });
  }
});

test('sealed destination must remain outside the public repository', async () => {
  const packet = await packetFixture();
  try {
    await completePacket(packet.packetDirectory, packet.label);
    await assertRejectCode(
      sealPrivateFlightPacket(packet.packetDirectory, join(REPOSITORY_ROOT, 'stc-mary-private-flight-sealed-unsafe')),
      'PRIVATE_FLIGHT_SEALED_OUTPUT_UNSAFE',
    );
  } finally {
    await rm(packet.root, { recursive: true, force: true });
  }
});

test('identical evidence and configuration produce identical sealed run and disposition identities', async () => {
  const root = await mkdtemp(join(tmpdir(), 'stc-mary-private-packet-repeat-'));
  try {
    const firstPacket = join(root, 'stc-mary-private-flight-first');
    const secondPacket = join(root, 'stc-mary-private-flight-second');
    const label = 'PRIVATE-FLIGHT-REPEAT-01';
    await initializePrivateFlightPacket(firstPacket, label);
    await initializePrivateFlightPacket(secondPacket, label);
    await completePacket(firstPacket, label);
    await completePacket(secondPacket, label);
    const first = await sealPrivateFlightPacket(firstPacket, join(root, 'stc-mary-private-flight-sealed-first'));
    const second = await sealPrivateFlightPacket(secondPacket, join(root, 'stc-mary-private-flight-sealed-second'));
    assert.equal(first.run.runId, second.run.runId);
    assert.equal(first.disposition.dispositionId, second.disposition.dispositionId);
    assert.deepEqual(first.verification, second.verification);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

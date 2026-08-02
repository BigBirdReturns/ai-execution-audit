import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import {
  mkdtemp,
  readFile,
  readdir,
  rm,
  writeFile,
} from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import {
  HostProjectionError,
  canonicalJson,
  compileHostProjections,
  renderSemanticHostSurface,
  validateMameProjection,
  validateMotionDeckCartridge,
  validateSemanticHostFrame,
} from '../host_projection.mjs';

const repositoryRoot = fileURLToPath(new URL('../../../', import.meta.url));
const mameRoot = join(repositoryRoot, 'mating_surface', 'test_hosts', 'mame');
const motionDeckRoot = join(repositoryRoot, 'mating_surface', 'test_hosts', 'motiondeck');

function digest(prefix, value) {
  return `${prefix}_${createHash('sha256').update(canonicalJson(value), 'utf8').digest('hex')}`;
}

function frameIdentityBody(frame) {
  const {
    schema: _schema,
    frameId: _frameId,
    claimBoundary: _claimBoundary,
    ...body
  } = frame;
  return body;
}

function frame() {
  const value = {
    schema: 'standards-semantic-rehearsal-frame/1',
    frameId: '',
    semanticConversationId: 'c2simsemanticconversation1_786ee47054ddef9e272122ec8bcfe556c77da6c1c5b0d920ec8080032e53cfbc',
    standardId: 'siso-std-019-2020-c2sim',
    artifactUseId: 'standardartifactuse1_41fc3dd2b39ec011dcfaf20b5ff98856140ddd6e5c7c2bd6e6c6578523bad977',
    scenarioDigest: 'standardfaultscenario1_74ef46c85742f76c3dad69d887010e686035995f5af24cb1677d70aa87df19bb',
    faultRunId: 'standardfaultrun1_69dfd2f260a7d691a2ef0bb6fb5a914fa11468b6e088e29a4d7478cf2c053533',
    faultJournalRoot: 'standardfaultrecord1_62e7e87a684d764f5edddc9ff6bfd6f18a7d017f56e69f819943baf09958d3fb',
    faultFrameId: 'standardporttestframe1_b52e41064a905d75b548512990c2a97ab59a962a3efb04e38f6d821ee9905295',
    authorityProfileId: 'c2sim-semantic-rehearsal-authority/1',
    authorityGeneration: 1,
    partitionEpochId: 'standardmessagepartitionepoch1_ddc8bd4f146e9387f92d0adad99024062fc09f23379ccde4712def175f1a2598',
    reconciliationId: 'standardmessagereconciliation1_dbe8f6507a13e8c49ebd74d879499851dc3129101b6f3a3ee02172aaa5f8453d',
    reconciliationStatus: 'explicitly_superseded',
    status: 'reconciled',
    messages: {
      schemaValid: 4,
      authorityAllowed: 4,
      receiverAccepted: 4,
      receiverRefused: 1,
      replayRefused: 1,
    },
    transport: {
      sentPackets: 4,
      deliveredCopies: 5,
      deliveredUniquePackets: 4,
      droppedPackets: 0,
      explicitDrops: 0,
      linkDownDrops: 0,
      queueCapacityDrops: 0,
      duplicateExtraCopies: 1,
      delayedPackets: 1,
      bufferedPackets: 1,
      pendingDelayedPackets: 0,
      pendingBufferedPackets: 0,
      reordered: true,
      finalLinkState: 'up',
    },
    lastEvent: {
      recordId: 'standardfaultrecord1_62e7e87a684d764f5edddc9ff6bfd6f18a7d017f56e69f819943baf09958d3fb',
      step: 6,
      type: 'deliver',
    },
    hostContracts: [
      {
        host: 'mame',
        mode: 'read_only',
        inputs: ['select_fixture', 'step', 'reset_rehearsal'],
        outputs: ['transport_metrics', 'authority_dispositions', 'replay_refusal', 'reconciliation_status'],
      },
      {
        host: 'motiondeck',
        mode: 'read_only',
        inputs: ['select_fixture', 'step', 'reset_rehearsal'],
        outputs: ['transport_metrics', 'authority_dispositions', 'replay_refusal', 'reconciliation_status'],
      },
    ],
    claimBoundary:
      'This frame is a read-only projection for replaceable rehearsal hosts. It contains no standard payload, provider interface, authority mutation, targeting, engagement, effector, or execution surface.',
  };
  value.frameId = digest('standardsemanticrehearsalframe1', frameIdentityBody(value));
  return value;
}

async function listFiles(root, relativeRoot = root) {
  const rows = [];
  for (const entry of await readdir(root, { withFileTypes: true })) {
    const path = join(root, entry.name);
    if (entry.isDirectory()) rows.push(...await listFiles(path, relativeRoot));
    else rows.push(path.slice(relativeRoot.length + 1).replaceAll('\\', '/'));
  }
  return rows.sort();
}

test('validates and renders one payload-free, product-neutral semantic host frame', () => {
  const value = validateSemanticHostFrame(frame());
  const html = renderSemanticHostSurface(value);
  assert.match(html, /C2SIM SEMANTIC REHEARSAL/);
  assert.match(html, /READ-ONLY STANDARDS RECEIPT/i);
  assert.match(html, /EXPLICITLY_SUPERSEDED/);
  assert.doesNotMatch(html, /<script\b/i);
  assert.doesNotMatch(html, /https?:\/\//i);
  assert.doesNotMatch(html, /polybolos|dandelion/i);
  assert.doesNotMatch(html, /<\?xml/i);
});

test('refuses frame fields that would expose payloads or execution surfaces', () => {
  const withPayload = { ...frame(), payload: '<xml />' };
  assert.throws(
    () => validateSemanticHostFrame(withPayload),
    (error) => error instanceof HostProjectionError
      && ['HOST_FRAME_FIELDS_INVALID', 'HOST_FRAME_FORBIDDEN_FIELD'].includes(error.code),
  );

  const withExecutionRequest = frame();
  withExecutionRequest.lastEvent = {
    ...withExecutionRequest.lastEvent,
    executionRequest: true,
  };
  assert.throws(
    () => validateSemanticHostFrame(withExecutionRequest),
    (error) => error instanceof HostProjectionError
      && ['HOST_FRAME_LAST_EVENT_INVALID', 'HOST_FRAME_FORBIDDEN_FIELD'].includes(error.code),
  );
});

test('qualifies the MAME plugin only while it remains local, menu-only, and authority-free', async () => {
  const initSource = await readFile(join(mameRoot, 'c2simrehearsal', 'init.lua'), 'utf8');
  const metadata = JSON.parse(await readFile(join(mameRoot, 'c2simrehearsal', 'plugin.json'), 'utf8'));
  const receipt = validateMameProjection(initSource, metadata);
  assert.match(receipt.sourceSha256, /^[0-9a-f]{64}$/);
  assert.equal(metadata.plugin.start, 'false');

  assert.throws(
    () => validateMameProjection(`${initSource}\nos.execute('forbidden')\n`, metadata),
    (error) => error instanceof HostProjectionError
      && error.code === 'MAME_PLUGIN_AUTHORITY_FORBIDDEN',
  );
  assert.throws(
    () => validateMameProjection(`${initSource}\nmanager.machine.memory\n`, metadata),
    (error) => error instanceof HostProjectionError
      && error.code === 'MAME_PLUGIN_AUTHORITY_FORBIDDEN',
  );
});

test('qualifies the MotionDeck cartridge only while MotionDeck owns presentation and authority remains forbidden', async () => {
  const cartridge = JSON.parse(
    await readFile(join(motionDeckRoot, 'c2sim-semantic-rehearsal.cartridge.json'), 'utf8'),
  );
  validateMotionDeckCartridge(cartridge);
  assert.equal(cartridge.data_flows[0].sink, 'motiondeck-owned-surface');
  assert.deepEqual(
    new Set(cartridge.capabilities.forbidden),
    new Set(['network.remote', 'execution.weapons', 'authority.command']),
  );

  const authorityLeak = structuredClone(cartridge);
  authorityLeak.capabilities.forbidden = authorityLeak.capabilities.forbidden
    .filter((row) => row !== 'authority.command');
  assert.throws(
    () => validateMotionDeckCartridge(authorityLeak),
    (error) => error instanceof HostProjectionError
      && error.code === 'MOTIONDECK_CARTRIDGE_AUTHORITY_FORBIDDEN',
  );

  const wrongFingerprint = structuredClone(cartridge);
  wrongFingerprint.fingerprint = '0'.repeat(64);
  assert.throws(
    () => validateMotionDeckCartridge(wrongFingerprint),
    (error) => error instanceof HostProjectionError
      && error.code === 'MOTIONDECK_CARTRIDGE_FINGERPRINT_INVALID',
  );
});

test('compiles exactly one deterministic nine-file projection estate', async () => {
  const temp = await mkdtemp(join(tmpdir(), 'semantic-host-projection-'));
  try {
    const framePath = join(temp, 'semantic-host-frame.json');
    const outputOne = join(temp, 'first');
    const outputTwo = join(temp, 'second');
    await writeFile(framePath, `${JSON.stringify(frame(), null, 2)}\n`, 'utf8');

    const first = await compileHostProjections(framePath, repositoryRoot, outputOne);
    const second = await compileHostProjections(framePath, repositoryRoot, outputTwo);
    assert.equal(first.status, 'pass');
    assert.equal(first.projectionId, second.projectionId);
    assert.equal(first.frameId, frame().frameId);
    assert.equal(first.mame.authority, 'none');
    assert.equal(first.motiondeck.authority, 'none');
    assert.equal(first.motiondeck.presentationOwner, 'motiondeck');
    assert.equal(first.mame.targetHostQualified, false);
    assert.equal(first.motiondeck.targetHostQualified, false);

    const expected = [
      'mame/Install-C2SIMRehearsalPlugin.ps1',
      'mame/c2simrehearsal/init.lua',
      'mame/c2simrehearsal/plugin.json',
      'mame/c2simrehearsal/semantic-host-frame.json',
      'motiondeck/START_C2SIM_SEMANTIC_REHEARSAL.cmd',
      'motiondeck/c2sim-semantic-rehearsal.cartridge.json',
      'motiondeck/c2sim-semantic-rehearsal.html',
      'motiondeck/semantic-host-frame.json',
      'projection-receipt.json',
    ];
    assert.deepEqual(await listFiles(outputOne), expected);
    assert.deepEqual(await listFiles(outputTwo), expected);

    for (const path of expected) {
      const [left, right] = await Promise.all([
        readFile(join(outputOne, path)),
        readFile(join(outputTwo, path)),
      ]);
      assert.deepEqual(left, right, path);
    }
    const generatedHtml = await readFile(
      join(outputOne, 'motiondeck', 'c2sim-semantic-rehearsal.html'),
      'utf8',
    );
    assert.doesNotMatch(generatedHtml, /<script\b|https?:\/\/|polybolos|dandelion/i);
  } finally {
    await rm(temp, { recursive: true, force: true });
  }
});

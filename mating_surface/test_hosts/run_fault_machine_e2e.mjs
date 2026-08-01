#!/usr/bin/env node
import { createHash } from 'node:crypto';
import { mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';
import {
  createFaultFrame,
  createTestPacket,
  deriveFaultScenarioDigest,
  runFaultScenario,
} from './core/fault_machine.mjs';
import { verifyFaultFrame } from './core/fault_verifier.mjs';

function readJson(path) {
  return JSON.parse(readFileSync(path, 'utf8'));
}

function writeJson(path, value) {
  writeFileSync(path, `${JSON.stringify(value, null, 2)}\n`, 'utf8');
}

function sha256(path) {
  return createHash('sha256').update(readFileSync(path)).digest('hex');
}

function expected(condition, message) {
  if (!condition) throw new Error(message);
}

function buildFixture(artifactTransaction, catalog) {
  const payloadRows = Array.from({ length: 7 }, (_, index) => ({
    messageIdentity: `transport-fixture-${index + 1}`,
    payload: Buffer.from(
      `standards-port-opaque-fixture/${artifactTransaction.use.useId}/${index + 1}`,
      'utf8',
    ),
  }));
  const packets = payloadRows.map((row, index) => createTestPacket({
    artifactTransaction,
    catalog,
    payload: row.payload,
    messageIdentity: row.messageIdentity,
    sourceSystemId: 'standards-rehearsal-generator',
    observedAt: `2026-08-01T00:00:${String(index + 1).padStart(2, '0')}Z`,
  }));
  const payloads = new Map(packets.map((packet, index) => [packet.packetId, payloadRows[index].payload]));
  const scenario = {
    schema: 'standards-port-fault-scenario/1',
    scenarioId: 'deterministic-partition-delay-duplicate-queue',
    mode: 'rehearsal',
    profileId: artifactTransaction.use.profileId,
    portId: artifactTransaction.use.portId,
    standardId: artifactTransaction.admission.standardId,
    artifactUseId: artifactTransaction.use.useId,
    initialLinkState: 'up',
    partitionPolicy: 'buffer',
    queueCapacity: 2,
    events: [
      { step: 0, type: 'send', packetId: packets[0].packetId, behavior: 'pass' },
      { step: 1, type: 'send', packetId: packets[1].packetId, behavior: 'duplicate', copies: 2 },
      { step: 2, type: 'send', packetId: packets[2].packetId, behavior: 'delay', releaseAt: 7 },
      { step: 3, type: 'link', state: 'down' },
      { step: 4, type: 'send', packetId: packets[3].packetId, behavior: 'pass' },
      { step: 5, type: 'send', packetId: packets[4].packetId, behavior: 'pass' },
      { step: 6, type: 'send', packetId: packets[5].packetId, behavior: 'pass' },
      { step: 7, type: 'link', state: 'up' },
      { step: 8, type: 'send', packetId: packets[6].packetId, behavior: 'drop' },
    ],
    claimBoundary:
      'This deterministic scenario exercises a rehearsal transport port with opaque synthetic packets. It does not define domain or command semantics.',
  };
  return { payloadRows, packets, payloads, scenario };
}

function executeFixture(fixture, artifactTransaction, catalog) {
  const run = runFaultScenario({
    scenario: fixture.scenario,
    packets: fixture.packets,
    payloads: fixture.payloads,
    artifactTransaction,
    catalog,
  });
  const frame = createFaultFrame(run);
  const verification = verifyFaultFrame(frame, run);
  return { run, frame, verification };
}

function main(argv) {
  if (argv.length !== 3) {
    console.error('usage: run_fault_machine_e2e.mjs <artifact-transaction.json> <xsd11-catalog.json> <output-dir>');
    return 2;
  }
  const [artifactPath, catalogPath, outputDir] = argv;
  rmSync(outputDir, { recursive: true, force: true });
  mkdirSync(outputDir, { recursive: true });
  const artifactTransaction = readJson(artifactPath);
  const catalog = readJson(catalogPath);
  const fixture = buildFixture(artifactTransaction, catalog);
  const first = executeFixture(fixture, artifactTransaction, catalog);
  const second = executeFixture(fixture, artifactTransaction, catalog);

  expected(
    first.run.scenarioDigest === deriveFaultScenarioDigest(fixture.scenario),
    'fault run is not bound to the executable scenario',
  );
  expected(first.run.runId === second.run.runId, 'fault run is not deterministic');
  expected(first.run.journalRoot === second.run.journalRoot, 'fault journal is not deterministic');
  expected(first.frame.frameId === second.frame.frameId, 'test frame is not deterministic');
  expected(first.verification.status === 'pass', 'detached verification did not pass');
  expected(first.run.metrics.sentPackets === 7, 'fault machine did not send all seven packets');
  expected(first.run.metrics.deliveredCopies === 6, 'fault machine delivery count changed');
  expected(first.run.metrics.droppedPackets === 2, 'fault machine drop count changed');
  expected(first.run.metrics.duplicateExtraCopies === 1, 'duplicate fault did not produce one extra copy');
  expected(first.run.metrics.delayedPackets === 1, 'delay fault was not retained');
  expected(first.run.metrics.bufferedPackets === 2, 'partition buffer did not retain two packets');
  expected(first.run.metrics.queueCapacityDrops === 1, 'bounded queue did not refuse the third partition packet');
  expected(first.run.metrics.reordered === true, 'delayed packet did not prove deterministic reordering');
  expected(first.frame.status === 'complete', 'read-only frame did not close cleanly');

  const encoded = JSON.stringify({
    packets: fixture.packets,
    scenario: fixture.scenario,
    run: first.run,
    frame: first.frame,
    verification: first.verification,
  });
  for (const row of fixture.payloadRows) {
    expected(!encoded.includes(row.payload.toString('utf8')), 'payload bytes escaped into retained evidence');
  }

  writeJson(join(outputDir, 'packet-set.json'), {
    schema: 'standards-port-test-packet-set/1',
    packets: fixture.packets,
    claimBoundary:
      'Payload bytes are deliberately omitted. These packets are opaque transport fixtures, not schema-valid command messages.',
  });
  writeJson(join(outputDir, 'scenario.json'), fixture.scenario);
  writeJson(join(outputDir, 'fault-run.json'), first.run);
  writeJson(join(outputDir, 'test-frame.json'), first.frame);
  writeJson(join(outputDir, 'verification.json'), first.verification);

  const evidenceFiles = [
    'packet-set.json',
    'scenario.json',
    'fault-run.json',
    'test-frame.json',
    'verification.json',
  ];
  const evidence = {
    schema: 'standards-port-fault-machine-qualification/1',
    status: 'pass',
    artifactAdmissionId: artifactTransaction.admission.admissionId,
    artifactUseId: artifactTransaction.use.useId,
    artifactSha256: artifactTransaction.admission.artifactSha256,
    catalogId: catalog.catalogId,
    scenarioDigest: first.run.scenarioDigest,
    runId: first.run.runId,
    frameId: first.frame.frameId,
    journalRoot: first.run.journalRoot,
    metrics: first.run.metrics,
    assertions: {
      deterministicReplay: true,
      exactAdmittedArtifactAndCatalog: true,
      exactPacketAndPayloadSet: true,
      opaquePayloadsNotExposed: true,
      boundedQueueRefusal: true,
      detachedRunAndFrameVerification: true,
      readOnlyHostFrame: true,
      domainSemanticsNotInvented: true,
    },
    files: Object.fromEntries(
      evidenceFiles.map((name) => [name, { sha256: sha256(join(outputDir, name)) }]),
    ),
    claimBoundary:
      'This qualification covers deterministic transport-fault behavior over opaque rehearsal packets. It does not validate a C2SIM message instance, prove operational network performance, or grant authority.',
  };
  writeJson(join(outputDir, 'qualification.json'), evidence);

  process.stdout.write(`${JSON.stringify({
    status: evidence.status,
    scenarioDigest: first.run.scenarioDigest,
    runId: first.run.runId,
    frameId: first.frame.frameId,
    journalRoot: first.run.journalRoot,
    metrics: first.run.metrics,
    outputDir,
  }, null, 2)}\n`);
  return 0;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  process.exitCode = main(process.argv.slice(2));
}

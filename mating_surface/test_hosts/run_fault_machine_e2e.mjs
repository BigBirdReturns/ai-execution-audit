#!/usr/bin/env node
import { createHash } from 'node:crypto';
import { mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';
import {
  createFaultFrame,
  createTestPacket,
  runFaultScenario,
} from './core/fault_machine.mjs';

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

async function main(argv) {
  if (argv.length !== 3) {
    console.error('usage: run_fault_machine_e2e.mjs <artifact-transaction.json> <xsd11-catalog.json> <output-dir>');
    return 2;
  }
  const [artifactPath, catalogPath, outputDir] = argv;
  rmSync(outputDir, { recursive: true, force: true });
  mkdirSync(outputDir, { recursive: true });
  const artifactTransaction = readJson(artifactPath);
  const catalog = readJson(catalogPath);

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

  const run = runFaultScenario({
    scenario,
    packets,
    payloads,
    artifactTransaction,
    catalog,
  });
  const frame = createFaultFrame(run);
  expected(run.metrics.sentPackets === 7, 'fault machine did not send all seven packets');
  expected(run.metrics.deliveredCopies === 6, 'fault machine delivery count changed');
  expected(run.metrics.droppedPackets === 2, 'fault machine drop count changed');
  expected(run.metrics.duplicateExtraCopies === 1, 'duplicate fault did not produce one extra copy');
  expected(run.metrics.delayedPackets === 1, 'delay fault was not retained');
  expected(run.metrics.bufferedPackets === 2, 'partition buffer did not retain two packets');
  expected(run.metrics.queueCapacityDrops === 1, 'bounded queue did not refuse the third partition packet');
  expected(run.metrics.reordered === true, 'delayed packet did not prove deterministic reordering');
  expected(frame.status === 'complete', 'read-only frame did not close cleanly');

  const encoded = JSON.stringify({ run, frame });
  for (const row of payloadRows) {
    expected(!encoded.includes(row.payload.toString('utf8')), 'payload bytes escaped into a receipt or frame');
  }

  writeJson(join(outputDir, 'packets.json'), {
    schema: 'standards-port-test-packet-set/1',
    packets,
    payloadCustody: payloadRows.map((row, index) => ({
      packetId: packets[index].packetId,
      payloadDigest: packets[index].payloadDigest,
      payloadBytes: packets[index].payloadBytes,
      validationClass: packets[index].validationClass,
    })),
    claimBoundary:
      'Payload bytes are deliberately omitted. These packets are opaque transport fixtures, not schema-valid command messages.',
  });
  writeJson(join(outputDir, 'scenario.json'), scenario);
  writeJson(join(outputDir, 'fault-run.json'), run);
  writeJson(join(outputDir, 'test-frame.json'), frame);

  const evidence = {
    schema: 'standards-port-fault-machine-qualification/1',
    status: 'pass',
    artifactAdmissionId: artifactTransaction.admission.admissionId,
    artifactUseId: artifactTransaction.use.useId,
    artifactSha256: artifactTransaction.admission.artifactSha256,
    catalogId: catalog.catalogId,
    runId: run.runId,
    frameId: frame.frameId,
    journalRoot: run.journalRoot,
    metrics: run.metrics,
    checks: {
      exact_admitted_artifact_and_catalog: true,
      opaque_payloads_not_exposed: true,
      deterministic_duplicate_delay_partition_queue_and_reconnect: true,
      bounded_queue_refusal: true,
      read_only_host_frame: true,
      no_domain_semantics_invented: true,
    },
    files: {},
    claimBoundary:
      'This qualification covers deterministic transport-fault behavior over opaque rehearsal packets. It does not validate a C2SIM message instance, prove operational network performance, or grant authority.',
  };
  for (const name of ['packets.json', 'scenario.json', 'fault-run.json', 'test-frame.json']) {
    evidence.files[name] = { sha256: sha256(join(outputDir, name)) };
  }
  writeJson(join(outputDir, 'qualification.json'), evidence);

  process.stdout.write(`${JSON.stringify({
    status: evidence.status,
    runId: run.runId,
    frameId: frame.frameId,
    journalRoot: run.journalRoot,
    metrics: run.metrics,
    outputDir,
  }, null, 2)}\n`);
  return 0;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  process.exitCode = await main(process.argv.slice(2));
}

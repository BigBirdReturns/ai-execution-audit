#!/usr/bin/env node
import { createHash } from 'node:crypto';
import {
  copyFile,
  mkdir,
  readFile,
  rm,
  writeFile,
} from 'node:fs/promises';
import { dirname, join, relative } from 'node:path';
import { pathToFileURL } from 'node:url';

const SHA256 = /^[0-9a-f]{64}$/;
const FRAME_KEYS = new Set([
  'schema',
  'frameId',
  'semanticConversationId',
  'standardId',
  'artifactUseId',
  'scenarioDigest',
  'faultRunId',
  'faultJournalRoot',
  'faultFrameId',
  'authorityProfileId',
  'authorityGeneration',
  'partitionEpochId',
  'reconciliationId',
  'reconciliationStatus',
  'status',
  'messages',
  'transport',
  'lastEvent',
  'hostContracts',
  'claimBoundary',
]);
const MESSAGE_KEYS = new Set([
  'schemaValid',
  'authorityAllowed',
  'receiverAccepted',
  'receiverRefused',
  'replayRefused',
]);
const TRANSPORT_KEYS = new Set([
  'sentPackets',
  'deliveredCopies',
  'deliveredUniquePackets',
  'droppedPackets',
  'explicitDrops',
  'linkDownDrops',
  'queueCapacityDrops',
  'duplicateExtraCopies',
  'delayedPackets',
  'bufferedPackets',
  'pendingDelayedPackets',
  'pendingBufferedPackets',
  'reordered',
  'finalLinkState',
]);
const LAST_EVENT_KEYS = new Set(['recordId', 'step', 'type']);
const HOST_CONTRACT_KEYS = new Set(['host', 'mode', 'inputs', 'outputs']);
const FORBIDDEN_FRAME_KEYS = new Set([
  'payload',
  'payloadbytes',
  'xml',
  'commandauthority',
  'targeting',
  'engagement',
  'effector',
  'effectorcontrol',
  'execute',
  'executionrequest',
]);
const FORBIDDEN_MAME_PATTERNS = [
  /os\.execute/i,
  /io\.popen/i,
  /manager\.machine\.devices/i,
  /manager\.machine\.memory/i,
  /manager\.machine\.ioport/i,
  /manager\.machine\.outputs/i,
  /emu\.keypost/i,
  /socket/i,
  /require\s*\(\s*["'](?:socket|http|https|ltn12)["']/i,
];
const REQUIRED_FORBIDDEN_CAPABILITIES = new Set([
  'network.remote',
  'execution.weapons',
  'authority.command',
]);

export class HostProjectionError extends Error {
  constructor(code, message) {
    super(message);
    this.name = 'HostProjectionError';
    this.code = code;
  }
}

function requireCondition(condition, code, message) {
  if (!condition) throw new HostProjectionError(code, message);
}

function isRecord(value) {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) return false;
  const prototype = Object.getPrototypeOf(value);
  return prototype === Object.prototype || prototype === null;
}

export function canonicalJson(value) {
  if (value === null) return 'null';
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(',')}]`;
  if (typeof value === 'object') {
    requireCondition(isRecord(value), 'NON_JSON_VALUE', 'canonical JSON requires plain objects');
    return `{${Object.keys(value)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${canonicalJson(value[key])}`)
      .join(',')}}`;
  }
  if (typeof value === 'number') {
    requireCondition(Number.isFinite(value), 'NON_JSON_NUMBER', 'non-finite numbers are not admissible');
  }
  const encoded = JSON.stringify(value);
  requireCondition(encoded !== undefined, 'NON_JSON_VALUE', 'non-JSON values are not admissible');
  return encoded;
}

function digest(prefix, value) {
  return `${prefix}_${createHash('sha256').update(canonicalJson(value), 'utf8').digest('hex')}`;
}

function sha256Bytes(bytes) {
  return createHash('sha256').update(bytes).digest('hex');
}

async function sha256File(path) {
  return sha256Bytes(await readFile(path));
}

function exactKeys(value, allowed, code, label) {
  requireCondition(isRecord(value), code, `${label} must be an object`);
  const unexpected = Object.keys(value).filter((key) => !allowed.has(key)).sort();
  requireCondition(unexpected.length === 0, code, `${label} contains unsupported field ${unexpected[0]}`);
  const missing = [...allowed].filter((key) => !Object.prototype.hasOwnProperty.call(value, key));
  requireCondition(missing.length === 0, code, `${label} is missing field ${missing[0]}`);
}

function boundedString(value, code, label, max = 2048) {
  requireCondition(typeof value === 'string', code, `${label} must be a string`);
  const normalized = value.trim();
  requireCondition(normalized.length > 0 && normalized.length <= max, code, `${label} is empty or unbounded`);
  return normalized;
}

function nonNegativeInteger(value, code, label) {
  requireCondition(Number.isSafeInteger(value) && value >= 0, code, `${label} must be a non-negative safe integer`);
  return value;
}

function normalizedKey(key) {
  return key.replace(/[^a-z0-9]/gi, '').toLowerCase();
}

function rejectForbiddenFrameKeys(value, path = '$') {
  if (Array.isArray(value)) {
    value.forEach((row, index) => rejectForbiddenFrameKeys(row, `${path}[${index}]`));
    return;
  }
  if (!isRecord(value)) return;
  for (const [key, nested] of Object.entries(value)) {
    requireCondition(
      !FORBIDDEN_FRAME_KEYS.has(normalizedKey(key)),
      'HOST_FRAME_FORBIDDEN_FIELD',
      `semantic host frame contains forbidden field ${key} at ${path}`,
    );
    rejectForbiddenFrameKeys(nested, `${path}.${key}`);
  }
}

function frameIdentityBody(frame) {
  const { schema: _schema, frameId: _frameId, claimBoundary: _claimBoundary, ...body } = frame;
  return body;
}

export function validateSemanticHostFrame(frame) {
  exactKeys(frame, FRAME_KEYS, 'HOST_FRAME_FIELDS_INVALID', 'semantic host frame');
  requireCondition(
    frame.schema === 'standards-semantic-rehearsal-frame/1',
    'HOST_FRAME_SCHEMA_INVALID',
    'semantic host frame schema is invalid',
  );
  for (const key of [
    'frameId',
    'semanticConversationId',
    'standardId',
    'artifactUseId',
    'scenarioDigest',
    'faultRunId',
    'faultJournalRoot',
    'faultFrameId',
    'authorityProfileId',
    'partitionEpochId',
    'reconciliationId',
    'claimBoundary',
  ]) {
    boundedString(frame[key], 'HOST_FRAME_FIELD_INVALID', key);
  }
  nonNegativeInteger(frame.authorityGeneration, 'HOST_FRAME_FIELD_INVALID', 'authorityGeneration');
  requireCondition(
    frame.status === 'reconciled' || frame.status === 'attention_required',
    'HOST_FRAME_STATUS_INVALID',
    'semantic host frame status is invalid',
  );
  requireCondition(
    ['continuous_authority', 'explicitly_superseded', 'human_required'].includes(frame.reconciliationStatus),
    'HOST_FRAME_RECONCILIATION_INVALID',
    'semantic host frame reconciliation status is invalid',
  );

  exactKeys(frame.messages, MESSAGE_KEYS, 'HOST_FRAME_MESSAGE_INVALID', 'message counters');
  for (const key of MESSAGE_KEYS) nonNegativeInteger(frame.messages[key], 'HOST_FRAME_MESSAGE_INVALID', key);
  requireCondition(
    frame.messages.receiverAccepted + frame.messages.receiverRefused
      >= frame.messages.schemaValid,
    'HOST_FRAME_MESSAGE_INVALID',
    'receiver outcomes do not cover the schema-valid conversation',
  );
  requireCondition(
    frame.messages.replayRefused <= frame.messages.receiverRefused,
    'HOST_FRAME_MESSAGE_INVALID',
    'replay refusals exceed receiver refusals',
  );

  exactKeys(frame.transport, TRANSPORT_KEYS, 'HOST_FRAME_TRANSPORT_INVALID', 'transport metrics');
  for (const key of [...TRANSPORT_KEYS].filter((key) => !['reordered', 'finalLinkState'].includes(key))) {
    nonNegativeInteger(frame.transport[key], 'HOST_FRAME_TRANSPORT_INVALID', key);
  }
  requireCondition(typeof frame.transport.reordered === 'boolean', 'HOST_FRAME_TRANSPORT_INVALID', 'reordered must be boolean');
  requireCondition(['up', 'down'].includes(frame.transport.finalLinkState), 'HOST_FRAME_TRANSPORT_INVALID', 'final link state is invalid');

  if (frame.lastEvent !== null) {
    exactKeys(frame.lastEvent, LAST_EVENT_KEYS, 'HOST_FRAME_LAST_EVENT_INVALID', 'last event');
    boundedString(frame.lastEvent.recordId, 'HOST_FRAME_LAST_EVENT_INVALID', 'last event recordId');
    nonNegativeInteger(frame.lastEvent.step, 'HOST_FRAME_LAST_EVENT_INVALID', 'last event step');
    boundedString(frame.lastEvent.type, 'HOST_FRAME_LAST_EVENT_INVALID', 'last event type');
  }

  requireCondition(Array.isArray(frame.hostContracts) && frame.hostContracts.length === 2, 'HOST_FRAME_CONTRACT_INVALID', 'two host contracts are required');
  const hosts = new Set();
  for (const [index, contract] of frame.hostContracts.entries()) {
    exactKeys(contract, HOST_CONTRACT_KEYS, 'HOST_FRAME_CONTRACT_INVALID', `host contract ${index}`);
    requireCondition(['mame', 'motiondeck'].includes(contract.host), 'HOST_FRAME_CONTRACT_INVALID', `unknown host ${contract.host}`);
    requireCondition(contract.mode === 'read_only', 'HOST_FRAME_CONTRACT_INVALID', `${contract.host} contract is not read-only`);
    requireCondition(Array.isArray(contract.inputs) && Array.isArray(contract.outputs), 'HOST_FRAME_CONTRACT_INVALID', `${contract.host} contract lists are invalid`);
    hosts.add(contract.host);
  }
  requireCondition(hosts.has('mame') && hosts.has('motiondeck'), 'HOST_FRAME_CONTRACT_INVALID', 'required host contracts are missing');
  rejectForbiddenFrameKeys(frame);

  const encoded = JSON.stringify(frame).toLowerCase();
  for (const forbidden of ['<?xml', 'polybolos', 'dandelion']) {
    requireCondition(!encoded.includes(forbidden), 'HOST_FRAME_CONTENT_FORBIDDEN', `semantic host frame contains forbidden content ${forbidden}`);
  }
  requireCondition(
    frame.frameId === digest('standardsemanticrehearsalframe1', frameIdentityBody(frame)),
    'HOST_FRAME_ID_INVALID',
    'semantic host frame identity is invalid',
  );
  return frame;
}

export function validateMameProjection(initSource, pluginMetadata) {
  requireCondition(typeof initSource === 'string' && initSource.length > 0, 'MAME_PLUGIN_INVALID', 'MAME plugin source is empty');
  requireCondition(isRecord(pluginMetadata) && isRecord(pluginMetadata.plugin), 'MAME_PLUGIN_METADATA_INVALID', 'MAME plugin metadata is invalid');
  requireCondition(pluginMetadata.plugin.name === 'c2simrehearsal', 'MAME_PLUGIN_METADATA_INVALID', 'MAME plugin name is invalid');
  requireCondition(pluginMetadata.plugin.type === 'plugin', 'MAME_PLUGIN_METADATA_INVALID', 'MAME plugin type is invalid');
  requireCondition(pluginMetadata.plugin.start === 'false', 'MAME_PLUGIN_METADATA_INVALID', 'MAME plugin must remain opt-in');
  for (const required of [
    'emu.register_menu',
    'semantic-host-frame.json',
    'standards-semantic-rehearsal-frame/1',
    'READ-ONLY RECEIPT',
    'NO VERIFIED FRAME',
  ]) {
    requireCondition(initSource.includes(required), 'MAME_PLUGIN_INVALID', `MAME plugin is missing ${required}`);
  }
  for (const pattern of FORBIDDEN_MAME_PATTERNS) {
    requireCondition(!pattern.test(initSource), 'MAME_PLUGIN_AUTHORITY_FORBIDDEN', `MAME plugin contains forbidden surface ${pattern}`);
  }
  const encoded = `${initSource}\n${JSON.stringify(pluginMetadata)}`.toLowerCase();
  for (const forbidden of ['polybolos', 'dandelion']) {
    requireCondition(!encoded.includes(forbidden), 'MAME_PLUGIN_BRANDING_FORBIDDEN', `MAME plugin contains forbidden product vocabulary ${forbidden}`);
  }
  return {
    sourceSha256: sha256Bytes(Buffer.from(initSource, 'utf8')),
    metadataSha256: sha256Bytes(Buffer.from(`${JSON.stringify(pluginMetadata, null, 2)}\n`, 'utf8')),
  };
}

function cartridgeFingerprintBody(cartridge) {
  const { fingerprint: _fingerprint, ...body } = cartridge;
  return body;
}

export function validateMotionDeckCartridge(cartridge) {
  requireCondition(isRecord(cartridge), 'MOTIONDECK_CARTRIDGE_INVALID', 'MotionDeck cartridge is invalid');
  requireCondition(cartridge.schema === 'handbus.game-cartridge.v1', 'MOTIONDECK_CARTRIDGE_INVALID', 'MotionDeck cartridge schema is invalid');
  requireCondition(cartridge.id === 'standards.c2sim-semantic-rehearsal', 'MOTIONDECK_CARTRIDGE_INVALID', 'MotionDeck cartridge identity is invalid');
  requireCondition(cartridge.launch?.kind === 'direct-owned-title', 'MOTIONDECK_CARTRIDGE_INVALID', 'MotionDeck launch kind is invalid');
  requireCondition(cartridge.launch?.foreign_launcher === 'forbidden', 'MOTIONDECK_CARTRIDGE_INVALID', 'foreign launcher must remain forbidden');
  requireCondition(cartridge.policy?.offline_required === true, 'MOTIONDECK_CARTRIDGE_INVALID', 'MotionDeck cartridge must remain offline');
  requireCondition(cartridge.safety?.fail_closed === true, 'MOTIONDECK_CARTRIDGE_INVALID', 'MotionDeck cartridge must fail closed');
  requireCondition(cartridge.safety?.execution_authority === 'none', 'MOTIONDECK_CARTRIDGE_AUTHORITY_FORBIDDEN', 'MotionDeck cartridge claims execution authority');
  requireCondition(Array.isArray(cartridge.capabilities?.forbidden), 'MOTIONDECK_CARTRIDGE_INVALID', 'MotionDeck forbidden capabilities are missing');
  const forbidden = new Set(cartridge.capabilities.forbidden);
  for (const capability of REQUIRED_FORBIDDEN_CAPABILITIES) {
    requireCondition(forbidden.has(capability), 'MOTIONDECK_CARTRIDGE_AUTHORITY_FORBIDDEN', `MotionDeck cartridge does not forbid ${capability}`);
  }
  requireCondition(Array.isArray(cartridge.data_flows) && cartridge.data_flows.length === 1, 'MOTIONDECK_CARTRIDGE_INVALID', 'MotionDeck cartridge requires one data flow');
  const flow = cartridge.data_flows[0];
  requireCondition(flow.source === 'standards-semantic-rehearsal-frame/1', 'MOTIONDECK_CARTRIDGE_INVALID', 'MotionDeck flow uses another source');
  requireCondition(flow.sink === 'motiondeck-owned-surface', 'MOTIONDECK_CARTRIDGE_INVALID', 'MotionDeck does not retain presentation ownership');
  requireCondition(flow.network === 'none', 'MOTIONDECK_CARTRIDGE_AUTHORITY_FORBIDDEN', 'MotionDeck flow uses a network');
  requireCondition(SHA256.test(cartridge.fingerprint), 'MOTIONDECK_CARTRIDGE_FINGERPRINT_INVALID', 'MotionDeck fingerprint is invalid');
  const expected = sha256Bytes(Buffer.from(canonicalJson(cartridgeFingerprintBody(cartridge)), 'utf8'));
  requireCondition(cartridge.fingerprint === expected, 'MOTIONDECK_CARTRIDGE_FINGERPRINT_INVALID', 'MotionDeck fingerprint does not match the cartridge');
  const encoded = JSON.stringify(cartridge).toLowerCase();
  for (const product of ['polybolos', 'dandelion']) {
    requireCondition(!encoded.includes(product), 'MOTIONDECK_CARTRIDGE_BRANDING_FORBIDDEN', `MotionDeck cartridge contains forbidden product vocabulary ${product}`);
  }
  return cartridge;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function metric(label, value) {
  return `<div class="metric"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`;
}

export function renderSemanticHostSurface(frame) {
  validateSemanticHostFrame(frame);
  const status = frame.status === 'reconciled' ? 'RECONCILED' : 'ATTENTION REQUIRED';
  const metrics = [
    metric('Schema-valid messages', frame.messages.schemaValid),
    metric('Authority allowed', frame.messages.authorityAllowed),
    metric('Receiver accepted', frame.messages.receiverAccepted),
    metric('Receiver refused', frame.messages.receiverRefused),
    metric('Replay refused', frame.messages.replayRefused),
    metric('Delivered copies', frame.transport.deliveredCopies),
    metric('Dropped packets', frame.transport.droppedPackets),
    metric('Buffered packets', frame.transport.bufferedPackets),
    metric('Delayed packets', frame.transport.delayedPackets),
    metric('Final link', frame.transport.finalLinkState.toUpperCase()),
  ].join('');
  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; img-src data:; base-uri 'none'; form-action 'none'">
<title>C2SIM Semantic Rehearsal</title>
<style>
:root{color-scheme:dark;--bg:#0d1114;--panel:#151b20;--line:#35414a;--text:#edf2f5;--muted:#9aa8b2;--good:#a9dfb2;--warn:#f2d38a}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font-family:ui-monospace,SFMono-Regular,Consolas,monospace;min-height:100vh;padding:clamp(18px,4vw,54px)}main{max-width:1180px;margin:auto}header{display:flex;gap:24px;align-items:flex-start;justify-content:space-between;border-bottom:1px solid var(--line);padding-bottom:24px;margin-bottom:24px}h1{font-size:clamp(24px,4vw,52px);line-height:1;margin:0 0 10px;letter-spacing:.03em}p{color:var(--muted);line-height:1.55;margin:.4rem 0}.status{border:1px solid var(--line);padding:12px 16px;font-weight:800;color:${frame.status === 'reconciled' ? 'var(--good)' : 'var(--warn)'}}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px}.metric,.receipt{background:var(--panel);border:1px solid var(--line);padding:16px}.metric span{display:block;color:var(--muted);font-size:12px;margin-bottom:10px}.metric strong{font-size:24px}.receipts{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:12px;margin-top:24px}.receipt h2{font-size:13px;color:var(--muted);font-weight:500;margin:0 0 10px}.receipt code{display:block;overflow-wrap:anywhere;font-size:12px;line-height:1.5}.boundary{margin-top:24px;border-top:1px solid var(--line);padding-top:18px;font-size:12px}.authority{color:var(--good);font-weight:700}
</style>
</head>
<body>
<main>
<header><div><h1>C2SIM SEMANTIC REHEARSAL</h1><p>${escapeHtml(frame.standardId)} · read-only standards receipt</p></div><div class="status">${status}</div></header>
<section class="grid">${metrics}</section>
<section class="receipts">
<div class="receipt"><h2>Conversation</h2><code>${escapeHtml(frame.semanticConversationId)}</code></div>
<div class="receipt"><h2>Fault run</h2><code>${escapeHtml(frame.faultRunId)}</code></div>
<div class="receipt"><h2>Partition epoch</h2><code>${escapeHtml(frame.partitionEpochId)}</code></div>
<div class="receipt"><h2>Reconciliation</h2><code>${escapeHtml(frame.reconciliationId)}</code><p class="authority">${escapeHtml(frame.reconciliationStatus.toUpperCase())}</p></div>
<div class="receipt"><h2>Frame</h2><code>${escapeHtml(frame.frameId)}</code></div>
<div class="receipt"><h2>Authority</h2><code>${escapeHtml(frame.authorityProfileId)} · generation ${escapeHtml(frame.authorityGeneration)}</code><p>Receipt projection only. No command authority.</p></div>
</section>
<p class="boundary">${escapeHtml(frame.claimBoundary)}</p>
</main>
</body>
</html>
`;
}

async function copyEnsuringParent(source, destination) {
  await mkdir(dirname(destination), { recursive: true });
  await copyFile(source, destination);
}

export async function compileHostProjections(framePath, sourceRoot, outputDir) {
  const frameBytes = await readFile(framePath);
  const frame = validateSemanticHostFrame(JSON.parse(frameBytes.toString('utf8')));
  const mameRoot = join(sourceRoot, 'mating_surface', 'test_hosts', 'mame');
  const motionDeckRoot = join(sourceRoot, 'mating_surface', 'test_hosts', 'motiondeck');
  const initPath = join(mameRoot, 'c2simrehearsal', 'init.lua');
  const pluginPath = join(mameRoot, 'c2simrehearsal', 'plugin.json');
  const installerPath = join(mameRoot, 'Install-C2SIMRehearsalPlugin.ps1');
  const cartridgePath = join(motionDeckRoot, 'c2sim-semantic-rehearsal.cartridge.json');
  const launcherPath = join(motionDeckRoot, 'START_C2SIM_SEMANTIC_REHEARSAL.cmd');

  const [initSource, pluginBytes, installerBytes, cartridgeBytes, launcherBytes] = await Promise.all([
    readFile(initPath, 'utf8'),
    readFile(pluginPath),
    readFile(installerPath),
    readFile(cartridgePath),
    readFile(launcherPath),
  ]);
  const pluginMetadata = JSON.parse(pluginBytes.toString('utf8'));
  const cartridge = JSON.parse(cartridgeBytes.toString('utf8'));
  const mame = validateMameProjection(initSource, pluginMetadata);
  validateMotionDeckCartridge(cartridge);
  const html = renderSemanticHostSurface(frame);
  requireCondition(!/<script\b/i.test(html), 'HOST_SURFACE_EXECUTABLE_SCRIPT_FORBIDDEN', 'host surface contains executable script');
  requireCondition(!/https?:\/\//i.test(html), 'HOST_SURFACE_NETWORK_FORBIDDEN', 'host surface contains a remote URL');

  await rm(outputDir, { recursive: true, force: true });
  const mameOut = join(outputDir, 'mame');
  const pluginOut = join(mameOut, 'c2simrehearsal');
  const motionDeckOut = join(outputDir, 'motiondeck');
  await Promise.all([
    copyEnsuringParent(initPath, join(pluginOut, 'init.lua')),
    copyEnsuringParent(pluginPath, join(pluginOut, 'plugin.json')),
    copyEnsuringParent(installerPath, join(mameOut, 'Install-C2SIMRehearsalPlugin.ps1')),
    copyEnsuringParent(framePath, join(pluginOut, 'semantic-host-frame.json')),
    copyEnsuringParent(cartridgePath, join(motionDeckOut, 'c2sim-semantic-rehearsal.cartridge.json')),
    copyEnsuringParent(launcherPath, join(motionDeckOut, 'START_C2SIM_SEMANTIC_REHEARSAL.cmd')),
    copyEnsuringParent(framePath, join(motionDeckOut, 'semantic-host-frame.json')),
  ]);
  await mkdir(motionDeckOut, { recursive: true });
  await writeFile(join(motionDeckOut, 'c2sim-semantic-rehearsal.html'), html, 'utf8');

  const generatedFiles = [
    'mame/Install-C2SIMRehearsalPlugin.ps1',
    'mame/c2simrehearsal/init.lua',
    'mame/c2simrehearsal/plugin.json',
    'mame/c2simrehearsal/semantic-host-frame.json',
    'motiondeck/START_C2SIM_SEMANTIC_REHEARSAL.cmd',
    'motiondeck/c2sim-semantic-rehearsal.cartridge.json',
    'motiondeck/c2sim-semantic-rehearsal.html',
    'motiondeck/semantic-host-frame.json',
  ];
  const files = {};
  for (const name of generatedFiles) {
    const path = join(outputDir, name);
    files[name] = {
      sha256: await sha256File(path),
      bytes: (await readFile(path)).length,
    };
  }
  const body = {
    frameId: frame.frameId,
    frameSha256: sha256Bytes(frameBytes),
    semanticConversationId: frame.semanticConversationId,
    standardId: frame.standardId,
    reconciliationStatus: frame.reconciliationStatus,
    mame: {
      sourceSha256: mame.sourceSha256,
      metadataSha256: mame.metadataSha256,
      authority: 'none',
      mode: 'read_only',
      targetHostQualified: false,
    },
    motiondeck: {
      cartridgeId: cartridge.id,
      cartridgeFingerprint: cartridge.fingerprint,
      presentationOwner: 'motiondeck',
      authority: 'none',
      targetHostQualified: false,
    },
    files,
  };
  const receipt = {
    schema: 'standards-semantic-test-host-projection/1',
    status: 'pass',
    projectionId: digest('standardsemantichostprojection1', body),
    ...body,
    claimBoundary:
      'This receipt proves deterministic read-only MAME and MotionDeck projection artifacts over one verified semantic rehearsal frame. It does not qualify a target MAME runtime, MotionDeck installation, Windows host, cabinet controls, display, room, or operational authority.',
  };
  await writeFile(join(outputDir, 'projection-receipt.json'), `${JSON.stringify(receipt, null, 2)}\n`, 'utf8');
  return receipt;
}

async function main(argv) {
  if (argv.length !== 3) {
    console.error('usage: host_projection.mjs <semantic-host-frame.json> <repository-root> <output-dir>');
    return 2;
  }
  const receipt = await compileHostProjections(argv[0], argv[1], argv[2]);
  process.stdout.write(`${JSON.stringify({
    status: receipt.status,
    projectionId: receipt.projectionId,
    frameId: receipt.frameId,
    files: Object.keys(receipt.files).length,
    output: argv[2],
  }, null, 2)}\n`);
  return 0;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  process.exitCode = await main(process.argv.slice(2));
}

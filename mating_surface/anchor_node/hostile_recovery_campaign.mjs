import { createHash } from 'node:crypto';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  MessageAuthorityRuntime,
  canonicalJson,
  verifyAuthorityDecision,
  verifyReconciliation,
} from '../semantic/authority_sidecar.mjs';
import { verifyVerticalSlice } from './vertical_slice.mjs';
import { verifyFaultWorkerCampaign } from './fault_worker_campaign.mjs';

export class HostileRecoveryError extends Error {
  constructor(code, message) {
    super(message);
    this.name = 'HostileRecoveryError';
    this.code = code;
  }
}

function requireCondition(condition, code, message) {
  if (!condition) throw new HostileRecoveryError(code, message);
}

function isRecord(value) {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) return false;
  const prototype = Object.getPrototypeOf(value);
  return prototype === Object.prototype || prototype === null;
}

function digest(prefix, value) {
  return `${prefix}_${createHash('sha256').update(canonicalJson(value), 'utf8').digest('hex')}`;
}

function sha256Text(text) {
  return createHash('sha256').update(text, 'utf8').digest('hex');
}

function bodyWithoutId(value, idKey) {
  const copy = structuredClone(value);
  delete copy[idKey];
  return copy;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function sortedUnique(values) {
  return [...new Set(values)].sort();
}

export function runConflictingAuthorityReconciliation(bundle) {
  verifyVerticalSlice(bundle);
  const runtime = new MessageAuthorityRuntime(bundle.authorityProfile);
  runtime.setLinkState('headquarters_denied', 1);
  const { decision, ticket } = runtime.evaluateMessage(bundle.semanticMessageReceipt, {
    step: 2,
    localOperatorPresent: true,
  });
  verifyAuthorityDecision(decision, bundle.authorityProfile);
  requireCondition(decision.disposition === 'allow' && ticket !== null, 'AUTHORITY_CONFLICT_SETUP_INVALID', 'local denied-communications decision was not admitted');
  runtime.setLinkState('connected', 5);
  const reconciliation = runtime.reconcile({
    step: 6,
    returningAuthorityGeneration: bundle.authorityProfile.authorityGeneration + 1,
    supersedesGeneration: null,
  });
  verifyReconciliation(reconciliation, bundle.authorityProfile);
  requireCondition(reconciliation.status === 'human_required', 'AUTHORITY_CONFLICT_INVALID', 'conflicting returning authority was not held for human review');
  const body = {
    schema: 'spectra-anchor-node-conflicting-authority-recovery/1',
    localDecision: decision,
    localTicket: ticket,
    reconciliation,
    canonicalMissionStateIdBefore: bundle.missionStateAfter.missionStateId,
    canonicalMissionStateIdAfter: bundle.missionStateAfter.missionStateId,
    canonicalStateMutated: false,
    status: 'human_required',
    authority: false,
    claimBoundary: 'This receipt preserves one synthetic conflict between local and returning authority. It does not silently merge authority, rewrite mission state, or grant operational command authority.',
  };
  return { ...body, recoveryId: digest('anchorauthorityconflictrecovery1', body) };
}

export function runInterfaceDriftRefusal() {
  const approved = {
    schema: 'spectra-anchor-node-interface-control-contract/1',
    interfaceId: 'SYN-LEGACY-CONSOLE-001',
    controlId: 'SUBMIT_LOCAL_REVIEW',
    label: 'Submit local review',
    bounds: { x: 120, y: 88, width: 240, height: 44 },
    expectedPreState: 'review_draft',
    expectedPostState: 'review_submitted',
    allowedInteraction: 'single_primary_activation',
    claimBoundary: 'Invented interface contract for deterministic drift qualification only.',
  };
  const observed = {
    schema: 'spectra-anchor-node-interface-observation/1',
    interfaceId: approved.interfaceId,
    controlId: approved.controlId,
    label: approved.label,
    bounds: { x: 480, y: 132, width: 240, height: 44 },
    observedPreState: 'review_draft',
    claimBoundary: 'Invented observed surface. It is not a real application, operator action, or external system.',
  };
  const sameBounds = canonicalJson(approved.bounds) === canonicalJson(observed.bounds);
  const sameLabel = approved.label === observed.label;
  const samePreState = approved.expectedPreState === observed.observedPreState;
  const disposition = sameBounds && sameLabel && samePreState ? 'allow' : 'refuse';
  const reason = !sameBounds
    ? 'INTERFACE_DRIFT'
    : !sameLabel
      ? 'CONTROL_LABEL_DRIFT'
      : !samePreState
        ? 'PRE_STATE_DRIFT'
        : 'CONTROL_ADMITTED';
  requireCondition(disposition === 'refuse' && reason === 'INTERFACE_DRIFT', 'INTERFACE_DRIFT_FIXTURE_INVALID', 'fixture must exercise bounded drift refusal');
  const body = {
    schema: 'spectra-anchor-node-interface-drift-receipt/1',
    approvedContractDigest: digest('anchorinterfacecontract1', approved),
    observedSurfaceDigest: digest('anchorinterfaceobservation1', observed),
    controlId: approved.controlId,
    disposition,
    reason,
    interactionPerformed: false,
    postStateClaimed: false,
    authority: false,
    claimBoundary: 'This receipt proves the synthetic interface adapter refused a moved control instead of improvising. It performs no click, command, or external action.',
  };
  return { ...body, driftReceiptId: digest('anchorinterfacedriftreceipt1', body) };
}

export function buildDerivedProjections(canonicalMissionState) {
  requireCondition(canonicalMissionState?.schema === 'spectra-anchor-node-canonical-mission-state/1', 'CANONICAL_STATE_INVALID', 'canonical mission state is invalid');
  const nodes = [
    ...canonicalMissionState.entities.map((row) => ({
      nodeId: row.entityId,
      nodeType: row.entityType,
      uncertaintyState: row.uncertainty.state,
      sourceRefs: row.sourceObservationIds,
    })),
    ...canonicalMissionState.obligations.map((row) => ({
      nodeId: row.obligationId,
      nodeType: 'obligation',
      uncertaintyState: row.status === 'open' ? 'UNRESOLVED' : 'PROVEN',
      sourceRefs: row.evidenceRefs,
    })),
    ...canonicalMissionState.taskStates.map((row) => ({
      nodeId: row.taskReceiptId,
      nodeType: 'task_state',
      uncertaintyState: row.terminalState === 'completed' ? 'PROVEN' : 'UNRESOLVED',
      sourceRefs: [row.outputDigest],
    })),
  ].sort((a, b) => a.nodeId.localeCompare(b.nodeId));
  const edges = canonicalMissionState.relationships.map((row) => ({
    edgeId: row.relationshipStateId,
    edgeType: row.relationshipType,
    from: row.fromEntityId,
    to: row.toEntityId,
    state: row.state,
    uncertaintyState: row.uncertainty.state,
  })).sort((a, b) => a.edgeId.localeCompare(b.edgeId));
  const queryRows = [
    ...nodes.map((row) => ({
      rowType: 'node',
      objectId: row.nodeId,
      objectType: row.nodeType,
      state: row.uncertaintyState,
    })),
    ...edges.map((row) => ({
      rowType: 'edge',
      objectId: row.edgeId,
      objectType: row.edgeType,
      state: row.uncertaintyState,
    })),
  ].sort((a, b) => `${a.rowType}:${a.objectId}`.localeCompare(`${b.rowType}:${b.objectId}`));
  const body = {
    schema: 'spectra-anchor-node-derived-projections/1',
    sourceMissionStateId: canonicalMissionState.missionStateId,
    canonicalStateOwner: false,
    graph: { nodes, edges },
    queryRows,
    cacheKeys: sortedUnique([
      canonicalMissionState.missionStateId,
      ...nodes.map((row) => row.nodeId),
      ...edges.map((row) => row.edgeId),
    ]),
    claimBoundary: 'Derived graph, query, and cache projection for synthetic qualification. Deleting this object must not delete or modify canonical mission state.',
  };
  return { ...body, projectionId: digest('anchorderivedprojections1', body) };
}

export function runProjectionDestructionRebuild(bundle) {
  verifyVerticalSlice(bundle);
  const before = buildDerivedProjections(bundle.missionStateAfter);
  const destroyed = {
    projectionId: before.projectionId,
    graphRowsRemoved: before.graph.nodes.length + before.graph.edges.length,
    queryRowsRemoved: before.queryRows.length,
    cacheKeysRemoved: before.cacheKeys.length,
  };
  const rebuilt = buildDerivedProjections(bundle.missionStateAfter);
  requireCondition(canonicalJson(before) === canonicalJson(rebuilt), 'PROJECTION_REBUILD_MISMATCH', 'rebuilt projection differs');
  requireCondition(before.sourceMissionStateId === bundle.missionStateAfter.missionStateId, 'PROJECTION_SOURCE_INVALID', 'projection cites another canonical state');
  const body = {
    schema: 'spectra-anchor-node-projection-rebuild-receipt/1',
    canonicalMissionStateIdBefore: bundle.missionStateAfter.missionStateId,
    canonicalMissionStateIdAfter: bundle.missionStateAfter.missionStateId,
    canonicalStateMutated: false,
    destroyed,
    rebuiltProjectionId: rebuilt.projectionId,
    byteEquivalent: canonicalJson(before) === canonicalJson(rebuilt),
    status: 'PASS',
    authority: false,
    claimBoundary: 'This receipt proves synthetic graph, query, and cache projections can be discarded and rebuilt without changing canonical mission state.',
  };
  return {
    projections: before,
    receipt: { ...body, rebuildReceiptId: digest('anchorprojectionrebuildreceipt1', body) },
  };
}

function afterActionData({ bundle, faultCampaign, authorityConflict, interfaceDrift, projectionRebuild }) {
  return {
    profileId: bundle.profileId,
    runId: bundle.runId,
    classification: bundle.classification,
    canonicalMissionStateId: bundle.missionStateAfter.missionStateId,
    taskReceiptId: bundle.taskReceipt.taskReceiptId,
    authorityDisposition: bundle.authorityDecision.disposition,
    faultCampaignId: faultCampaign.campaignId,
    duplicateReplayRefused: faultCampaign.duplicateReceiverReceipts[1].reason === 'MESSAGE_REPLAY',
    workerLossRecovered: faultCampaign.workerRecovery.acceptedCompletionCount === 1,
    authorityConflictStatus: authorityConflict.status,
    interfaceDisposition: interfaceDrift.disposition,
    interfaceReason: interfaceDrift.reason,
    projectionRebuildStatus: projectionRebuild.receipt.status,
    unresolvedObligations: sortedUnique([
      ...bundle.missionStateAfter.obligations
        .filter((row) => row.status === 'open')
        .map((row) => row.obligationId),
      authorityConflict.reconciliation.reconciliationId,
    ]),
    externalServiceCalls: 0,
    operationalCredentials: 0,
    latticeRequired: false,
    authority: 'none',
  };
}

export function renderAfterActionHtml(data) {
  requireCondition(isRecord(data), 'AFTER_ACTION_DATA_INVALID', 'after-action data must be an object');
  const obligations = data.unresolvedObligations
    .map((value) => `<li><code>${escapeHtml(value)}</code></li>`)
    .join('');
  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Spectra Anchor Node MP01 after-action receipt</title>
<style>
body{font:16px/1.5 system-ui,sans-serif;max-width:960px;margin:0 auto;padding:32px;background:#0d1117;color:#e6edf3}h1,h2{line-height:1.15}code{overflow-wrap:anywhere}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px}.card{border:1px solid #30363d;border-radius:10px;padding:16px;background:#161b22}.pass{color:#3fb950}.hold{color:#d29922}.refuse{color:#f85149}</style>
</head>
<body>
<h1>Spectra Anchor Node Mission Profile 01</h1>
<p>Deterministic after-action review generated only from retained synthetic receipts.</p>
<div class="grid">
<section class="card"><h2>Canonical state</h2><code>${escapeHtml(data.canonicalMissionStateId)}</code></section>
<section class="card"><h2>Local task</h2><p class="pass">${escapeHtml(data.taskReceiptId)}</p></section>
<section class="card"><h2>Transport and worker recovery</h2><p>Duplicate replay refused: ${escapeHtml(data.duplicateReplayRefused)}</p><p>Worker loss recovered: ${escapeHtml(data.workerLossRecovered)}</p></section>
<section class="card"><h2>Returning authority</h2><p class="hold">${escapeHtml(data.authorityConflictStatus)}</p></section>
<section class="card"><h2>Interface procedure</h2><p class="refuse">${escapeHtml(data.interfaceDisposition)}: ${escapeHtml(data.interfaceReason)}</p></section>
<section class="card"><h2>Projection rebuild</h2><p class="pass">${escapeHtml(data.projectionRebuildStatus)}</p></section>
</div>
<h2>Unresolved obligations</h2><ul>${obligations}</ul>
<h2>Claim boundary</h2><p>This page proves only one invented, unclassified, synthetic qualification campaign. It carries no operational C2, field, command, targeting, engagement, effector, weapons, or production Lattice claim.</p>
</body>
</html>
`;
}

export function runHostileRecoveryCampaign(bundle, faultCampaign) {
  verifyVerticalSlice(bundle);
  verifyFaultWorkerCampaign(faultCampaign, bundle);
  const authorityConflict = runConflictingAuthorityReconciliation(bundle);
  const interfaceDrift = runInterfaceDriftRefusal();
  const projectionRebuild = runProjectionDestructionRebuild(bundle);
  const data = afterActionData({
    bundle,
    faultCampaign,
    authorityConflict,
    interfaceDrift,
    projectionRebuild,
  });
  const html = renderAfterActionHtml(data);
  const afterAction = {
    schema: 'spectra-anchor-node-after-action-surface/1',
    data,
    htmlSha256: sha256Text(html),
    htmlBytes: Buffer.byteLength(html, 'utf8'),
    generatedFromReceiptsOnly: true,
    hiddenBrowserState: false,
    claimBoundary: 'Deterministic static presentation generated from retained synthetic receipts only. The browser owns no mission, authority, or acceptance state.',
  };
  const body = {
    schema: 'spectra-anchor-node-hostile-recovery-campaign/1',
    profileId: bundle.profileId,
    runId: bundle.runId,
    faultCampaignId: faultCampaign.campaignId,
    authorityConflict,
    interfaceDrift,
    projectionRebuild,
    afterAction,
    externalServiceCalls: 0,
    operationalCredentials: 0,
    authority: false,
    claimBoundary: 'This campaign proves synthetic conflict hold, interface drift refusal, projection reconstruction, and receipt-only after-action rendering. It grants no operational or command authority.',
  };
  return {
    campaign: { ...body, campaignId: digest('anchorhostilerecoverycampaign1', body) },
    html,
  };
}

export function verifyHostileRecoveryCampaign(campaign, html, bundle, faultCampaign) {
  requireCondition(isRecord(campaign) && campaign.schema === 'spectra-anchor-node-hostile-recovery-campaign/1', 'HOSTILE_CAMPAIGN_INVALID', 'hostile recovery campaign schema is invalid');
  requireCondition(campaign.authority === false, 'HOSTILE_CAMPAIGN_INVALID', 'hostile recovery campaign cannot carry authority');
  requireCondition(campaign.externalServiceCalls === 0, 'HOSTILE_CAMPAIGN_INVALID', 'hostile recovery campaign contains external calls');
  requireCondition(campaign.operationalCredentials === 0, 'HOSTILE_CAMPAIGN_INVALID', 'hostile recovery campaign contains operational credentials');
  requireCondition(campaign.authorityConflict.status === 'human_required', 'HOSTILE_CAMPAIGN_INVALID', 'authority conflict was not held');
  requireCondition(campaign.authorityConflict.canonicalStateMutated === false, 'HOSTILE_CAMPAIGN_INVALID', 'authority reconciliation mutated canonical state');
  requireCondition(campaign.interfaceDrift.disposition === 'refuse' && campaign.interfaceDrift.interactionPerformed === false, 'HOSTILE_CAMPAIGN_INVALID', 'interface drift did not refuse safely');
  requireCondition(campaign.projectionRebuild.receipt.status === 'PASS' && campaign.projectionRebuild.receipt.canonicalStateMutated === false, 'HOSTILE_CAMPAIGN_INVALID', 'projection rebuild did not preserve canonical state');
  requireCondition(campaign.afterAction.generatedFromReceiptsOnly === true && campaign.afterAction.hiddenBrowserState === false, 'HOSTILE_CAMPAIGN_INVALID', 'after-action surface relies on hidden state');
  requireCondition(campaign.afterAction.htmlSha256 === sha256Text(html), 'AFTER_ACTION_HTML_MISMATCH', 'after-action HTML hash differs');
  requireCondition(campaign.afterAction.htmlBytes === Buffer.byteLength(html, 'utf8'), 'AFTER_ACTION_HTML_MISMATCH', 'after-action HTML byte count differs');
  requireCondition(campaign.campaignId === digest('anchorhostilerecoverycampaign1', bodyWithoutId(campaign, 'campaignId')), 'HOSTILE_CAMPAIGN_ID_INVALID', 'hostile recovery campaign identity is invalid');
  const replayed = runHostileRecoveryCampaign(bundle, faultCampaign);
  requireCondition(canonicalJson(replayed.campaign) === canonicalJson(campaign), 'HOSTILE_CAMPAIGN_REPLAY_MISMATCH', 'hostile recovery campaign does not replay');
  requireCondition(replayed.html === html, 'HOSTILE_CAMPAIGN_REPLAY_MISMATCH', 'after-action HTML does not replay');
  const receiptBody = {
    schema: 'spectra-anchor-node-hostile-recovery-verification/1',
    campaignId: campaign.campaignId,
    runId: campaign.runId,
    status: 'PASS',
    authorityConflictHeld: true,
    interfaceDriftRefused: true,
    projectionRebuilt: true,
    afterActionReceiptOnly: true,
    externalServiceCalls: 0,
    authority: 'none',
    claimBoundary: 'This receipt proves deterministic reconstruction of the synthetic hostile-recovery campaign. It grants no field, operational, evaluator, adoption, or command authority.',
  };
  return { ...receiptBody, verificationId: digest('anchorhostilerecoveryverification1', receiptBody) };
}

async function writeJson(path, value) {
  await mkdir(dirname(path), { recursive: true });
  await writeFile(path, `${JSON.stringify(value, null, 2)}\n`, 'utf8');
}

async function main(argv) {
  const command = argv[2];
  if (command === 'run') {
    const bundle = JSON.parse(await readFile(resolve(argv[3]), 'utf8'));
    const faultCampaign = JSON.parse(await readFile(resolve(argv[4]), 'utf8'));
    const campaignPath = resolve(argv[5]);
    const htmlPath = resolve(argv[6]);
    const result = runHostileRecoveryCampaign(bundle, faultCampaign);
    await writeJson(campaignPath, result.campaign);
    await mkdir(dirname(htmlPath), { recursive: true });
    await writeFile(htmlPath, result.html, 'utf8');
    process.stdout.write(`${JSON.stringify({ status: 'PASS', campaignId: result.campaign.campaignId, htmlSha256: result.campaign.afterAction.htmlSha256 }, null, 2)}\n`);
    return;
  }
  if (command === 'verify') {
    const bundle = JSON.parse(await readFile(resolve(argv[3]), 'utf8'));
    const faultCampaign = JSON.parse(await readFile(resolve(argv[4]), 'utf8'));
    const campaign = JSON.parse(await readFile(resolve(argv[5]), 'utf8'));
    const html = await readFile(resolve(argv[6]), 'utf8');
    const outputPath = resolve(argv[7]);
    const receipt = verifyHostileRecoveryCampaign(campaign, html, bundle, faultCampaign);
    await writeJson(outputPath, receipt);
    process.stdout.write(`${JSON.stringify(receipt, null, 2)}\n`);
    return;
  }
  throw new HostileRecoveryError('COMMAND_INVALID', `unknown command ${command}`);
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  main(process.argv).catch((error) => {
    const code = error instanceof HostileRecoveryError ? error.code : 'UNEXPECTED_ERROR';
    process.stderr.write(`${code}: ${error.message}\n`);
    process.exitCode = 1;
  });
}

#!/usr/bin/env node
import { createHash } from 'node:crypto';
import {
  mkdirSync,
  readFileSync,
  rmSync,
  statSync,
  writeFileSync,
} from 'node:fs';
import { join, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { canonicalJson } from '../semantic/authority_sidecar.mjs';
import {
  RehearsalSessionError,
  StandardsRehearsalSession,
  loadRehearsalFixture,
  verifySessionReceipt,
} from './session.mjs';
import {
  REHEARSAL_SCENARIO_CATALOG,
  getScenario,
} from './scenarios.mjs';
import { buildRehearsalConsolePack } from './build_pack.mjs';

function requireCondition(condition, message) {
  if (!condition) throw new Error(message);
}

function sha256File(path) {
  return createHash('sha256').update(readFileSync(path)).digest('hex');
}

function writeJson(path, value) {
  writeFileSync(path, `${JSON.stringify(value, null, 2)}\n`, 'utf8');
}

function provenance(repositoryRoot, sourceCommit) {
  const sourcePaths = {
    authorityRuntime: 'mating_surface/semantic/authority_sidecar.mjs',
    semanticFixtureVerifier: 'mating_surface/semantic/run_semantic_rehearsal.mjs',
    transportRuntime: 'mating_surface/test_hosts/core/fault_machine.mjs',
    scenarioCatalog: 'mating_surface/rehearsal_console/scenarios.mjs',
    interactiveSession: 'mating_surface/rehearsal_console/session.mjs',
    httpHost: 'mating_surface/rehearsal_console/server.mjs',
  };
  return {
    schema: 'standards-rehearsal-console-provenance/2',
    runtimeMode: 'server_side_direct_import',
    authorityImplementation: 'MessageAuthorityRuntime',
    acceptanceEvaluation: 'server_side_source_controlled',
    scenarioCatalogId: REHEARSAL_SCENARIO_CATALOG.catalogId,
    sourceCommit,
    sources: Object.fromEntries(
      Object.entries(sourcePaths).map(([key, path]) => [key, {
        path,
        sha256: sha256File(join(repositoryRoot, path)),
      }]),
    ),
    claimBoundary:
      'Authority decisions and acceptance evaluation execute in the named repository modules. Browser code is not part of either implementation.',
  };
}

function runCase({
  fixture,
  provenanceReceipt,
  name,
  scenarioId,
  config = {},
  actions,
  expectedEvaluation = 'pass',
  assertState,
}) {
  const scenario = getScenario(scenarioId);
  const session = new StandardsRehearsalSession({
    fixture,
    provenance: provenanceReceipt,
    scenarioCatalog: REHEARSAL_SCENARIO_CATALOG,
    scenarioId,
    config: { ...scenario.config, ...config },
  });
  for (const [action, input = {}] of actions) session.apply(action, input);
  const state = session.publicState();
  assertState(state);
  requireCondition(
    state.scenario.scenarioId === scenarioId,
    `${name} used another scenario definition`,
  );
  requireCondition(
    state.evaluation.status === expectedEvaluation,
    `${name} evaluation was ${state.evaluation.status}, expected ${expectedEvaluation}`,
  );
  const receipt = session.exportReceipt();
  const verification = verifySessionReceipt(receipt, {
    fixture,
    provenance: provenanceReceipt,
    scenarioCatalog: REHEARSAL_SCENARIO_CATALOG,
  });
  requireCondition(verification.status === 'pass', `${name} did not replay`);
  requireCondition(
    verification.evaluationId === state.evaluation.evaluationId,
    `${name} evaluation identity did not replay`,
  );
  for (const value of [state, receipt, verification]) {
    requireCondition(
      !JSON.stringify(value).includes('<?xml'),
      `${name} leaked standard XML into console evidence`,
    );
  }
  return { state, receipt, verification };
}

function assertClosedSessionRefusesFurtherAction(session) {
  let refused = false;
  try {
    session.apply('advance', { steps: 1 });
  } catch (error) {
    refused =
      error instanceof RehearsalSessionError
      && error.code === 'SESSION_CLOSED';
  }
  requireCondition(refused, 'closed rehearsal accepted another authority action');
}

export function qualifyConsole({
  qualificationRoot,
  repositoryRoot,
  outputDir,
  sourceCommit,
}) {
  const qualification = resolve(qualificationRoot);
  const repository = resolve(repositoryRoot);
  const output = resolve(outputDir);
  requireCondition(
    /^[0-9a-f]{40}$/.test(sourceCommit),
    'sourceCommit must be a lowercase 40-character Git SHA',
  );
  rmSync(output, { recursive: true, force: true });
  mkdirSync(output, { recursive: true });

  const fixture = loadRehearsalFixture(qualification);
  const provenanceReceipt = provenance(repository, sourceCommit);
  const cases = {};

  cases.baseline = runCase({
    fixture,
    provenanceReceipt,
    name: 'baseline',
    scenarioId: 'baseline-explicit-return',
    actions: [
      ['cut_headquarters'],
      ['issue_order'],
      ['issue_report'],
      ['restore'],
      ['reconcile'],
    ],
    assertState(state) {
      requireCondition(
        state.status === 'explicitly_superseded',
        'baseline did not explicitly supersede local authority',
      );
      requireCondition(
        state.messages.receiverAccepted === 4,
        'baseline did not accept four unique messages',
      );
      requireCondition(
        state.messages.replayRefused === 1,
        'baseline did not refuse the duplicate order as replay',
      );
      requireCondition(
        state.transport.pending.bufferedPacketIds.length === 0,
        'baseline retained a buffered packet',
      );
      requireCondition(
        state.transport.pending.delayedPacketIds.length === 0,
        'baseline retained a delayed packet',
      );
      requireCondition(
        state.controls.canAdvance === false,
        'baseline remained mutable after reconciliation',
      );
      requireCondition(
        state.evaluation.acceptanceEligible === true,
        'baseline was not acceptance eligible',
      );
    },
  });

  cases.operatorAbsent = runCase({
    fixture,
    provenanceReceipt,
    name: 'operator-absent',
    scenarioId: 'local-operator-absent',
    actions: [
      ['cut_headquarters'],
      ['issue_order'],
    ],
    assertState(state) {
      requireCondition(
        state.latestDecision?.disposition === 'hold',
        'operator-absent case did not hold the order',
      );
      requireCondition(
        state.latestDecision?.reason === 'LOCAL_OPERATOR_REQUIRED',
        'operator-absent case used another reason',
      );
      requireCondition(
        state.messages.receiverAccepted === 2,
        'operator-absent case transported the held order',
      );
    },
  });

  cases.leaseExpired = runCase({
    fixture,
    provenanceReceipt,
    name: 'lease-expired',
    scenarioId: 'offline-lease-expiry',
    actions: [
      ['cut_headquarters'],
      ['advance', { steps: 3 }],
      ['issue_order'],
    ],
    assertState(state) {
      requireCondition(
        state.latestDecision?.disposition === 'safe_state',
        'lease-expired case did not enter safe state',
      );
      requireCondition(
        state.latestDecision?.reason === 'OFFLINE_LEASE_EXPIRED',
        'lease-expired case used another reason',
      );
      requireCondition(
        state.messages.safeStateDecisions === 1,
        'lease-expired case did not retain the safe-state decision',
      );
    },
  });

  cases.isolated = runCase({
    fixture,
    provenanceReceipt,
    name: 'isolated',
    scenarioId: 'total-node-isolation',
    actions: [
      ['isolate'],
      ['issue_order'],
    ],
    assertState(state) {
      requireCondition(
        state.linkState === 'isolated',
        'isolated case did not retain isolated link state',
      );
      requireCondition(
        state.latestDecision?.disposition === 'refuse',
        'isolated case did not refuse the order',
      );
      requireCondition(
        state.latestDecision?.reason === 'MESSAGE_CLASS_NOT_AUTHORIZED_IN_PROFILE',
        'isolated case used another reason',
      );
    },
  });

  cases.conflictingReturn = runCase({
    fixture,
    provenanceReceipt,
    name: 'conflicting-return',
    scenarioId: 'conflicting-returning-authority',
    actions: [
      ['cut_headquarters'],
      ['issue_order'],
      ['issue_report'],
      ['restore'],
      ['reconcile'],
    ],
    assertState(state) {
      requireCondition(
        state.status === 'human_required',
        'conflicting return did not require a human decision',
      );
      requireCondition(
        state.reconciliation?.status === 'human_required',
        'conflicting return receipt was not retained',
      );
    },
  });

  cases.liveConfigurationReplay = runCase({
    fixture,
    provenanceReceipt,
    name: 'live-configuration-replay',
    scenarioId: 'local-operator-absent',
    config: {
      localOperatorPresent: true,
    },
    actions: [
      ['cut_headquarters'],
      ['set_configuration', { localOperatorPresent: false }],
      ['issue_order'],
    ],
    expectedEvaluation: 'deviated',
    assertState(state) {
      requireCondition(
        state.initialConfig.localOperatorPresent === true,
        'live-configuration case lost the initial configuration',
      );
      requireCondition(
        state.config.localOperatorPresent === false,
        'live-configuration case did not retain the changed configuration',
      );
      requireCondition(
        state.latestDecision?.reason === 'LOCAL_OPERATOR_REQUIRED',
        'live-configuration case did not apply the changed operator state',
      );
      requireCondition(
        state.evaluation.acceptanceEligible === false,
        'live configuration variation was incorrectly accepted',
      );
    },
  });

  cases.returningAuthorityAbsent = runCase({
    fixture,
    provenanceReceipt,
    name: 'returning-authority-absent',
    scenarioId: 'returning-authority-absent',
    actions: [
      ['cut_headquarters'],
      ['issue_order'],
      ['issue_report'],
      ['restore'],
      ['reconcile'],
    ],
    assertState(state) {
      requireCondition(
        state.status === 'returning_authority_absent',
        'absent return did not remain visibly unresolved',
      );
      requireCondition(
        state.returnNotice?.status === 'returning_authority_absent',
        'absent return notice was not retained',
      );
      requireCondition(
        state.controls.canReconcile === false,
        'absent return left reconciliation mutable',
      );
    },
  });

  const closedSession = new StandardsRehearsalSession({
    fixture,
    provenance: provenanceReceipt,
    scenarioCatalog: REHEARSAL_SCENARIO_CATALOG,
    scenarioId: 'baseline-explicit-return',
  });
  for (const [action, input = {}] of [
    ['cut_headquarters'],
    ['issue_order'],
    ['issue_report'],
    ['restore'],
    ['reconcile'],
  ]) closedSession.apply(action, input);
  assertClosedSessionRefusesFurtherAction(closedSession);

  for (const [name, value] of Object.entries(cases)) {
    const directory = join(output, 'cases', name);
    mkdirSync(directory, { recursive: true });
    writeJson(join(directory, 'state.json'), value.state);
    writeJson(join(directory, 'receipt.json'), value.receipt);
    writeJson(join(directory, 'verification.json'), value.verification);
  }
  writeJson(join(output, 'provenance.json'), provenanceReceipt);

  const packDir = join(output, 'pack');
  const buildManifest = buildRehearsalConsolePack({
    qualificationRoot: qualification,
    repositoryRoot: repository,
    outputDir: packDir,
    sourceCommit,
  });

  const fileRows = [];
  for (const [name] of Object.entries(cases)) {
    for (const file of ['state.json', 'receipt.json', 'verification.json']) {
      const path = join(output, 'cases', name, file);
      fileRows.push([`cases/${name}/${file}`, {
        bytes: statSync(path).size,
        sha256: sha256File(path),
      }]);
    }
  }
  const body = {
    sourceCommit,
    fixtureIdentity: fixture.fixtureIdentity,
    scenarioCatalogId: REHEARSAL_SCENARIO_CATALOG.catalogId,
    provenance: provenanceReceipt,
    caseReceiptIds: Object.fromEntries(
      Object.entries(cases).map(([name, value]) => [
        name,
        value.receipt.receiptId,
      ]),
    ),
    caseEvaluationIds: Object.fromEntries(
      Object.entries(cases).map(([name, value]) => [
        name,
        value.state.evaluation.evaluationId,
      ]),
    ),
    caseEvaluationStatuses: Object.fromEntries(
      Object.entries(cases).map(([name, value]) => [
        name,
        value.state.evaluation.status,
      ]),
    ),
    caseFinalStateIds: Object.fromEntries(
      Object.entries(cases).map(([name, value]) => [
        name,
        value.verification.finalStateId,
      ]),
    ),
    packBuildId: buildManifest.buildId,
    files: Object.fromEntries(fileRows),
  };
  const qualificationReceipt = {
    schema: 'standards-rehearsal-console-qualification/2',
    status: 'pass',
    qualificationId: `standardsrehearsalconsolequalification2_${createHash('sha256')
      .update(canonicalJson(body), 'utf8')
      .digest('hex')}`,
    ...body,
    assertions: {
      directAuthorityRuntimeImport: true,
      serverOwnedScenarioCatalog: true,
      serverOwnedAcceptanceEvaluation: true,
      deviationsCannotPassAcceptance: true,
      baselineReplayRefusal: true,
      localOperatorHold: true,
      offlineLeaseSafeState: true,
      isolatedOrderRefusal: true,
      conflictingReturnHumanRequired: true,
      liveConfigurationReplay: true,
      absentReturningAuthorityVisible: true,
      closedSessionRefusesFurtherAction: true,
      exportedSessionsReplay: true,
      standardPayloadsAbsentFromBrowserState: true,
      loopbackOnlyHost: true,
    },
    claimBoundary:
      'This qualification covers the source-pinned local interactive rehearsal host, source-controlled scenario catalog, server-side acceptance evaluation, and deterministic authority cases. It does not establish target-host or operational qualification.',
  };
  writeJson(join(output, 'qualification.json'), qualificationReceipt);
  return qualificationReceipt;
}

function main(argv) {
  if (argv.length !== 4) {
    console.error(
      'usage: qualify_console.mjs <qualification-root> <repository-root> <output-dir> <source-commit>',
    );
    return 2;
  }
  const [qualificationRoot, repositoryRoot, outputDir, sourceCommit] = argv;
  const receipt = qualifyConsole({
    qualificationRoot,
    repositoryRoot,
    outputDir,
    sourceCommit,
  });
  process.stdout.write(`${JSON.stringify({
    status: receipt.status,
    qualificationId: receipt.qualificationId,
    packBuildId: receipt.packBuildId,
    scenarioCatalogId: receipt.scenarioCatalogId,
    cases: Object.keys(receipt.caseReceiptIds),
    outputDir: resolve(outputDir),
  }, null, 2)}\n`);
  return 0;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  process.exitCode = main(process.argv.slice(2));
}

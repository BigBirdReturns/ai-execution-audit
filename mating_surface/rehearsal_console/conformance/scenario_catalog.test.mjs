import assert from 'node:assert/strict';
import test from 'node:test';
import { readFile } from 'node:fs/promises';
import {
  REHEARSAL_SCENARIO_CATALOG,
  evaluateScenario,
  getScenario,
  publicScenarioCatalog,
  validateScenarioCatalog,
} from '../scenarios.mjs';

function baselineState() {
  return {
    status: 'explicitly_superseded',
    messages: {
      receiverAccepted: 4,
      replayRefused: 1,
    },
    transport: {
      pending: {
        delayedPacketIds: [],
        bufferedPacketIds: [],
      },
    },
  };
}

function baselineActions() {
  return [
    { action: 'cut_headquarters', input: {} },
    { action: 'issue_order', input: {} },
    { action: 'issue_report', input: {} },
    { action: 'restore', input: {} },
    { action: 'reconcile', input: {} },
  ];
}

test('catalog is deterministic, bounded, and contains six qualified scenarios', () => {
  const first = validateScenarioCatalog(REHEARSAL_SCENARIO_CATALOG);
  const second = publicScenarioCatalog();
  assert.equal(first.catalogId, second.catalogId);
  assert.equal(first.scenarios.length, 6);
  assert.equal(new Set(first.scenarios.map((row) => row.scenarioId)).size, 6);
  assert.equal(new Set(first.scenarios.map((row) => row.scenarioDefinitionId)).size, 6);
  for (const scenario of first.scenarios) {
    assert.match(scenario.scenarioDefinitionId, /^standardrehearsalscenario1_[0-9a-f]{64}$/);
    assert.ok(scenario.procedure.length > 0);
    assert.ok(scenario.checks.length > 0);
  }
});

test('exact baseline procedure and configuration produce a server-owned pass', () => {
  const scenario = getScenario('baseline-explicit-return');
  const evaluation = evaluateScenario({
    scenario,
    state: baselineState(),
    userActions: baselineActions(),
    initialConfig: scenario.config,
    evaluatedStateCoreId: 'standardsinteractivestatecore1_' + '1'.repeat(64),
  });
  assert.equal(evaluation.status, 'pass');
  assert.equal(evaluation.acceptanceEligible, true);
  assert.equal(evaluation.procedure.complete, true);
  assert.deepEqual(evaluation.procedure.deviations, []);
  assert.deepEqual(evaluation.configurationDeviations, []);
  assert.equal(evaluation.checks.every((row) => row.status === 'pass'), true);
});

test('configuration drift remains evidence-bearing but cannot pass acceptance', () => {
  const scenario = getScenario('baseline-explicit-return');
  const evaluation = evaluateScenario({
    scenario,
    state: baselineState(),
    userActions: baselineActions(),
    initialConfig: { ...scenario.config, duplicateOrder: false },
    evaluatedStateCoreId: 'standardsinteractivestatecore1_' + '2'.repeat(64),
  });
  assert.equal(evaluation.status, 'deviated');
  assert.equal(evaluation.acceptanceEligible, false);
  assert.deepEqual(evaluation.configurationDeviations.map((row) => row.field), ['duplicateOrder']);
});

test('off-procedure action is a retained deviation rather than a silent pass', () => {
  const scenario = getScenario('baseline-explicit-return');
  const actions = baselineActions();
  actions.splice(1, 0, { action: 'advance', input: { steps: 1 } });
  const evaluation = evaluateScenario({
    scenario,
    state: baselineState(),
    userActions: actions,
    initialConfig: scenario.config,
    evaluatedStateCoreId: 'standardsinteractivestatecore1_' + '3'.repeat(64),
  });
  assert.equal(evaluation.status, 'deviated');
  assert.equal(evaluation.procedure.complete, true);
  assert.equal(evaluation.procedure.deviations.length, 1);
  assert.equal(evaluation.procedure.deviations[0].reason, 'ACTION_OUT_OF_PROCEDURE');
});

test('unfinished procedure stays incomplete even when current state happens to match checks', () => {
  const scenario = getScenario('baseline-explicit-return');
  const evaluation = evaluateScenario({
    scenario,
    state: baselineState(),
    userActions: baselineActions().slice(0, 2),
    initialConfig: scenario.config,
    evaluatedStateCoreId: 'standardsinteractivestatecore1_' + '4'.repeat(64),
  });
  assert.equal(evaluation.status, 'incomplete');
  assert.equal(evaluation.acceptanceEligible, false);
  assert.equal(evaluation.procedure.nextExpectedAction, 'issue_report');
});

test('catalog and scenario identity tampering fail closed', () => {
  const catalog = publicScenarioCatalog();
  catalog.scenarios[0].passCondition = 'Anything passes';
  assert.throws(
    () => validateScenarioCatalog(catalog),
    (error) => error.code === 'SCENARIO_IDENTITY_INVALID',
  );

  const catalogIdTamper = publicScenarioCatalog();
  catalogIdTamper.catalogId = 'standardrehearsalscenariocatalog1_' + '0'.repeat(64);
  assert.throws(
    () => validateScenarioCatalog(catalogIdTamper),
    (error) => error.code === 'SCENARIO_CATALOG_IDENTITY_INVALID',
  );
});

test('browser consumes scenarios and evaluations from the local API', async () => {
  const [app, session, server] = await Promise.all([
    readFile(new URL('../public/app.js', import.meta.url), 'utf8'),
    readFile(new URL('../session.mjs', import.meta.url), 'utf8'),
    readFile(new URL('../server.mjs', import.meta.url), 'utf8'),
  ]);
  assert.match(app, /requestJson\('\/api\/scenarios'/);
  assert.match(app, /state\.evaluation/);
  assert.equal(app.includes('const scenarios ='), false);
  assert.equal(app.includes('function evaluationRows'), false);
  assert.match(session, /evaluateScenario\(/);
  assert.match(session, /scenarioDefinitionId/);
  assert.match(server, /url\.pathname === '\/api\/scenarios'/);
});

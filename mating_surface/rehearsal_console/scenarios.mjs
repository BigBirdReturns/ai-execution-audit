import { createHash } from 'node:crypto';
import { canonicalJson } from '../semantic/authority_sidecar.mjs';

const SCENARIO_SCHEMA = 'standards-rehearsal-scenario/1';
const CATALOG_SCHEMA = 'standards-rehearsal-scenario-catalog/1';
const EVALUATION_SCHEMA = 'standards-rehearsal-scenario-evaluation/1';
const CATALOG_REVISION = '1.0.0';
const ALLOWED_CONFIG_KEYS = new Set([
  'offlineLeaseSteps',
  'localOperatorPresent',
  'duplicateOrder',
  'delayReport',
  'returnMode',
]);
const ALLOWED_ACTIONS = new Set([
  'cut_headquarters',
  'isolate',
  'issue_order',
  'issue_report',
  'advance',
  'restore',
  'reconcile',
]);
const ALLOWED_CHECKS = new Set(['equals', 'pending_transport_equals']);

export class ScenarioCatalogError extends Error {
  constructor(code, message) {
    super(message);
    this.name = 'ScenarioCatalogError';
    this.code = code;
  }
}

function requireCondition(condition, code, message) {
  if (!condition) throw new ScenarioCatalogError(code, message);
}

function isRecord(value) {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) return false;
  const prototype = Object.getPrototypeOf(value);
  return prototype === Object.prototype || prototype === null;
}

function digest(prefix, value) {
  return `${prefix}_${createHash('sha256').update(canonicalJson(value), 'utf8').digest('hex')}`;
}

function boundedString(value, code, label, maximum = 2_000) {
  requireCondition(typeof value === 'string', code, `${label} must be a string`);
  const normalized = value.trim();
  requireCondition(normalized.length > 0 && normalized.length <= maximum, code, `${label} is empty or unbounded`);
  return normalized;
}

function exactKeys(value, allowed, required, code, label) {
  requireCondition(isRecord(value), code, `${label} must be an object`);
  const unexpected = Object.keys(value).filter((key) => !allowed.has(key)).sort();
  requireCondition(unexpected.length === 0, code, `${label} contains unsupported field ${unexpected[0]}`);
  const missing = [...required].filter((key) => !Object.hasOwn(value, key));
  requireCondition(missing.length === 0, code, `${label} is missing field ${missing[0]}`);
}

function publicScenarioBody(scenario) {
  const {
    schema: _schema,
    scenarioDefinitionId: _scenarioDefinitionId,
    claimBoundary: _claimBoundary,
    ...body
  } = scenario;
  return body;
}

function scenarioDefinitionId(scenario) {
  return digest('standardrehearsalscenario1', publicScenarioBody(scenario));
}

function actionMatches(expected, observed) {
  if (expected.action !== observed.action) return false;
  const expectedInput = expected.input ?? {};
  const observedInput = observed.input ?? {};
  return Object.entries(expectedInput).every(([key, value]) => (
    canonicalJson(observedInput[key]) === canonicalJson(value)
  ));
}

function readPath(value, path) {
  let current = value;
  for (const segment of path.split('.')) {
    if (!segment || current === null || typeof current !== 'object') return undefined;
    current = current[segment];
  }
  return current;
}

function displayValue(value) {
  if (value === undefined) return 'Unavailable';
  if (value === null) return 'None';
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  if (typeof value === 'string') {
    return value
      .replaceAll('_', ' ')
      .replace(/\b\w/g, (character) => character.toUpperCase());
  }
  if (Array.isArray(value)) return String(value.length);
  return String(value);
}

function validateConfig(config, label) {
  exactKeys(
    config,
    ALLOWED_CONFIG_KEYS,
    ALLOWED_CONFIG_KEYS,
    'SCENARIO_CONFIG_INVALID',
    label,
  );
  requireCondition(
    Number.isSafeInteger(config.offlineLeaseSteps)
      && [0, 2, 5, 10].includes(config.offlineLeaseSteps),
    'SCENARIO_CONFIG_INVALID',
    `${label}.offlineLeaseSteps is invalid`,
  );
  for (const key of ['localOperatorPresent', 'duplicateOrder', 'delayReport']) {
    requireCondition(typeof config[key] === 'boolean', 'SCENARIO_CONFIG_INVALID', `${label}.${key} must be boolean`);
  }
  requireCondition(
    ['continuous', 'superseding', 'conflicting', 'absent'].includes(config.returnMode),
    'SCENARIO_CONFIG_INVALID',
    `${label}.returnMode is invalid`,
  );
}

function validateProcedure(procedure, scenarioId) {
  requireCondition(Array.isArray(procedure) && procedure.length > 0 && procedure.length <= 20, 'SCENARIO_PROCEDURE_INVALID', `${scenarioId} procedure is invalid`);
  for (const [index, step] of procedure.entries()) {
    exactKeys(
      step,
      new Set(['stepId', 'action', 'input', 'label', 'help']),
      new Set(['stepId', 'action', 'label', 'help']),
      'SCENARIO_PROCEDURE_INVALID',
      `${scenarioId} procedure step ${index}`,
    );
    boundedString(step.stepId, 'SCENARIO_PROCEDURE_INVALID', 'stepId', 120);
    requireCondition(ALLOWED_ACTIONS.has(step.action), 'SCENARIO_PROCEDURE_INVALID', `${scenarioId} uses unsupported action ${step.action}`);
    boundedString(step.label, 'SCENARIO_PROCEDURE_INVALID', 'step label');
    boundedString(step.help, 'SCENARIO_PROCEDURE_INVALID', 'step help');
    if (Object.hasOwn(step, 'input')) {
      requireCondition(isRecord(step.input), 'SCENARIO_PROCEDURE_INVALID', `${scenarioId} step input must be an object`);
    }
  }
}

function validateChecks(checks, scenarioId) {
  requireCondition(Array.isArray(checks) && checks.length > 0 && checks.length <= 20, 'SCENARIO_CHECK_INVALID', `${scenarioId} checks are invalid`);
  const ids = new Set();
  for (const [index, check] of checks.entries()) {
    exactKeys(
      check,
      new Set(['checkId', 'name', 'kind', 'path', 'expected', 'expectedText']),
      new Set(['checkId', 'name', 'kind', 'expected', 'expectedText']),
      'SCENARIO_CHECK_INVALID',
      `${scenarioId} check ${index}`,
    );
    boundedString(check.checkId, 'SCENARIO_CHECK_INVALID', 'checkId', 120);
    requireCondition(!ids.has(check.checkId), 'SCENARIO_CHECK_INVALID', `${scenarioId} repeats check ${check.checkId}`);
    ids.add(check.checkId);
    boundedString(check.name, 'SCENARIO_CHECK_INVALID', 'check name');
    boundedString(check.expectedText, 'SCENARIO_CHECK_INVALID', 'expectedText');
    requireCondition(ALLOWED_CHECKS.has(check.kind), 'SCENARIO_CHECK_INVALID', `${scenarioId} uses unsupported check kind ${check.kind}`);
    if (check.kind === 'equals') {
      boundedString(check.path, 'SCENARIO_CHECK_INVALID', 'check path', 300);
    } else {
      requireCondition(!Object.hasOwn(check, 'path'), 'SCENARIO_CHECK_INVALID', `${scenarioId} pending transport check may not set path`);
    }
  }
}

function defineScenario(input) {
  exactKeys(
    input,
    new Set([
      'scenarioId',
      'revision',
      'name',
      'shortName',
      'classification',
      'objective',
      'expectedOutcome',
      'passCondition',
      'config',
      'procedure',
      'checks',
    ]),
    new Set([
      'scenarioId',
      'revision',
      'name',
      'shortName',
      'classification',
      'objective',
      'expectedOutcome',
      'passCondition',
      'config',
      'procedure',
      'checks',
    ]),
    'SCENARIO_INVALID',
    'scenario',
  );
  const scenario = {
    schema: SCENARIO_SCHEMA,
    scenarioDefinitionId: '',
    scenarioId: boundedString(input.scenarioId, 'SCENARIO_ID_INVALID', 'scenarioId', 120),
    revision: boundedString(input.revision, 'SCENARIO_REVISION_INVALID', 'revision', 80),
    name: boundedString(input.name, 'SCENARIO_INVALID', 'name'),
    shortName: boundedString(input.shortName, 'SCENARIO_INVALID', 'shortName', 120),
    classification: boundedString(input.classification, 'SCENARIO_INVALID', 'classification', 120),
    objective: boundedString(input.objective, 'SCENARIO_INVALID', 'objective'),
    expectedOutcome: boundedString(input.expectedOutcome, 'SCENARIO_INVALID', 'expectedOutcome'),
    passCondition: boundedString(input.passCondition, 'SCENARIO_INVALID', 'passCondition'),
    config: structuredClone(input.config),
    procedure: structuredClone(input.procedure),
    checks: structuredClone(input.checks),
    claimBoundary:
      'This definition is a rehearsal acceptance plan. It does not grant authority or establish operational suitability.',
  };
  validateConfig(scenario.config, `${scenario.scenarioId}.config`);
  validateProcedure(scenario.procedure, scenario.scenarioId);
  validateChecks(scenario.checks, scenario.scenarioId);
  scenario.scenarioDefinitionId = scenarioDefinitionId(scenario);
  return Object.freeze(scenario);
}

const SCENARIOS = [
  defineScenario({
    scenarioId: 'baseline-explicit-return',
    revision: '1.0.0',
    name: 'Baseline partition and explicit return',
    shortName: 'Baseline return',
    classification: 'UNCLASSIFIED · REHEARSAL ONLY',
    objective: 'Prove that an order and report survive a bounded headquarters partition, a duplicate delivery is refused as replay, and returning authority explicitly supersedes the local generation.',
    expectedOutcome: 'Four unique messages accepted, one duplicate refused, final authority explicitly superseded.',
    passCondition: 'Replay refusal equals 1, accepted messages equal 4, no transport remains pending, and final status is explicitly superseded.',
    config: {
      offlineLeaseSteps: 5,
      localOperatorPresent: true,
      duplicateOrder: true,
      delayReport: true,
      returnMode: 'superseding',
    },
    procedure: [
      { stepId: 'cut-hq', action: 'cut_headquarters', label: 'Cut headquarters link', help: 'Begin one persistent partition epoch.' },
      { stepId: 'issue-order', action: 'issue_order', label: 'Issue order', help: 'Submit the schema-valid order under the delegated profile.' },
      { stepId: 'issue-report', action: 'issue_report', label: 'Issue report', help: 'Submit the report with one deterministic transport delay.' },
      { stepId: 'restore', action: 'restore', label: 'Restore communications', help: 'Close the partition without rewriting its history.' },
      { stepId: 'reconcile', action: 'reconcile', label: 'Classify returning authority', help: 'Apply explicit supersession and close the run.' },
    ],
    checks: [
      { checkId: 'accepted', name: 'Unique message acceptance', kind: 'equals', path: 'messages.receiverAccepted', expected: 4, expectedText: '4 accepted' },
      { checkId: 'replay', name: 'Replay handling', kind: 'equals', path: 'messages.replayRefused', expected: 1, expectedText: '1 replay refused' },
      { checkId: 'return', name: 'Returning authority', kind: 'equals', path: 'status', expected: 'explicitly_superseded', expectedText: 'Explicitly superseded' },
      { checkId: 'pending', name: 'Pending transport', kind: 'pending_transport_equals', expected: 0, expectedText: '0 messages' },
    ],
  }),
  defineScenario({
    scenarioId: 'local-operator-absent',
    revision: '1.0.0',
    name: 'Local operator absent',
    shortName: 'Operator absent',
    classification: 'UNCLASSIFIED · REHEARSAL ONLY',
    objective: 'Prove that a valid order is held when the delegated profile requires a local operator and none is present.',
    expectedOutcome: 'Order held with LOCAL_OPERATOR_REQUIRED; no order delivery enters transport.',
    passCondition: 'Latest authority decision is hold with reason LOCAL_OPERATOR_REQUIRED and only the two initialization messages are accepted.',
    config: {
      offlineLeaseSteps: 5,
      localOperatorPresent: false,
      duplicateOrder: false,
      delayReport: false,
      returnMode: 'superseding',
    },
    procedure: [
      { stepId: 'cut-hq', action: 'cut_headquarters', label: 'Cut headquarters link', help: 'Begin the delegated partition.' },
      { stepId: 'issue-order', action: 'issue_order', label: 'Issue order', help: 'Observe the missing-local-operator hold.' },
    ],
    checks: [
      { checkId: 'disposition', name: 'Order disposition', kind: 'equals', path: 'latestDecision.disposition', expected: 'hold', expectedText: 'Hold' },
      { checkId: 'reason', name: 'Decision reason', kind: 'equals', path: 'latestDecision.reason', expected: 'LOCAL_OPERATOR_REQUIRED', expectedText: 'LOCAL_OPERATOR_REQUIRED' },
      { checkId: 'accepted', name: 'Unique message acceptance', kind: 'equals', path: 'messages.receiverAccepted', expected: 2, expectedText: '2 initialization messages' },
    ],
  }),
  defineScenario({
    scenarioId: 'offline-lease-expiry',
    revision: '1.0.0',
    name: 'Offline authority lease expiry',
    shortName: 'Lease expiry',
    classification: 'UNCLASSIFIED · REHEARSAL ONLY',
    objective: 'Prove that advancing beyond the delegated lease produces safe state before the order is admitted.',
    expectedOutcome: 'Order receives safe_state with OFFLINE_LEASE_EXPIRED.',
    passCondition: 'One safe-state decision is retained and the order never enters transport.',
    config: {
      offlineLeaseSteps: 2,
      localOperatorPresent: true,
      duplicateOrder: false,
      delayReport: false,
      returnMode: 'superseding',
    },
    procedure: [
      { stepId: 'cut-hq', action: 'cut_headquarters', label: 'Cut headquarters link', help: 'Start the two-tick delegated lease.' },
      { stepId: 'advance', action: 'advance', input: { steps: 3 }, label: 'Advance 3 ticks', help: 'Move beyond the lease without renewing it.' },
      { stepId: 'issue-order', action: 'issue_order', label: 'Issue order', help: 'Observe the safe-state result.' },
    ],
    checks: [
      { checkId: 'disposition', name: 'Order disposition', kind: 'equals', path: 'latestDecision.disposition', expected: 'safe_state', expectedText: 'Safe state' },
      { checkId: 'reason', name: 'Decision reason', kind: 'equals', path: 'latestDecision.reason', expected: 'OFFLINE_LEASE_EXPIRED', expectedText: 'OFFLINE_LEASE_EXPIRED' },
      { checkId: 'safe-count', name: 'Safe-state decisions', kind: 'equals', path: 'messages.safeStateDecisions', expected: 1, expectedText: '1' },
    ],
  }),
  defineScenario({
    scenarioId: 'total-node-isolation',
    revision: '1.0.0',
    name: 'Total node isolation',
    shortName: 'Isolation refusal',
    classification: 'UNCLASSIFIED · REHEARSAL ONLY',
    objective: 'Prove that the order class does not survive the fully isolated authority profile.',
    expectedOutcome: 'Order refused with MESSAGE_CLASS_NOT_AUTHORIZED_IN_PROFILE.',
    passCondition: 'Link remains isolated and the latest decision is refuse for the expected reason.',
    config: {
      offlineLeaseSteps: 5,
      localOperatorPresent: true,
      duplicateOrder: false,
      delayReport: false,
      returnMode: 'superseding',
    },
    procedure: [
      { stepId: 'isolate', action: 'isolate', label: 'Isolate node', help: 'Enter the fully isolated communications condition.' },
      { stepId: 'issue-order', action: 'issue_order', label: 'Issue order', help: 'Observe profile refusal for the order class.' },
    ],
    checks: [
      { checkId: 'comms', name: 'Communications state', kind: 'equals', path: 'linkState', expected: 'isolated', expectedText: 'Isolated' },
      { checkId: 'disposition', name: 'Order disposition', kind: 'equals', path: 'latestDecision.disposition', expected: 'refuse', expectedText: 'Refuse' },
      { checkId: 'reason', name: 'Decision reason', kind: 'equals', path: 'latestDecision.reason', expected: 'MESSAGE_CLASS_NOT_AUTHORIZED_IN_PROFILE', expectedText: 'MESSAGE_CLASS_NOT_AUTHORIZED_IN_PROFILE' },
    ],
  }),
  defineScenario({
    scenarioId: 'conflicting-returning-authority',
    revision: '1.0.0',
    name: 'Conflicting returning authority',
    shortName: 'Conflict review',
    classification: 'UNCLASSIFIED · REHEARSAL ONLY',
    objective: 'Prove that a returning authority generation which does not supersede the partition generation is preserved for human disposition.',
    expectedOutcome: 'Final status human_required with both authority histories retained.',
    passCondition: 'Reconciliation and final status both equal human_required.',
    config: {
      offlineLeaseSteps: 5,
      localOperatorPresent: true,
      duplicateOrder: false,
      delayReport: false,
      returnMode: 'conflicting',
    },
    procedure: [
      { stepId: 'cut-hq', action: 'cut_headquarters', label: 'Cut headquarters link', help: 'Begin the partition.' },
      { stepId: 'issue-order', action: 'issue_order', label: 'Issue order', help: 'Create one local partition decision.' },
      { stepId: 'issue-report', action: 'issue_report', label: 'Issue report', help: 'Create a second local message receipt.' },
      { stepId: 'restore', action: 'restore', label: 'Restore communications', help: 'Close the partition.' },
      { stepId: 'reconcile', action: 'reconcile', label: 'Classify returning authority', help: 'Present a non-superseding generation.' },
    ],
    checks: [
      { checkId: 'status', name: 'Final authority state', kind: 'equals', path: 'status', expected: 'human_required', expectedText: 'Human required' },
      { checkId: 'reconciliation', name: 'Reconciliation result', kind: 'equals', path: 'reconciliation.status', expected: 'human_required', expectedText: 'Human required' },
    ],
  }),
  defineScenario({
    scenarioId: 'returning-authority-absent',
    revision: '1.0.0',
    name: 'Returning authority absent',
    shortName: 'No return',
    classification: 'UNCLASSIFIED · REHEARSAL ONLY',
    objective: 'Prove that the system does not invent a returning authority when communications are restored without one.',
    expectedOutcome: 'Final status returning_authority_absent and the run closes visibly unresolved.',
    passCondition: 'Return notice and final status both show returning_authority_absent; reconciliation is no longer mutable.',
    config: {
      offlineLeaseSteps: 5,
      localOperatorPresent: true,
      duplicateOrder: false,
      delayReport: false,
      returnMode: 'absent',
    },
    procedure: [
      { stepId: 'cut-hq', action: 'cut_headquarters', label: 'Cut headquarters link', help: 'Begin the partition.' },
      { stepId: 'issue-order', action: 'issue_order', label: 'Issue order', help: 'Create one local partition decision.' },
      { stepId: 'issue-report', action: 'issue_report', label: 'Issue report', help: 'Create a second local message receipt.' },
      { stepId: 'restore', action: 'restore', label: 'Restore communications', help: 'Close the partition.' },
      { stepId: 'reconcile', action: 'reconcile', label: 'Attempt authority classification', help: 'Record that no returning authority was supplied.' },
    ],
    checks: [
      { checkId: 'status', name: 'Final authority state', kind: 'equals', path: 'status', expected: 'returning_authority_absent', expectedText: 'Returning authority absent' },
      { checkId: 'notice', name: 'Return notice', kind: 'equals', path: 'returnNotice.status', expected: 'returning_authority_absent', expectedText: 'Returning authority absent' },
      { checkId: 'closed', name: 'Reconciliation mutable', kind: 'equals', path: 'controls.canReconcile', expected: false, expectedText: 'No' },
    ],
  }),
];

const SCENARIO_BY_ID = new Map(SCENARIOS.map((scenario) => [scenario.scenarioId, scenario]));
const catalogBody = {
  revision: CATALOG_REVISION,
  scenarios: SCENARIOS.map((scenario) => scenario.scenarioDefinitionId),
};

export const REHEARSAL_SCENARIO_CATALOG = Object.freeze({
  schema: CATALOG_SCHEMA,
  catalogId: digest('standardrehearsalscenariocatalog1', catalogBody),
  revision: CATALOG_REVISION,
  scenarios: Object.freeze(SCENARIOS),
  claimBoundary:
    'This catalog defines qualified rehearsal plans and machine-readable acceptance checks. It grants no authority and does not substitute for a program-approved test plan.',
});

export function publicScenarioCatalog(catalog = REHEARSAL_SCENARIO_CATALOG) {
  validateScenarioCatalog(catalog);
  return structuredClone(catalog);
}

export function getScenario(scenarioId, catalog = REHEARSAL_SCENARIO_CATALOG) {
  validateScenarioCatalog(catalog);
  const scenario = catalog === REHEARSAL_SCENARIO_CATALOG
    ? SCENARIO_BY_ID.get(scenarioId)
    : catalog.scenarios.find((row) => row.scenarioId === scenarioId);
  requireCondition(scenario, 'SCENARIO_UNKNOWN', `unknown rehearsal scenario ${scenarioId}`);
  return scenario;
}

export function validateScenarioCatalog(catalog) {
  exactKeys(
    catalog,
    new Set(['schema', 'catalogId', 'revision', 'scenarios', 'claimBoundary']),
    new Set(['schema', 'catalogId', 'revision', 'scenarios', 'claimBoundary']),
    'SCENARIO_CATALOG_INVALID',
    'scenario catalog',
  );
  requireCondition(catalog.schema === CATALOG_SCHEMA, 'SCENARIO_CATALOG_INVALID', 'scenario catalog schema is invalid');
  boundedString(catalog.revision, 'SCENARIO_CATALOG_INVALID', 'catalog revision', 80);
  boundedString(catalog.claimBoundary, 'SCENARIO_CATALOG_INVALID', 'catalog claim boundary');
  requireCondition(Array.isArray(catalog.scenarios) && catalog.scenarios.length > 0, 'SCENARIO_CATALOG_INVALID', 'scenario catalog is empty');
  const ids = new Set();
  for (const scenario of catalog.scenarios) {
    requireCondition(scenario.schema === SCENARIO_SCHEMA, 'SCENARIO_INVALID', 'scenario schema is invalid');
    requireCondition(!ids.has(scenario.scenarioId), 'SCENARIO_CATALOG_INVALID', `duplicate scenario ${scenario.scenarioId}`);
    ids.add(scenario.scenarioId);
    validateConfig(scenario.config, `${scenario.scenarioId}.config`);
    validateProcedure(scenario.procedure, scenario.scenarioId);
    validateChecks(scenario.checks, scenario.scenarioId);
    requireCondition(scenario.scenarioDefinitionId === scenarioDefinitionId(scenario), 'SCENARIO_IDENTITY_INVALID', `${scenario.scenarioId} definition identity is invalid`);
  }
  const expected = digest('standardrehearsalscenariocatalog1', {
    revision: catalog.revision,
    scenarios: catalog.scenarios.map((scenario) => scenario.scenarioDefinitionId),
  });
  requireCondition(catalog.catalogId === expected, 'SCENARIO_CATALOG_IDENTITY_INVALID', 'scenario catalog identity is invalid');
  return catalog;
}

function configurationDeviations(scenario, config) {
  const rows = [];
  for (const key of ALLOWED_CONFIG_KEYS) {
    if (canonicalJson(config[key]) !== canonicalJson(scenario.config[key])) {
      rows.push({
        field: key,
        expected: scenario.config[key],
        observed: config[key],
      });
    }
  }
  return rows;
}

function procedureEvaluation(scenario, userActions) {
  const steps = scenario.procedure.map((step) => ({
    stepId: step.stepId,
    action: step.action,
    input: step.input ?? {},
    label: step.label,
    help: step.help,
    status: 'pending',
    observedSequence: null,
  }));
  const deviations = [];
  let expectedIndex = 0;
  for (const [sequence, observed] of userActions.entries()) {
    const expected = steps[expectedIndex] ?? null;
    if (expected && actionMatches(expected, observed)) {
      expected.status = 'complete';
      expected.observedSequence = sequence;
      expectedIndex += 1;
      continue;
    }
    deviations.push({
      sequence,
      action: observed.action,
      input: structuredClone(observed.input ?? {}),
      expectedAction: expected?.action ?? null,
      expectedStepId: expected?.stepId ?? null,
      reason: expected ? 'ACTION_OUT_OF_PROCEDURE' : 'ACTION_AFTER_PROCEDURE',
    });
  }
  if (expectedIndex < steps.length) steps[expectedIndex].status = 'active';
  return {
    complete: expectedIndex === steps.length,
    nextExpectedStepId: steps[expectedIndex]?.stepId ?? null,
    nextExpectedAction: steps[expectedIndex]?.action ?? null,
    steps,
    deviations,
  };
}

function checkEvaluation(check, state) {
  let observed;
  if (check.kind === 'equals') {
    observed = readPath(state, check.path);
  } else {
    observed = (state.transport?.pending?.delayedPacketIds?.length ?? 0)
      + (state.transport?.pending?.bufferedPacketIds?.length ?? 0);
  }
  return {
    checkId: check.checkId,
    name: check.name,
    expected: structuredClone(check.expected),
    expectedText: check.expectedText,
    observedPresent: observed !== undefined,
    observed: observed === undefined ? null : structuredClone(observed),
    observedText: displayValue(observed),
    status:
      observed !== undefined
      && canonicalJson(observed) === canonicalJson(check.expected)
        ? 'pass'
        : 'fail',
  };
}

export function evaluateScenario({ scenario, state, userActions, initialConfig, evaluatedStateCoreId }) {
  requireCondition(scenario?.schema === SCENARIO_SCHEMA, 'SCENARIO_INVALID', 'scenario is invalid');
  requireCondition(isRecord(state), 'SCENARIO_EVALUATION_INVALID', 'state must be an object');
  requireCondition(Array.isArray(userActions), 'SCENARIO_EVALUATION_INVALID', 'userActions must be an array');
  requireCondition(isRecord(initialConfig), 'SCENARIO_EVALUATION_INVALID', 'initialConfig must be an object');
  boundedString(evaluatedStateCoreId, 'SCENARIO_EVALUATION_INVALID', 'evaluatedStateCoreId', 160);

  const procedure = procedureEvaluation(scenario, userActions);
  const configDeviations = configurationDeviations(scenario, initialConfig);
  const checks = scenario.checks.map((check) => checkEvaluation(check, state));
  const allPass = checks.every((check) => check.status === 'pass');
  const hasDeviations = configDeviations.length > 0 || procedure.deviations.length > 0;
  const status = !procedure.complete
    ? 'incomplete'
    : hasDeviations
      ? 'deviated'
      : allPass
        ? 'pass'
        : 'fail';
  const body = {
    scenarioDefinitionId: scenario.scenarioDefinitionId,
    evaluatedStateCoreId,
    status,
    procedure,
    configurationDeviations: configDeviations,
    checks,
  };
  return {
    schema: EVALUATION_SCHEMA,
    evaluationId: digest('standardrehearsalevaluation1', body),
    ...body,
    acceptanceEligible: status === 'pass',
    claimBoundary:
      'This evaluation compares one recorded session with one source-controlled rehearsal plan. Detached session replay remains required, and the result grants no operational authority.',
  };
}

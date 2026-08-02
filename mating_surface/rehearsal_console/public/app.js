const elements = {
  tabs: [...document.querySelectorAll('[role="tab"]')],
  views: [...document.querySelectorAll('[role="tabpanel"]')],
  runChip: document.querySelector('#runChip'),
  commsChip: document.querySelector('#commsChip'),
  authorityChip: document.querySelector('#authorityChip'),
  runState: document.querySelector('#runState'),
  commsState: document.querySelector('#commsState'),
  authorityState: document.querySelector('#authorityState'),
  scenarioSelect: document.querySelector('#scenarioSelect'),
  scenarioName: document.querySelector('#scenarioName'),
  scenarioObjective: document.querySelector('#scenarioObjective'),
  scenarioExpected: document.querySelector('#scenarioExpected'),
  scenarioPass: document.querySelector('#scenarioPass'),
  scenarioProcedure: document.querySelector('#scenarioProcedure'),
  planControls: document.querySelector('#planControls'),
  leaseSelect: document.querySelector('#leaseSelect'),
  operatorToggle: document.querySelector('#operatorToggle'),
  duplicateToggle: document.querySelector('#duplicateToggle'),
  delayToggle: document.querySelector('#delayToggle'),
  returnSelect: document.querySelector('#returnSelect'),
  startButton: document.querySelector('#startButton'),
  planStatus: document.querySelector('#planStatus'),
  tickValue: document.querySelector('#tickValue'),
  activeScenarioName: document.querySelector('#activeScenarioName'),
  currentInstruction: document.querySelector('#currentInstruction'),
  nextActionLabel: document.querySelector('#nextActionLabel'),
  nextActionHelp: document.querySelector('#nextActionHelp'),
  procedureList: document.querySelector('#procedureList'),
  returnToPlanButton: document.querySelector('#returnToPlanButton'),
  runPlane: document.querySelector('#runPlane'),
  linkPlane: document.querySelector('#linkPlane'),
  authorityPlane: document.querySelector('#authorityPlane'),
  runPlaneValue: document.querySelector('#runPlaneValue'),
  runPlaneDetail: document.querySelector('#runPlaneDetail'),
  linkValue: document.querySelector('#linkValue'),
  linkDetail: document.querySelector('#linkDetail'),
  authorityPlaneValue: document.querySelector('#authorityPlaneValue'),
  authorityPlaneDetail: document.querySelector('#authorityPlaneDetail'),
  decisionCard: document.querySelector('#decisionCard'),
  decisionIcon: document.querySelector('#decisionIcon'),
  decisionDisposition: document.querySelector('#decisionDisposition'),
  decisionReason: document.querySelector('#decisionReason'),
  decisionId: document.querySelector('#decisionId'),
  schemaCount: document.querySelector('#schemaCount'),
  allowedCount: document.querySelector('#allowedCount'),
  heldCount: document.querySelector('#heldCount'),
  refusedCount: document.querySelector('#refusedCount'),
  safeCount: document.querySelector('#safeCount'),
  acceptedValue: document.querySelector('#acceptedValue'),
  replayValue: document.querySelector('#replayValue'),
  pendingCount: document.querySelector('#pendingCount'),
  actionFeedback: document.querySelector('#actionFeedback'),
  feedbackSymbol: document.querySelector('#feedbackSymbol'),
  feedbackTitle: document.querySelector('#feedbackTitle'),
  feedbackMessage: document.querySelector('#feedbackMessage'),
  feedbackRecovery: document.querySelector('#feedbackRecovery'),
  runResetButton: document.querySelector('#runResetButton'),
  outcomeBanner: document.querySelector('#outcomeBanner'),
  outcomeSymbol: document.querySelector('#outcomeSymbol'),
  outcomeLabel: document.querySelector('#outcomeLabel'),
  outcomeExplanation: document.querySelector('#outcomeExplanation'),
  acceptanceRows: document.querySelector('#acceptanceRows'),
  verifyButton: document.querySelector('#verifyButton'),
  verificationResult: document.querySelector('#verificationResult'),
  reviewScenario: document.querySelector('#reviewScenario'),
  reviewExpected: document.querySelector('#reviewExpected'),
  reviewObserved: document.querySelector('#reviewObserved'),
  reviewComms: document.querySelector('#reviewComms'),
  partitionEpoch: document.querySelector('#partitionEpoch'),
  stateId: document.querySelector('#stateId'),
  authorityImplementation: document.querySelector('#authorityImplementation'),
  authorityHash: document.querySelector('#authorityHash'),
  conversationId: document.querySelector('#conversationId'),
  standardRevision: document.querySelector('#standardRevision'),
  artifactId: document.querySelector('#artifactId'),
  exportButton: document.querySelector('#exportButton'),
  exportResult: document.querySelector('#exportResult'),
  eventLog: document.querySelector('#eventLog'),
  receiptJson: document.querySelector('#receiptJson'),
  confirmDialog: document.querySelector('#confirmDialog'),
  confirmTitle: document.querySelector('#confirmTitle'),
  confirmMessage: document.querySelector('#confirmMessage'),
  confirmActionButton: document.querySelector('#confirmActionButton'),
};

const scenarios = {
  baseline: {
    name: 'Baseline partition and explicit return',
    shortName: 'Baseline return',
    objective: 'Prove that an order and report survive a bounded headquarters partition, a duplicate delivery is refused as replay, and returning authority explicitly supersedes the local generation.',
    expected: 'Four unique messages accepted, one duplicate refused, final authority explicitly superseded.',
    pass: 'Replay refusal equals 1, accepted messages equal 4, and final status is explicitly superseded.',
    config: {
      offlineLeaseSteps: 5,
      localOperatorPresent: true,
      duplicateOrder: true,
      delayReport: true,
      returnMode: 'superseding',
    },
    procedure: [
      ['cut_headquarters', 'Cut headquarters link', 'Begin one persistent partition epoch.'],
      ['issue_order', 'Issue order', 'Submit the schema-valid order under the delegated profile.'],
      ['issue_report', 'Issue report', 'Submit the report with one deterministic transport delay.'],
      ['restore', 'Restore communications', 'Close the partition without rewriting its history.'],
      ['reconcile', 'Classify returning authority', 'Apply explicit supersession and close the run.'],
    ],
    checks: [
      ['Unique message acceptance', '4 accepted', (state) => [state.messages.receiverAccepted, 4]],
      ['Replay handling', '1 replay refused', (state) => [state.messages.replayRefused, 1]],
      ['Returning authority', 'Explicitly superseded', (state) => [state.status, 'explicitly_superseded']],
      ['Pending transport', '0 messages', (state) => [pendingCount(state), 0]],
    ],
  },
  operatorAbsent: {
    name: 'Local operator absent',
    shortName: 'Operator absent',
    objective: 'Prove that a valid order is held when the delegated profile requires a local operator and none is present.',
    expected: 'Order held with LOCAL_OPERATOR_REQUIRED; no order delivery enters transport.',
    pass: 'Latest authority decision is hold with reason LOCAL_OPERATOR_REQUIRED.',
    config: {
      offlineLeaseSteps: 5,
      localOperatorPresent: false,
      duplicateOrder: false,
      delayReport: false,
      returnMode: 'superseding',
    },
    procedure: [
      ['cut_headquarters', 'Cut headquarters link', 'Begin the delegated partition.'],
      ['issue_order', 'Issue order', 'Observe the missing-local-operator hold.'],
    ],
    checks: [
      ['Order disposition', 'Hold', (state) => [state.latestDecision?.disposition, 'hold']],
      ['Decision reason', 'LOCAL_OPERATOR_REQUIRED', (state) => [state.latestDecision?.reason, 'LOCAL_OPERATOR_REQUIRED']],
      ['Unique message acceptance', '2 initialization messages', (state) => [state.messages.receiverAccepted, 2]],
    ],
  },
  leaseExpired: {
    name: 'Offline authority lease expiry',
    shortName: 'Lease expiry',
    objective: 'Prove that advancing beyond the delegated lease produces safe state before the order is admitted.',
    expected: 'Order receives safe_state with OFFLINE_LEASE_EXPIRED.',
    pass: 'One safe-state decision is retained and the order never enters transport.',
    config: {
      offlineLeaseSteps: 2,
      localOperatorPresent: true,
      duplicateOrder: false,
      delayReport: false,
      returnMode: 'superseding',
    },
    procedure: [
      ['cut_headquarters', 'Cut headquarters link', 'Start the two-tick delegated lease.'],
      ['advance', 'Advance 3 ticks', 'Move beyond the lease without renewing it.'],
      ['issue_order', 'Issue order', 'Observe the safe-state result.'],
    ],
    checks: [
      ['Order disposition', 'Safe state', (state) => [state.latestDecision?.disposition, 'safe_state']],
      ['Decision reason', 'OFFLINE_LEASE_EXPIRED', (state) => [state.latestDecision?.reason, 'OFFLINE_LEASE_EXPIRED']],
      ['Safe-state decisions', '1', (state) => [state.messages.safeStateDecisions, 1]],
    ],
  },
  isolated: {
    name: 'Total node isolation',
    shortName: 'Isolation refusal',
    objective: 'Prove that the order class does not survive the fully isolated authority profile.',
    expected: 'Order refused with MESSAGE_CLASS_NOT_AUTHORIZED_IN_PROFILE.',
    pass: 'Link remains isolated and the latest decision is refuse.',
    config: {
      offlineLeaseSteps: 5,
      localOperatorPresent: true,
      duplicateOrder: false,
      delayReport: false,
      returnMode: 'superseding',
    },
    procedure: [
      ['isolate', 'Isolate node', 'Enter the fully isolated communications condition.'],
      ['issue_order', 'Issue order', 'Observe profile refusal for the order class.'],
    ],
    checks: [
      ['Communications state', 'Isolated', (state) => [state.linkState, 'isolated']],
      ['Order disposition', 'Refuse', (state) => [state.latestDecision?.disposition, 'refuse']],
      ['Decision reason', 'MESSAGE_CLASS_NOT_AUTHORIZED_IN_PROFILE', (state) => [state.latestDecision?.reason, 'MESSAGE_CLASS_NOT_AUTHORIZED_IN_PROFILE']],
    ],
  },
  conflictingReturn: {
    name: 'Conflicting returning authority',
    shortName: 'Conflict review',
    objective: 'Prove that conflicting returning authority preserves both histories and requires a human disposition.',
    expected: 'Final status human_required; no mechanical winner is selected.',
    pass: 'Reconciliation status equals human_required.',
    config: {
      offlineLeaseSteps: 5,
      localOperatorPresent: true,
      duplicateOrder: false,
      delayReport: false,
      returnMode: 'conflicting',
    },
    procedure: [
      ['cut_headquarters', 'Cut headquarters link', 'Begin the partition.'],
      ['issue_order', 'Issue order', 'Admit the order under delegated authority.'],
      ['issue_report', 'Issue report', 'Admit the report under the same partition.'],
      ['restore', 'Restore communications', 'Close the partition.'],
      ['reconcile', 'Classify returning authority', 'Present conflicting authority and require human review.'],
    ],
    checks: [
      ['Returning authority', 'Human required', (state) => [state.status, 'human_required']],
      ['Reconciliation receipt', 'human_required', (state) => [state.reconciliation?.status, 'human_required']],
      ['Unique message acceptance', '4 accepted', (state) => [state.messages.receiverAccepted, 4]],
    ],
  },
  noReturn: {
    name: 'Returning authority absent',
    shortName: 'No authority return',
    objective: 'Prove that the system exposes an unresolved return instead of silently inventing or selecting authority.',
    expected: 'Final status returning_authority_absent and the session closes until reset.',
    pass: 'The return notice is retained and no reconciliation receipt is invented.',
    config: {
      offlineLeaseSteps: 5,
      localOperatorPresent: true,
      duplicateOrder: false,
      delayReport: false,
      returnMode: 'absent',
    },
    procedure: [
      ['cut_headquarters', 'Cut headquarters link', 'Begin the partition.'],
      ['issue_order', 'Issue order', 'Admit the order under delegated authority.'],
      ['issue_report', 'Issue report', 'Admit the report under the same partition.'],
      ['restore', 'Restore communications', 'Close the partition.'],
      ['reconcile', 'Classify returning authority', 'Record that no returning authority was supplied.'],
    ],
    checks: [
      ['Returning authority', 'Absent and unresolved', (state) => [state.status, 'returning_authority_absent']],
      ['Return notice', 'retained', (state) => [Boolean(state.returnNotice), true]],
      ['Reconciliation receipt', 'not created', (state) => [state.reconciliation, null]],
    ],
  },
};

const labels = {
  connected: 'Connected',
  headquarters_denied: 'Headquarters denied',
  isolated: 'Node isolated',
  lease_expired: 'Lease expired',
  safe_state: 'Safe state',
  explicitly_superseded: 'Explicitly superseded',
  continuous_authority: 'Continuous authority',
  human_required: 'Human decision required',
  returning_authority_absent: 'Returning authority absent',
  allow: 'Allow',
  hold: 'Hold',
  refuse: 'Refuse',
  accept: 'Accept',
};

const reasonLabels = {
  INITIALIZATION_ACCEPTED: 'The schema-valid initialization messages were admitted while connected.',
  HEADQUARTERS_LINK_DENIED: 'The headquarters link is unavailable. One partition epoch now governs the delegated lease.',
  NODE_ISOLATED: 'The node is fully isolated. Only message classes retained by the isolated profile may proceed.',
  COMMUNICATIONS_RESTORED: 'Communications returned. Buffered and due transport receipts were evaluated.',
  MESSAGE_CLASS_ADMITTED: 'The exact message class is admitted by the current authority profile.',
  MESSAGE_CLASS_NOT_AUTHORIZED_IN_PROFILE: 'The message class is outside the authority profile that survives this communications state.',
  LOCAL_OPERATOR_REQUIRED: 'This message requires a local operator under the current profile.',
  OFFLINE_LEASE_EXPIRED: 'The bounded offline authority lease expired before this message was evaluated.',
  MESSAGE_ACCEPTED: 'The receiver accepted the first valid delivery under its admission ticket.',
  MESSAGE_REPLAY: 'A second delivery of the same message identity was refused as replay.',
  ADMISSION_TICKET_EXPIRED: 'The message arrived after its admission ticket expired.',
  RETURNING_AUTHORITY_CLASSIFIED: 'Returning authority was classified without rewriting the partition history.',
  RETURNING_AUTHORITY_ABSENT: 'No returning authority was supplied. The partition remains unresolved until reset or a new authority object is provided.',
  AUTHORITY_CLOCK_ADVANCED: 'The rehearsal clock advanced. The authority lease was not renewed or reset.',
  LIVE_CONFIGURATION_UPDATED: 'The rehearsal configuration was updated before the relevant message entered transport.',
};

const recoveryByCode = {
  CONFIG_LOCKED: 'Reset the rehearsal, change the plan, and start a new run.',
  LEASE_CHANGE_REQUIRES_RESET: 'Return to Plan, choose the new lease, then start a clean run.',
  LINK_TRANSITION_INVALID: 'Use an enabled communications action shown in the Run workspace.',
  RECONCILIATION_REQUIRED: 'Restore communications if needed, then classify the returning authority.',
  RECONCILIATION_LINK_INVALID: 'Restore communications before classifying the returning authority.',
  RECONCILIATION_EPOCH_MISSING: 'Create and close a partition before attempting reconciliation.',
  SESSION_CLOSED: 'Reset the rehearsal to start another scenario.',
  MESSAGE_ALREADY_SENT: 'The message already entered transport; reset to rerun it.',
  REQUEST_FAILED: 'Check the local host and reload the station.',
  HOST_FAILURE: 'Confirm that the loopback server is still running, then reload.',
};

let currentState = null;
let activeScenarioId = 'baseline';
let activeView = 'plan';
let pendingConfirmation = null;
let lastVerification = null;

function isRecord(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function titleCase(value) {
  return String(value ?? '—')
    .replaceAll('_', ' ')
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function shortId(value, length = 24) {
  if (!value) return '—';
  if (value.length <= length) return value;
  return `${value.slice(0, 11)}…${value.slice(-9)}`;
}

function pendingCount(state) {
  return (state.transport?.pending?.delayedPacketIds?.length ?? 0)
    + (state.transport?.pending?.bufferedPacketIds?.length ?? 0);
}

function scenario() {
  return scenarios[activeScenarioId];
}

async function requestJson(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers ?? {}),
    },
  });
  const value = await response.json();
  if (!response.ok) {
    const error = new Error(value.message ?? `Request failed with status ${response.status}`);
    error.code = value.error ?? 'REQUEST_FAILED';
    throw error;
  }
  return value;
}

function selectedConfig() {
  return {
    offlineLeaseSteps: Number.parseInt(elements.leaseSelect.value, 10),
    localOperatorPresent: elements.operatorToggle.checked,
    duplicateOrder: elements.duplicateToggle.checked,
    delayReport: elements.delayToggle.checked,
    returnMode: elements.returnSelect.value,
  };
}

function setSelectedConfig(config) {
  elements.leaseSelect.value = String(config.offlineLeaseSteps);
  elements.operatorToggle.checked = config.localOperatorPresent;
  elements.duplicateToggle.checked = config.duplicateOrder;
  elements.delayToggle.checked = config.delayReport;
  elements.returnSelect.value = config.returnMode;
}

function configsEqual(left, right) {
  return JSON.stringify(left) === JSON.stringify(right);
}

function identifyScenarioFromConfig(config) {
  return Object.entries(scenarios).find(([, value]) => configsEqual(value.config, config))?.[0] ?? null;
}

function latestOutcome(state) {
  if (state.reconciliation) {
    return {
      disposition: state.reconciliation.status,
      reason: 'RETURNING_AUTHORITY_CLASSIFIED',
      id: state.reconciliation.reconciliationId,
    };
  }
  if (state.returnNotice) {
    return {
      disposition: state.returnNotice.status,
      reason: 'RETURNING_AUTHORITY_ABSENT',
      id: state.returnNotice.partitionEpochId,
    };
  }
  if (state.latestReceiver?.disposition === 'refuse') {
    return {
      disposition: state.latestReceiver.disposition,
      reason: state.latestReceiver.reason,
      id: state.latestReceiver.receiverReceiptId,
    };
  }
  if (state.latestDecision) {
    return {
      disposition: state.latestDecision.disposition,
      reason: state.latestDecision.reason,
      id: state.latestDecision.decisionId,
    };
  }
  return {
    disposition: 'initialized',
    reason: 'INITIALIZATION_ACCEPTED',
    id: state.stateId,
  };
}

function runLifecycle(state) {
  if (state.reconciliation || state.returnNotice) {
    return { value: 'Complete', detail: 'Returning authority classified; reset required', tone: state.status === 'human_required' || state.status === 'returning_authority_absent' ? 'attention' : 'resolved' };
  }
  if (state.controls?.canReconcile) {
    return { value: 'Awaiting review', detail: 'Partition closed; classify returning authority', tone: 'attention' };
  }
  const userEvents = normalizedUserEvents(state);
  if (userEvents.length === 0) {
    return { value: 'Ready', detail: 'Qualified initialization loaded', tone: 'normal' };
  }
  return { value: 'Running', detail: `${userEvents.length} test-conductor action${userEvents.length === 1 ? '' : 's'} recorded`, tone: state.status === 'safe_state' ? 'danger' : 'normal' };
}

function commsPosture(state) {
  if (state.linkState === 'headquarters_denied') return { value: 'HQ denied', detail: 'Delegated authority lease active', tone: 'attention' };
  if (state.linkState === 'isolated') return { value: 'Isolated', detail: 'Restricted isolated profile', tone: 'danger' };
  if (state.controls?.canReconcile) return { value: 'Restored', detail: 'Partition history awaits classification', tone: 'attention' };
  return { value: 'Connected', detail: 'Full communications profile', tone: state.reconciliation ? 'resolved' : 'normal' };
}

function authorityPosture(state) {
  const outcome = latestOutcome(state);
  const disposition = outcome.disposition;
  if (disposition === 'safe_state') return { value: 'Safe state', detail: reasonLabels[outcome.reason], tone: 'danger', icon: '!' };
  if (disposition === 'refuse') return { value: 'Refuse', detail: reasonLabels[outcome.reason], tone: 'danger', icon: '×' };
  if (disposition === 'hold') return { value: 'Hold', detail: reasonLabels[outcome.reason], tone: 'attention', icon: '∥' };
  if (['human_required', 'returning_authority_absent'].includes(disposition)) return { value: labels[disposition], detail: reasonLabels[outcome.reason], tone: 'attention', icon: '?' };
  if (['explicitly_superseded', 'continuous_authority'].includes(disposition)) return { value: labels[disposition], detail: reasonLabels[outcome.reason], tone: 'resolved', icon: '✓' };
  if (disposition === 'allow') return { value: 'Allow', detail: reasonLabels[outcome.reason], tone: 'normal', icon: '✓' };
  return { value: titleCase(disposition), detail: reasonLabels[outcome.reason] ?? titleCase(outcome.reason), tone: 'normal', icon: 'i' };
}

function normalizedUserEvents(state) {
  return state.events
    .filter((event) => !['automatic_message', 'receiver_delivery', 'reset'].includes(event.action))
    .map((event) => {
      if (event.action === 'issue_message') return `issue_${event.messageClass}`;
      return event.action;
    });
}

function procedureProgress(state) {
  const observed = [...normalizedUserEvents(state)];
  return scenario().procedure.map(([action, label, help], index) => {
    const found = observed.indexOf(action);
    if (found >= 0) observed.splice(found, 1);
    const complete = found >= 0;
    const priorComplete = scenario().procedure.slice(0, index).every(([prior]) => normalizedUserEvents(state).includes(prior));
    return {
      action,
      label,
      help,
      status: complete ? 'complete' : priorComplete ? 'active' : 'pending',
    };
  });
}

function nextProcedureStep(state) {
  return procedureProgress(state).find((row) => row.status === 'active') ?? null;
}

function toneForState(state) {
  return authorityPosture(state).tone;
}

function switchView(view, { focus = true } = {}) {
  activeView = view;
  for (const tab of elements.tabs) {
    const selected = tab.dataset.view === view;
    tab.setAttribute('aria-selected', String(selected));
    tab.tabIndex = selected ? 0 : -1;
  }
  for (const panel of elements.views) {
    panel.hidden = panel.id !== `view-${view}`;
  }
  if (focus) {
    const heading = document.querySelector(`#view-${view} h2`);
    heading?.setAttribute('tabindex', '-1');
    heading?.focus({ preventScroll: true });
    heading?.scrollIntoView({ block: 'start' });
  }
}

function renderScenarioPlan() {
  const selected = scenario();
  elements.scenarioSelect.value = activeScenarioId;
  elements.scenarioName.textContent = selected.name;
  elements.scenarioObjective.textContent = selected.objective;
  elements.scenarioExpected.textContent = selected.expected;
  elements.scenarioPass.textContent = selected.pass;
  elements.scenarioProcedure.replaceChildren(...selected.procedure.map(([, label, help]) => {
    const item = document.createElement('li');
    const strong = document.createElement('strong');
    strong.textContent = label;
    const detail = document.createElement('span');
    detail.textContent = ` — ${help}`;
    item.append(strong, detail);
    return item;
  }));
  elements.activeScenarioName.textContent = selected.shortName;
  elements.reviewScenario.textContent = selected.name;
  elements.reviewExpected.textContent = selected.expected;
}

function renderTrack(state, tone) {
  const active = state.reconciliation || state.returnNotice ? 'reconciled' : state.linkState;
  document.querySelectorAll('[data-track]').forEach((node) => {
    const isActive = node.dataset.track === active;
    node.dataset.active = String(isActive);
    node.dataset.tone = isActive ? tone : 'normal';
  });
}

function renderProcedure(state) {
  const progress = procedureProgress(state);
  elements.procedureList.replaceChildren(...progress.map((row) => {
    const item = document.createElement('li');
    item.dataset.status = row.status;
    const container = document.createElement('div');
    const strong = document.createElement('strong');
    strong.textContent = row.label;
    const small = document.createElement('small');
    small.textContent = row.help;
    container.append(strong, small);
    item.append(container);
    return item;
  }));
  const next = progress.find((row) => row.status === 'active');
  if (next) {
    elements.nextActionLabel.textContent = next.label;
    elements.nextActionHelp.textContent = next.help;
  } else if (state.reconciliation || state.returnNotice) {
    elements.nextActionLabel.textContent = 'Run complete';
    elements.nextActionHelp.textContent = 'Evaluate the result, verify the receipt, and export evidence before reset.';
  } else {
    elements.nextActionLabel.textContent = 'Review observed result';
    elements.nextActionHelp.textContent = 'The planned actions are complete; open Evaluate to compare expected and observed behavior.';
  }
}

function renderEvents(events) {
  if (!events.length) {
    const empty = document.createElement('div');
    empty.className = 'event-row';
    empty.innerHTML = '<span>—</span><strong>No events</strong><span>—</span><code>—</code>';
    elements.eventLog.replaceChildren(empty);
    return;
  }
  elements.eventLog.replaceChildren(...events.slice().reverse().map((event) => {
    const row = document.createElement('div');
    row.className = 'event-row';
    const tick = document.createElement('span');
    tick.textContent = `T${event.step}`;
    const action = document.createElement('strong');
    action.textContent = event.action === 'issue_message'
      ? `Issue ${event.messageClass}`
      : titleCase(event.action);
    const disposition = document.createElement('span');
    disposition.textContent = titleCase(event.disposition ?? 'recorded');
    const reason = document.createElement('code');
    reason.textContent = event.reason ?? event.decisionId ?? event.receiverReceiptId ?? '—';
    reason.title = reason.textContent;
    row.append(tick, action, disposition, reason);
    return row;
  }));
}

function renderControls(state) {
  const controls = state.controls ?? {};
  const mapping = {
    cut_headquarters: controls.canCutHeadquarters,
    isolate: controls.canIsolate,
    issue_order: controls.canIssueOrder,
    issue_report: controls.canIssueReport,
    advance: controls.canAdvance,
    restore: controls.canRestore,
    reconcile: controls.canReconcile,
  };
  document.querySelectorAll('[data-action]').forEach((button) => {
    button.disabled = mapping[button.dataset.action] === false;
    button.dataset.recommended = String(button.dataset.action === nextProcedureStep(state)?.action);
  });
  const runStarted = normalizedUserEvents(state).length > 0;
  elements.startButton.textContent = runStarted ? 'Restart with this plan' : 'Start clean rehearsal';
  elements.planStatus.textContent = runStarted
    ? 'Starting this plan will discard the current local run after confirmation.'
    : 'Starting the plan resets the server session and records the selected conditions as the initial configuration.';
}

function renderHeader(state) {
  const run = runLifecycle(state);
  const comms = commsPosture(state);
  const authority = authorityPosture(state);
  elements.runChip.dataset.tone = run.tone;
  elements.commsChip.dataset.tone = comms.tone;
  elements.authorityChip.dataset.tone = authority.tone;
  elements.runState.textContent = run.value;
  elements.commsState.textContent = comms.value;
  elements.authorityState.textContent = authority.value;
}

function renderPosture(state) {
  const run = runLifecycle(state);
  const comms = commsPosture(state);
  const authority = authorityPosture(state);
  elements.tickValue.textContent = state.currentStep;
  elements.runPlane.dataset.tone = run.tone;
  elements.linkPlane.dataset.tone = comms.tone;
  elements.authorityPlane.dataset.tone = authority.tone;
  elements.runPlaneValue.textContent = run.value;
  elements.runPlaneDetail.textContent = run.detail;
  elements.linkValue.textContent = comms.value;
  elements.linkDetail.textContent = comms.detail;
  elements.authorityPlaneValue.textContent = authority.value;
  elements.authorityPlaneDetail.textContent = authority.detail;
  elements.decisionCard.dataset.tone = authority.tone;
  elements.decisionIcon.textContent = authority.icon;
  elements.decisionDisposition.textContent = authority.value;
  elements.decisionReason.textContent = authority.detail;
  elements.decisionId.textContent = latestOutcome(state).id ?? '—';
  elements.decisionId.title = latestOutcome(state).id ?? '';

  elements.schemaCount.textContent = state.messages.schemaValid;
  elements.allowedCount.textContent = state.messages.authorityAllowed;
  elements.heldCount.textContent = state.messages.authorityHeld;
  elements.refusedCount.textContent = state.messages.authorityRefused;
  elements.safeCount.textContent = state.messages.safeStateDecisions;
  elements.acceptedValue.textContent = state.messages.receiverAccepted;
  elements.replayValue.textContent = state.messages.replayRefused;
  elements.pendingCount.textContent = pendingCount(state);
  renderTrack(state, authority.tone);
}

function compareValue(observed, expected) {
  if (expected === null) return observed === null;
  return observed === expected;
}

function evaluationRows(state) {
  return scenario().checks.map(([name, expectedText, observe]) => {
    const [observed, expected] = observe(state);
    const complete = normalizedUserEvents(state).length >= scenario().procedure.length;
    const passed = complete && compareValue(observed, expected);
    return {
      name,
      expectedText,
      observedText: observed === null || observed === undefined ? 'Not present' : titleCase(observed),
      status: passed ? 'pass' : complete ? 'fail' : 'pending',
    };
  });
}

function renderEvaluation(state) {
  const rows = evaluationRows(state);
  elements.acceptanceRows.replaceChildren(...rows.map((row) => {
    const tr = document.createElement('tr');
    for (const value of [row.name, row.expectedText, row.observedText]) {
      const td = document.createElement('td');
      td.textContent = value;
      tr.append(td);
    }
    const status = document.createElement('td');
    const mark = document.createElement('span');
    mark.className = 'result-mark';
    mark.dataset.tone = row.status === 'pass' ? 'resolved' : row.status === 'fail' ? 'danger' : 'attention';
    mark.textContent = row.status === 'pass' ? '✓ Pass' : row.status === 'fail' ? '× Fail' : '… Pending';
    status.append(mark);
    tr.append(status);
    return tr;
  }));

  const allComplete = rows.every((row) => row.status !== 'pending');
  const allPass = rows.every((row) => row.status === 'pass');
  elements.outcomeBanner.dataset.tone = !allComplete ? 'attention' : allPass ? 'resolved' : 'danger';
  elements.outcomeSymbol.textContent = !allComplete ? '…' : allPass ? '✓' : '×';
  elements.outcomeLabel.textContent = !allComplete ? 'Run incomplete' : allPass ? 'Expected outcome observed' : 'Observed result diverges';
  elements.outcomeExplanation.textContent = !allComplete
    ? 'Complete the selected procedure before accepting or rejecting the run.'
    : allPass
      ? 'The visible acceptance checks match the selected scenario card. Run detached verification before export.'
      : 'One or more visible checks differ from the scenario card. Inspect the event history and exact receipt.';

  elements.reviewObserved.textContent = authorityPosture(state).value;
  elements.reviewComms.textContent = commsPosture(state).value;
  elements.partitionEpoch.textContent = state.posture.partitionEpochId ?? 'None';
  elements.partitionEpoch.title = state.posture.partitionEpochId ?? '';
  elements.stateId.textContent = shortId(state.stateId, 32);
  elements.stateId.title = state.stateId;

  if (lastVerification) {
    elements.verificationResult.dataset.tone = lastVerification.status === 'pass' ? 'resolved' : 'danger';
    elements.verificationResult.innerHTML = '';
    const strong = document.createElement('strong');
    strong.textContent = lastVerification.status === 'pass' ? '✓ Detached replay passed' : '× Verification refused';
    const detail = document.createElement('p');
    detail.textContent = lastVerification.status === 'pass'
      ? `Receipt ${shortId(lastVerification.receiptId)} rebuilt to the same final state.`
      : `${lastVerification.error ?? 'VERIFY_FAILED'}: ${lastVerification.message ?? 'Session could not be reconstructed.'}`;
    elements.verificationResult.append(strong, detail);
  }
}

function renderEvidence(state) {
  const authoritySource = state.provenance?.sources?.authorityRuntime;
  elements.authorityImplementation.textContent = state.provenance?.authorityImplementation ?? 'MessageAuthorityRuntime';
  elements.authorityHash.textContent = authoritySource ? `sha256:${authoritySource.sha256}` : 'Unavailable';
  elements.authorityHash.title = authoritySource?.path ?? '';
  elements.conversationId.textContent = state.fixture.semanticConversationId;
  elements.conversationId.title = state.fixture.semanticConversationId;
  elements.standardRevision.textContent = state.fixture.standardRevision;
  elements.artifactId.textContent = state.fixture.artifactAdmissionId;
  elements.artifactId.title = state.fixture.artifactAdmissionId;
  elements.receiptJson.textContent = JSON.stringify(state, null, 2);
  renderEvents(state.events);
}

function render(state) {
  currentState = state;
  const matchingScenario = identifyScenarioFromConfig(state.initialConfig ?? state.config);
  if (matchingScenario && normalizedUserEvents(state).length > 0) activeScenarioId = matchingScenario;
  renderScenarioPlan();
  renderHeader(state);
  renderProcedure(state);
  renderControls(state);
  renderPosture(state);
  renderEvaluation(state);
  renderEvidence(state);
}

function feedback({ title, message, recovery = 'The server-owned control state remains authoritative.', tone = 'normal', symbol = 'i', focus = true }) {
  elements.actionFeedback.dataset.tone = tone;
  elements.feedbackSymbol.textContent = symbol;
  elements.feedbackTitle.textContent = title;
  elements.feedbackMessage.textContent = message;
  elements.feedbackRecovery.textContent = recovery;
  if (focus) elements.actionFeedback.focus({ preventScroll: true });
}

function actionSuccess(action, state) {
  const event = state.events.at(-1);
  const authority = authorityPosture(state);
  feedback({
    title: `${titleCase(action)} recorded`,
    message: event?.reason ? (reasonLabels[event.reason] ?? titleCase(event.reason)) : `The server returned state ${state.status}.`,
    recovery: nextProcedureStep(state)
      ? `Next expected action: ${nextProcedureStep(state).label}.`
      : 'Open Evaluate to compare the observed result with the scenario card.',
    tone: authority.tone,
    symbol: authority.icon,
  });
}

function actionFailure(error) {
  feedback({
    title: `${error.code ?? 'REFUSED'} · Action not applied`,
    message: error.message,
    recovery: recoveryByCode[error.code] ?? 'Review the enabled actions and the current state before retrying.',
    tone: 'danger',
    symbol: '×',
  });
}

async function runAction(action, input = {}) {
  try {
    const state = await requestJson('/api/action', {
      method: 'POST',
      body: JSON.stringify({ action, input }),
    });
    render(state);
    actionSuccess(action, state);
    if (state.reconciliation || state.returnNotice) switchView('evaluate', { focus: false });
    return state;
  } catch (error) {
    actionFailure(error);
    throw error;
  }
}

function confirmationCopy(kind) {
  if (kind === 'isolate') {
    return {
      title: 'Isolate the node?',
      message: 'This deepens the communications condition to total isolation. The selected scenario expects the order class to be refused under the isolated profile.',
      label: 'Isolate node',
    };
  }
  if (kind === 'reconcile') {
    return {
      title: 'Classify returning authority?',
      message: 'This records the returning-authority disposition and closes the current rehearsal session. Further actions require reset.',
      label: 'Classify authority',
    };
  }
  return {
    title: 'Reset the rehearsal?',
    message: 'This discards the current local run state and starts again from the selected plan. Export evidence first when the current run must be retained.',
    label: 'Reset rehearsal',
  };
}

function confirmThen(kind, operation) {
  const copy = confirmationCopy(kind);
  pendingConfirmation = operation;
  elements.confirmTitle.textContent = copy.title;
  elements.confirmMessage.textContent = copy.message;
  elements.confirmActionButton.textContent = copy.label;
  elements.confirmDialog.showModal();
}

function initializeScenarioOptions() {
  for (const [id, value] of Object.entries(scenarios)) {
    const option = document.createElement('option');
    option.value = id;
    option.textContent = value.name;
    elements.scenarioSelect.append(option);
  }
  setSelectedConfig(scenarios[activeScenarioId].config);
  renderScenarioPlan();
}

for (const tab of elements.tabs) {
  tab.addEventListener('click', () => switchView(tab.dataset.view));
  tab.addEventListener('keydown', (event) => {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
    event.preventDefault();
    const index = elements.tabs.indexOf(tab);
    const target = event.key === 'Home'
      ? 0
      : event.key === 'End'
        ? elements.tabs.length - 1
        : (index + (event.key === 'ArrowRight' ? 1 : -1) + elements.tabs.length) % elements.tabs.length;
    elements.tabs[target].focus();
    switchView(elements.tabs[target].dataset.view, { focus: false });
  });
}

elements.scenarioSelect.addEventListener('change', () => {
  activeScenarioId = elements.scenarioSelect.value;
  setSelectedConfig(scenario().config);
  renderScenarioPlan();
});

elements.startButton.addEventListener('click', () => {
  const start = async () => {
    activeScenarioId = elements.scenarioSelect.value;
    const state = await runAction('reset', selectedConfig());
    lastVerification = null;
    render(state);
    switchView('run');
    feedback({
      title: `${scenario().shortName} started`,
      message: 'The qualified initialization messages are loaded and the selected initial conditions are recorded.',
      recovery: `Next expected action: ${nextProcedureStep(state)?.label ?? 'Review the runbook'}.`,
      tone: 'normal',
      symbol: 'i',
    });
  };
  if (currentState && normalizedUserEvents(currentState).length > 0) confirmThen('reset', start);
  else start();
});

elements.returnToPlanButton.addEventListener('click', () => switchView('plan'));

elements.runResetButton.addEventListener('click', () => confirmThen('reset', async () => {
  const state = await runAction('reset', selectedConfig());
  lastVerification = null;
  render(state);
  switchView('plan');
}));

document.querySelectorAll('[data-action]').forEach((button) => {
  button.addEventListener('click', () => {
    const input = button.dataset.steps
      ? { steps: Number.parseInt(button.dataset.steps, 10) }
      : {};
    const operation = () => runAction(button.dataset.action, input);
    if (button.dataset.confirm) confirmThen(button.dataset.confirm, operation);
    else operation();
  });
});

elements.confirmDialog.addEventListener('close', () => {
  if (elements.confirmDialog.returnValue === 'confirm' && pendingConfirmation) {
    const operation = pendingConfirmation;
    pendingConfirmation = null;
    operation();
  } else {
    pendingConfirmation = null;
  }
});

elements.verifyButton.addEventListener('click', async () => {
  try {
    lastVerification = await requestJson('/api/verify');
    renderEvaluation(currentState);
    elements.verificationResult.focus?.();
  } catch (error) {
    lastVerification = {
      status: 'refuse',
      error: error.code,
      message: error.message,
    };
    renderEvaluation(currentState);
  }
});

elements.exportButton.addEventListener('click', async () => {
  try {
    const receipt = await requestJson('/api/export');
    const blob = new Blob([`${JSON.stringify(receipt, null, 2)}\n`], { type: 'application/json' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `standards-rehearsal-${receipt.receiptId.slice(-12)}.json`;
    link.click();
    URL.revokeObjectURL(link.href);
    elements.exportResult.innerHTML = '';
    const strong = document.createElement('strong');
    strong.textContent = '✓ Session receipt exported';
    const detail = document.createElement('p');
    detail.textContent = `Receipt ${shortId(receipt.receiptId)} contains the initial configuration, test-conductor action ledger, and final identities.`;
    elements.exportResult.append(strong, detail);
  } catch (error) {
    elements.exportResult.innerHTML = '';
    const strong = document.createElement('strong');
    strong.textContent = `× ${error.code ?? 'EXPORT_FAILED'}`;
    const detail = document.createElement('p');
    detail.textContent = `${error.message} ${recoveryByCode[error.code] ?? ''}`.trim();
    elements.exportResult.append(strong, detail);
  }
});

initializeScenarioOptions();
requestJson('/api/state')
  .then((state) => {
    currentState = state;
    const match = identifyScenarioFromConfig(state.initialConfig ?? state.config);
    if (match) activeScenarioId = match;
    setSelectedConfig(scenario().config);
    render(state);
    if (state.reconciliation || state.returnNotice) switchView('evaluate', { focus: false });
  })
  .catch((error) => {
    actionFailure({ code: 'HOST_FAILURE', message: error.message });
    switchView('run', { focus: false });
  });

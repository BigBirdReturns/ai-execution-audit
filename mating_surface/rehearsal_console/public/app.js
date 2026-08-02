const elements = {
  statusDot: document.querySelector('#statusDot'),
  statusText: document.querySelector('#statusText'),
  stepValue: document.querySelector('#stepValue'),
  linkValue: document.querySelector('#linkValue'),
  leaseValue: document.querySelector('#leaseValue'),
  acceptedValue: document.querySelector('#acceptedValue'),
  replayValue: document.querySelector('#replayValue'),
  decisionCard: document.querySelector('#decisionCard'),
  decisionDisposition: document.querySelector('#decisionDisposition'),
  decisionReason: document.querySelector('#decisionReason'),
  decisionId: document.querySelector('#decisionId'),
  schemaCount: document.querySelector('#schemaCount'),
  allowedCount: document.querySelector('#allowedCount'),
  heldCount: document.querySelector('#heldCount'),
  refusedCount: document.querySelector('#refusedCount'),
  safeCount: document.querySelector('#safeCount'),
  pendingCount: document.querySelector('#pendingCount'),
  eventLog: document.querySelector('#eventLog'),
  receiptJson: document.querySelector('#receiptJson'),
  authorityImplementation: document.querySelector('#authorityImplementation'),
  authorityHash: document.querySelector('#authorityHash'),
  conversationId: document.querySelector('#conversationId'),
  standardRevision: document.querySelector('#standardRevision'),
  artifactId: document.querySelector('#artifactId'),
  leaseSelect: document.querySelector('#leaseSelect'),
  operatorToggle: document.querySelector('#operatorToggle'),
  duplicateToggle: document.querySelector('#duplicateToggle'),
  delayToggle: document.querySelector('#delayToggle'),
  returnSelect: document.querySelector('#returnSelect'),
  resetButton: document.querySelector('#resetButton'),
  verifyButton: document.querySelector('#verifyButton'),
  exportButton: document.querySelector('#exportButton'),
  toast: document.querySelector('#toast'),
};

const labels = {
  connected: 'Connected',
  headquarters_denied: 'Delegated under partition',
  isolated: 'Node isolated',
  lease_expired: 'Delegated lease expired',
  safe_state: 'Safe state',
  explicitly_superseded: 'Reconciled: explicitly superseded',
  continuous_authority: 'Reconciled: continuous authority',
  human_required: 'Human decision required',
  returning_authority_absent: 'Returning authority absent',
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
  RETURNING_AUTHORITY_ABSENT: 'No returning authority was supplied. The partition remains unresolved until a human resets or supplies authority.',
  AUTHORITY_CLOCK_ADVANCED: 'The rehearsal clock advanced. The authority lease was not renewed or reset.',
  LIVE_CONFIGURATION_UPDATED: 'The local rehearsal controls were updated. Authority rules remain server-owned.',
};

let toastTimer = null;

function shortId(value, length = 22) {
  if (!value) return '—';
  if (value.length <= length) return value;
  return `${value.slice(0, 10)}…${value.slice(-8)}`;
}

function titleCase(value) {
  return String(value ?? '—')
    .replaceAll('_', ' ')
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function toneForState(state) {
  const status = state.status;
  if (['safe_state', 'lease_expired'].includes(status)) return 'danger';
  if (
    ['headquarters_denied', 'isolated', 'human_required', 'returning_authority_absent']
      .includes(status)
  ) return 'attention';
  if (['explicitly_superseded', 'continuous_authority'].includes(status)) return 'resolved';
  if (state.latestDecision?.disposition === 'refuse') return 'danger';
  if (state.latestDecision?.disposition === 'hold') return 'attention';
  return 'normal';
}

function showToast(message, tone = 'normal') {
  window.clearTimeout(toastTimer);
  elements.toast.textContent = message;
  elements.toast.dataset.visible = 'true';
  elements.toast.dataset.tone = tone;
  toastTimer = window.setTimeout(() => {
    elements.toast.dataset.visible = 'false';
  }, 3200);
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

function renderTrack(state, tone) {
  const active = state.reconciliation || state.returnNotice
    ? 'reconciled'
    : state.linkState;
  document.querySelectorAll('[data-track]').forEach((node) => {
    const isActive = node.dataset.track === active;
    node.dataset.active = String(isActive);
    node.dataset.tone = isActive ? tone : 'normal';
  });
}

function renderEvents(events) {
  if (!events.length) {
    elements.eventLog.innerHTML = '<div class="event-row"><span>—</span><strong>No events</strong><span>—</span><code>—</code></div>';
    return;
  }
  elements.eventLog.replaceChildren(...events.slice().reverse().map((event) => {
    const row = document.createElement('div');
    row.className = 'event-row';
    const step = document.createElement('span');
    step.textContent = `S${event.step}`;
    const action = document.createElement('strong');
    action.textContent = titleCase(event.action);
    const disposition = document.createElement('span');
    disposition.textContent = titleCase(event.disposition ?? 'recorded');
    const reason = document.createElement('code');
    reason.textContent = event.reason ?? event.decisionId ?? event.receiverReceiptId ?? '—';
    row.append(step, action, disposition, reason);
    return row;
  }));
}

function applyControlState(state) {
  const controls = state.controls ?? {};
  document.querySelectorAll('[data-action]').forEach((button) => {
    const action = button.dataset.action;
    const mapping = {
      cut_headquarters: controls.canCutHeadquarters,
      isolate: controls.canIsolate,
      issue_order: controls.canIssueOrder,
      issue_report: controls.canIssueReport,
      advance: controls.canAdvance,
      restore: controls.canRestore,
      reconcile: controls.canReconcile,
    };
    button.disabled = mapping[action] === false;
  });
  elements.operatorToggle.disabled = controls.canChangeLocalOperator === false;
  elements.duplicateToggle.disabled = controls.canChangeDuplicateOrder === false;
  elements.delayToggle.disabled = controls.canChangeDelayReport === false;
  elements.returnSelect.disabled = controls.canChangeReturnMode === false;
  elements.resetButton.disabled = controls.resetAvailable === false;
}

function render(state) {
  const tone = toneForState(state);
  const outcome = latestOutcome(state);
  elements.statusDot.dataset.tone = tone;
  elements.statusText.textContent = labels[state.status] ?? titleCase(state.status);
  elements.stepValue.textContent = state.currentStep;
  elements.linkValue.textContent = titleCase(state.linkState);
  elements.leaseValue.textContent = state.posture.remainingSteps === null
    ? '—'
    : `${state.posture.remainingSteps} step${state.posture.remainingSteps === 1 ? '' : 's'}`;
  elements.acceptedValue.textContent = state.messages.receiverAccepted;
  elements.replayValue.textContent = state.messages.replayRefused;
  elements.schemaCount.textContent = state.messages.schemaValid;
  elements.allowedCount.textContent = state.messages.authorityAllowed;
  elements.heldCount.textContent = state.messages.authorityHeld;
  elements.refusedCount.textContent = state.messages.authorityRefused;
  elements.safeCount.textContent = state.messages.safeStateDecisions;
  const pending = (state.transport?.pending?.delayedPacketIds?.length ?? 0)
    + (state.transport?.pending?.bufferedPacketIds?.length ?? 0);
  elements.pendingCount.textContent = pending;

  elements.decisionCard.dataset.tone = tone;
  elements.decisionDisposition.textContent = titleCase(outcome.disposition);
  elements.decisionReason.textContent = reasonLabels[outcome.reason] ?? titleCase(outcome.reason);
  elements.decisionId.textContent = outcome.id ?? '—';
  elements.decisionId.title = outcome.id ?? '';

  renderTrack(state, tone);
  renderEvents(state.events);
  applyControlState(state);

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

  elements.operatorToggle.checked = state.config.localOperatorPresent;
  elements.duplicateToggle.checked = state.config.duplicateOrder;
  elements.delayToggle.checked = state.config.delayReport;
  elements.returnSelect.value = state.config.returnMode;
  elements.leaseSelect.value = String(state.config.offlineLeaseSteps);
}

async function runAction(action, input = {}) {
  try {
    const state = await requestJson('/api/action', {
      method: 'POST',
      body: JSON.stringify({ action, input }),
    });
    render(state);
  } catch (error) {
    showToast(`${error.code ?? 'REFUSED'}: ${error.message}`, 'danger');
  }
}

document.querySelectorAll('[data-action]').forEach((button) => {
  button.addEventListener('click', () => {
    const input = button.dataset.steps
      ? { steps: Number.parseInt(button.dataset.steps, 10) }
      : {};
    runAction(button.dataset.action, input);
  });
});

elements.resetButton.addEventListener('click', () => runAction('reset', selectedConfig()));

for (const [element, key] of [
  [elements.operatorToggle, 'localOperatorPresent'],
  [elements.duplicateToggle, 'duplicateOrder'],
  [elements.delayToggle, 'delayReport'],
  [elements.returnSelect, 'returnMode'],
]) {
  element.addEventListener('change', () => runAction('set_configuration', {
    [key]: key === 'returnMode' ? element.value : element.checked,
  }));
}

elements.leaseSelect.addEventListener('change', () => {
  showToast('Reset the rehearsal to apply a different offline lease.');
});

elements.verifyButton.addEventListener('click', async () => {
  try {
    const receipt = await requestJson('/api/verify');
    showToast(`Session replay verified · ${shortId(receipt.receiptId)}`);
  } catch (error) {
    showToast(`${error.code ?? 'REFUSED'}: ${error.message}`, 'danger');
  }
});

elements.exportButton.addEventListener('click', async () => {
  try {
    const receipt = await requestJson('/api/export');
    const blob = new Blob([`${JSON.stringify(receipt, null, 2)}\n`], {
      type: 'application/json',
    });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `standards-rehearsal-${receipt.receiptId.slice(-12)}.json`;
    link.click();
    URL.revokeObjectURL(link.href);
    showToast('Interactive session receipt exported.');
  } catch (error) {
    showToast(`${error.code ?? 'REFUSED'}: ${error.message}`, 'danger');
  }
});

requestJson('/api/state')
  .then(render)
  .catch((error) => showToast(`HOST_FAILURE: ${error.message}`, 'danger'));

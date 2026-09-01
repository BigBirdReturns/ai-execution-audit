"use strict";

const OPERATOR = globalThis.AXMOperatorContract;
const PLAN = globalThis.AXMOperationPlanContract;
const PORT_NAME = "axm-browser-physical-audition-operator-console-v1";
const FILE_LIMIT = 262144;
const PLAN_MARK_EVENT_TYPES = new Set([
  "availability-observation",
  "adapter-artifact",
  "formation-declaration",
  "formation-member",
  "model-manifest",
  "model-artifact",
  "performance-start",
  "token-mark",
  "member-drop",
  "output-equivalence",
  "privacy-declaration",
  "observation-receipt-ref",
  "rtc-stats",
]);
const MUTATING_METHODS = new Set(OPERATOR.METHODS.filter((method) => method !== "exportCapture"));

const state = {
  port: null,
  sessionId: null,
  tabId: null,
  pending: new Map(),
  plan: null,
  bindings: null,
  nextIndex: 0,
  resultRefs: new Map(),
  barrierCode: null,
  barrierAcknowledged: false,
  running: false,
  probeMutationPossible: false,
  terminal: "IDLE",
};

const el = Object.freeze({
  bindingsFile: document.querySelector("#bindings-file"),
  planFile: document.querySelector("#plan-file"),
  load: document.querySelector("#load-bundle"),
  bundleState: document.querySelector("#bundle-state"),
  planId: document.querySelector("#plan-id"),
  bindingsId: document.querySelector("#bindings-id"),
  stepCount: document.querySelector("#step-count"),
  open: document.querySelector("#open-session"),
  status: document.querySelector("#status-session"),
  close: document.querySelector("#close-session"),
  sessionState: document.querySelector("#session-state"),
  probeState: document.querySelector("#probe-state"),
  probeEarly: document.querySelector("#probe-early"),
  probeEvents: document.querySelector("#probe-events"),
  barrier: document.querySelector("#barrier-statement"),
  acknowledge: document.querySelector("#acknowledge-barrier"),
  run: document.querySelector("#run-plan"),
  executionState: document.querySelector("#execution-state"),
  nextStep: document.querySelector("#next-step"),
  completed: document.querySelector("#completed-steps"),
  saved: document.querySelector("#saved-results"),
  log: document.querySelector("#event-log"),
});

function randomRequestId() {
  const words = new Uint32Array(4);
  crypto.getRandomValues(words);
  return `request:${Array.from(words, (value) => value.toString(16).padStart(8, "0")).join("")}`;
}
function log(status, message) {
  const row = document.createElement("li");
  row.className = status.toLowerCase();
  row.textContent = `${new Date().toLocaleTimeString()} ${status}: ${message}`;
  el.log.prepend(row);
  while (el.log.children.length > 100) el.log.lastElementChild.remove();
}
function updateInspection(inspection) {
  if (!inspection) return;
  el.probeState.textContent = inspection.status === "PASS" ? `version ${inspection.probeVersion}` : inspection.code || "refused";
  el.probeEarly.textContent = inspection.installedBeforeApplication === true ? "yes" : "no";
  el.probeEvents.textContent = String(inspection.observedEventCount ?? 0);
}
function requireHealthyInspection(inspection) {
  updateInspection(inspection);
  if (!inspection || inspection.status !== "PASS") {
    throw Object.assign(new Error(inspection?.code || "probe inspection refused"), {
      code: inspection?.code || "PROBE_INSPECTION_REFUSED",
    });
  }
  if (!Object.prototype.hasOwnProperty.call(inspection, "probeRefused")) {
    throw Object.assign(new Error("probe refusal state is absent"), {
      code: "PROBE_REFUSAL_STATE_ABSENT",
    });
  }
  if (inspection.probeRefused !== null) {
    throw Object.assign(new Error("probe reported a capture refusal"), {
      code: "PROBE_CAPTURE_REFUSED",
    });
  }
  return inspection;
}
function refreshControls() {
  const loaded = Boolean(state.plan && state.bindings);
  const open = Boolean(state.sessionId && Number.isInteger(state.tabId));
  const halted = state.terminal === "HALTED_PARTIAL_CAPTURE" || state.terminal === "COMPLETE";
  el.load.disabled = open || halted || state.running;
  el.open.disabled = !loaded || open || halted;
  el.status.disabled = !open || halted || state.running;
  el.close.disabled = !open || state.running;
  el.run.disabled = !open || halted || state.running || Boolean(state.barrierCode && !state.barrierAcknowledged);
  el.acknowledge.disabled = !open || halted || state.running || !state.barrierCode || state.barrierAcknowledged;
  el.sessionState.textContent = open ? "OPEN" : "CLOSED";
  el.executionState.textContent = state.terminal;
  el.completed.textContent = String(state.nextIndex);
  el.saved.textContent = String(state.resultRefs.size);
  el.nextStep.textContent = state.plan?.steps[state.nextIndex]?.stepId || "none";
}
function resetExecutionProgress() {
  state.nextIndex = 0;
  state.resultRefs.clear();
  state.barrierCode = null;
  state.barrierAcknowledged = false;
  state.probeMutationPossible = false;
  el.barrier.hidden = true;
  el.barrier.textContent = "";
}
function settleSessionLoss(cleanTerminal) {
  if (state.terminal === "COMPLETE") return;
  if (state.probeMutationPossible) {
    state.terminal = "HALTED_PARTIAL_CAPTURE";
    return;
  }
  resetExecutionProgress();
  state.terminal = cleanTerminal;
}
function discardSessionState(reason) {
  for (const pending of state.pending.values()) {
    clearTimeout(pending.timer);
    pending.reject(new Error(reason));
  }
  state.pending.clear();
  state.sessionId = null;
  state.tabId = null;
}
function connectPort() {
  const port = chrome.runtime.connect({ name: PORT_NAME });
  state.port = port;
  port.onMessage.addListener((message) => {
    const pending = state.pending.get(message.requestId);
    if (!pending) return;
    clearTimeout(pending.timer);
    state.pending.delete(message.requestId);
    if (message.status === "PASS") pending.resolve(message);
    else pending.reject(Object.assign(new Error(message.message || message.code || "console refused"), { code: message.code }));
  });
  port.onDisconnect.addListener(() => {
    if (state.port !== port) return;
    state.port = null;
    discardSessionState("extension service worker disconnected");
    settleSessionLoss(state.plan && state.bindings ? "LOADED" : "IDLE");
    log("REFUSED", state.terminal === "HALTED_PARTIAL_CAPTURE"
      ? "service worker disconnected after probe mutation may have occurred; discard this page ledger"
      : "service worker disconnected before probe mutation; execution cursor reset");
    refreshControls();
  });
  return port;
}
function ensurePort() { return state.port || connectPort(); }
function send(message) {
  return new Promise((resolve, reject) => {
    const requestId = randomRequestId();
    const timer = setTimeout(() => {
      state.pending.delete(requestId);
      reject(Object.assign(new Error("console response timeout"), { code: "CONSOLE_TIMEOUT" }));
    }, 20000);
    state.pending.set(requestId, { resolve, reject, timer });
    const port = ensurePort();
    try { port.postMessage({ ...message, requestId }); }
    catch (error) {
      clearTimeout(timer);
      state.pending.delete(requestId);
      if (state.port === port) state.port = null;
      reject(error);
    }
  });
}
async function activeTabId() {
  const rows = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
  if (rows.length !== 1 || !Number.isInteger(rows[0].id)) throw new Error("one active tab is required");
  return rows[0].id;
}
async function sessionMessage(kind, extra = {}) {
  if (!state.sessionId || !Number.isInteger(state.tabId)) throw new Error("document session is not open");
  return send({ protocol: OPERATOR.PROTOCOL, kind, tabId: state.tabId, sessionId: state.sessionId, ...extra });
}
async function readJsonFile(input, label) {
  const file = input.files?.[0];
  if (!file) throw new Error(`${label} file is required`);
  if (file.size < 2 || file.size > FILE_LIMIT) throw new Error(`${label} file size is outside the bounded denominator`);
  const text = await file.text();
  if (/[^\t\n\r\x20-\x7e\u0080-\uffff]/.test(text)) throw new Error(`${label} contains a forbidden control byte`);
  const value = JSON.parse(text);
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error(`${label} must be one JSON object`);
  return value;
}
function resetLoadedState() {
  state.plan = null;
  state.bindings = null;
  resetExecutionProgress();
  state.terminal = "IDLE";
  el.bundleState.textContent = "NOT LOADED";
  el.planId.textContent = "none";
  el.bindingsId.textContent = "none";
  el.stepCount.textContent = "0";
  el.barrier.hidden = true;
  el.barrier.textContent = "";
}
async function loadBundle() {
  if (state.terminal === "HALTED_PARTIAL_CAPTURE" || state.terminal === "COMPLETE") {
    return log("REFUSED", "this panel lifecycle is sealed; discard the target document ledger and reload the panel before another operation");
  }
  if (state.sessionId) return log("REFUSED", "close the existing document session before loading another bundle");
  resetLoadedState();
  try {
    const [bindings, plan] = await Promise.all([readJsonFile(el.bindingsFile, "bindings"), readJsonFile(el.planFile, "plan")]);
    const verdict = await PLAN.validateBundle(plan, bindings);
    state.plan = plan;
    state.bindings = bindings;
    state.terminal = "LOADED";
    el.bundleState.textContent = "PASS";
    el.planId.textContent = verdict.planId;
    el.bindingsId.textContent = verdict.bindingsId;
    el.stepCount.textContent = String(verdict.stepCount);
    log("PASS", `content-bound bundle loaded with ${verdict.probeInvocationCount} probe invocations`);
  } catch (error) {
    resetLoadedState();
    el.bundleState.textContent = "REFUSED";
    log("REFUSED", `${error.code || "BUNDLE_INVALID"}: ${error.message}`);
  }
  refreshControls();
}
async function openSession() {
  try {
    const tabId = await activeTabId();
    const response = await send({ protocol: OPERATOR.PROTOCOL, kind: "open-session", tabId });
    requireHealthyInspection(response.inspection);
    state.sessionId = response.sessionId;
    state.tabId = response.tabId;
    state.terminal = "SESSION_OPEN";
    log("PASS", "exact active document bound to a fresh console session");
  } catch (error) {
    discardSessionState("session open failed");
    log("REFUSED", `${error.code || "OPEN_FAILED"}: ${error.message}`);
  }
  refreshControls();
}
async function inspectStatus() {
  try {
    const response = await sessionMessage("status");
    requireHealthyInspection(response.inspection);
    log("PASS", "document session and probe status inspected");
  } catch (error) {
    await halt(error);
  }
}
async function closeSession() {
  try { if (state.sessionId) await sessionMessage("close-session"); }
  catch (error) { log("REFUSED", `${error.code || "CLOSE_FAILED"}: ${error.message}`); }
  finally {
    discardSessionState("session closed");
    settleSessionLoss(state.plan && state.bindings ? "LOADED" : "IDLE");
    refreshControls();
  }
}
async function halt(error) {
  settleSessionLoss("REFUSED");
  log("REFUSED", `${error.code || "PLAN_EXECUTION_FAILED"}: ${error.message}. Discard this page ledger before retrying.`);
  try { if (state.sessionId) await sessionMessage("close-session"); } catch { /* best effort only */ }
  discardSessionState("plan execution halted");
  refreshControls();
}
function requirePristineCapture(capture) {
  if (!capture || capture.schema !== "axm-head/browser-probe-private-capture@1" || !Array.isArray(capture.events)) {
    throw Object.assign(new Error("preflight capture shape differs"), { code: "PREFLIGHT_CAPTURE_INVALID" });
  }
  if (capture.installedBeforeApplication !== true) {
    throw Object.assign(new Error("probe was not installed before the application"), { code: "PROBE_INSTALLATION_LATE" });
  }
  if (capture.refused !== null) {
    throw Object.assign(new Error("probe has already refused capture"), { code: "PROBE_CAPTURE_REFUSED" });
  }
  const installed = capture.events.filter((row) => row && row.type === "probe-installed");
  if (installed.length !== 1 || capture.events[0]?.type !== "probe-installed") {
    throw Object.assign(new Error("probe installation event denominator differs"), { code: "PROBE_INSTALL_EVENT_INVALID" });
  }
  const priorMark = capture.events.find((row) => row && PLAN_MARK_EVENT_TYPES.has(row.type));
  if (priorMark) {
    throw Object.assign(new Error(`probe ledger already contains ${priorMark.type}`), { code: "PROBE_LEDGER_ALREADY_MARKED" });
  }
  return capture;
}
function serializeCaptureForDownload(capture) {
  const serialized = JSON.stringify(capture);
  const bytes = new TextEncoder().encode(serialized).byteLength;
  if (bytes > OPERATOR.MAX_CAPTURE_BYTES) {
    throw Object.assign(new Error("capture exceeds admitted byte ceiling"), { code: "CAPTURE_DOWNLOAD_LIMIT_EXCEEDED" });
  }
  return serialized;
}
function downloadCapture(capture) {
  const serialized = serializeCaptureForDownload(capture);
  const blob = new Blob([serialized], { type: "application/json" });
  const localObject = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = localObject;
  anchor.download = "axm-browser-audition-private-capture.json";
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(localObject), 0);
}
async function runPlan() {
  if (!state.plan || !state.bindings || !state.sessionId || state.running) return;
  state.running = true;
  state.terminal = "RUNNING";
  refreshControls();
  try {
    while (state.nextIndex < state.plan.steps.length) {
      const current = state.plan.steps[state.nextIndex];
      if (current.kind === "operator-barrier") {
        if (state.barrierCode !== current.code || !state.barrierAcknowledged) {
          state.barrierCode = current.code;
          state.barrierAcknowledged = false;
          el.barrier.textContent = `${current.code}: ${current.statement}`;
          el.barrier.hidden = false;
          state.terminal = "AWAITING_OPERATOR_BARRIER";
          log("INFO", `stopped at ${current.code}`);
          break;
        }
        state.barrierCode = null;
        state.barrierAcknowledged = false;
        el.barrier.hidden = true;
        el.barrier.textContent = "";
        state.nextIndex += 1;
        continue;
      }
      if (current.kind === "console-status") {
        const response = await sessionMessage("status");
        requireHealthyInspection(response.inspection);
      } else if (current.kind === "probe-call") {
        const args = PLAN.resolveStepArgs(current, state.bindings, state.resultRefs);
        if (MUTATING_METHODS.has(current.method)) state.probeMutationPossible = true;
        const response = await sessionMessage("invoke", { method: current.method, args });
        requireHealthyInspection(response.inspection);
        if (current.method === "exportCapture" && current.captureUse === "preflight") {
          requirePristineCapture(response.result);
        }
        if (current.saveResultAs) {
          if (typeof response.result !== "string" || !/^opaque:[0-9a-f]{32}$/.test(response.result)) throw Object.assign(new Error("saved member result is not an admitted opaque identifier"), { code: "RESULT_VALUE_INVALID" });
          state.resultRefs.set(current.saveResultAs, response.result);
        }
        if (current.method === "exportCapture" && current.captureUse === "download") downloadCapture(response.result);
      } else throw Object.assign(new Error(`unsupported step kind ${current.kind}`), { code: "STEP_KIND_INVALID" });
      state.nextIndex += 1;
      el.completed.textContent = String(state.nextIndex);
      el.saved.textContent = String(state.resultRefs.size);
      el.nextStep.textContent = state.plan.steps[state.nextIndex]?.stepId || "none";
      log("PASS", `${current.stepId} completed`);
    }
    if (state.nextIndex >= state.plan.steps.length) {
      state.terminal = "COMPLETE";
      log("PASS", "private capture exported; this state does not qualify the route or supplier");
      try { await sessionMessage("close-session"); } catch { /* the capture is already local */ }
      discardSessionState("operation complete");
    }
  } catch (error) {
    await halt(error);
  } finally {
    state.running = false;
    refreshControls();
  }
}
function acknowledgeBarrier() {
  if (!state.barrierCode || state.barrierAcknowledged) return;
  state.barrierAcknowledged = true;
  state.terminal = "BARRIER_ACKNOWLEDGED";
  log("INFO", `${state.barrierCode} acknowledged by the operator`);
  refreshControls();
}

el.load.addEventListener("click", loadBundle);
el.open.addEventListener("click", openSession);
el.status.addEventListener("click", inspectStatus);
el.close.addEventListener("click", closeSession);
el.run.addEventListener("click", runPlan);
el.acknowledge.addEventListener("click", acknowledgeBarrier);
resetLoadedState();
refreshControls();

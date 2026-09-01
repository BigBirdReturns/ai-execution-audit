"use strict";

const PROTOCOL = "axm-head/browser-physical-audition-operator-console@1";
const PORT_NAME = "axm-browser-physical-audition-operator-console-v1";
const SHA_PLACEHOLDER = `sha256:${"0".repeat(64)}`;

const OPERATION_FIELDS = Object.freeze({
  markAvailability: [
    { name: "observedAtUnixMs", label: "Observed time, Unix ms", type: "integer", defaultValue: () => Date.now() },
    { name: "evidenceRef", label: "Availability evidence SHA-256 reference", type: "sha" },
    { name: "observed", label: "Availability observed", type: "boolean", defaultValue: true },
  ],
  markAdapterArtifact: [
    { name: "artifactBytes", label: "Executable adapter bytes", type: "integer" },
    { name: "artifactDigest", label: "Executable adapter SHA-256", type: "sha" },
    { name: "evidenceRef", label: "Adapter evidence SHA-256 reference", type: "sha" },
    { name: "executableObserved", label: "Executable bytes observed", type: "boolean", defaultValue: true },
  ],
  markFormation: [
    { name: "artifactBound", label: "Formation is artifact-bound", type: "boolean", defaultValue: true },
    { name: "capacityBasis", label: "Capacity basis", type: "select", options: ["artifact-bound-shards"] },
    { name: "capacityReceiptRef", label: "Capacity receipt SHA-256 reference", type: "sha" },
    { name: "modelCapacityBytes", label: "Composite model capacity bytes", type: "integer" },
    { name: "partitionMode", label: "Partition mode", type: "select", options: ["pipeline-layer"] },
    { name: "topologyReceiptRef", label: "Topology receipt SHA-256 reference", type: "sha" },
  ],
  markMember: [
    { name: "memberId", label: "Local opaque member label", type: "label", help: "The probe hashes this value before recording it." },
    { name: "role", label: "Pipeline role", type: "select", options: ["pipeline-input", "pipeline-output", "pipeline-stage", "coordinator"] },
    { name: "pledgedBytes", label: "Pledged bytes", type: "integer" },
  ],
  markModelManifest: [
    { name: "claimedId", label: "Claimed model identifier", type: "model" },
    { name: "boundModelId", label: "Artifact-bound model identifier", type: "model" },
    { name: "observedManifestDigest", label: "Observed manifest SHA-256", type: "sha" },
  ],
  markModelArtifact: [
    { name: "artifactId", label: "Local artifact label", type: "label", help: "The probe hashes this value before recording it." },
    { name: "bytes", label: "Artifact bytes", type: "integer" },
    { name: "digest", label: "Artifact SHA-256", type: "sha" },
    { name: "layerStart", label: "First layer", type: "integer" },
    { name: "layerEnd", label: "Last layer", type: "integer" },
    { name: "memberIdHash", label: "Opaque member identifier", type: "member" },
  ],
  markPerformanceStart: [
    { name: "promptTokenCount", label: "Prompt token count", type: "integer" },
    { name: "startMonotonicMs", label: "Optional monotonic start ms", type: "number", optional: true },
  ],
  markToken: [
    { name: "index", label: "Generated token index", type: "integer" },
    { name: "monotonicMs", label: "Optional monotonic appearance ms", type: "number", optional: true },
  ],
  markDrop: [
    { name: "memberIdHash", label: "Removed opaque member identifier", type: "member" },
    { name: "observedTerminal", label: "Observed route state", type: "select", options: ["HALTED", "DEGRADED", "RECOVERED"] },
    { name: "recovered", label: "Route recovered", type: "boolean", defaultValue: false },
    { name: "evidenceRef", label: "Controlled-drop SHA-256 reference", type: "sha" },
    { name: "controlled", label: "Removal was controlled", type: "boolean", defaultValue: true },
  ],
  markEquivalence: [
    { name: "referenceDigest", label: "Reference output SHA-256", type: "sha" },
    { name: "candidateDigest", label: "Candidate output SHA-256", type: "sha" },
    { name: "promptTokenCount", label: "Prompt token count", type: "integer" },
    { name: "outputTokenCount", label: "Output token count", type: "integer" },
    { name: "evidenceRef", label: "Equivalence evidence SHA-256 reference", type: "sha" },
  ],
  markPrivacyDeclaration: [
    { name: "scope", label: "Declaration scope", type: "select", options: ["browser-observed-network-surface-only"] },
    { name: "evidenceRef", label: "Privacy declaration SHA-256 reference", type: "sha" },
    { name: "claimsEndToEndConfidentiality", label: "Claims end-to-end confidentiality", type: "boolean", defaultValue: false },
  ],
  markObservationReceipt: [
    {
      name: "kind",
      label: "Receipt class",
      type: "select",
      options: [
        "current-availability-observation",
        "executable-adapter-artifact",
        "formation-capacity-receipt",
        "formation-topology-receipt",
        "member-drop-behavior-receipt",
        "model-output-equivalence-receipt",
        "performance-receipt",
        "network-exposure-observation",
        "privacy-declaration",
      ],
    },
    { name: "evidenceRef", label: "Receipt SHA-256 reference", type: "sha" },
  ],
});

const state = {
  port: chrome.runtime.connect({ name: PORT_NAME }),
  sessionId: null,
  tabId: null,
  pending: new Map(),
  memberHashes: new Set(),
};

const elements = {
  sessionState: document.querySelector("#session-state"),
  open: document.querySelector("#open-session"),
  refresh: document.querySelector("#refresh-status"),
  close: document.querySelector("#close-session"),
  execute: document.querySelector("#execute-operation"),
  sample: document.querySelector("#sample-peer-stats"),
  export: document.querySelector("#export-capture"),
  operation: document.querySelector("#operation"),
  form: document.querySelector("#operation-form"),
  memberList: document.querySelector("#member-list"),
  memberData: document.querySelector("#member-hashes"),
  log: document.querySelector("#command-log"),
  probeAvailable: document.querySelector("#probe-available"),
  probeEarly: document.querySelector("#probe-early"),
  probeEvents: document.querySelector("#probe-events"),
  probeRefusal: document.querySelector("#probe-refusal"),
};

function randomRequestId() {
  const words = new Uint32Array(4);
  crypto.getRandomValues(words);
  return `request:${Array.from(words, (value) => value.toString(16).padStart(8, "0")).join("")}`;
}

function appendLog(status, text) {
  const row = document.createElement("li");
  row.className = status.toLowerCase();
  row.textContent = `${new Date().toLocaleTimeString()} ${status}: ${text}`;
  elements.log.prepend(row);
  while (elements.log.children.length > 80) {
    elements.log.lastElementChild.remove();
  }
}

function setSessionOpen(open) {
  elements.sessionState.textContent = open ? "OPEN" : "CLOSED";
  elements.open.disabled = open;
  elements.refresh.disabled = !open;
  elements.close.disabled = !open;
  elements.execute.disabled = !open;
  elements.sample.disabled = !open;
  elements.export.disabled = !open;
}

function updateInspection(inspection) {
  if (!inspection) return;
  elements.probeAvailable.textContent = inspection.status === "PASS" ? `version ${inspection.probeVersion}` : inspection.code || "refused";
  elements.probeEarly.textContent = inspection.installedBeforeApplication === true ? "yes" : "no";
  elements.probeEvents.textContent = String(inspection.observedEventCount ?? 0);
  elements.probeRefusal.textContent = inspection.probeRefused || "none observed";
}

function send(message) {
  return new Promise((resolve, reject) => {
    const requestId = message.requestId || randomRequestId();
    const timeout = setTimeout(() => {
      state.pending.delete(requestId);
      reject(new Error("console response timeout"));
    }, 15000);
    state.pending.set(requestId, { resolve, reject, timeout });
    state.port.postMessage({ ...message, requestId });
  });
}

state.port.onMessage.addListener((message) => {
  const pending = state.pending.get(message.requestId);
  if (!pending) return;
  clearTimeout(pending.timeout);
  state.pending.delete(message.requestId);
  if (message.status === "PASS") pending.resolve(message);
  else pending.reject(Object.assign(new Error(message.message || message.code), { code: message.code }));
});

state.port.onDisconnect.addListener(() => {
  for (const pending of state.pending.values()) {
    clearTimeout(pending.timeout);
    pending.reject(new Error("operator console disconnected"));
  }
  state.pending.clear();
  state.sessionId = null;
  state.tabId = null;
  setSessionOpen(false);
  appendLog("REFUSED", "extension service worker disconnected");
});

async function activeTabId() {
  const tabs = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
  if (tabs.length !== 1 || !Number.isInteger(tabs[0].id)) throw new Error("one active tab is required");
  return tabs[0].id;
}

async function openSession() {
  try {
    const tabId = await activeTabId();
    const result = await send({ protocol: PROTOCOL, kind: "open-session", tabId });
    state.sessionId = result.sessionId;
    state.tabId = result.tabId;
    setSessionOpen(true);
    updateInspection(result.inspection);
    appendLog("PASS", `session opened on tab ${result.tabId}`);
  } catch (error) {
    appendLog("REFUSED", `${error.code || "OPEN_FAILED"}: ${error.message}`);
  }
}

async function sessionMessage(kind, extra = {}) {
  if (!state.sessionId || !Number.isInteger(state.tabId)) throw new Error("open a session first");
  return send({ protocol: PROTOCOL, kind, tabId: state.tabId, sessionId: state.sessionId, ...extra });
}

function createInput(field) {
  if (field.type === "boolean") {
    const row = document.createElement("div");
    row.className = "checkbox-row";
    const input = document.createElement("input");
    input.type = "checkbox";
    input.id = `field-${field.name}`;
    input.name = field.name;
    input.checked = field.defaultValue === true;
    const label = document.createElement("label");
    label.htmlFor = input.id;
    label.textContent = field.label;
    row.append(input, label);
    return row;
  }

  const wrapper = document.createElement("div");
  const label = document.createElement("label");
  label.htmlFor = `field-${field.name}`;
  label.textContent = field.optional ? `${field.label} (optional)` : field.label;
  let input;
  if (field.type === "select") {
    input = document.createElement("select");
    for (const value of field.options) {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = value;
      input.append(option);
    }
  } else {
    input = document.createElement("input");
    input.type = field.type === "integer" || field.type === "number" ? "number" : "text";
    if (field.type === "integer") input.step = "1";
    if (field.type === "number") input.step = "any";
    if (field.type === "sha") input.placeholder = SHA_PLACEHOLDER;
    if (field.type === "member") input.setAttribute("list", "member-hashes");
    if (typeof field.defaultValue === "function") input.value = String(field.defaultValue());
    else if (field.defaultValue !== undefined) input.value = String(field.defaultValue);
  }
  input.id = `field-${field.name}`;
  input.name = field.name;
  input.required = !field.optional;
  wrapper.append(label, input);
  if (field.help) {
    const help = document.createElement("p");
    help.className = "field-help";
    help.textContent = field.help;
    wrapper.append(help);
  }
  return wrapper;
}

function renderOperation() {
  elements.form.replaceChildren();
  for (const field of OPERATION_FIELDS[elements.operation.value]) {
    elements.form.append(createInput(field));
  }
}

function readArgs() {
  const fields = OPERATION_FIELDS[elements.operation.value];
  const args = {};
  for (const field of fields) {
    const input = elements.form.elements.namedItem(field.name);
    input.classList?.remove("invalid");
    if (field.type === "boolean") {
      args[field.name] = input.checked;
      continue;
    }
    const raw = input.value.trim();
    if (field.optional && raw === "") continue;
    if (raw === "") {
      input.classList.add("invalid");
      throw new Error(`${field.label} is required`);
    }
    if (field.type === "integer") args[field.name] = Number.parseInt(raw, 10);
    else if (field.type === "number") args[field.name] = Number(raw);
    else args[field.name] = raw;
  }
  return args;
}

function rememberMember(value) {
  if (typeof value !== "string" || state.memberHashes.has(value)) return;
  state.memberHashes.add(value);
  const option = document.createElement("option");
  option.value = value;
  elements.memberData.append(option);
  const row = document.createElement("li");
  row.textContent = value;
  elements.memberList.append(row);
}

async function executeOperation() {
  try {
    const method = elements.operation.value;
    const args = readArgs();
    const result = await sessionMessage("invoke", { method, args });
    if (method === "markMember") rememberMember(result.result);
    updateInspection(result.inspection);
    appendLog("PASS", `${method} recorded`);
  } catch (error) {
    appendLog("REFUSED", `${error.code || "COMMAND_FAILED"}: ${error.message}`);
  }
}

async function refreshStatus() {
  try {
    const result = await sessionMessage("status");
    updateInspection(result.inspection);
    appendLog("PASS", `probe status refreshed after ${result.requestCount} commands`);
  } catch (error) {
    appendLog("REFUSED", `${error.code || "STATUS_FAILED"}: ${error.message}`);
  }
}

async function samplePeerStats() {
  try {
    const result = await sessionMessage("invoke", { method: "samplePeerStats", args: {} });
    updateInspection(result.inspection);
    appendLog("PASS", `sampled ${Array.isArray(result.result) ? result.result.length : 0} peer connections`);
  } catch (error) {
    appendLog("REFUSED", `${error.code || "STATS_FAILED"}: ${error.message}`);
  }
}

async function exportCapture() {
  try {
    const result = await sessionMessage("invoke", { method: "exportCapture", args: {} });
    const body = JSON.stringify(result.result, null, 2) + "\n";
    const blob = new Blob([body], { type: "application/json" });
    const objectReference = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = objectReference;
    link.download = `axm-browser-private-capture-${new Date().toISOString().replace(/[:.]/g, "-")}.json`;
    document.body.append(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(objectReference);
    appendLog("PASS", `private capture exported, ${body.length} characters`);
  } catch (error) {
    appendLog("REFUSED", `${error.code || "EXPORT_FAILED"}: ${error.message}`);
  }
}

async function closeSession() {
  try {
    await sessionMessage("close-session");
    appendLog("PASS", "session closed and in-memory request ledger discarded");
  } catch (error) {
    appendLog("REFUSED", `${error.code || "CLOSE_FAILED"}: ${error.message}`);
  } finally {
    state.sessionId = null;
    state.tabId = null;
    state.memberHashes.clear();
    elements.memberData.replaceChildren();
    elements.memberList.replaceChildren();
    setSessionOpen(false);
  }
}

for (const method of Object.keys(OPERATION_FIELDS)) {
  const option = document.createElement("option");
  option.value = method;
  option.textContent = method;
  elements.operation.append(option);
}
renderOperation();
setSessionOpen(false);

elements.operation.addEventListener("change", renderOperation);
elements.open.addEventListener("click", openSession);
elements.refresh.addEventListener("click", refreshStatus);
elements.close.addEventListener("click", closeSession);
elements.execute.addEventListener("click", executeOperation);
elements.sample.addEventListener("click", samplePeerStats);
elements.export.addEventListener("click", exportCapture);

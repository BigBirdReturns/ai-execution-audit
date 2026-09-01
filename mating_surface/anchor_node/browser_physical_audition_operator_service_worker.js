"use strict";

importScripts("browser_physical_audition_operator_contract.js");

const CONTRACT = globalThis.AXMOperatorContract;
const CONSOLE_PORT = "axm-browser-physical-audition-operator-console-v1";
const sessions = new Map();

function randomId(prefix) {
  const words = new Uint32Array(4);
  crypto.getRandomValues(words);
  return `${prefix}:${Array.from(words, (value) => value.toString(16).padStart(8, "0")).join("")}`;
}

function refusal(requestId, error) {
  return {
    protocol: CONTRACT.PROTOCOL,
    status: "REFUSED",
    requestId: typeof requestId === "string" ? requestId : "request:00000000000000000000000000000000",
    code: error?.code || "CONSOLE_FAILURE",
    message: String(error?.message || error || "console failure").slice(0, 512),
    actualSupplierQualified: false,
    physicalEstateQualified: false,
    missionAuthority: "none",
    commandAuthority: "none",
  };
}

async function currentActiveTabId() {
  const rows = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
  return rows.length === 1 && Number.isInteger(rows[0].id) ? rows[0].id : null;
}

async function inspectProbeInPage(expectedMethods, maximumCaptureBytes) {
  const descriptor = Object.getOwnPropertyDescriptor(globalThis, "__AXM_AUDITION__");
  if (!descriptor || descriptor.enumerable || descriptor.writable || descriptor.configurable) {
    return { status: "REFUSED", code: "PROBE_DESCRIPTOR_INVALID" };
  }
  const api = descriptor.value;
  if (!api || !Object.isFrozen(api) || api.version !== "1") {
    return { status: "REFUSED", code: "PROBE_API_INVALID" };
  }
  const observedMethods = Object.keys(api).filter((key) => key !== "version").sort();
  const requiredMethods = [...expectedMethods].sort();
  if (JSON.stringify(observedMethods) !== JSON.stringify(requiredMethods)) {
    return { status: "REFUSED", code: "PROBE_METHOD_DENOMINATOR_INVALID", observedMethods };
  }
  const capture = api.exportCapture();
  const encodedBytes = new TextEncoder().encode(JSON.stringify(capture)).byteLength;
  if (
    !capture ||
    capture.schema !== "axm-head/browser-probe-private-capture@1" ||
    encodedBytes > maximumCaptureBytes
  ) {
    return { status: "REFUSED", code: "PROBE_CAPTURE_INVALID" };
  }
  return {
    status: "PASS",
    probeVersion: api.version,
    installedBeforeApplication: capture.installedBeforeApplication === true,
    probeRefused: capture.refused,
    observedEventCount: Number(capture.observed?.eventCount || 0),
    observedEncodedBytes: Number(capture.observed?.encodedBytes || 0),
  };
}

async function invokeProbeInPage(method, args, expectedMethods, maximumCaptureBytes) {
  const descriptor = Object.getOwnPropertyDescriptor(globalThis, "__AXM_AUDITION__");
  if (!descriptor || descriptor.enumerable || descriptor.writable || descriptor.configurable) {
    return { status: "REFUSED", code: "PROBE_DESCRIPTOR_INVALID" };
  }
  const api = descriptor.value;
  if (!api || !Object.isFrozen(api) || api.version !== "1") {
    return { status: "REFUSED", code: "PROBE_API_INVALID" };
  }
  const observedMethods = Object.keys(api).filter((key) => key !== "version").sort();
  const requiredMethods = [...expectedMethods].sort();
  if (JSON.stringify(observedMethods) !== JSON.stringify(requiredMethods)) {
    return { status: "REFUSED", code: "PROBE_METHOD_DENOMINATOR_INVALID", observedMethods };
  }
  const preflightCapture = api.exportCapture();
  const preflightBytes = new TextEncoder().encode(JSON.stringify(preflightCapture)).byteLength;
  if (
    !preflightCapture ||
    preflightCapture.schema !== "axm-head/browser-probe-private-capture@1" ||
    preflightBytes > maximumCaptureBytes
  ) {
    return { status: "REFUSED", code: "PROBE_CAPTURE_INVALID" };
  }
  const inspection = {
    status: "PASS",
    probeVersion: api.version,
    installedBeforeApplication: preflightCapture.installedBeforeApplication === true,
    probeRefused: preflightCapture.refused,
    observedEventCount: Number(preflightCapture.observed?.eventCount || 0),
    observedEncodedBytes: Number(preflightCapture.observed?.encodedBytes || 0),
  };
  if (typeof api[method] !== "function") {
    return { status: "REFUSED", code: "PROBE_METHOD_UNAVAILABLE" };
  }
  try {
    const result = await api[method](args);
    if (method === "exportCapture") {
      const encodedBytes = new TextEncoder().encode(JSON.stringify(result)).byteLength;
      if (
        !result ||
        result.schema !== "axm-head/browser-probe-private-capture@1" ||
        encodedBytes > maximumCaptureBytes
      ) {
        return { status: "REFUSED", code: "CAPTURE_EXPORT_INVALID" };
      }
    }
    return { status: "PASS", result: result === undefined ? null : result, inspection };
  } catch (error) {
    return {
      status: "REFUSED",
      code: "PROBE_INVOCATION_FAILED",
      errorClass: error?.constructor?.name || "Error",
    };
  }
}

async function executeInMain(tabId, func, args) {
  const rows = await chrome.scripting.executeScript({
    target: { tabId, frameIds: [0] },
    world: "MAIN",
    func,
    args,
  });
  if (!Array.isArray(rows) || rows.length !== 1 || !rows[0] || !("result" in rows[0])) {
    throw Object.assign(new Error("MAIN-world result denominator differs"), {
      code: "MAIN_WORLD_RESULT_INVALID",
    });
  }
  return rows[0].result;
}

function requireSession(port, message) {
  const session = sessions.get(port);
  if (!session || session.sessionId !== message.sessionId) {
    throw Object.assign(new Error("session is absent or stale"), { code: "SESSION_INVALID" });
  }
  if (session.tabId !== message.tabId) {
    throw Object.assign(new Error("session tab differs"), { code: "SESSION_TAB_MISMATCH" });
  }
  if (Date.now() - session.createdAtUnixMs > CONTRACT.SESSION_MAX_AGE_MS) {
    sessions.delete(port);
    throw Object.assign(new Error("session expired"), { code: "SESSION_EXPIRED" });
  }
  if (session.seenRequestIds.has(message.requestId)) {
    throw Object.assign(new Error("request identifier was replayed"), { code: "REQUEST_REPLAY" });
  }
  if (session.requestCount >= CONTRACT.MAX_SESSION_REQUESTS) {
    sessions.delete(port);
    throw Object.assign(new Error("session request ceiling reached"), {
      code: "SESSION_REQUEST_LIMIT_EXCEEDED",
    });
  }
  session.seenRequestIds.add(message.requestId);
  session.requestCount += 1;
  return session;
}

async function handleMessage(port, rawMessage) {
  let message;
  try {
    message = CONTRACT.validateEnvelope(rawMessage);
    if (message.kind === "close-session") {
      const session = requireSession(port, message);
      sessions.delete(port);
      return CONTRACT.response("PASS", message.requestId, {
        kind: "session-closed",
        sessionId: session.sessionId,
      });
    }

    const activeTabId = await currentActiveTabId();
    if (activeTabId !== message.tabId) {
      throw Object.assign(new Error("the session target is not the active tab"), {
        code: "ACTIVE_TAB_MISMATCH",
      });
    }

    if (message.kind === "open-session") {
      if (sessions.has(port)) {
        throw Object.assign(new Error("this panel already owns a session"), {
          code: "SESSION_ALREADY_OPEN",
        });
      }
      const inspection = await executeInMain(message.tabId, inspectProbeInPage, [
        CONTRACT.METHODS,
        CONTRACT.MAX_CAPTURE_BYTES,
      ]);
      if (!inspection || inspection.status !== "PASS") {
        throw Object.assign(new Error(inspection?.code || "probe inspection refused"), {
          code: inspection?.code || "PROBE_INSPECTION_REFUSED",
        });
      }
      const session = {
        sessionId: randomId("session"),
        tabId: message.tabId,
        createdAtUnixMs: Date.now(),
        requestCount: 0,
        seenRequestIds: new Set([message.requestId]),
      };
      sessions.set(port, session);
      return CONTRACT.response("PASS", message.requestId, {
        kind: "session-opened",
        sessionId: session.sessionId,
        tabId: session.tabId,
        methods: CONTRACT.METHODS,
        inspection,
        actualSupplierQualified: false,
        physicalEstateQualified: false,
        missionAuthority: "none",
        commandAuthority: "none",
      });
    }

    const session = requireSession(port, message);
    if (message.kind === "status") {
      const inspection = await executeInMain(message.tabId, inspectProbeInPage, [
        CONTRACT.METHODS,
        CONTRACT.MAX_CAPTURE_BYTES,
      ]);
      return CONTRACT.response("PASS", message.requestId, {
        kind: "status",
        sessionId: session.sessionId,
        tabId: session.tabId,
        requestCount: session.requestCount,
        inspection,
      });
    }
    const invocation = await executeInMain(message.tabId, invokeProbeInPage, [
      message.method,
      message.args,
      CONTRACT.METHODS,
      CONTRACT.MAX_CAPTURE_BYTES,
    ]);
    if (!invocation || invocation.status !== "PASS") {
      throw Object.assign(new Error(invocation?.code || "probe invocation refused"), {
        code: invocation?.code || "PROBE_INVOCATION_REFUSED",
      });
    }
    return CONTRACT.response("PASS", message.requestId, {
      kind: "invocation",
      sessionId: session.sessionId,
      method: message.method,
      result: invocation.result,
      inspection: invocation.inspection,
      actualSupplierQualified: false,
      physicalEstateQualified: false,
      missionAuthority: "none",
      commandAuthority: "none",
    });
  } catch (error) {
    return refusal(message?.requestId || rawMessage?.requestId, error);
  }
}

chrome.runtime.onConnect.addListener((port) => {
  if (port.name !== CONSOLE_PORT || port.sender?.id !== chrome.runtime.id) {
    try {
      port.disconnect();
    } catch {
      // Nothing is retained for an invalid port.
    }
    return;
  }

  port.onMessage.addListener((message) => {
    handleMessage(port, message).then(
      (result) => {
        try {
          port.postMessage(result);
        } catch {
          sessions.delete(port);
        }
      },
      (error) => {
        try {
          port.postMessage(refusal(message?.requestId, error));
        } catch {
          sessions.delete(port);
        }
      }
    );
  });
  port.onDisconnect.addListener(() => sessions.delete(port));
});

chrome.sidePanel
  .setPanelBehavior({ openPanelOnActionClick: true })
  .catch(() => undefined);

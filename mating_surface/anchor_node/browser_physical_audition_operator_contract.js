(() => {
  "use strict";

  const PROTOCOL = "axm-head/browser-physical-audition-operator-console@1";
  const SESSION_MAX_AGE_MS = 2 * 60 * 60 * 1000;
  const MAX_SESSION_REQUESTS = 512;
  const MAX_COMMAND_BYTES = 65536;
  const MAX_CAPTURE_BYTES = 1048576;
  const SHA256_PATTERN = /^sha256:[0-9a-f]{64}$/;
  const LOCAL_LABEL_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._:@+\/-]{0,127}$/;
  const MODEL_ID_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._:@+\/-]{0,191}$/;
  const OPAQUE_MEMBER_PATTERN = /^opaque:[0-9a-f]{32}$/;
  const REQUEST_ID_PATTERN = /^request:[0-9a-f]{32}$/;
  const SESSION_ID_PATTERN = /^session:[0-9a-f]{32}$/;

  const METHODS = Object.freeze([
    "markAvailability",
    "markAdapterArtifact",
    "markFormation",
    "markMember",
    "markModelManifest",
    "markModelArtifact",
    "markPerformanceStart",
    "markToken",
    "markDrop",
    "markEquivalence",
    "markPrivacyDeclaration",
    "markObservationReceipt",
    "samplePeerStats",
    "exportCapture",
  ]);

  const RECEIPT_KINDS = Object.freeze([
    "current-availability-observation",
    "executable-adapter-artifact",
    "formation-capacity-receipt",
    "formation-topology-receipt",
    "member-drop-behavior-receipt",
    "model-output-equivalence-receipt",
    "performance-receipt",
    "network-exposure-observation",
    "privacy-declaration",
  ]);

  const FORBIDDEN_KEYS = new Set([
    "prompt",
    "promptText",
    "completion",
    "completionText",
    "tokenText",
    "sdp",
    "iceAddress",
    "candidateAddress",
    "credential",
    "credentials",
    "password",
    "secret",
    "responseBody",
    "hostname",
    "localPath",
    "rawUrl",
    "url",
    "supplier",
    "supplierRef",
    "supplierAdmissionReceipt",
    "supplierAdmissionReceiptPresent",
    "terminal",
    "authority",
    "missionAuthority",
    "commandAuthority",
    "targetingAuthority",
    "engagementAuthority",
    "effectorAuthority",
    "weaponsAuthority",
    "namedHumanConfirmation",
  ]);

  class ContractError extends Error {
    constructor(code, message) {
      super(message);
      this.name = "ContractError";
      this.code = code;
    }
  }

  function fail(code, message) {
    throw new ContractError(code, message);
  }

  function isPlainObject(value) {
    if (value === null || typeof value !== "object" || Array.isArray(value)) {
      return false;
    }
    const prototype = Object.getPrototypeOf(value);
    return prototype === Object.prototype || prototype === null;
  }

  function exactKeys(value, required, optional = []) {
    if (!isPlainObject(value)) {
      fail("OBJECT_REQUIRED", "a plain object is required");
    }
    const requiredSet = new Set(required);
    const allowed = new Set([...required, ...optional]);
    const keys = Object.keys(value);
    const missing = required.filter((key) => !Object.prototype.hasOwnProperty.call(value, key));
    const extra = keys.filter((key) => !allowed.has(key));
    if (missing.length || extra.length) {
      fail(
        "KEY_DENOMINATOR_INVALID",
        `missing=${JSON.stringify(missing)} extra=${JSON.stringify(extra)}`
      );
    }
    for (const key of requiredSet) {
      if (value[key] === undefined) {
        fail("REQUIRED_VALUE_UNDEFINED", key);
      }
    }
    return value;
  }

  function encodedBytes(value) {
    return new TextEncoder().encode(JSON.stringify(value)).byteLength;
  }

  function assertNoForbiddenKeys(value, path = "$") {
    if (Array.isArray(value)) {
      if (value.length > 1024) {
        fail("ARRAY_LIMIT_EXCEEDED", path);
      }
      value.forEach((item, index) => assertNoForbiddenKeys(item, `${path}[${index}]`));
      return;
    }
    if (!isPlainObject(value)) {
      return;
    }
    for (const [key, item] of Object.entries(value)) {
      if (FORBIDDEN_KEYS.has(key)) {
        fail("FORBIDDEN_FIELD", `${path}.${key}`);
      }
      assertNoForbiddenKeys(item, `${path}.${key}`);
    }
  }

  function stringValue(value, name, { pattern = null, max = 256, enumValues = null } = {}) {
    if (typeof value !== "string" || value.length < 1 || value.length > max || /[\r\n\u0000]/.test(value)) {
      fail("STRING_INVALID", name);
    }
    if (pattern && !pattern.test(value)) {
      fail("STRING_PATTERN_INVALID", name);
    }
    if (enumValues && !enumValues.includes(value)) {
      fail("ENUM_INVALID", name);
    }
    if (/^(?:https?|wss?|file):/i.test(value) || /^[A-Za-z]:[\\/]/.test(value) || /^\\\\/.test(value)) {
      fail("RAW_COORDINATE_FORBIDDEN", name);
    }
    if (/^(?:\d{1,3}\.){3}\d{1,3}(?::\d+)?$/.test(value)) {
      fail("RAW_NETWORK_IDENTITY_FORBIDDEN", name);
    }
    return value;
  }

  function sha256(value, name) {
    return stringValue(value, name, { pattern: SHA256_PATTERN, max: 71 });
  }

  function booleanValue(value, name) {
    if (typeof value !== "boolean") {
      fail("BOOLEAN_INVALID", name);
    }
    return value;
  }

  function finiteNumber(value, name, { integer = false, min = 0, max = Number.MAX_SAFE_INTEGER } = {}) {
    if (typeof value !== "number" || !Number.isFinite(value)) {
      fail("NUMBER_INVALID", name);
    }
    if (integer && !Number.isInteger(value)) {
      fail("INTEGER_REQUIRED", name);
    }
    if (value < min || value > max) {
      fail("NUMBER_RANGE_INVALID", name);
    }
    return value;
  }

  function optionalFiniteNumber(value, name, options = {}) {
    if (value === undefined || value === null || value === "") {
      return undefined;
    }
    return finiteNumber(value, name, options);
  }

  const validators = Object.freeze({
    markAvailability(args) {
      exactKeys(args, ["observedAtUnixMs", "evidenceRef", "observed"]);
      return {
        observedAtUnixMs: finiteNumber(args.observedAtUnixMs, "observedAtUnixMs", {
          integer: true,
          min: 946684800000,
          max: 4102444800000,
        }),
        evidenceRef: sha256(args.evidenceRef, "evidenceRef"),
        observed: booleanValue(args.observed, "observed"),
      };
    },
    markAdapterArtifact(args) {
      exactKeys(args, ["artifactBytes", "artifactDigest", "evidenceRef", "executableObserved"]);
      return {
        artifactBytes: finiteNumber(args.artifactBytes, "artifactBytes", { integer: true, min: 1 }),
        artifactDigest: sha256(args.artifactDigest, "artifactDigest"),
        evidenceRef: sha256(args.evidenceRef, "evidenceRef"),
        executableObserved: booleanValue(args.executableObserved, "executableObserved"),
      };
    },
    markFormation(args) {
      exactKeys(args, [
        "artifactBound",
        "capacityBasis",
        "capacityReceiptRef",
        "modelCapacityBytes",
        "partitionMode",
        "topologyReceiptRef",
      ]);
      return {
        artifactBound: booleanValue(args.artifactBound, "artifactBound"),
        capacityBasis: stringValue(args.capacityBasis, "capacityBasis", {
          enumValues: ["artifact-bound-shards"],
        }),
        capacityReceiptRef: sha256(args.capacityReceiptRef, "capacityReceiptRef"),
        modelCapacityBytes: finiteNumber(args.modelCapacityBytes, "modelCapacityBytes", {
          integer: true,
          min: 1,
        }),
        partitionMode: stringValue(args.partitionMode, "partitionMode", {
          enumValues: ["pipeline-layer"],
        }),
        topologyReceiptRef: sha256(args.topologyReceiptRef, "topologyReceiptRef"),
      };
    },
    markMember(args) {
      exactKeys(args, ["memberId", "role", "pledgedBytes"]);
      return {
        memberId: stringValue(args.memberId, "memberId", { pattern: LOCAL_LABEL_PATTERN, max: 128 }),
        role: stringValue(args.role, "role", {
          enumValues: ["pipeline-input", "pipeline-output", "pipeline-stage", "coordinator"],
        }),
        pledgedBytes: finiteNumber(args.pledgedBytes, "pledgedBytes", { integer: true, min: 1 }),
      };
    },
    markModelManifest(args) {
      exactKeys(args, ["claimedId", "boundModelId", "observedManifestDigest"]);
      return {
        claimedId: stringValue(args.claimedId, "claimedId", { pattern: MODEL_ID_PATTERN, max: 192 }),
        boundModelId: stringValue(args.boundModelId, "boundModelId", { pattern: MODEL_ID_PATTERN, max: 192 }),
        observedManifestDigest: sha256(args.observedManifestDigest, "observedManifestDigest"),
      };
    },
    markModelArtifact(args) {
      exactKeys(args, ["artifactId", "bytes", "digest", "layerStart", "layerEnd", "memberIdHash"]);
      const layerStart = finiteNumber(args.layerStart, "layerStart", { integer: true, min: 0, max: 1048575 });
      const layerEnd = finiteNumber(args.layerEnd, "layerEnd", { integer: true, min: 0, max: 1048575 });
      if (layerEnd < layerStart) {
        fail("LAYER_RANGE_INVALID", "layerEnd precedes layerStart");
      }
      return {
        artifactId: stringValue(args.artifactId, "artifactId", { pattern: LOCAL_LABEL_PATTERN, max: 128 }),
        bytes: finiteNumber(args.bytes, "bytes", { integer: true, min: 1 }),
        digest: sha256(args.digest, "digest"),
        layerStart,
        layerEnd,
        memberIdHash: stringValue(args.memberIdHash, "memberIdHash", {
          pattern: OPAQUE_MEMBER_PATTERN,
          max: 39,
        }),
      };
    },
    markPerformanceStart(args) {
      exactKeys(args, ["promptTokenCount"], ["startMonotonicMs"]);
      const result = {
        promptTokenCount: finiteNumber(args.promptTokenCount, "promptTokenCount", {
          integer: true,
          min: 1,
          max: 1048576,
        }),
      };
      const mark = optionalFiniteNumber(args.startMonotonicMs, "startMonotonicMs", { min: 0 });
      if (mark !== undefined) {
        result.startMonotonicMs = mark;
      }
      return result;
    },
    markToken(args) {
      exactKeys(args, ["index"], ["monotonicMs"]);
      const result = {
        index: finiteNumber(args.index, "index", { integer: true, min: 0, max: 1048575 }),
      };
      const mark = optionalFiniteNumber(args.monotonicMs, "monotonicMs", { min: 0 });
      if (mark !== undefined) {
        result.monotonicMs = mark;
      }
      return result;
    },
    markDrop(args) {
      exactKeys(args, ["memberIdHash", "observedTerminal", "recovered", "evidenceRef", "controlled"]);
      return {
        memberIdHash: stringValue(args.memberIdHash, "memberIdHash", {
          pattern: OPAQUE_MEMBER_PATTERN,
          max: 39,
        }),
        observedTerminal: stringValue(args.observedTerminal, "observedTerminal", {
          enumValues: ["HALTED", "DEGRADED", "RECOVERED"],
        }),
        recovered: booleanValue(args.recovered, "recovered"),
        evidenceRef: sha256(args.evidenceRef, "evidenceRef"),
        controlled: booleanValue(args.controlled, "controlled"),
      };
    },
    markEquivalence(args) {
      exactKeys(args, [
        "referenceDigest",
        "candidateDigest",
        "promptTokenCount",
        "outputTokenCount",
        "evidenceRef",
      ]);
      return {
        referenceDigest: sha256(args.referenceDigest, "referenceDigest"),
        candidateDigest: sha256(args.candidateDigest, "candidateDigest"),
        promptTokenCount: finiteNumber(args.promptTokenCount, "promptTokenCount", {
          integer: true,
          min: 1,
          max: 1048576,
        }),
        outputTokenCount: finiteNumber(args.outputTokenCount, "outputTokenCount", {
          integer: true,
          min: 1,
          max: 1048576,
        }),
        evidenceRef: sha256(args.evidenceRef, "evidenceRef"),
      };
    },
    markPrivacyDeclaration(args) {
      exactKeys(args, ["scope", "evidenceRef", "claimsEndToEndConfidentiality"]);
      return {
        scope: stringValue(args.scope, "scope", {
          enumValues: ["browser-observed-network-surface-only"],
        }),
        evidenceRef: sha256(args.evidenceRef, "evidenceRef"),
        claimsEndToEndConfidentiality: booleanValue(
          args.claimsEndToEndConfidentiality,
          "claimsEndToEndConfidentiality"
        ),
      };
    },
    markObservationReceipt(args) {
      exactKeys(args, ["kind", "evidenceRef"]);
      return {
        kind: stringValue(args.kind, "kind", { enumValues: RECEIPT_KINDS }),
        evidenceRef: sha256(args.evidenceRef, "evidenceRef"),
      };
    },
    samplePeerStats(args) {
      exactKeys(args, []);
      return {};
    },
    exportCapture(args) {
      exactKeys(args, []);
      return {};
    },
  });

  function validateMethod(method) {
    if (typeof method !== "string" || !METHODS.includes(method)) {
      fail("METHOD_NOT_ALLOWED", String(method));
    }
    return method;
  }

  function validateArgs(method, args) {
    validateMethod(method);
    assertNoForbiddenKeys(args);
    if (encodedBytes(args) > MAX_COMMAND_BYTES) {
      fail("COMMAND_BYTE_LIMIT_EXCEEDED", method);
    }
    return validators[method](args);
  }

  function validateEnvelope(message) {
    exactKeys(message, ["protocol", "kind", "requestId", "tabId"], ["sessionId", "method", "args"]);
    if (message.protocol !== PROTOCOL) {
      fail("PROTOCOL_INVALID", String(message.protocol));
    }
    stringValue(message.requestId, "requestId", { pattern: REQUEST_ID_PATTERN, max: 40 });
    finiteNumber(message.tabId, "tabId", { integer: true, min: 0, max: 2147483647 });
    if (!["open-session", "invoke", "close-session", "status"].includes(message.kind)) {
      fail("MESSAGE_KIND_INVALID", String(message.kind));
    }
    if (message.kind === "open-session") {
      exactKeys(message, ["protocol", "kind", "requestId", "tabId"]);
      return { ...message };
    }
    stringValue(message.sessionId, "sessionId", { pattern: SESSION_ID_PATTERN, max: 40 });
    if (message.kind === "invoke") {
      exactKeys(message, ["protocol", "kind", "requestId", "tabId", "sessionId", "method", "args"]);
      return { ...message, method: validateMethod(message.method), args: validateArgs(message.method, message.args) };
    }
    exactKeys(message, ["protocol", "kind", "requestId", "tabId", "sessionId"]);
    return { ...message };
  }

  function response(status, requestId, values = {}) {
    const body = { protocol: PROTOCOL, status, requestId, ...values };
    if (status === "PASS") {
      exactKeys(body, ["protocol", "status", "requestId"], Object.keys(values));
    }
    return body;
  }

  const api = Object.freeze({
    PROTOCOL,
    METHODS,
    RECEIPT_KINDS,
    SESSION_MAX_AGE_MS,
    MAX_SESSION_REQUESTS,
    MAX_COMMAND_BYTES,
    MAX_CAPTURE_BYTES,
    ContractError,
    validateMethod,
    validateArgs,
    validateEnvelope,
    encodedBytes,
    response,
  });

  Object.defineProperty(globalThis, "AXMOperatorContract", {
    value: api,
    enumerable: false,
    writable: false,
    configurable: false,
  });
})();

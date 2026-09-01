(() => {
  "use strict";

  const OPERATOR = globalThis.AXMOperatorContract;
  if (!OPERATOR || !Object.isFrozen(OPERATOR)) throw new Error("admitted operator contract unavailable");

  const PROFILE_ID = "axm-head/browser-audition-operation-plan/0.1";
  const PLAN_SCHEMA = "axm-head/browser-audition-operation-plan@1";
  const BINDINGS_SCHEMA = "axm-head/browser-audition-operation-bindings@1";
  const PLAN_PROTOCOL = "axm-head/browser-audition-operation-plan@1";
  const INTERFACE = "axm/distributed-model-inference@1";
  const MAX_PLAN_BYTES = 262144;
  const MAX_BINDINGS_BYTES = 262144;
  const MAX_PLAN_STEPS = 480;
  const MAX_PROBE_INVOCATIONS = 500;
  const MAX_TOKEN_MARKS = 400;
  const MIN_MEMBER_COUNT = 2;
  const MAX_MEMBER_COUNT = 32;
  const MAX_ARTIFACT_COUNT = 256;
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
  const CLAIM_BOUNDARY = Object.freeze({
    operationPlanSourceConstructed: true,
    operationPlanSourceAdmitted: false,
    operationPlanExecuted: false,
    browserLaunched: false,
    supplierEndpointContacted: false,
    modelDownloaded: false,
    peerConnectionFormed: false,
    inferenceExecuted: false,
    physicalAuditionCompleted: false,
    namedHumanConfirmationSupplied: false,
    actualSupplierQualified: false,
    physicalEstateQualified: false,
    missionAuthority: "none",
    commandAuthority: "none",
  });
  const FORBIDDEN_KEYS = new Set([
    "prompt", "promptText", "completion", "completionText", "tokenText", "sdp", "iceAddress",
    "candidateAddress", "credential", "credentials", "password", "secret", "responseBody", "hostname",
    "localPath", "rawUrl", "url", "supplier", "supplierRef", "supplierAdmissionReceipt",
    "supplierAdmissionReceiptPresent", "terminal", "authority", "missionAuthority", "commandAuthority",
    "targetingAuthority", "engagementAuthority", "effectorAuthority", "weaponsAuthority", "namedHumanConfirmation",
  ]);
  const SHA_RE = /^sha256:[0-9a-f]{64}$/;
  const ALIAS_RE = /^member:[a-z0-9][a-z0-9._-]{0,63}$/;

  class PlanContractError extends Error {
    constructor(code, message) {
      super(message);
      this.name = "PlanContractError";
      this.code = code;
    }
  }
  const fail = (code, message) => { throw new PlanContractError(code, message); };
  const isPlainObject = (value) => {
    if (value === null || typeof value !== "object" || Array.isArray(value)) return false;
    const prototype = Object.getPrototypeOf(value);
    return prototype === Object.prototype || prototype === null;
  };
  function exactKeys(value, required, optional = []) {
    if (!isPlainObject(value)) fail("OBJECT_REQUIRED", "plain object required");
    const allowed = new Set([...required, ...optional]);
    const missing = required.filter((key) => !Object.prototype.hasOwnProperty.call(value, key));
    const extra = Object.keys(value).filter((key) => !allowed.has(key));
    if (missing.length || extra.length) fail("KEY_DENOMINATOR_INVALID", `missing=${JSON.stringify(missing)} extra=${JSON.stringify(extra)}`);
    return value;
  }
  function assertNoForbidden(value, path = "$") {
    if (Array.isArray(value)) {
      if (value.length > 2048) fail("ARRAY_LIMIT_EXCEEDED", path);
      value.forEach((item, index) => assertNoForbidden(item, `${path}[${index}]`));
      return;
    }
    if (!isPlainObject(value)) return;
    for (const [key, item] of Object.entries(value)) {
      if (FORBIDDEN_KEYS.has(key)) fail("FORBIDDEN_FIELD", `${path}.${key}`);
      assertNoForbidden(item, `${path}.${key}`);
    }
  }
  function stringValue(value, name, pattern = null) {
    if (typeof value !== "string" || value.length < 1 || value.length > 256 || /[\u0000-\u001f\u007f]/.test(value)) fail("STRING_INVALID", name);
    if (pattern && !pattern.test(value)) fail("STRING_PATTERN_INVALID", name);
    if (/^(?:https?|wss?|file):/i.test(value) || /^[A-Za-z]:[\\/]/.test(value) || /^\\\\/.test(value)) fail("RAW_COORDINATE_FORBIDDEN", name);
    return value;
  }
  function sha256Value(value, name) { return stringValue(value, name, SHA_RE); }
  function integerValue(value, name, min = 0, max = Number.MAX_SAFE_INTEGER) {
    if (!Number.isInteger(value) || value < min || value > max) fail("INTEGER_REQUIRED", name);
    return value;
  }
  function encodedBytes(value) { return new TextEncoder().encode(JSON.stringify(value)).byteLength; }
  function sortedValue(value) {
    if (Array.isArray(value)) return value.map(sortedValue);
    if (isPlainObject(value)) {
      const result = {};
      for (const key of Object.keys(value).sort()) result[key] = sortedValue(value[key]);
      return result;
    }
    return value;
  }
  function canonical(value) { return JSON.stringify(sortedValue(value)); }
  function equal(a, b) { return canonical(a) === canonical(b); }
  async function digestText(value) {
    const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(canonical(value)));
    return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
  }
  async function contentIdentity(prefix, value) { return `${prefix}_${await digestText(value)}`; }
  function withNullId(value, key) { const copy = structuredClone(value); copy[key] = null; return copy; }

  function normalizeBindingsStructure(bindings) {
    if (encodedBytes(bindings) > MAX_BINDINGS_BYTES) fail("BINDINGS_BYTE_LIMIT_EXCEEDED", String(encodedBytes(bindings)));
    exactKeys(bindings, ["schema", "bindingsId", "profileId", "protocol", "interface", "transactionRef", "seatRef", "values", "claimBoundary"]);
    if (bindings.schema !== BINDINGS_SCHEMA || bindings.profileId !== PROFILE_ID || bindings.protocol !== PLAN_PROTOCOL || bindings.interface !== INTERFACE) fail("BINDINGS_IDENTITY_INVALID", "bindings");
    sha256Value(bindings.transactionRef, "transactionRef");
    sha256Value(bindings.seatRef, "seatRef");
    if (!equal(bindings.claimBoundary, CLAIM_BOUNDARY)) fail("CLAIM_BOUNDARY_INVALID", "bindings");
    assertNoForbidden(bindings.values, "$.values");
    const values = exactKeys(bindings.values, ["availability", "adapterArtifact", "formation", "members", "modelManifest", "modelArtifacts", "performanceStart", "tokenMarks", "drop", "equivalence", "privacy", "receipts"]);

    for (const [method, key] of [
      ["markAvailability", "availability"], ["markAdapterArtifact", "adapterArtifact"], ["markFormation", "formation"],
      ["markModelManifest", "modelManifest"], ["markPerformanceStart", "performanceStart"],
      ["markEquivalence", "equivalence"], ["markPrivacyDeclaration", "privacy"],
    ]) OPERATOR.validateArgs(method, values[key]);

    if (!Array.isArray(values.members) || values.members.length < MIN_MEMBER_COUNT || values.members.length > MAX_MEMBER_COUNT) fail("MEMBER_COUNT_INVALID", String(values.members?.length));
    const aliases = new Set();
    const memberIds = new Set();
    const roleCounts = { "pipeline-input": 0, "pipeline-output": 0 };
    values.members.forEach((row, index) => {
      exactKeys(row, ["alias", "args"]);
      const alias = stringValue(row.alias, `members[${index}].alias`, ALIAS_RE);
      if (aliases.has(alias)) fail("MEMBER_ALIAS_DUPLICATE", alias);
      aliases.add(alias);
      const checked = OPERATOR.validateArgs("markMember", row.args);
      if (memberIds.has(checked.memberId)) fail("MEMBER_ID_DUPLICATE", checked.memberId);
      memberIds.add(checked.memberId);
      if (Object.prototype.hasOwnProperty.call(roleCounts, checked.role)) roleCounts[checked.role] += 1;
    });
    if (roleCounts["pipeline-input"] !== 1 || roleCounts["pipeline-output"] !== 1) fail("MEMBER_ROLE_DENOMINATOR_INVALID", JSON.stringify(roleCounts));

    if (!Array.isArray(values.modelArtifacts) || values.modelArtifacts.length < 1 || values.modelArtifacts.length > MAX_ARTIFACT_COUNT) fail("ARTIFACT_COUNT_INVALID", String(values.modelArtifacts?.length));
    let expectedLayer = 0;
    let totalBytes = 0;
    const artifactIds = new Set();
    values.modelArtifacts.forEach((row, index) => {
      exactKeys(row, ["memberAlias", "args"]);
      const alias = stringValue(row.memberAlias, `modelArtifacts[${index}].memberAlias`, ALIAS_RE);
      if (!aliases.has(alias)) fail("MEMBER_ALIAS_UNRESOLVED", alias);
      exactKeys(row.args, ["artifactId", "bytes", "digest", "layerStart", "layerEnd"]);
      if (artifactIds.has(row.args.artifactId)) fail("ARTIFACT_ID_DUPLICATE", String(row.args.artifactId));
      artifactIds.add(row.args.artifactId);
      const checked = OPERATOR.validateArgs("markModelArtifact", { ...row.args, memberIdHash: `opaque:${"0".repeat(32)}` });
      if (checked.layerStart !== expectedLayer) fail("LAYER_DENOMINATOR_NOT_CONTIGUOUS", `expected=${expectedLayer} observed=${checked.layerStart}`);
      expectedLayer = checked.layerEnd + 1;
      totalBytes += checked.bytes;
    });
    if (totalBytes !== values.formation.modelCapacityBytes) fail("FORMATION_CAPACITY_MISMATCH", `formation=${values.formation.modelCapacityBytes} artifacts=${totalBytes}`);

    if (!Array.isArray(values.tokenMarks) || values.tokenMarks.length < 1 || values.tokenMarks.length > MAX_TOKEN_MARKS) fail("TOKEN_COUNT_INVALID", String(values.tokenMarks?.length));
    let previous = null;
    values.tokenMarks.forEach((args, index) => {
      const checked = OPERATOR.validateArgs("markToken", args);
      if (checked.index !== index) fail("TOKEN_INDEX_NOT_CONTIGUOUS", `expected=${index} observed=${checked.index}`);
      if (checked.monotonicMs !== undefined && previous !== null && checked.monotonicMs < previous) fail("TOKEN_TIME_REGRESSION", String(index));
      if (checked.monotonicMs !== undefined) previous = checked.monotonicMs;
    });

    exactKeys(values.drop, ["memberAlias", "args"]);
    const dropAlias = stringValue(values.drop.memberAlias, "drop.memberAlias", ALIAS_RE);
    if (!aliases.has(dropAlias)) fail("MEMBER_ALIAS_UNRESOLVED", dropAlias);
    OPERATOR.validateArgs("markDrop", { ...values.drop.args, memberIdHash: `opaque:${"0".repeat(32)}` });
    if (values.performanceStart.startMonotonicMs !== undefined && !Number.isInteger(values.performanceStart.startMonotonicMs)) fail("MONOTONIC_TIME_INTEGER_REQUIRED", "performanceStart.startMonotonicMs");
    values.tokenMarks.forEach((mark, index) => {
      if (mark.monotonicMs !== undefined && !Number.isInteger(mark.monotonicMs)) fail("MONOTONIC_TIME_INTEGER_REQUIRED", `tokenMarks[${index}].monotonicMs`);
    });
    if (values.performanceStart.promptTokenCount !== values.equivalence.promptTokenCount) fail("PROMPT_TOKEN_DENOMINATOR_MISMATCH", "performance and equivalence");
    if (values.equivalence.outputTokenCount !== values.tokenMarks.length) fail("OUTPUT_TOKEN_DENOMINATOR_MISMATCH", "equivalence and token marks");

    if (!Array.isArray(values.receipts) || values.receipts.length !== RECEIPT_KINDS.length) fail("RECEIPT_COUNT_INVALID", String(values.receipts?.length));
    values.receipts.forEach((args, index) => {
      const checked = OPERATOR.validateArgs("markObservationReceipt", args);
      if (checked.kind !== RECEIPT_KINDS[index]) fail("RECEIPT_DENOMINATOR_INVALID", `index=${index}`);
    });
    const evidence = {
      "current-availability-observation": values.availability.evidenceRef,
      "executable-adapter-artifact": values.adapterArtifact.evidenceRef,
      "formation-capacity-receipt": values.formation.capacityReceiptRef,
      "formation-topology-receipt": values.formation.topologyReceiptRef,
      "member-drop-behavior-receipt": values.drop.args.evidenceRef,
      "model-output-equivalence-receipt": values.equivalence.evidenceRef,
      "privacy-declaration": values.privacy.evidenceRef,
    };
    values.receipts.forEach((receipt) => {
      if (evidence[receipt.kind] && evidence[receipt.kind] !== receipt.evidenceRef) fail("RECEIPT_EVIDENCE_BINDING_MISMATCH", receipt.kind);
    });
    return bindings;
  }

  function makeStep(stepId, kind, values = {}) { return { stepId, kind, ...values }; }
  function expectedSteps(bindings) {
    const values = bindings.values;
    const steps = [
      makeStep("step:status-preflight", "console-status"),
      makeStep("step:capture-preflight", "probe-call", { method: "exportCapture", literalArgs: {}, captureUse: "preflight" }),
      makeStep("step:barrier-before-execution", "operator-barrier", { code: "BEFORE_PLAN_EXECUTION", statement: "The operator has reviewed the bound transaction, seat, and complete invocation denominator." }),
      makeStep("step:availability", "probe-call", { method: "markAvailability", argsRef: "values.availability" }),
      makeStep("step:adapter-artifact", "probe-call", { method: "markAdapterArtifact", argsRef: "values.adapterArtifact" }),
      makeStep("step:formation", "probe-call", { method: "markFormation", argsRef: "values.formation" }),
    ];
    values.members.forEach((member, index) => steps.push(makeStep(`step:member-${String(index).padStart(2, "0")}`, "probe-call", { method: "markMember", argsRef: `values.members.${index}.args`, saveResultAs: member.alias })));
    steps.push(makeStep("step:model-manifest", "probe-call", { method: "markModelManifest", argsRef: "values.modelManifest" }));
    values.modelArtifacts.forEach((artifact, index) => steps.push(makeStep(`step:model-artifact-${String(index).padStart(3, "0")}`, "probe-call", { method: "markModelArtifact", argsRef: `values.modelArtifacts.${index}.args`, resultRefs: { memberIdHash: artifact.memberAlias } })));
    steps.push(makeStep("step:performance-start", "probe-call", { method: "markPerformanceStart", argsRef: "values.performanceStart" }));
    values.tokenMarks.forEach((_, index) => steps.push(makeStep(`step:token-${String(index).padStart(3, "0")}`, "probe-call", { method: "markToken", argsRef: `values.tokenMarks.${index}` })));
    steps.push(makeStep("step:controlled-drop", "probe-call", { method: "markDrop", argsRef: "values.drop.args", resultRefs: { memberIdHash: values.drop.memberAlias } }));
    steps.push(makeStep("step:equivalence", "probe-call", { method: "markEquivalence", argsRef: "values.equivalence" }));
    steps.push(makeStep("step:privacy", "probe-call", { method: "markPrivacyDeclaration", argsRef: "values.privacy" }));
    values.receipts.forEach((receipt, index) => steps.push(makeStep(`step:receipt-${String(index).padStart(2, "0")}`, "probe-call", { method: "markObservationReceipt", argsRef: `values.receipts.${index}`, receiptKind: receipt.kind })));
    steps.push(makeStep("step:peer-stats", "probe-call", { method: "samplePeerStats", literalArgs: {} }));
    steps.push(makeStep("step:barrier-before-export", "operator-barrier", { code: "BEFORE_CAPTURE_EXPORT", statement: "The operator has completed the physical observation and authorizes local private capture export." }));
    steps.push(makeStep("step:capture-export", "probe-call", { method: "exportCapture", literalArgs: {}, captureUse: "download" }));
    return steps;
  }
  async function compilePlan(bindings) {
    await validateBindings(bindings);
    const steps = expectedSteps(bindings);
    const probeInvocationCount = steps.filter((row) => row.kind === "probe-call").length;
    if (steps.length > MAX_PLAN_STEPS || probeInvocationCount > MAX_PROBE_INVOCATIONS || probeInvocationCount + 4 > OPERATOR.MAX_SESSION_REQUESTS) fail("PLAN_LIMIT_EXCEEDED", `${steps.length}/${probeInvocationCount}`);
    const plan = {
      schema: PLAN_SCHEMA,
      planId: null,
      profileId: PROFILE_ID,
      protocol: PLAN_PROTOCOL,
      operatorProtocol: OPERATOR.PROTOCOL,
      interface: INTERFACE,
      bindingsId: bindings.bindingsId,
      transactionRef: bindings.transactionRef,
      seatRef: bindings.seatRef,
      stepCount: steps.length,
      probeInvocationCount,
      steps,
      claimBoundary: CLAIM_BOUNDARY,
    };
    plan.planId = await contentIdentity("axmoperationplan", withNullId(plan, "planId"));
    return plan;
  }
  async function validateBindings(bindings) {
    normalizeBindingsStructure(bindings);
    const expected = await contentIdentity("axmoperationbindings", withNullId(bindings, "bindingsId"));
    if (bindings.bindingsId !== expected) fail("BINDINGS_CONTENT_ID_INVALID", String(bindings.bindingsId));
    return bindings;
  }
  async function validatePlan(plan, bindings) {
    if (encodedBytes(plan) > MAX_PLAN_BYTES) fail("PLAN_BYTE_LIMIT_EXCEEDED", String(encodedBytes(plan)));
    exactKeys(plan, ["schema", "planId", "profileId", "protocol", "operatorProtocol", "interface", "bindingsId", "transactionRef", "seatRef", "stepCount", "probeInvocationCount", "steps", "claimBoundary"]);
    assertNoForbidden(plan.steps, "$.steps");
    const expected = await compilePlan(bindings);
    if (!equal(plan, expected)) fail("PLAN_NOT_DETERMINISTIC", "plan differs from compiler output");
    return plan;
  }
  async function validateBundle(plan, bindings) {
    await validateBindings(bindings);
    await validatePlan(plan, bindings);
    return { status: "PASS", planId: plan.planId, bindingsId: bindings.bindingsId, stepCount: plan.stepCount, probeInvocationCount: plan.probeInvocationCount };
  }
  function resolvePath(root, path) {
    if (typeof path !== "string" || !/^values(?:\.[A-Za-z0-9_-]+|\.\d+)+$/.test(path)) fail("ARGS_REFERENCE_INVALID", String(path));
    let value = root;
    for (const part of path.split(".")) {
      if (Array.isArray(value)) {
        if (!/^\d+$/.test(part) || Number(part) >= value.length) fail("ARGS_REFERENCE_UNRESOLVED", path);
        value = value[Number(part)];
      } else if (isPlainObject(value) && Object.prototype.hasOwnProperty.call(value, part)) value = value[part];
      else fail("ARGS_REFERENCE_UNRESOLVED", path);
    }
    return structuredClone(value);
  }
  function resolveStepArgs(step, bindings, results) {
    let args;
    if (Object.prototype.hasOwnProperty.call(step, "literalArgs")) args = structuredClone(step.literalArgs);
    else args = resolvePath(bindings, step.argsRef);
    if (step.resultRefs) {
      for (const [key, alias] of Object.entries(step.resultRefs)) {
        if (!results.has(alias)) fail("RESULT_REFERENCE_UNRESOLVED", alias);
        args[key] = results.get(alias);
      }
    }
    return OPERATOR.validateArgs(step.method, args);
  }

  const api = Object.freeze({
    PROFILE_ID, PLAN_SCHEMA, BINDINGS_SCHEMA, PLAN_PROTOCOL, INTERFACE,
    CLAIM_BOUNDARY, RECEIPT_KINDS, MAX_PLAN_BYTES, MAX_BINDINGS_BYTES, MAX_PLAN_STEPS,
    PlanContractError, encodedBytes, validateBindings, validatePlan, validateBundle,
    compilePlan, resolveStepArgs,
  });
  Object.defineProperty(globalThis, "AXMOperationPlanContract", { value: api, enumerable: false, writable: false, configurable: false });
})();

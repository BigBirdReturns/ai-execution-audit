(() => {
  "use strict";

  const OPERATOR = globalThis.AXMOperatorContract;
  if (!OPERATOR || OPERATOR.PROTOCOL !== "axm-head/browser-physical-audition-operator-console@1") {
    throw new Error("the admitted operator contract is unavailable");
  }

  const PROFILE_ID = "axm-head/browser-physical-flight-choreographer/0.1";
  const PROTOCOL = "axm-head/browser-physical-flight-choreographer@1";
  const CARD_SCHEMA = "axm-head/browser-physical-flight-card@1";
  const SUPPLEMENT_SCHEMA = "axm-head/browser-physical-flight-postflight-supplement@1";
  const INTERFACE = "axm/distributed-model-inference@1";
  const MAX_CARD_BYTES = 262144;
  const MAX_SUPPLEMENT_BYTES = 131072;
  const MAX_PRIVATE_TEXT_BYTES = 65536;
  const MAX_AVAILABILITY_AGE_MS = 15 * 60 * 1000;
  const MAX_MEMBERS = 32;
  const MAX_ARTIFACTS = 200;
  const OUTPUT_TOKEN_COUNT = 1;
  const SESSION_REQUESTS_PER_INVOCATION = 2;
  const SESSION_REQUEST_RESERVE = 4;
  const SHA_RE = /^sha256:[0-9a-f]{64}$/;
  const ID_RE = /^[A-Za-z0-9][A-Za-z0-9._:@+/-]{0,191}$/;
  const ALIAS_RE = /^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$/;
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
    operationCardConstructed: true,
    operationCardExecuted: false,
    browserLaunched: false,
    supplierEndpointContacted: false,
    modelDownloaded: false,
    peerConnectionFormed: false,
    inferenceExecuted: false,
    physicalAuditionCompleted: false,
    routeTerminalProduced: false,
    namedHumanConfirmationSupplied: false,
    actualSupplierQualified: false,
    physicalEstateQualified: false,
    missionAuthority: "none",
    commandAuthority: "none",
  });
  const FORBIDDEN_KEYS = new Set([
    "supplier", "supplierRef", "endpoint", "url", "rawUrl", "hostname", "localPath",
    "credential", "credentials", "password", "secret", "prompt", "promptText",
    "completion", "completionText", "tokenText", "sdp", "iceAddress", "candidateAddress",
    "responseBody", "terminal", "authority", "missionAuthority", "commandAuthority",
    "namedHumanConfirmation",
  ]);

  class ChoreographerContractError extends Error {
    constructor(code, message) {
      super(message);
      this.name = "ChoreographerContractError";
      this.code = code;
    }
  }
  const fail = (code, message) => { throw new ChoreographerContractError(code, message); };
  const isPlainObject = (value) => {
    if (value === null || typeof value !== "object" || Array.isArray(value)) return false;
    const prototype = Object.getPrototypeOf(value);
    return prototype === Object.prototype || prototype === null;
  };
  function exactKeys(value, expected, code) {
    if (!isPlainObject(value)) fail(code, "object required");
    const wanted = new Set(expected);
    const observed = new Set(Object.keys(value));
    const missing = [...wanted].filter((key) => !observed.has(key));
    const extra = [...observed].filter((key) => !wanted.has(key));
    if (missing.length || extra.length) fail(code, `missing=${JSON.stringify(missing)} extra=${JSON.stringify(extra)}`);
    return value;
  }
  function assertNoForbidden(value, path = "$") {
    if (Array.isArray(value)) {
      if (value.length > 4096) fail("ARRAY_LIMIT_EXCEEDED", path);
      value.forEach((row, index) => assertNoForbidden(row, `${path}[${index}]`));
      return;
    }
    if (!isPlainObject(value)) return;
    for (const [key, row] of Object.entries(value)) {
      if (FORBIDDEN_KEYS.has(key)) fail("FORBIDDEN_FIELD", `${path}.${key}`);
      assertNoForbidden(row, `${path}.${key}`);
    }
  }
  function encodedBytes(value) { return new TextEncoder().encode(JSON.stringify(value)).byteLength; }
  function sortedValue(value) {
    if (Array.isArray(value)) return value.map(sortedValue);
    if (isPlainObject(value)) {
      const out = {};
      for (const key of Object.keys(value).sort()) out[key] = sortedValue(value[key]);
      return out;
    }
    return value;
  }
  function canonical(value) { return JSON.stringify(sortedValue(value)); }
  function equal(a, b) { return canonical(a) === canonical(b); }
  async function digestBytes(bytes) {
    const digest = await crypto.subtle.digest("SHA-256", bytes);
    return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
  }
  async function digestText(value) { return digestBytes(new TextEncoder().encode(value)); }
  async function contentIdentity(prefix, value) { return `${prefix}_${await digestText(canonical(value))}`; }
  function withNullId(value, key) { const copy = structuredClone(value); copy[key] = null; return copy; }
  function stringValue(value, name, pattern = null, maximum = 256) {
    if (typeof value !== "string" || value.length < 1 || value.length > maximum || /[\u0000-\u001f\u007f]/.test(value)) fail("STRING_INVALID", name);
    if (pattern && !pattern.test(value)) fail("STRING_PATTERN_INVALID", name);
    if (/^(?:https?|wss?|file):/i.test(value) || /^[A-Za-z]:[\\/]/.test(value) || /^\\\\/.test(value)) fail("RAW_COORDINATE_FORBIDDEN", name);
    if (/^(?:\d{1,3}\.){3}\d{1,3}(?::\d+)?$/.test(value)) fail("RAW_NETWORK_IDENTITY_FORBIDDEN", name);
    return value;
  }
  function shaValue(value, name) { return stringValue(value, name, SHA_RE, 71); }
  function integerValue(value, name, minimum = 0, maximum = Number.MAX_SAFE_INTEGER) {
    if (!Number.isInteger(value) || value < minimum || value > maximum) fail("INTEGER_REQUIRED", name);
    return value;
  }
  function booleanValue(value, name) { if (typeof value !== "boolean") fail("BOOLEAN_REQUIRED", name); return value; }
  function validateClaimBoundary(value, name) {
    exactKeys(value, Object.keys(CLAIM_BOUNDARY), "CLAIM_BOUNDARY_KEYS_INVALID");
    if (!equal(value, CLAIM_BOUNDARY)) fail("CLAIM_BOUNDARY_INVALID", name);
    return value;
  }

  function validateAvailability(value) {
    OPERATOR.validateArgs("markAvailability", value);
    if (value.observed !== true) fail("AVAILABILITY_NOT_OBSERVED", "availability.observed");
  }
  function validateAdapter(value) {
    OPERATOR.validateArgs("markAdapterArtifact", value);
    if (value.executableObserved !== true) fail("ADAPTER_NOT_EXECUTABLE", "adapterArtifact.executableObserved");
  }
  function validateFormation(value) {
    OPERATOR.validateArgs("markFormation", value);
    if (value.artifactBound !== true) fail("FORMATION_NOT_ARTIFACT_BOUND", "formation.artifactBound");
  }
  function validateMembers(value) {
    if (!Array.isArray(value) || value.length < 2 || value.length > MAX_MEMBERS) fail("MEMBER_COUNT_INVALID", String(value?.length));
    const aliases = new Set();
    const ids = new Set();
    const roles = { "pipeline-input": 0, "pipeline-output": 0 };
    value.forEach((row, index) => {
      exactKeys(row, ["alias", "args"], "MEMBER_KEYS_INVALID");
      const alias = stringValue(row.alias, `members[${index}].alias`, ALIAS_RE, 64);
      if (aliases.has(alias)) fail("MEMBER_ALIAS_DUPLICATE", alias);
      aliases.add(alias);
      const args = OPERATOR.validateArgs("markMember", row.args);
      if (ids.has(args.memberId)) fail("MEMBER_ID_DUPLICATE", args.memberId);
      ids.add(args.memberId);
      if (Object.prototype.hasOwnProperty.call(roles, args.role)) roles[args.role] += 1;
    });
    if (roles["pipeline-input"] !== 1 || roles["pipeline-output"] !== 1) fail("MEMBER_ROLE_DENOMINATOR_INVALID", JSON.stringify(roles));
    return aliases;
  }
  function validateArtifacts(value, aliases, capacity) {
    if (!Array.isArray(value) || value.length < 1 || value.length > MAX_ARTIFACTS) fail("ARTIFACT_COUNT_INVALID", String(value?.length));
    const ids = new Set();
    let expectedLayer = 0;
    let total = 0;
    value.forEach((row, index) => {
      exactKeys(row, ["memberAlias", "args"], "ARTIFACT_KEYS_INVALID");
      const alias = stringValue(row.memberAlias, `modelArtifacts[${index}].memberAlias`, ALIAS_RE, 64);
      if (!aliases.has(alias)) fail("MEMBER_ALIAS_UNRESOLVED", alias);
      exactKeys(row.args, ["artifactId", "bytes", "digest", "layerStart", "layerEnd"], "ARTIFACT_ARGS_KEYS_INVALID");
      if (ids.has(row.args.artifactId)) fail("ARTIFACT_ID_DUPLICATE", String(row.args.artifactId));
      ids.add(row.args.artifactId);
      const checked = OPERATOR.validateArgs("markModelArtifact", { ...row.args, memberIdHash: `opaque:${"0".repeat(32)}` });
      if (checked.layerStart !== expectedLayer) fail("LAYER_DENOMINATOR_NOT_CONTIGUOUS", `expected=${expectedLayer} observed=${checked.layerStart}`);
      expectedLayer = checked.layerEnd + 1;
      total += checked.bytes;
    });
    if (total !== capacity) fail("FORMATION_CAPACITY_MISMATCH", `formation=${capacity} artifacts=${total}`);
  }

  function probeInvocationCount(card) {
    return 21 + card.static.members.length + card.static.modelArtifacts.length;
  }
  function requiredSessionRequests(card) {
    return probeInvocationCount(card) * SESSION_REQUESTS_PER_INVOCATION + SESSION_REQUEST_RESERVE;
  }
  function normalizeCard(card) {
    exactKeys(card, ["schema", "cardId", "profileId", "protocol", "interface", "transactionRef", "seatRef", "seatId", "expectedRole", "prompt", "expectedOutput", "static", "dropTarget", "requestBudget", "claimBoundary"], "CARD_KEYS_INVALID");
    if (card.schema !== CARD_SCHEMA || card.profileId !== PROFILE_ID || card.protocol !== PROTOCOL || card.interface !== INTERFACE) fail("CARD_IDENTITY_INVALID", "card");
    shaValue(card.transactionRef, "transactionRef");
    shaValue(card.seatRef, "seatRef");
    if (!["seat-01", "seat-02"].includes(card.seatId)) fail("SEAT_ID_INVALID", String(card.seatId));
    const expectedRole = card.seatId === "seat-01" ? "pipeline-input" : "pipeline-output";
    if (card.expectedRole !== expectedRole) fail("SEAT_ROLE_MISMATCH", `${card.seatId}/${card.expectedRole}`);
    exactKeys(card.prompt, ["sha256", "encodedBytes", "tokenCount", "tokenizerEvidenceRef"], "PROMPT_KEYS_INVALID");
    shaValue(card.prompt.sha256, "prompt.sha256");
    integerValue(card.prompt.encodedBytes, "prompt.encodedBytes", 1, MAX_PRIVATE_TEXT_BYTES);
    integerValue(card.prompt.tokenCount, "prompt.tokenCount", 1, 1048576);
    shaValue(card.prompt.tokenizerEvidenceRef, "prompt.tokenizerEvidenceRef");
    exactKeys(card.expectedOutput, ["sha256", "encodedBytes", "tokenCount", "referenceEvidenceRef"], "EXPECTED_OUTPUT_KEYS_INVALID");
    shaValue(card.expectedOutput.sha256, "expectedOutput.sha256");
    integerValue(card.expectedOutput.encodedBytes, "expectedOutput.encodedBytes", 1, 256);
    if (card.expectedOutput.tokenCount !== OUTPUT_TOKEN_COUNT) fail("ONE_TOKEN_CHALLENGE_REQUIRED", String(card.expectedOutput.tokenCount));
    shaValue(card.expectedOutput.referenceEvidenceRef, "expectedOutput.referenceEvidenceRef");
    exactKeys(card.static, ["availability", "adapterArtifact", "formation", "members", "modelManifest", "modelArtifacts"], "STATIC_KEYS_INVALID");
    validateAvailability(card.static.availability);
    validateAdapter(card.static.adapterArtifact);
    validateFormation(card.static.formation);
    const aliases = validateMembers(card.static.members);
    OPERATOR.validateArgs("markModelManifest", card.static.modelManifest);
    validateArtifacts(card.static.modelArtifacts, aliases, card.static.formation.modelCapacityBytes);
    exactKeys(card.dropTarget, ["memberAlias"], "DROP_TARGET_KEYS_INVALID");
    const dropAlias = stringValue(card.dropTarget.memberAlias, "dropTarget.memberAlias", ALIAS_RE, 64);
    if (!aliases.has(dropAlias)) fail("DROP_MEMBER_ALIAS_UNRESOLVED", dropAlias);
    exactKeys(card.requestBudget, ["probeInvocationCount", "sessionRequestCount", "sessionRequestCeiling", "sessionRequestsPerProbeInvocation", "sessionRequestReserve"], "REQUEST_BUDGET_KEYS_INVALID");
    const expectedBudget = {
      probeInvocationCount: probeInvocationCount(card),
      sessionRequestCount: requiredSessionRequests(card),
      sessionRequestCeiling: OPERATOR.MAX_SESSION_REQUESTS,
      sessionRequestsPerProbeInvocation: SESSION_REQUESTS_PER_INVOCATION,
      sessionRequestReserve: SESSION_REQUEST_RESERVE,
    };
    if (!equal(card.requestBudget, expectedBudget)) fail("REQUEST_BUDGET_INVALID", JSON.stringify(card.requestBudget));
    if (expectedBudget.sessionRequestCount > OPERATOR.MAX_SESSION_REQUESTS) fail("SESSION_REQUEST_LIMIT_EXCEEDED", String(expectedBudget.sessionRequestCount));
    validateClaimBoundary(card.claimBoundary, "card");
    assertNoForbidden(card.static, "$.static");
    return card;
  }
  async function validateCard(card) {
    if (encodedBytes(card) > MAX_CARD_BYTES) fail("CARD_BYTE_LIMIT_EXCEEDED", String(encodedBytes(card)));
    normalizeCard(card);
    const expected = await contentIdentity("axmphysicalflightcard", withNullId(card, "cardId"));
    if (card.cardId !== expected) fail("CARD_CONTENT_ID_INVALID", String(card.cardId));
    return card;
  }
  function normalizeSupplement(value, card) {
    exactKeys(value, ["schema", "supplementId", "profileId", "protocol", "interface", "cardId", "transactionRef", "seatRef", "outputEvidenceRef", "drop", "privacy", "receipts", "claimBoundary"], "SUPPLEMENT_KEYS_INVALID");
    if (value.schema !== SUPPLEMENT_SCHEMA || value.profileId !== PROFILE_ID || value.protocol !== PROTOCOL || value.interface !== INTERFACE) fail("SUPPLEMENT_IDENTITY_INVALID", "supplement");
    if (value.cardId !== card.cardId || value.transactionRef !== card.transactionRef || value.seatRef !== card.seatRef) fail("SUPPLEMENT_CARD_BINDING_INVALID", "supplement");
    shaValue(value.outputEvidenceRef, "outputEvidenceRef");
    exactKeys(value.drop, ["observedTerminal", "recovered", "evidenceRef", "controlled"], "DROP_KEYS_INVALID");
    OPERATOR.validateArgs("markDrop", { memberIdHash: `opaque:${"0".repeat(32)}`, ...value.drop });
    if (value.drop.controlled !== true) fail("DROP_CONTROL_INVALID", "drop.controlled");
    exactKeys(value.privacy, ["scope", "evidenceRef", "claimsEndToEndConfidentiality"], "PRIVACY_KEYS_INVALID");
    OPERATOR.validateArgs("markPrivacyDeclaration", value.privacy);
    if (value.privacy.scope !== "browser-observed-network-surface-only" || value.privacy.claimsEndToEndConfidentiality !== false) fail("PRIVACY_SCOPE_INVALID", "privacy");
    if (!Array.isArray(value.receipts) || value.receipts.length !== RECEIPT_KINDS.length) fail("RECEIPT_COUNT_INVALID", String(value.receipts?.length));
    value.receipts.forEach((row, index) => {
      const checked = OPERATOR.validateArgs("markObservationReceipt", row);
      if (checked.kind !== RECEIPT_KINDS[index]) fail("RECEIPT_ORDER_INVALID", String(index));
    });
    const expectedRefs = {
      "current-availability-observation": card.static.availability.evidenceRef,
      "executable-adapter-artifact": card.static.adapterArtifact.evidenceRef,
      "formation-capacity-receipt": card.static.formation.capacityReceiptRef,
      "formation-topology-receipt": card.static.formation.topologyReceiptRef,
      "member-drop-behavior-receipt": value.drop.evidenceRef,
      "model-output-equivalence-receipt": value.outputEvidenceRef,
      "privacy-declaration": value.privacy.evidenceRef,
    };
    value.receipts.forEach((row) => {
      if (expectedRefs[row.kind] && row.evidenceRef !== expectedRefs[row.kind]) fail("RECEIPT_EVIDENCE_BINDING_MISMATCH", row.kind);
    });
    validateClaimBoundary(value.claimBoundary, "supplement");
    assertNoForbidden({ drop: value.drop, privacy: value.privacy, receipts: value.receipts }, "$.postflight");
    return value;
  }
  async function validateSupplement(value, card) {
    await validateCard(card);
    if (encodedBytes(value) > MAX_SUPPLEMENT_BYTES) fail("SUPPLEMENT_BYTE_LIMIT_EXCEEDED", String(encodedBytes(value)));
    normalizeSupplement(value, card);
    const expected = await contentIdentity("axmphysicalflightpostflight", withNullId(value, "supplementId"));
    if (value.supplementId !== expected) fail("SUPPLEMENT_CONTENT_ID_INVALID", String(value.supplementId));
    return value;
  }
  function staticInvocations(card) {
    const rows = [
      { method: "exportCapture", args: {}, captureUse: "preflight" },
      { method: "markAvailability", args: structuredClone(card.static.availability) },
      { method: "markAdapterArtifact", args: structuredClone(card.static.adapterArtifact) },
      { method: "markFormation", args: structuredClone(card.static.formation) },
    ];
    card.static.members.forEach((member) => rows.push({ method: "markMember", args: structuredClone(member.args), saveResultAs: member.alias }));
    rows.push({ method: "markModelManifest", args: structuredClone(card.static.modelManifest) });
    card.static.modelArtifacts.forEach((artifact) => rows.push({ method: "markModelArtifact", args: structuredClone(artifact.args), memberAlias: artifact.memberAlias }));
    return rows;
  }
  function postflightInvocations(card, supplement, candidateDigest, resultRefs) {
    if (!SHA_RE.test(candidateDigest)) fail("CANDIDATE_DIGEST_INVALID", String(candidateDigest));
    const memberIdHash = resultRefs.get(card.dropTarget.memberAlias);
    if (!memberIdHash) fail("DROP_MEMBER_RESULT_UNRESOLVED", card.dropTarget.memberAlias);
    const rows = [
      { method: "markDrop", args: { memberIdHash, ...structuredClone(supplement.drop) } },
      { method: "markPrivacyDeclaration", args: structuredClone(supplement.privacy) },
    ];
    supplement.receipts.forEach((row) => rows.push({ method: "markObservationReceipt", args: structuredClone(row) }));
    rows.push({ method: "samplePeerStats", args: {} });
    return rows;
  }

  const api = Object.freeze({
    PROFILE_ID, PROTOCOL, CARD_SCHEMA, SUPPLEMENT_SCHEMA, INTERFACE, RECEIPT_KINDS,
    CLAIM_BOUNDARY, OUTPUT_TOKEN_COUNT, MAX_AVAILABILITY_AGE_MS, MAX_SUPPLEMENT_BYTES, SESSION_REQUESTS_PER_INVOCATION, SESSION_REQUEST_RESERVE,
    ChoreographerContractError, encodedBytes, digestBytes, validateCard, validateSupplement,
    probeInvocationCount, requiredSessionRequests, staticInvocations, postflightInvocations,
  });
  Object.defineProperty(globalThis, "AXMPhysicalFlightChoreographerContract", {
    value: api, enumerable: false, writable: false, configurable: false,
  });
})();

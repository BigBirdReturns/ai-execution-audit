(() => {
  "use strict";

  if (Object.prototype.hasOwnProperty.call(globalThis, "__AXM_AUDITION__")) {
    return;
  }

  const DEFAULT_EVENT_LIMIT = 4096;
  const DEFAULT_BYTE_LIMIT = 1048576;
  const config = Object.freeze({
    eventLimit: Number.isInteger(globalThis.__AXM_AUDITION_CONFIG__?.eventLimit)
      ? globalThis.__AXM_AUDITION_CONFIG__.eventLimit
      : DEFAULT_EVENT_LIMIT,
    byteLimit: Number.isInteger(globalThis.__AXM_AUDITION_CONFIG__?.byteLimit)
      ? globalThis.__AXM_AUDITION_CONFIG__.byteLimit
      : DEFAULT_BYTE_LIMIT,
  });

  const encoder = new TextEncoder();
  const installedAt = performance.now();
  const installedBeforeApplication = document.readyState === "loading";
  const events = [];
  const peerConnections = new Set();
  const channels = new Set();
  const members = new Map();
  const artifacts = [];
  const tokenMarks = [];
  const drops = [];
  const equivalenceMarks = [];
  const privacyDeclarations = [];
  let encodedBytes = 0;
  let refused = null;

  const opaqueIds = new Map();

  function randomOpaqueId() {
    const words = new Uint32Array(4);
    crypto.getRandomValues(words);
    return `opaque:${Array.from(words, (value) => value.toString(16).padStart(8, "0")).join("")}`;
  }

  function opaqueHash(value) {
    const key = String(value ?? "");
    if (!opaqueIds.has(key)) {
      opaqueIds.set(key, randomOpaqueId());
    }
    return opaqueIds.get(key);
  }

  function monotonicMs() {
    return Number(performance.now().toFixed(3));
  }

  function byteLength(value) {
    return encoder.encode(JSON.stringify(value)).byteLength;
  }

  function record(type, body = {}) {
    if (refused !== null) {
      return false;
    }
    const row = Object.freeze({ type, monotonicMs: monotonicMs(), ...body });
    const nextBytes = encodedBytes + byteLength(row);
    if (events.length + 1 > config.eventLimit) {
      refused = "CAPTURE_EVENT_CEILING_EXCEEDED";
      return false;
    }
    if (nextBytes > config.byteLimit) {
      refused = "CAPTURE_BYTE_CEILING_EXCEEDED";
      return false;
    }
    events.push(row);
    encodedBytes = nextBytes;
    return true;
  }

  function endpointSummary(input) {
    try {
      const parsed = new URL(String(input), location.href);
      return {
        scheme: parsed.protocol.replace(":", ""),
        endpointHash: opaqueHash(`${parsed.protocol}//${parsed.host}${parsed.pathname}`),
      };
    } catch {
      return { scheme: "unparsed", endpointHash: opaqueHash(input) };
    }
  }

  function payloadBytes(value) {
    if (typeof value === "string") {
      return encoder.encode(value).byteLength;
    }
    if (value instanceof ArrayBuffer) {
      return value.byteLength;
    }
    if (ArrayBuffer.isView(value)) {
      return value.byteLength;
    }
    if (value instanceof Blob) {
      return value.size;
    }
    return 0;
  }

  function wrapDataChannel(channel, origin) {
    if (!channel || channels.has(channel)) {
      return channel;
    }
    channels.add(channel);
    const channelIdHash = opaqueHash(`${origin}:${channel.label}:${channels.size}`);
    record("rtc-data-channel", {
      channelIdHash,
      origin,
      ordered: channel.ordered === true,
      maxRetransmits: channel.maxRetransmits ?? null,
      maxPacketLifeTime: channel.maxPacketLifeTime ?? null,
      protocolHash: opaqueHash(channel.protocol || ""),
    });

    const originalSend = channel.send.bind(channel);
    channel.send = function auditedSend(data) {
      record("rtc-data-channel-send", {
        channelIdHash,
        bytes: payloadBytes(data),
      });
      return originalSend(data);
    };
    channel.addEventListener("message", (event) => {
      record("rtc-data-channel-receive", {
        channelIdHash,
        bytes: payloadBytes(event.data),
      });
    });
    channel.addEventListener("open", () => record("rtc-data-channel-state", { channelIdHash, state: "open" }));
    channel.addEventListener("close", () => record("rtc-data-channel-state", { channelIdHash, state: "closed" }));
    channel.addEventListener("error", () => record("rtc-data-channel-state", { channelIdHash, state: "error" }));
    return channel;
  }

  function installFetchObserver() {
    if (typeof globalThis.fetch !== "function") {
      return;
    }
    const originalFetch = globalThis.fetch.bind(globalThis);
    globalThis.fetch = async function auditedFetch(input, init = undefined) {
      const requestLike = input instanceof Request ? input : null;
      const target = requestLike ? requestLike.url : input;
      const summary = endpointSummary(target);
      const method = String(init?.method || requestLike?.method || "GET").toUpperCase();
      const startedAt = monotonicMs();
      record("fetch-start", { ...summary, method });
      try {
        const response = await originalFetch(input, init);
        const lengthHeader = response.headers.get("content-length");
        const declaredBytes = lengthHeader && /^\d+$/.test(lengthHeader) ? Number(lengthHeader) : null;
        record("fetch-complete", {
          ...summary,
          method,
          status: response.status,
          declaredBytes,
          elapsedMs: Number((monotonicMs() - startedAt).toFixed(3)),
        });
        return response;
      } catch (error) {
        record("fetch-failed", {
          ...summary,
          method,
          errorClass: error?.constructor?.name || "Error",
          elapsedMs: Number((monotonicMs() - startedAt).toFixed(3)),
        });
        throw error;
      }
    };
  }

  function installWebSocketObserver() {
    const NativeWebSocket = globalThis.WebSocket;
    if (typeof NativeWebSocket !== "function") {
      return;
    }
    class AuditedWebSocket extends NativeWebSocket {
      constructor(endpoint, protocols) {
        super(endpoint, protocols);
        const summary = endpointSummary(endpoint);
        const socketIdHash = opaqueHash(`${summary.endpointHash}:${monotonicMs()}`);
        record("websocket-create", {
          ...summary,
          socketIdHash,
          protocolCount: Array.isArray(protocols) ? protocols.length : protocols ? 1 : 0,
        });
        this.addEventListener("open", () => record("websocket-state", { socketIdHash, state: "open" }));
        this.addEventListener("close", (event) =>
          record("websocket-state", { socketIdHash, state: "closed", code: event.code })
        );
        this.addEventListener("error", () => record("websocket-state", { socketIdHash, state: "error" }));
        this.addEventListener("message", (event) =>
          record("websocket-receive", { socketIdHash, bytes: payloadBytes(event.data) })
        );
        const nativeSend = this.send.bind(this);
        this.send = (data) => {
          record("websocket-send", { socketIdHash, bytes: payloadBytes(data) });
          return nativeSend(data);
        };
      }
    }
    Object.defineProperties(AuditedWebSocket, {
      CONNECTING: { value: NativeWebSocket.CONNECTING },
      OPEN: { value: NativeWebSocket.OPEN },
      CLOSING: { value: NativeWebSocket.CLOSING },
      CLOSED: { value: NativeWebSocket.CLOSED },
    });
    globalThis.WebSocket = AuditedWebSocket;
  }

  function installEventSourceObserver() {
    const NativeEventSource = globalThis.EventSource;
    if (typeof NativeEventSource !== "function") {
      return;
    }
    globalThis.EventSource = class AuditedEventSource extends NativeEventSource {
      constructor(endpoint, options) {
        super(endpoint, options);
        const summary = endpointSummary(endpoint);
        const sourceIdHash = opaqueHash(`${summary.endpointHash}:${monotonicMs()}`);
        record("eventsource-create", { ...summary, sourceIdHash });
        this.addEventListener("open", () => record("eventsource-state", { sourceIdHash, state: "open" }));
        this.addEventListener("error", () => record("eventsource-state", { sourceIdHash, state: "error" }));
        this.addEventListener("message", (event) =>
          record("eventsource-receive", { sourceIdHash, bytes: payloadBytes(event.data) })
        );
      }
    };
  }

  function installCacheObserver() {
    if (typeof globalThis.Cache !== "function") {
      return;
    }
    const prototype = globalThis.Cache.prototype;
    const nativeMatch = prototype.match;
    const nativePut = prototype.put;
    const nativeAdd = prototype.add;
    const nativeAddAll = prototype.addAll;

    if (typeof nativeMatch === "function") {
      prototype.match = async function auditedCacheMatch(request, options = undefined) {
        const summary = endpointSummary(request instanceof Request ? request.url : request);
        const response = await nativeMatch.call(this, request, options);
        record("cache-match", { ...summary, hit: response !== undefined });
        return response;
      };
    }
    if (typeof nativePut === "function") {
      prototype.put = async function auditedCachePut(request, response) {
        const summary = endpointSummary(request instanceof Request ? request.url : request);
        const declared = response?.headers?.get?.("content-length");
        record("cache-put", {
          ...summary,
          declaredBytes: declared && /^\d+$/.test(declared) ? Number(declared) : null,
        });
        return nativePut.call(this, request, response);
      };
    }
    if (typeof nativeAdd === "function") {
      prototype.add = function auditedCacheAdd(request) {
        record("cache-add", endpointSummary(request instanceof Request ? request.url : request));
        return nativeAdd.call(this, request);
      };
    }
    if (typeof nativeAddAll === "function") {
      prototype.addAll = function auditedCacheAddAll(requests) {
        record("cache-add-all", { requestCount: Array.from(requests || []).length });
        return nativeAddAll.call(this, requests);
      };
    }
  }

  function installIndexedDbObserver() {
    const factory = globalThis.indexedDB;
    if (!factory || typeof factory.open !== "function") {
      return;
    }
    const nativeOpen = factory.open.bind(factory);
    factory.open = function auditedIndexedDbOpen(name, version = undefined) {
      const databaseIdHash = opaqueHash(name);
      record("indexeddb-open", { databaseIdHash, version: version ?? null });
      const request = version === undefined ? nativeOpen(name) : nativeOpen(name, version);
      request.addEventListener("upgradeneeded", () =>
        record("indexeddb-state", { databaseIdHash, state: "upgradeneeded" })
      );
      request.addEventListener("success", () =>
        record("indexeddb-state", {
          databaseIdHash,
          state: "open",
          objectStoreCount: request.result?.objectStoreNames?.length ?? 0,
        })
      );
      request.addEventListener("error", () =>
        record("indexeddb-state", { databaseIdHash, state: "error" })
      );
      return request;
    };

    const databasePrototype = globalThis.IDBDatabase?.prototype;
    if (databasePrototype && typeof databasePrototype.transaction === "function") {
      const nativeTransaction = databasePrototype.transaction;
      databasePrototype.transaction = function auditedTransaction(storeNames, mode = "readonly", options = undefined) {
        const names = typeof storeNames === "string" ? [storeNames] : Array.from(storeNames || []);
        record("indexeddb-transaction", {
          objectStoreHashes: names.map(opaqueHash).sort(),
          mode: String(mode),
        });
        return nativeTransaction.call(this, storeNames, mode, options);
      };
    }
  }

  function installRtcObserver() {
    const NativePeerConnection = globalThis.RTCPeerConnection;
    if (typeof NativePeerConnection !== "function") {
      return;
    }
    globalThis.RTCPeerConnection = class AuditedPeerConnection extends NativePeerConnection {
      constructor(configuration = undefined) {
        super(configuration);
        const peerIdHash = opaqueHash(`peer:${peerConnections.size}:${monotonicMs()}`);
        peerConnections.add(this);
        Object.defineProperty(this, "__axmPeerIdHash", { value: peerIdHash });
        record("rtc-peer-create", {
          peerIdHash,
          iceServerCount: Array.isArray(configuration?.iceServers) ? configuration.iceServers.length : 0,
          bundlePolicy: configuration?.bundlePolicy || null,
          rtcpMuxPolicy: configuration?.rtcpMuxPolicy || null,
        });
        this.addEventListener("connectionstatechange", () =>
          record("rtc-peer-state", { peerIdHash, dimension: "connection", state: this.connectionState })
        );
        this.addEventListener("iceconnectionstatechange", () =>
          record("rtc-peer-state", { peerIdHash, dimension: "ice", state: this.iceConnectionState })
        );
        this.addEventListener("icegatheringstatechange", () =>
          record("rtc-peer-state", { peerIdHash, dimension: "gathering", state: this.iceGatheringState })
        );
        this.addEventListener("datachannel", (event) => wrapDataChannel(event.channel, "remote"));
      }

      createDataChannel(label, options = undefined) {
        const channel = super.createDataChannel(label, options);
        return wrapDataChannel(channel, "local");
      }
    };
  }

  function installWebGpuObserver() {
    const gpu = navigator.gpu;
    if (!gpu || typeof gpu.requestAdapter !== "function") {
      record("webgpu-unavailable");
      return;
    }
    const nativeRequestAdapter = gpu.requestAdapter.bind(gpu);
    gpu.requestAdapter = async function auditedRequestAdapter(options = undefined) {
      const requestedAt = monotonicMs();
      const adapter = await nativeRequestAdapter(options);
      record("webgpu-adapter", {
        available: adapter !== null,
        powerPreference: options?.powerPreference || null,
        forceFallbackAdapter: options?.forceFallbackAdapter === true,
        elapsedMs: Number((monotonicMs() - requestedAt).toFixed(3)),
      });
      if (!adapter || typeof adapter.requestDevice !== "function") {
        return adapter;
      }
      const nativeRequestDevice = adapter.requestDevice.bind(adapter);
      adapter.requestDevice = async function auditedRequestDevice(descriptor = undefined) {
        const deviceRequestedAt = monotonicMs();
        const device = await nativeRequestDevice(descriptor);
        record("webgpu-device", {
          requiredFeatureCount: descriptor?.requiredFeatures?.length || 0,
          requiredLimitCount: descriptor?.requiredLimits
            ? Object.keys(descriptor.requiredLimits).length
            : 0,
          elapsedMs: Number((monotonicMs() - deviceRequestedAt).toFixed(3)),
        });
        device.lost.then((info) =>
          record("webgpu-device-lost", {
            reason: info.reason || "unknown",
            messageHash: opaqueHash(info.message || ""),
          })
        );
        return device;
      };
      return adapter;
    };
  }

  async function samplePeerStats() {
    const snapshots = [];
    for (const peer of peerConnections) {
      const peerIdHash = peer.__axmPeerIdHash || opaqueHash("unknown-peer");
      const report = await peer.getStats();
      let selectedPair = null;
      const candidates = new Map();
      report.forEach((row) => {
        if (row.type === "local-candidate" || row.type === "remote-candidate") {
          candidates.set(row.id, {
            candidateType: row.candidateType || null,
            protocol: row.protocol || null,
          });
        }
      });
      report.forEach((row) => {
        if (row.type === "candidate-pair" && row.state === "succeeded" && row.nominated) {
          const local = candidates.get(row.localCandidateId) || {};
          const remote = candidates.get(row.remoteCandidateId) || {};
          selectedPair = {
            localCandidateType: local.candidateType || null,
            remoteCandidateType: remote.candidateType || null,
            protocol: local.protocol || remote.protocol || null,
            bytesSent: Number.isFinite(row.bytesSent) ? row.bytesSent : 0,
            bytesReceived: Number.isFinite(row.bytesReceived) ? row.bytesReceived : 0,
            currentRoundTripTime: Number.isFinite(row.currentRoundTripTime)
              ? row.currentRoundTripTime
              : null,
          };
        }
      });
      const snapshot = { peerIdHash, selectedPair };
      snapshots.push(snapshot);
      record("rtc-stats", snapshot);
    }
    return snapshots;
  }

  function markAvailability({ observedAtUnixMs, evidenceRef, observed = true }) {
    const row = Object.freeze({
      observed: observed === true,
      observedAtUnixMs: Number(observedAtUnixMs),
      evidenceRef: String(evidenceRef),
    });
    record("availability-observation", row);
  }

  function markAdapterArtifact({ artifactBytes, artifactDigest, evidenceRef, executableObserved = true }) {
    const row = Object.freeze({
      artifactBytes: Number(artifactBytes),
      artifactDigest: String(artifactDigest),
      evidenceRef: String(evidenceRef),
      executableObserved: executableObserved === true,
    });
    record("adapter-artifact", row);
  }

  function markFormation({
    artifactBound,
    capacityBasis,
    capacityReceiptRef,
    modelCapacityBytes,
    partitionMode,
    topologyReceiptRef,
  }) {
    const row = Object.freeze({
      artifactBound: artifactBound === true,
      capacityBasis: String(capacityBasis),
      capacityReceiptRef: String(capacityReceiptRef),
      modelCapacityBytes: Number(modelCapacityBytes),
      partitionMode: String(partitionMode),
      topologyReceiptRef: String(topologyReceiptRef),
    });
    record("formation-declaration", row);
  }

  function markModelManifest({ claimedId, boundModelId, observedManifestDigest }) {
    const row = Object.freeze({
      claimedId: String(claimedId),
      boundModelId: String(boundModelId),
      observedManifestDigest: String(observedManifestDigest),
    });
    record("model-manifest", row);
  }

  function markPerformanceStart({ promptTokenCount, startMonotonicMs = undefined }) {
    const row = Object.freeze({
      promptTokenCount: Number(promptTokenCount),
      startMonotonicMs: startMonotonicMs === undefined ? monotonicMs() : Number(startMonotonicMs),
    });
    record("performance-start", row);
  }

  function markObservationReceipt({ kind, evidenceRef }) {
    const row = Object.freeze({ kind: String(kind), evidenceRef: String(evidenceRef) });
    record("observation-receipt-ref", row);
  }

  function markMember({ memberId, role, pledgedBytes }) {
    const memberIdHash = opaqueHash(memberId);
    const row = Object.freeze({ memberIdHash, role: String(role), pledgedBytes: Number(pledgedBytes) });
    members.set(memberIdHash, row);
    record("formation-member", row);
    return memberIdHash;
  }

  function markModelArtifact({
    artifactId,
    bytes,
    digest,
    layerStart,
    layerEnd,
    memberIdHash,
  }) {
    const row = Object.freeze({
      artifactIdHash: opaqueHash(artifactId),
      artifactBytes: Number(bytes),
      artifactDigest: String(digest),
      layerStart: Number(layerStart),
      layerEnd: Number(layerEnd),
      memberIdHash: String(memberIdHash),
    });
    artifacts.push(row);
    record("model-artifact", row);
  }

  function markToken({ index, monotonicMs: suppliedTime = undefined }) {
    const row = Object.freeze({
      index: Number(index),
      monotonicMs: suppliedTime === undefined ? monotonicMs() : Number(suppliedTime),
    });
    tokenMarks.push(row);
    record("token-mark", row);
  }

  function markDrop({ memberIdHash, observedTerminal, recovered, evidenceRef, controlled = true }) {
    const row = Object.freeze({
      memberIdHash: String(memberIdHash),
      observedTerminal: String(observedTerminal),
      recovered: recovered === true,
      controlled: controlled === true,
      evidenceRef: String(evidenceRef),
    });
    drops.push(row);
    record("member-drop", row);
  }

  function markEquivalence({
    referenceDigest,
    candidateDigest,
    promptTokenCount,
    outputTokenCount,
    evidenceRef,
  }) {
    const row = Object.freeze({
      referenceDigest: String(referenceDigest),
      candidateDigest: String(candidateDigest),
      promptTokenCount: Number(promptTokenCount),
      outputTokenCount: Number(outputTokenCount),
      match: String(referenceDigest) === String(candidateDigest),
      evidenceRef: String(evidenceRef),
    });
    equivalenceMarks.push(row);
    record("output-equivalence", row);
  }

  function markPrivacyDeclaration({ scope, evidenceRef, claimsEndToEndConfidentiality = false }) {
    const row = Object.freeze({
      scope: String(scope),
      evidenceRef: String(evidenceRef),
      claimsEndToEndConfidentiality: claimsEndToEndConfidentiality === true,
    });
    privacyDeclarations.push(row);
    record("privacy-declaration", row);
  }

  function exportCapture() {
    return structuredClone({
      schema: "axm-head/browser-probe-private-capture@1",
      installedAtMonotonicMs: installedAt,
      installedBeforeApplication,
      limits: { events: config.eventLimit, encodedBytes: config.byteLimit },
      observed: { eventCount: events.length, encodedBytes },
      refused,
      events,
      summaries: {
        memberCount: members.size,
        members: [...members.values()],
        artifactCount: artifacts.length,
        artifacts,
        tokenMarks,
        drops,
        equivalenceMarks,
        privacyDeclarations,
        peerConnectionCount: peerConnections.size,
        dataChannelCount: channels.size,
      },
    });
  }

  installFetchObserver();
  installWebSocketObserver();
  installEventSourceObserver();
  installCacheObserver();
  installIndexedDbObserver();
  installRtcObserver();
  installWebGpuObserver();
  record("probe-installed", { installedBeforeApplication });

  const api = Object.freeze({
    version: "1",
    markAvailability,
    markAdapterArtifact,
    markFormation,
    markMember,
    markModelManifest,
    markModelArtifact,
    markPerformanceStart,
    markToken,
    markDrop,
    markEquivalence,
    markPrivacyDeclaration,
    markObservationReceipt,
    samplePeerStats,
    exportCapture,
  });
  Object.defineProperty(globalThis, "__AXM_AUDITION__", {
    value: api,
    enumerable: false,
    writable: false,
    configurable: false,
  });
})();

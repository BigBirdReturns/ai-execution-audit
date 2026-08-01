import {
  createHash,
  createPrivateKey,
  createPublicKey,
  sign as signMessage,
  verify as verifyMessage,
} from 'node:crypto';
import {
  appendFileSync,
  closeSync,
  existsSync,
  fsyncSync,
  openSync,
  readFileSync,
  truncateSync,
  unlinkSync,
  writeFileSync,
} from 'node:fs';
import { dirname } from 'node:path';
import { mkdirSync } from 'node:fs';
import {
  canonicalJson,
  deriveAuthorityId,
  evaluateCandidateAuthority,
} from './authority_gate.mjs';

const ZERO_RECORD = '0'.repeat(64);
const MAX_CLOCK_SKEW_MS = 5_000;
const LINK_STATES = new Set(['up', 'down', 'degraded', 'unknown']);
const EXPIRY_DISPOSITIONS = new Set(['safe_state', 'hold', 'refuse']);

class PartitionError extends Error {
  constructor(code, message) {
    super(message);
    this.name = 'PartitionError';
    this.code = code;
  }
}

function requireCondition(condition, code, message) {
  if (!condition) throw new PartitionError(code, message);
}

function isRecord(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function digest(prefix, value) {
  return `${prefix}_${createHash('sha256').update(canonicalJson(value), 'utf8').digest('hex')}`;
}

function parseTime(value, code, label) {
  const milliseconds = Date.parse(value);
  requireCondition(Number.isFinite(milliseconds), code, `${label} is not a valid date-time`);
  return milliseconds;
}

function iso(milliseconds) {
  return new Date(milliseconds).toISOString();
}

function sortedUniqueStrings(value, code, label) {
  requireCondition(Array.isArray(value), code, `${label} must be an array`);
  const rows = value.map((row) => {
    requireCondition(typeof row === 'string' && row.trim(), code, `${label} entries must be strings`);
    return row.trim();
  });
  requireCondition(new Set(rows).size === rows.length, code, `${label} entries must be unique`);
  return [...rows].sort();
}

function clone(value) {
  return structuredClone(value);
}

function signedAuthorityBody(authority) {
  const { signature: _signature, ...body } = authority;
  return body;
}

function authorityIdentityBody(authority) {
  const { authorityId: _authorityId, signature: _signature, ...body } = authority;
  return body;
}

function findTrustedAuthorityKey(authority, trustStore) {
  requireCondition(
    isRecord(trustStore) && trustStore.schema === 'axm-authority-trust/1' && Array.isArray(trustStore.keys),
    'AUTHORITY_TRUST_INVALID',
    'authority trust store is invalid',
  );
  return trustStore.keys.find((row) =>
    isRecord(row)
    && row.keyId === authority.signature?.keyId
    && row.issuer === authority.issuer
    && row.algorithm === 'Ed25519'
  );
}

export function verifyPartitionAuthority(authority, trustStore) {
  requireCondition(
    isRecord(authority) && authority.schema === 'axm-command-authority/1',
    'AUTHORITY_SCHEMA_INVALID',
    'authority schema is invalid',
  );
  requireCondition(
    authority.subject === 'polybolos-command-candidate',
    'AUTHORITY_SUBJECT_INVALID',
    'authority subject does not cover candidate evaluation',
  );
  requireCondition(
    authority.authorityId === deriveAuthorityId(authority),
    'AUTHORITY_IDENTITY_INVALID',
    'authority identity does not match its contents',
  );
  requireCondition(
    isRecord(authority.signature)
      && authority.signature.algorithm === 'Ed25519'
      && typeof authority.signature.value === 'string',
    'AUTHORITY_SIGNATURE_INVALID',
    'authority signature metadata is invalid',
  );
  const key = findTrustedAuthorityKey(authority, trustStore);
  requireCondition(key && typeof key.publicKeyPem === 'string', 'AUTHORITY_KEY_UNTRUSTED', 'authority key is untrusted');
  let valid = false;
  try {
    valid = verifyMessage(
      null,
      Buffer.from(canonicalJson(signedAuthorityBody(authority)), 'utf8'),
      createPublicKey(key.publicKeyPem),
      Buffer.from(authority.signature.value, 'base64'),
    );
  } catch {
    valid = false;
  }
  requireCondition(valid, 'AUTHORITY_SIGNATURE_INVALID', 'authority signature did not verify');
  validatePartitionPolicy(authority.partitionPolicy);
  return authority;
}

function validatePartitionPolicy(policy) {
  requireCondition(isRecord(policy), 'PARTITION_POLICY_INVALID', 'partitionPolicy must be an object');
  const links = sortedUniqueStrings(policy.links, 'PARTITION_POLICY_INVALID', 'partitionPolicy.links');
  requireCondition(links.length > 0 && links.length <= 64, 'PARTITION_POLICY_INVALID', 'partitionPolicy.links is unbounded');
  requireCondition(Array.isArray(policy.profiles) && policy.profiles.length > 0, 'PARTITION_POLICY_INVALID', 'partition profiles are missing');

  const profileIds = new Set();
  let connectedProfiles = 0;
  for (const profile of policy.profiles) {
    requireCondition(isRecord(profile), 'PARTITION_POLICY_INVALID', 'partition profile must be an object');
    requireCondition(typeof profile.id === 'string' && profile.id.trim(), 'PARTITION_POLICY_INVALID', 'profile id is missing');
    requireCondition(!profileIds.has(profile.id), 'PARTITION_POLICY_INVALID', `duplicate profile ${profile.id}`);
    profileIds.add(profile.id);
    requireCondition(typeof profile.partition === 'boolean', 'PARTITION_POLICY_INVALID', `profile ${profile.id} partition flag is invalid`);
    if (!profile.partition) connectedProfiles += 1;
    requireCondition(isRecord(profile.states), 'PARTITION_POLICY_INVALID', `profile ${profile.id} states are missing`);
    const stateKeys = Object.keys(profile.states).sort();
    requireCondition(
      canonicalJson(stateKeys) === canonicalJson(links),
      'PARTITION_POLICY_INVALID',
      `profile ${profile.id} does not define the exact link set`,
    );
    for (const [link, state] of Object.entries(profile.states)) {
      requireCondition(LINK_STATES.has(state), 'PARTITION_POLICY_INVALID', `profile ${profile.id} has invalid state for ${link}`);
    }
    sortedUniqueStrings(
      profile.allowedActionClasses,
      'PARTITION_POLICY_INVALID',
      `profile ${profile.id}.allowedActionClasses`,
    );
    requireCondition(
      Number.isInteger(profile.maxOfflineMs) && profile.maxOfflineMs >= 0,
      'PARTITION_POLICY_INVALID',
      `profile ${profile.id} maxOfflineMs is invalid`,
    );
    requireCondition(
      typeof profile.requiresLocalOperator === 'boolean',
      'PARTITION_POLICY_INVALID',
      `profile ${profile.id} requiresLocalOperator is invalid`,
    );
    requireCondition(
      EXPIRY_DISPOSITIONS.has(profile.expiryDisposition),
      'PARTITION_POLICY_INVALID',
      `profile ${profile.id} expiryDisposition is invalid`,
    );
  }
  requireCondition(connectedProfiles === 1, 'PARTITION_POLICY_INVALID', 'partition policy must define exactly one connected profile');
  return { links, profiles: policy.profiles };
}

function observationIdentityBody(observation) {
  const { observationId: _observationId, signature: _signature, ...body } = observation;
  return body;
}

function signedObservationBody(observation) {
  const { signature: _signature, ...body } = observation;
  return body;
}

export function deriveLinkObservationId(observation) {
  return digest('linkobservation1', observationIdentityBody(observation));
}

function findTrustedNodeKey(observation, nodeTrustStore) {
  requireCondition(
    isRecord(nodeTrustStore) && nodeTrustStore.schema === 'axm-node-trust/1' && Array.isArray(nodeTrustStore.keys),
    'NODE_TRUST_INVALID',
    'node trust store is invalid',
  );
  return nodeTrustStore.keys.find((row) =>
    isRecord(row)
    && row.keyId === observation.signature?.keyId
    && row.nodeId === observation.nodeId
    && row.algorithm === 'Ed25519'
  );
}

export function verifyLinkObservation(observation, nodeTrustStore) {
  requireCondition(
    isRecord(observation) && observation.schema === 'axm-link-observation/1',
    'LINK_OBSERVATION_SCHEMA_INVALID',
    'link observation schema is invalid',
  );
  requireCondition(typeof observation.nodeId === 'string' && observation.nodeId, 'LINK_OBSERVATION_NODE_INVALID', 'nodeId is missing');
  parseTime(observation.observedAt, 'LINK_OBSERVATION_TIME_INVALID', 'link observation observedAt');
  requireCondition(isRecord(observation.links), 'LINK_OBSERVATION_LINKS_INVALID', 'links must be an object');
  for (const [link, state] of Object.entries(observation.links)) {
    requireCondition(typeof link === 'string' && link, 'LINK_OBSERVATION_LINKS_INVALID', 'link name is invalid');
    requireCondition(LINK_STATES.has(state), 'LINK_OBSERVATION_LINKS_INVALID', `link ${link} has invalid state`);
  }
  requireCondition(
    typeof observation.localOperatorPresent === 'boolean',
    'LINK_OBSERVATION_OPERATOR_INVALID',
    'localOperatorPresent must be boolean',
  );
  requireCondition(
    observation.observationId === deriveLinkObservationId(observation),
    'LINK_OBSERVATION_IDENTITY_INVALID',
    'link observation identity does not match its contents',
  );
  requireCondition(
    isRecord(observation.signature)
      && observation.signature.algorithm === 'Ed25519'
      && typeof observation.signature.value === 'string',
    'LINK_OBSERVATION_SIGNATURE_INVALID',
    'link observation signature metadata is invalid',
  );
  const key = findTrustedNodeKey(observation, nodeTrustStore);
  requireCondition(key && typeof key.publicKeyPem === 'string', 'NODE_KEY_UNTRUSTED', 'node signing key is untrusted');
  let valid = false;
  try {
    valid = verifyMessage(
      null,
      Buffer.from(canonicalJson(signedObservationBody(observation)), 'utf8'),
      createPublicKey(key.publicKeyPem),
      Buffer.from(observation.signature.value, 'base64'),
    );
  } catch {
    valid = false;
  }
  requireCondition(valid, 'LINK_OBSERVATION_SIGNATURE_INVALID', 'link observation signature did not verify');
  return observation;
}

function profileForObservation(authority, observation) {
  const { links, profiles } = validatePartitionPolicy(authority.partitionPolicy);
  const observedKeys = Object.keys(observation.links).sort();
  requireCondition(
    canonicalJson(observedKeys) === canonicalJson(links),
    'LINK_OBSERVATION_TOPOLOGY_INVALID',
    'link observation does not cover the exact authority link set',
  );
  return profiles.find((profile) =>
    links.every((link) => profile.states[link] === observation.links[link])
  ) ?? null;
}

function initialState(nodeId, nowMs) {
  return {
    schema: 'axm-partition-runtime-state/1',
    runtimeId: digest('partitionruntime1', { nodeId, createdAt: iso(nowMs) }),
    nodeId,
    journalSequence: 0,
    currentAuthorityId: null,
    currentProfileId: null,
    lastObservation: null,
    activeEpoch: null,
    pendingReconciliation: null,
    decisionIds: [],
  };
}

function journalRecordBody(record) {
  const { recordId: _recordId, signature: _signature, ...body } = record;
  return body;
}

function signedJournalRecordBody(record) {
  const { signature: _signature, ...body } = record;
  return body;
}

function verifyJournalRecord(record, expectedSequence, expectedPrevious, nodeTrustStore) {
  requireCondition(
    isRecord(record) && record.schema === 'axm-partition-journal-record/1',
    'PARTITION_JOURNAL_SCHEMA_INVALID',
    'partition journal record schema is invalid',
  );
  requireCondition(record.sequence === expectedSequence, 'PARTITION_JOURNAL_SEQUENCE_INVALID', 'partition journal sequence is invalid');
  requireCondition(record.previousRecordId === expectedPrevious, 'PARTITION_JOURNAL_CHAIN_INVALID', 'partition journal chain is invalid');
  requireCondition(
    record.recordId === digest('partitionrecord1', journalRecordBody(record)),
    'PARTITION_JOURNAL_IDENTITY_INVALID',
    'partition journal record identity is invalid',
  );
  const observationShape = {
    signature: record.signature,
    nodeId: record.nodeId,
  };
  const key = findTrustedNodeKey(observationShape, nodeTrustStore);
  requireCondition(key && typeof key.publicKeyPem === 'string', 'PARTITION_JOURNAL_KEY_UNTRUSTED', 'partition journal key is untrusted');
  let valid = false;
  try {
    valid = verifyMessage(
      null,
      Buffer.from(canonicalJson(signedJournalRecordBody(record)), 'utf8'),
      createPublicKey(key.publicKeyPem),
      Buffer.from(record.signature.value, 'base64'),
    );
  } catch {
    valid = false;
  }
  requireCondition(valid, 'PARTITION_JOURNAL_SIGNATURE_INVALID', 'partition journal signature did not verify');
  requireCondition(isRecord(record.stateAfter), 'PARTITION_JOURNAL_STATE_INVALID', 'partition journal state is invalid');
}

export class PartitionAuthorityRuntime {
  constructor({
    journalPath,
    nodeId,
    journalKeyId,
    journalPrivateKeyPem,
    nodeTrustStore,
    authorityTrustStore,
    clock = () => Date.now(),
  }) {
    requireCondition(typeof journalPath === 'string' && journalPath, 'PARTITION_RUNTIME_CONFIG_INVALID', 'journalPath is required');
    requireCondition(typeof nodeId === 'string' && nodeId, 'PARTITION_RUNTIME_CONFIG_INVALID', 'nodeId is required');
    requireCondition(typeof journalKeyId === 'string' && journalKeyId, 'PARTITION_RUNTIME_CONFIG_INVALID', 'journalKeyId is required');
    requireCondition(typeof journalPrivateKeyPem === 'string' && journalPrivateKeyPem, 'PARTITION_RUNTIME_CONFIG_INVALID', 'journal private key is required');
    requireCondition(typeof clock === 'function', 'PARTITION_RUNTIME_CONFIG_INVALID', 'clock must be a function');

    this.journalPath = journalPath;
    this.lockPath = `${journalPath}.lock`;
    this.nodeId = nodeId;
    this.journalKeyId = journalKeyId;
    this.privateKey = createPrivateKey(journalPrivateKeyPem);
    this.nodeTrustStore = nodeTrustStore;
    this.authorityTrustStore = authorityTrustStore;
    this.clock = clock;
    this.closed = false;
    this.truncatedTailBytes = 0;
    this.lastRecordId = ZERO_RECORD;
    this.state = initialState(nodeId, this.clock());

    mkdirSync(dirname(journalPath), { recursive: true });
    try {
      this.lockFd = openSync(this.lockPath, 'wx', 0o600);
      writeFileSync(this.lockFd, `${process.pid}\n`, 'utf8');
      fsyncSync(this.lockFd);
    } catch (error) {
      throw new PartitionError('PARTITION_RUNTIME_LOCKED', `partition runtime journal is already owned: ${error.message}`);
    }

    try {
      this.load();
      if (this.state.journalSequence === 0) {
        this.commit(
          { type: 'runtime_initialized', at: iso(this.clock()) },
          () => {},
        );
      }
    } catch (error) {
      this.releaseLock();
      throw error;
    }
  }

  load() {
    if (!existsSync(this.journalPath)) return;
    let bytes = readFileSync(this.journalPath);
    if (bytes.length === 0) return;
    if (bytes.at(-1) !== 0x0a) {
      const lastNewline = bytes.lastIndexOf(0x0a);
      requireCondition(lastNewline >= 0, 'PARTITION_JOURNAL_TAIL_INVALID', 'partition journal contains no complete record');
      this.truncatedTailBytes = bytes.length - lastNewline - 1;
      truncateSync(this.journalPath, lastNewline + 1);
      bytes = bytes.subarray(0, lastNewline + 1);
    }

    const lines = bytes.toString('utf8').split('\n').filter(Boolean);
    let previous = ZERO_RECORD;
    let sequence = 0;
    for (const line of lines) {
      let record;
      try {
        record = JSON.parse(line);
      } catch (error) {
        throw new PartitionError('PARTITION_JOURNAL_JSON_INVALID', `partition journal JSON is invalid: ${error.message}`);
      }
      sequence += 1;
      verifyJournalRecord(record, sequence, previous, this.nodeTrustStore);
      requireCondition(record.nodeId === this.nodeId, 'PARTITION_JOURNAL_NODE_INVALID', 'partition journal belongs to another node');
      previous = record.recordId;
      this.state = record.stateAfter;
    }
    this.lastRecordId = previous;
    requireCondition(this.state.journalSequence === sequence, 'PARTITION_JOURNAL_STATE_INVALID', 'partition state sequence does not match journal');
  }

  releaseLock() {
    if (this.lockFd !== undefined) {
      try {
        closeSync(this.lockFd);
      } catch {}
      this.lockFd = undefined;
    }
    try {
      unlinkSync(this.lockPath);
    } catch {}
  }

  close() {
    if (this.closed) return;
    this.closed = true;
    this.releaseLock();
  }

  snapshot() {
    return clone({
      ...this.state,
      diagnostics: {
        truncatedTailBytes: this.truncatedTailBytes,
        journalPath: this.journalPath,
        lastRecordId: this.lastRecordId,
      },
    });
  }

  commit(event, mutate) {
    requireCondition(!this.closed, 'PARTITION_RUNTIME_CLOSED', 'partition runtime is closed');
    const nextState = clone(this.state);
    mutate(nextState);
    const sequence = this.state.journalSequence + 1;
    nextState.journalSequence = sequence;
    const unsigned = {
      schema: 'axm-partition-journal-record/1',
      sequence,
      previousRecordId: this.lastRecordId,
      nodeId: this.nodeId,
      event,
      stateAfter: nextState,
    };
    const recordId = digest('partitionrecord1', unsigned);
    const signed = { ...unsigned, recordId };
    const signature = signMessage(
      null,
      Buffer.from(canonicalJson(signed), 'utf8'),
      this.privateKey,
    ).toString('base64');
    const record = {
      ...signed,
      signature: {
        algorithm: 'Ed25519',
        keyId: this.journalKeyId,
        value: signature,
      },
    };
    const fd = openSync(this.journalPath, 'a', 0o600);
    try {
      appendFileSync(fd, `${JSON.stringify(record)}\n`, 'utf8');
      fsyncSync(fd);
    } finally {
      closeSync(fd);
    }
    this.state = nextState;
    this.lastRecordId = recordId;
    return record;
  }

  observe(observation, authority) {
    const nowMs = this.clock();
    const verifiedAuthority = verifyPartitionAuthority(authority, this.authorityTrustStore);
    const verifiedObservation = verifyLinkObservation(observation, this.nodeTrustStore);
    requireCondition(verifiedObservation.nodeId === this.nodeId, 'LINK_OBSERVATION_NODE_INVALID', 'observation belongs to another node');
    const observedAtMs = parseTime(verifiedObservation.observedAt, 'LINK_OBSERVATION_TIME_INVALID', 'link observation observedAt');
    requireCondition(observedAtMs <= nowMs + MAX_CLOCK_SKEW_MS, 'LINK_OBSERVATION_FROM_FUTURE', 'link observation exceeds clock skew');
    if (this.state.lastObservation) {
      const priorMs = parseTime(this.state.lastObservation.observedAt, 'PARTITION_STATE_INVALID', 'prior observation time');
      requireCondition(observedAtMs >= priorMs, 'LINK_OBSERVATION_REGRESSION', 'link observation time regressed');
    }

    const profile = profileForObservation(verifiedAuthority, verifiedObservation);
    const priorEpoch = this.state.activeEpoch;
    if (profile?.partition && this.state.pendingReconciliation) {
      throw new PartitionError('PARTITION_RECONCILIATION_REQUIRED', 'a prior partition must be reconciled before another begins');
    }
    if (priorEpoch && priorEpoch.authorityId !== verifiedAuthority.authorityId) {
      throw new PartitionError(
        'PARTITION_AUTHORITY_CHANGE_REQUIRES_RECONCILIATION',
        'authority cannot change inside an active partition epoch',
      );
    }

    const event = {
      type: 'link_observation_admitted',
      at: iso(nowMs),
      observationId: verifiedObservation.observationId,
      authorityId: verifiedAuthority.authorityId,
      profileId: profile?.id ?? null,
    };
    this.commit(event, (state) => {
      state.currentAuthorityId = verifiedAuthority.authorityId;
      state.currentProfileId = profile?.id ?? 'unknown';
      state.lastObservation = clone(verifiedObservation);

      if (!profile) return;
      if (profile.partition) {
        if (!state.activeEpoch) {
          state.activeEpoch = {
            schema: 'axm-partition-epoch/1',
            epochId: digest('partitionepoch1', {
              runtimeId: state.runtimeId,
              authorityId: verifiedAuthority.authorityId,
              startedAt: verifiedObservation.observedAt,
              observationId: verifiedObservation.observationId,
            }),
            authorityId: verifiedAuthority.authorityId,
            startedAt: verifiedObservation.observedAt,
            profileId: profile.id,
            firstObservationId: verifiedObservation.observationId,
            lastObservationId: verifiedObservation.observationId,
            decisionIds: [],
          };
        } else {
          state.activeEpoch.profileId = profile.id;
          state.activeEpoch.lastObservationId = verifiedObservation.observationId;
        }
      } else if (state.activeEpoch) {
        state.pendingReconciliation = {
          schema: 'axm-partition-reconciliation-pending/1',
          epoch: clone(state.activeEpoch),
          endedAt: verifiedObservation.observedAt,
          returningObservationId: verifiedObservation.observationId,
        };
        state.activeEpoch = null;
      }
    });

    return {
      schema: 'axm-partition-observation-receipt/1',
      observationId: verifiedObservation.observationId,
      authorityId: verifiedAuthority.authorityId,
      profileId: profile?.id ?? 'unknown',
      activeEpochId: this.state.activeEpoch?.epochId ?? null,
      pendingReconciliationEpochId: this.state.pendingReconciliation?.epoch?.epochId ?? null,
      claimBoundary: 'This receipt classifies signed link state. It carries no candidate or execution authority.',
    };
  }

  evaluate(transaction, authority) {
    const nowMs = this.clock();
    const checkedAt = iso(nowMs);
    const verifiedAuthority = verifyPartitionAuthority(authority, this.authorityTrustStore);
    const baseDecision = evaluateCandidateAuthority(
      transaction,
      verifiedAuthority,
      this.authorityTrustStore,
      checkedAt,
    );
    let disposition = baseDecision.disposition;
    let code = baseDecision.reasons[0]?.code ?? 'base_authority_refused';
    let message = baseDecision.reasons[0]?.message ?? 'base authority gate refused candidate';
    let profile = null;
    let elapsedMs = null;

    if (disposition === 'allow') {
      if (!this.state.lastObservation || !this.state.currentProfileId) {
        disposition = 'safe_state';
        code = 'partition_topology_unknown';
        message = 'no signed current topology is available';
      } else if (this.state.currentAuthorityId !== verifiedAuthority.authorityId) {
        disposition = 'refuse';
        code = 'partition_authority_mismatch';
        message = 'runtime topology was admitted under another authority';
      } else {
        profile = verifiedAuthority.partitionPolicy.profiles.find(
          (row) => row.id === this.state.currentProfileId,
        ) ?? null;
        if (!profile) {
          disposition = 'safe_state';
          code = 'partition_profile_unknown';
          message = 'signed topology does not map to an admitted profile';
        } else if (!profile.allowedActionClasses.includes(transaction.candidate.actionClass)) {
          disposition = 'refuse';
          code = 'partition_action_not_surviving';
          message = 'candidate action class does not survive the current communications profile';
        } else if (profile.requiresLocalOperator && !this.state.lastObservation.localOperatorPresent) {
          disposition = 'safe_state';
          code = 'partition_local_operator_absent';
          message = 'current partition profile requires a local operator';
        } else if (profile.partition) {
          if (!this.state.activeEpoch) {
            disposition = 'safe_state';
            code = 'partition_epoch_missing';
            message = 'partition profile has no runtime-owned epoch';
          } else {
            const startedAtMs = parseTime(this.state.activeEpoch.startedAt, 'PARTITION_STATE_INVALID', 'partition epoch startedAt');
            elapsedMs = Math.max(0, nowMs - startedAtMs);
            if (nowMs + MAX_CLOCK_SKEW_MS < startedAtMs) {
              disposition = 'hold';
              code = 'partition_clock_regression';
              message = 'runtime clock is earlier than the persisted partition epoch';
            } else if (elapsedMs > profile.maxOfflineMs) {
              disposition = profile.expiryDisposition;
              code = 'partition_offline_lease_expired';
              message = 'runtime-owned offline lease has expired';
            }
          }
        }
      }
    }

    const body = {
      baseDecisionId: baseDecision.decisionId,
      candidateId: transaction?.candidate?.candidateId ?? null,
      snapshotId: transaction?.snapshot?.snapshotId ?? null,
      authorityId: verifiedAuthority.authorityId,
      checkedAt,
      profileId: profile?.id ?? this.state.currentProfileId,
      epochId: this.state.activeEpoch?.epochId ?? null,
      epochStartedAt: this.state.activeEpoch?.startedAt ?? null,
      elapsedMs,
      disposition,
      reason: { code, message },
    };
    const decision = {
      schema: 'axm-partition-authority-decision/1',
      decisionId: digest('partitiondecision1', body),
      ...body,
      baseDecision,
      claimBoundary:
        'This receipt applies signed communications-state constraints to candidate eligibility. It has no actuation surface and cannot itself execute, target, engage, command an effector, or release a weapon.',
    };

    this.commit(
      {
        type: 'candidate_evaluated',
        at: checkedAt,
        decisionId: decision.decisionId,
        disposition,
        reasonCode: code,
      },
      (state) => {
        state.decisionIds.push(decision.decisionId);
        if (state.decisionIds.length > 20_000) {
          state.decisionIds.splice(0, state.decisionIds.length - 20_000);
        }
        if (state.activeEpoch) state.activeEpoch.decisionIds.push(decision.decisionId);
      },
    );
    return decision;
  }

  reconcile(returningAuthority) {
    const nowMs = this.clock();
    const verifiedAuthority = verifyPartitionAuthority(returningAuthority, this.authorityTrustStore);
    const pending = this.state.pendingReconciliation;
    requireCondition(pending, 'PARTITION_RECONCILIATION_NOT_PENDING', 'no partition is awaiting reconciliation');
    requireCondition(this.state.currentProfileId, 'PARTITION_RECONCILIATION_TOPOLOGY_UNKNOWN', 'current topology is unknown');
    const currentProfile = verifiedAuthority.partitionPolicy.profiles.find(
      (row) => row.id === this.state.currentProfileId,
    );
    requireCondition(currentProfile && !currentProfile.partition, 'PARTITION_RECONCILIATION_NOT_CONNECTED', 'reconciliation requires a connected profile');

    const supersedes = Array.isArray(verifiedAuthority.supersedes)
      ? verifiedAuthority.supersedes.filter((value) => typeof value === 'string')
      : [];
    const explicit = supersedes.includes(pending.epoch.authorityId);
    const body = {
      epochId: pending.epoch.epochId,
      priorAuthorityId: pending.epoch.authorityId,
      returningAuthorityId: verifiedAuthority.authorityId,
      startedAt: pending.epoch.startedAt,
      endedAt: pending.endedAt,
      reconciledAt: iso(nowMs),
      localDecisionIds: [...pending.epoch.decisionIds],
      disposition: explicit ? 'explicitly_superseded' : 'human_required',
    };
    const receipt = {
      schema: 'axm-partition-reconciliation/1',
      reconciliationId: digest('partitionreconciliation1', body),
      ...body,
      claimBoundary:
        'This receipt preserves the disconnected history and classifies returning authority. It does not erase, relabel, or execute any local decision.',
    };

    this.commit(
      {
        type: 'partition_reconciled',
        at: body.reconciledAt,
        reconciliationId: receipt.reconciliationId,
        disposition: receipt.disposition,
      },
      (state) => {
        if (explicit) {
          state.pendingReconciliation = null;
          state.currentAuthorityId = verifiedAuthority.authorityId;
        }
      },
    );
    return receipt;
  }
}

export function signLinkObservation(observationBody, keyId, privateKeyPem) {
  const observationId = deriveLinkObservationId(observationBody);
  const signed = { ...observationBody, observationId };
  return {
    ...signed,
    signature: {
      algorithm: 'Ed25519',
      keyId,
      value: signMessage(
        null,
        Buffer.from(canonicalJson(signed), 'utf8'),
        createPrivateKey(privateKeyPem),
      ).toString('base64'),
    },
  };
}

export function signAuthorityEnvelope(authorityBody, keyId, privateKeyPem) {
  const authorityId = digest('authority1', authorityIdentityBody(authorityBody));
  const signed = { ...authorityBody, authorityId };
  return {
    ...signed,
    signature: {
      algorithm: 'Ed25519',
      keyId,
      value: signMessage(
        null,
        Buffer.from(canonicalJson(signed), 'utf8'),
        createPrivateKey(privateKeyPem),
      ).toString('base64'),
    },
  };
}

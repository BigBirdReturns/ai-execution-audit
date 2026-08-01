import { createHash } from 'node:crypto';

const RESERVED_AUTHORITY_KEYS = new Set([
  'authorized',
  'isauthorized',
  'authorization',
  'authority',
  'authoritygranted',
  'approved',
  'isapproved',
  'approval',
  'allow',
  'allowed',
  'execute',
  'executionauthorized',
  'executionapproved',
  'engagementauthorized',
  'engagementapproved',
  'commandauthority',
  'releaseauthority',
  'weaponsrelease',
  'weaponsreleaseauthorized',
  'effectorcommand',
  'actuationauthorized',
]);

const MAP_STATUSES = new Set(['provisional', 'confirmed', 'retired']);
const FIELD_STATUSES = new Set(['provisional', 'confirmed', 'unresolved']);
const ROUND_TRIP_MODES = new Set(['exact', 'normalized_datetime', 'set_equal', 'none']);
const TYPE_NAMES = new Set([
  'bounded_string',
  'date_time',
  'string_set',
  'finite_number',
  'nonnegative_integer',
]);
const FORBIDDEN_OBJECT_KEYS = new Set(['__proto__', 'constructor', 'prototype']);
const MAX_JSON_DEPTH = 16;
const MAX_JSON_NODES = 16_384;
const MAX_STRING_LENGTH = 64 * 1024;
const MAX_STRING_SET = 64;

export class CongruenceError extends Error {
  constructor(code, message) {
    super(message);
    this.name = 'CongruenceError';
    this.code = code;
  }
}

function requireCondition(condition, code, message) {
  if (!condition) throw new CongruenceError(code, message);
}

function isRecord(value) {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) return false;
  const prototype = Object.getPrototypeOf(value);
  return prototype === Object.prototype || prototype === null;
}

export function canonicalJson(value) {
  if (value === null) return 'null';
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(',')}]`;
  if (typeof value === 'object') {
    requireCondition(isRecord(value), 'NON_JSON_VALUE', 'canonical JSON requires plain objects');
    return `{${Object.keys(value)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${canonicalJson(value[key])}`)
      .join(',')}}`;
  }
  if (typeof value === 'number') {
    requireCondition(Number.isFinite(value), 'NON_JSON_NUMBER', 'non-finite numbers are not admissible');
  }
  const encoded = JSON.stringify(value);
  requireCondition(encoded !== undefined, 'NON_JSON_VALUE', 'non-JSON values are not admissible');
  return encoded;
}

function digest(prefix, value) {
  return `${prefix}_${createHash('sha256').update(canonicalJson(value), 'utf8').digest('hex')}`;
}

function normalizedKey(key) {
  return key.replace(/[^a-z0-9]/gi, '').toLowerCase();
}

function assertCandidateData(value, path = '$', depth = 0, counter = { nodes: 0 }) {
  counter.nodes += 1;
  requireCondition(counter.nodes <= MAX_JSON_NODES, 'EXTERNAL_SHAPE_BOUNDS', 'external shape exceeds bounded value count');
  requireCondition(depth <= MAX_JSON_DEPTH, 'EXTERNAL_SHAPE_BOUNDS', 'external shape exceeds bounded depth');

  if (value === null || typeof value === 'boolean') return;
  if (typeof value === 'number') {
    requireCondition(Number.isFinite(value), 'EXTERNAL_SHAPE_NON_JSON', `non-finite number at ${path}`);
    return;
  }
  if (typeof value === 'string') {
    requireCondition(value.length <= MAX_STRING_LENGTH, 'EXTERNAL_SHAPE_BOUNDS', `string exceeds bound at ${path}`);
    return;
  }
  if (Array.isArray(value)) {
    value.forEach((item, index) => assertCandidateData(item, `${path}[${index}]`, depth + 1, counter));
    return;
  }
  requireCondition(isRecord(value), 'EXTERNAL_SHAPE_NON_JSON', `non-JSON value at ${path}`);
  for (const [key, nested] of Object.entries(value)) {
    requireCondition(!FORBIDDEN_OBJECT_KEYS.has(key), 'EXTERNAL_SHAPE_FORBIDDEN_KEY', `forbidden object key ${key} at ${path}`);
    requireCondition(
      !RESERVED_AUTHORITY_KEYS.has(normalizedKey(key)),
      'CANDIDATE_SELF_AUTHORIZATION',
      `candidate data carries reserved authority field ${key} at ${path}`,
    );
    assertCandidateData(nested, `${path}.${key}`, depth + 1, counter);
  }
}

function pointerSegments(pointer) {
  requireCondition(typeof pointer === 'string' && pointer.startsWith('/'), 'MAP_POINTER_INVALID', `invalid JSON pointer ${pointer}`);
  return pointer
    .slice(1)
    .split('/')
    .map((segment) => segment.replace(/~1/g, '/').replace(/~0/g, '~'));
}

function getPointer(value, pointer) {
  let current = value;
  for (const segment of pointerSegments(pointer)) {
    if (!isRecord(current) && !Array.isArray(current)) return { found: false, value: undefined };
    if (!Object.prototype.hasOwnProperty.call(current, segment)) return { found: false, value: undefined };
    current = current[segment];
  }
  return { found: true, value: current };
}

function setPointer(target, pointer, value) {
  const segments = pointerSegments(pointer);
  let current = target;
  segments.forEach((segment, index) => {
    requireCondition(!FORBIDDEN_OBJECT_KEYS.has(segment), 'MAP_POINTER_INVALID', `forbidden target segment ${segment}`);
    if (index === segments.length - 1) {
      current[segment] = structuredClone(value);
      return;
    }
    if (!Object.prototype.hasOwnProperty.call(current, segment)) current[segment] = {};
    requireCondition(isRecord(current[segment]), 'MAP_TARGET_CONFLICT', `target path conflicts at ${pointer}`);
    current = current[segment];
  });
}

function normalizeValue(value, type, label) {
  switch (type) {
    case 'bounded_string': {
      requireCondition(typeof value === 'string', 'MAPPED_TYPE_INVALID', `${label} must be a string`);
      const normalized = value.trim();
      requireCondition(normalized.length > 0 && normalized.length <= 512, 'MAPPED_TYPE_INVALID', `${label} is empty or unbounded`);
      return normalized;
    }
    case 'date_time': {
      requireCondition(typeof value === 'string', 'MAPPED_TYPE_INVALID', `${label} must be a date-time string`);
      const milliseconds = Date.parse(value);
      requireCondition(Number.isFinite(milliseconds), 'MAPPED_TYPE_INVALID', `${label} is not a valid date-time`);
      return new Date(milliseconds).toISOString();
    }
    case 'string_set': {
      requireCondition(Array.isArray(value) && value.length > 0 && value.length <= MAX_STRING_SET, 'MAPPED_TYPE_INVALID', `${label} must be a bounded string set`);
      const rows = value.map((row) => {
        requireCondition(typeof row === 'string', 'MAPPED_TYPE_INVALID', `${label} entries must be strings`);
        const normalized = row.trim();
        requireCondition(normalized.length > 0 && normalized.length <= 512, 'MAPPED_TYPE_INVALID', `${label} contains an invalid string`);
        return normalized;
      });
      requireCondition(new Set(rows).size === rows.length, 'MAPPED_TYPE_INVALID', `${label} contains duplicate values`);
      return [...rows].sort();
    }
    case 'finite_number':
      requireCondition(typeof value === 'number' && Number.isFinite(value), 'MAPPED_TYPE_INVALID', `${label} must be a finite number`);
      return value;
    case 'nonnegative_integer':
      requireCondition(Number.isSafeInteger(value) && value >= 0, 'MAPPED_TYPE_INVALID', `${label} must be a non-negative integer`);
      return value;
    default:
      throw new CongruenceError('MAP_TYPE_INVALID', `unsupported mapping type ${type}`);
  }
}

function mapIdentityBody(map) {
  const { mapId: _mapId, claimBoundary: _claimBoundary, ...body } = map;
  return body;
}

export function deriveMapId(map) {
  return digest('polybolosmap1', mapIdentityBody(map));
}

export function validateShapeMap(map) {
  requireCondition(isRecord(map) && map.schema === 'axm-polybolos-shape-map/1', 'MAP_SCHEMA_INVALID', 'shape map schema is invalid');
  requireCondition(MAP_STATUSES.has(map.status), 'MAP_STATUS_INVALID', 'shape map status is invalid');
  requireCondition(typeof map.externalShape === 'string' && map.externalShape, 'MAP_SHAPE_INVALID', 'external shape is missing');
  requireCondition(map.neutralShape === 'axm-polybolos-candidate-input/1', 'MAP_SHAPE_INVALID', 'neutral shape is unsupported');
  requireCondition(map.authorityFieldPolicy === 'refuse', 'MAP_POLICY_INVALID', 'candidate authority fields must be refused');
  requireCondition(map.unknownFieldPolicy === 'digest_and_names', 'MAP_POLICY_INVALID', 'unknown field policy is unsupported');
  requireCondition(Array.isArray(map.mappings) && map.mappings.length > 0, 'MAP_FIELDS_INVALID', 'shape map has no mappings');
  requireCondition(Array.isArray(map.declaredLossIds), 'MAP_LOSSES_INVALID', 'declared loss IDs are missing');

  const sources = new Set();
  const targets = new Set();
  for (const field of map.mappings) {
    requireCondition(isRecord(field), 'MAP_FIELDS_INVALID', 'mapping row must be an object');
    requireCondition(typeof field.semantic === 'string' && field.semantic, 'MAP_FIELDS_INVALID', 'mapping semantic is missing');
    pointerSegments(field.source);
    pointerSegments(field.target);
    requireCondition(!sources.has(field.source), 'MAP_FIELDS_INVALID', `duplicate source pointer ${field.source}`);
    requireCondition(!targets.has(field.target), 'MAP_FIELDS_INVALID', `duplicate target pointer ${field.target}`);
    sources.add(field.source);
    targets.add(field.target);
    requireCondition(FIELD_STATUSES.has(field.status), 'MAP_FIELDS_INVALID', `invalid status for ${field.semantic}`);
    requireCondition(typeof field.required === 'boolean', 'MAP_FIELDS_INVALID', `required flag is invalid for ${field.semantic}`);
    requireCondition(TYPE_NAMES.has(field.type), 'MAP_FIELDS_INVALID', `invalid type for ${field.semantic}`);
    requireCondition(ROUND_TRIP_MODES.has(field.roundTrip), 'MAP_FIELDS_INVALID', `invalid round-trip rule for ${field.semantic}`);
  }
  if (map.derived !== undefined) {
    requireCondition(Array.isArray(map.derived), 'MAP_DERIVED_INVALID', 'derived mappings must be an array');
    for (const row of map.derived) {
      requireCondition(isRecord(row) && row.rule === 'copy', 'MAP_DERIVED_INVALID', 'only explicit copy derivation is supported');
      pointerSegments(row.sourceTarget);
      pointerSegments(row.target);
    }
  }

  const computed = deriveMapId(map);
  if (map.mapId !== null && map.mapId !== undefined) {
    requireCondition(map.mapId === computed, 'MAP_IDENTITY_INVALID', 'shape map identity does not match its contents');
  }
  return { mapId: computed, map };
}

function resolveLosses(map, lossRegistry) {
  requireCondition(
    isRecord(lossRegistry)
      && lossRegistry.schema === 'axm-polybolos-declared-losses/1'
      && Array.isArray(lossRegistry.losses),
    'LOSS_REGISTRY_INVALID',
    'declared loss registry is invalid',
  );
  const byId = new Map(lossRegistry.losses.map((loss) => [loss.id, loss]));
  return map.declaredLossIds.map((id) => {
    const loss = byId.get(id);
    requireCondition(loss, 'LOSS_REGISTRY_INVALID', `shape map cites unknown loss ${id}`);
    return structuredClone(loss);
  });
}

function mappedTopLevelNames(map) {
  return new Set(map.mappings.map((field) => pointerSegments(field.source)[0]));
}

function unknownTopLevelRecord(external, map) {
  const consumed = mappedTopLevelNames(map);
  consumed.add('schema');
  const names = Object.keys(external).filter((key) => !consumed.has(key)).sort();
  const record = Object.fromEntries(names.map((key) => [key, external[key]]));
  return {
    names,
    digest: digest('polybolosunknown1', record),
  };
}

function validateNeutralProjection(neutral) {
  for (const field of ['requestId', 'producer', 'producerBuildId', 'createdAt', 'deadlineAt', 'actionClass']) {
    requireCondition(typeof neutral[field] === 'string' && neutral[field], 'NEUTRAL_SHAPE_INVALID', `neutral field ${field} is missing`);
  }
  const createdAtMs = Date.parse(neutral.createdAt);
  const deadlineAtMs = Date.parse(neutral.deadlineAt);
  requireCondition(Number.isFinite(createdAtMs) && Number.isFinite(deadlineAtMs), 'NEUTRAL_SHAPE_INVALID', 'neutral time fields are invalid');
  requireCondition(deadlineAtMs >= createdAtMs, 'NEUTRAL_DEADLINE_INVALID', 'candidate deadline predates candidate creation');
  requireCondition(Array.isArray(neutral.entityIds) && neutral.entityIds.length >= 1 && neutral.entityIds.length <= 16, 'NEUTRAL_ENTITY_BOUND_INVALID', 'neutral entity references must contain between 1 and 16 IDs');
  requireCondition(isRecord(neutral.payload), 'NEUTRAL_SHAPE_INVALID', 'neutral payload is missing');
  requireCondition(
    canonicalJson(neutral.payload.entityIds) === canonicalJson(neutral.entityIds),
    'NEUTRAL_EVIDENCE_CLOSURE_INVALID',
    'neutral payload entity references differ from the candidate evidence set',
  );
  requireCondition(isRecord(neutral.trace), 'NEUTRAL_SHAPE_INVALID', 'neutral trace is missing');
}

export function translateExternalProposal(external, map, lossRegistry, options = {}) {
  const mode = options.mode ?? 'fixture';
  requireCondition(mode === 'fixture' || mode === 'live', 'TRANSLATION_MODE_INVALID', 'translation mode is invalid');
  const { mapId } = validateShapeMap(map);
  if (mode === 'live') {
    requireCondition(map.status === 'confirmed', 'MAPPING_NOT_CONFIRMED', 'live translation requires a confirmed shape map');
    requireCondition(
      map.mappings.every((field) => field.status === 'confirmed'),
      'MAPPING_NOT_CONFIRMED',
      'live translation contains unconfirmed fields',
    );
  }
  requireCondition(isRecord(external), 'EXTERNAL_SHAPE_INVALID', 'external proposal must be an object');
  requireCondition(external.schema === map.externalShape, 'EXTERNAL_SCHEMA_INVALID', 'external proposal schema does not match the shape map');
  assertCandidateData(external);

  const neutral = {
    schema: map.neutralShape,
    mappingId: mapId,
    sourceShapeId: digest('polybolossource1', external),
  };
  for (const field of map.mappings) {
    if (field.status === 'unresolved') {
      requireCondition(!field.required, 'MAPPING_UNRESOLVED', `required semantic remains unresolved: ${field.semantic}`);
      continue;
    }
    const source = getPointer(external, field.source);
    if (!source.found) {
      requireCondition(!field.required, 'MAPPED_FIELD_MISSING', `required external field is missing: ${field.source}`);
      continue;
    }
    setPointer(neutral, field.target, normalizeValue(source.value, field.type, field.semantic));
  }
  for (const derived of map.derived ?? []) {
    const source = getPointer(neutral, derived.sourceTarget);
    requireCondition(source.found, 'MAP_DERIVED_INVALID', `derived source is missing: ${derived.sourceTarget}`);
    setPointer(neutral, derived.target, source.value);
  }
  validateNeutralProjection(neutral);

  const unknown = unknownTopLevelRecord(external, map);
  const body = {
    ...neutral,
    mode,
    mappingStatus: map.status,
    unknownTopLevelFields: unknown.names,
    unknownTopLevelDigest: unknown.digest,
    declaredLosses: resolveLosses(map, lossRegistry),
  };
  return {
    ...body,
    projectionId: digest('polybolosprojection1', body),
    claimBoundary:
      'This is an AXM-neutral candidate projection produced through an explicit adapter map. It is not a Polybolos-native schema and carries no command authority.',
  };
}

export function reconstructMappedExternal(projection, map) {
  const { mapId } = validateShapeMap(map);
  requireCondition(isRecord(projection) && projection.schema === map.neutralShape, 'NEUTRAL_SHAPE_INVALID', 'neutral projection schema is invalid');
  requireCondition(projection.mappingId === mapId, 'MAPPING_ID_MISMATCH', 'neutral projection was produced by another shape map');
  const external = { schema: map.externalShape };
  for (const field of map.mappings) {
    if (field.roundTrip === 'none' || field.status === 'unresolved') continue;
    const target = getPointer(projection, field.target);
    if (!target.found) {
      requireCondition(!field.required, 'ROUNDTRIP_FIELD_MISSING', `required neutral field is missing: ${field.target}`);
      continue;
    }
    setPointer(external, field.source, target.value);
  }
  return external;
}

export function verifyMappedRoundTrip(external, projection, map) {
  const reconstructed = reconstructMappedExternal(projection, map);
  const mismatches = [];
  for (const field of map.mappings) {
    if (field.roundTrip === 'none' || field.status === 'unresolved') continue;
    const original = getPointer(external, field.source);
    const returned = getPointer(reconstructed, field.source);
    if (!original.found && !field.required) continue;
    if (!original.found || !returned.found) {
      mismatches.push({ semantic: field.semantic, reason: 'missing' });
      continue;
    }
    const normalizedOriginal = normalizeValue(original.value, field.type, field.semantic);
    if (canonicalJson(normalizedOriginal) !== canonicalJson(returned.value)) {
      mismatches.push({ semantic: field.semantic, reason: 'value' });
    }
  }
  return {
    schema: 'axm-polybolos-roundtrip-receipt/1',
    projectionId: projection.projectionId,
    mappingId: projection.mappingId,
    pass: mismatches.length === 0,
    mismatches,
    claimBoundary: 'This receipt covers only fields promised by the adapter map. It does not certify unmapped Polybolos internals.',
  };
}

export function toBoundedCandidateRequest(projection) {
  requireCondition(
    isRecord(projection) && projection.schema === 'axm-polybolos-candidate-input/1',
    'NEUTRAL_SHAPE_INVALID',
    'bounded request requires an AXM-neutral Polybolos candidate projection',
  );
  validateNeutralProjection(projection);
  const request = {
    producer: projection.producer,
    createdAt: projection.createdAt,
    actionClass: projection.actionClass,
    entityIds: structuredClone(projection.entityIds),
    payload: structuredClone(projection.payload),
  };
  const custody = {
    requestId: projection.requestId,
    producerBuildId: projection.producerBuildId,
    deadlineAt: projection.deadlineAt,
    trace: structuredClone(projection.trace),
    projectionId: projection.projectionId,
    sourceShapeId: projection.sourceShapeId,
    mappingId: projection.mappingId,
  };
  return {
    schema: 'axm-polybolos-bounded-candidate-request/1',
    request,
    custody,
    requestId: digest('polybolosboundedrequest1', { request, custody }),
    claimBoundary:
      'The request is shaped for the existing bounded Command Intelligence candidate endpoint. Custody fields remain at the AXM gateway and do not become Command Intelligence observations or command authority.',
  };
}

function statusFromReceipt(receipt) {
  if (receipt.schema === 'axm-partition-reconciliation/1') {
    if (receipt.disposition === 'explicitly_superseded') return { status: 'reconciled', reasonCode: 'partition_explicitly_superseded' };
    if (receipt.disposition === 'human_required') return { status: 'human_required', reasonCode: 'partition_human_disposition_required' };
    throw new CongruenceError('RETURN_DISPOSITION_INVALID', `unknown reconciliation disposition ${receipt.disposition}`);
  }
  const disposition = receipt.disposition;
  const statuses = {
    allow: 'eligible',
    hold: 'hold',
    refuse: 'refused',
    safe_state: 'safe_state',
  };
  requireCondition(Object.prototype.hasOwnProperty.call(statuses, disposition), 'RETURN_DISPOSITION_INVALID', `unknown AXM disposition ${disposition}`);
  return {
    status: statuses[disposition],
    reasonCode: receipt.reason?.code ?? receipt.reasons?.[0]?.code ?? 'unspecified',
  };
}

export function projectAxmStatus(receipt, context) {
  requireCondition(isRecord(receipt), 'RETURN_RECEIPT_INVALID', 'AXM receipt must be an object');
  requireCondition(isRecord(context) && typeof context.requestId === 'string' && context.requestId, 'RETURN_CONTEXT_INVALID', 'return context requires requestId');
  const mapped = statusFromReceipt(receipt);
  const body = {
    schema: 'polybolos-axm-status-projection/1',
    requestId: context.requestId,
    status: mapped.status,
    reasonCode: mapped.reasonCode,
    decisionId: receipt.decisionId ?? receipt.reconciliationId ?? null,
    candidateId: receipt.candidateId ?? null,
    checkpointId: receipt.checkpointId ?? null,
    authorityId: receipt.authorityId ?? receipt.returningAuthorityId ?? null,
    epochId: receipt.epochId ?? null,
    evidenceRef: context.evidenceRef ?? null,
  };
  return {
    ...body,
    statusProjectionId: digest('polybolosstatus1', body),
    claimBoundary:
      'This is a neutral AXM status projection for a Polybolos-owned return adapter. It does not represent a Polybolos-native UI, workflow, or internal state object.',
  };
}

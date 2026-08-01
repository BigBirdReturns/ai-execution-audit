import { createHash } from 'node:crypto';

const FORBIDDEN_KEYS = new Set(['__proto__', 'constructor', 'prototype']);
const AUTHORITY_TOKENS = new Set([
  'authorized',
  'authorization',
  'authority',
  'approved',
  'approval',
  'allow',
  'execute',
  'execution',
  'engagement',
  'command',
  'release',
  'weapon',
  'weapons',
  'effector',
  'actuation',
]);
const MAX_DEPTH = 32;
const MAX_NODES = 200_000;
const MAX_PATH_LENGTH = 2_048;

export class ShapeProfileError extends Error {
  constructor(code, message) {
    super(message);
    this.name = 'ShapeProfileError';
    this.code = code;
  }
}

function requireCondition(condition, code, message) {
  if (!condition) throw new ShapeProfileError(code, message);
}

function isRecord(value) {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) return false;
  const prototype = Object.getPrototypeOf(value);
  return prototype === Object.prototype || prototype === null;
}

function canonicalJson(value) {
  if (value === null) return 'null';
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(',')}]`;
  if (typeof value === 'object') {
    requireCondition(isRecord(value), 'PROFILE_NON_JSON', 'shape profile requires plain JSON objects');
    return `{${Object.keys(value)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${canonicalJson(value[key])}`)
      .join(',')}}`;
  }
  if (typeof value === 'number') {
    requireCondition(Number.isFinite(value), 'PROFILE_NON_JSON', 'non-finite numbers are not admissible');
  }
  const encoded = JSON.stringify(value);
  requireCondition(encoded !== undefined, 'PROFILE_NON_JSON', 'non-JSON values are not admissible');
  return encoded;
}

function digest(prefix, value) {
  return `${prefix}_${createHash('sha256').update(canonicalJson(value), 'utf8').digest('hex')}`;
}

function escapePointerSegment(value) {
  return value.replace(/~/g, '~0').replace(/\//g, '~1');
}

function pointer(parent, segment) {
  const result = `${parent}/${escapePointerSegment(segment)}`;
  requireCondition(result.length <= MAX_PATH_LENGTH, 'PROFILE_PATH_BOUNDS', 'shape profile path exceeds bound');
  return result;
}

function valueKind(value) {
  if (value === null) return 'null';
  if (Array.isArray(value)) return 'array';
  if (isRecord(value)) return 'object';
  if (typeof value === 'number') return Number.isInteger(value) ? 'integer' : 'number';
  if (typeof value === 'string' || typeof value === 'boolean') return typeof value;
  throw new ShapeProfileError('PROFILE_NON_JSON', 'shape contains a non-JSON value');
}

function normalizedTokens(segment) {
  return segment
    .replace(/([a-z0-9])([A-Z])/g, '$1 $2')
    .toLowerCase()
    .split(/[^a-z0-9]+/)
    .filter(Boolean);
}

function authorityLikePath(path) {
  const segments = path.split('/').filter(Boolean);
  return segments.some((segment) => normalizedTokens(segment).some((token) => AUTHORITY_TOKENS.has(token)));
}

function pathRow(path) {
  return {
    path,
    kinds: new Set(),
    observations: 0,
    objectKeys: new Set(),
    arrayItemKinds: new Set(),
    arrayMinLength: null,
    arrayMaxLength: null,
    authorityLike: authorityLikePath(path),
  };
}

function rowFor(rows, path) {
  let row = rows.get(path);
  if (!row) {
    row = pathRow(path);
    rows.set(path, row);
  }
  return row;
}

function walk(value, path, rows, counter, depth) {
  counter.nodes += 1;
  requireCondition(counter.nodes <= MAX_NODES, 'PROFILE_NODE_BOUNDS', 'shape profile exceeds bounded node count');
  requireCondition(depth <= MAX_DEPTH, 'PROFILE_DEPTH_BOUNDS', 'shape profile exceeds bounded depth');
  const kind = valueKind(value);
  const row = rowFor(rows, path);
  row.kinds.add(kind);
  row.observations += 1;

  if (kind === 'object') {
    const keys = Object.keys(value).sort();
    for (const key of keys) {
      requireCondition(!FORBIDDEN_KEYS.has(key), 'PROFILE_FORBIDDEN_KEY', `shape contains forbidden object key ${key}`);
      row.objectKeys.add(key);
      walk(value[key], pointer(path, key), rows, counter, depth + 1);
    }
    return;
  }

  if (kind === 'array') {
    row.arrayMinLength = row.arrayMinLength === null ? value.length : Math.min(row.arrayMinLength, value.length);
    row.arrayMaxLength = row.arrayMaxLength === null ? value.length : Math.max(row.arrayMaxLength, value.length);
    const childPath = pointer(path, '*');
    for (const item of value) {
      const itemKind = valueKind(item);
      row.arrayItemKinds.add(itemKind);
      walk(item, childPath, rows, counter, depth + 1);
    }
  }
}

function structuralRows(rows) {
  return [...rows.values()]
    .map((row) => ({
      path: row.path || '/',
      kinds: [...row.kinds].sort(),
      objectKeys: [...row.objectKeys].sort(),
      arrayItemKinds: [...row.arrayItemKinds].sort(),
      authorityLike: row.authorityLike,
    }))
    .sort((a, b) => a.path.localeCompare(b.path));
}

function observedRows(rows) {
  return [...rows.values()]
    .map((row) => ({
      path: row.path || '/',
      observations: row.observations,
      arrayMinLength: row.arrayMinLength,
      arrayMaxLength: row.arrayMaxLength,
    }))
    .sort((a, b) => a.path.localeCompare(b.path));
}

function profileIdentityBody(profile) {
  const { profileId: _profileId, fixtureDigest: _fixtureDigest, observations: _observations, claimBoundary: _claimBoundary, ...body } = profile;
  return body;
}

export function deriveShapeProfileId(profile) {
  return digest('polybolosshape1', profileIdentityBody(profile));
}

export function profileExternalShape(value, options = {}) {
  requireCondition(isRecord(value), 'PROFILE_ROOT_INVALID', 'external shape root must be an object');
  const externalShape = options.externalShape ?? value.schema;
  requireCondition(typeof externalShape === 'string' && externalShape.trim(), 'PROFILE_SCHEMA_MISSING', 'external shape schema is required');
  const rows = new Map();
  walk(value, '', rows, { nodes: 0 }, 0);
  const paths = structuralRows(rows);
  const body = {
    schema: 'axm-polybolos-shape-profile/1',
    externalShape: externalShape.trim(),
    rootKind: 'object',
    paths,
    pathCount: paths.length,
    authorityLikePaths: paths.filter((row) => row.authorityLike).map((row) => row.path),
  };
  const profile = {
    ...body,
    profileId: '',
    fixtureDigest: digest('polybolosfixture1', value),
    observations: observedRows(rows),
    claimBoundary:
      'This profile retains JSON structure, field names, types, and array cardinality observations without retaining field values. A single fixture establishes observed shape, not universal optionality or semantic meaning.',
  };
  profile.profileId = deriveShapeProfileId(profile);
  return profile;
}

export function compareShapeProfiles(expected, observed) {
  requireCondition(
    isRecord(expected) && expected.schema === 'axm-polybolos-shape-profile/1',
    'PROFILE_SCHEMA_INVALID',
    'expected shape profile is invalid',
  );
  requireCondition(
    isRecord(observed) && observed.schema === 'axm-polybolos-shape-profile/1',
    'PROFILE_SCHEMA_INVALID',
    'observed shape profile is invalid',
  );
  const before = new Map(expected.paths.map((row) => [row.path, row]));
  const after = new Map(observed.paths.map((row) => [row.path, row]));
  const added = [...after.keys()].filter((path) => !before.has(path)).sort();
  const removed = [...before.keys()].filter((path) => !after.has(path)).sort();
  const changed = [...after.keys()]
    .filter((path) => before.has(path) && canonicalJson(before.get(path)) !== canonicalJson(after.get(path)))
    .sort();
  return {
    schema: 'axm-polybolos-shape-diff/1',
    expectedProfileId: expected.profileId,
    observedProfileId: observed.profileId,
    equal: added.length === 0 && removed.length === 0 && changed.length === 0,
    added,
    removed,
    changed,
  };
}

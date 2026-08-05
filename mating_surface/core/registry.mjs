#!/usr/bin/env node
import { createHash } from 'node:crypto';
import { readFile } from 'node:fs/promises';
import { pathToFileURL } from 'node:url';

const SHA256 = /^[0-9a-f]{64}$/;
const PROVIDER_MODES = new Set(['pass_through', 'official_codegen', 'loss_accounted_gateway']);
const FORBIDDEN_CANONICAL_KEYS = new Set([
  'vendor',
  'vendorname',
  'brand',
  'branding',
  'logo',
  'dandelion',
  'productui',
  'privateschema',
  'nativefields',
]);

export class SurfaceError extends Error {
  constructor(code, message) {
    super(message);
    this.name = 'SurfaceError';
    this.code = code;
  }
}

function requireCondition(condition, code, message) {
  if (!condition) throw new SurfaceError(code, message);
}

function isRecord(value) {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) return false;
  const prototype = Object.getPrototypeOf(value);
  return prototype === Object.prototype || prototype === null;
}

function normalizedKey(value) {
  return String(value).replace(/[^a-z0-9]/gi, '').toLowerCase();
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

function assertNoCanonicalBranding(value, path = '$') {
  if (Array.isArray(value)) {
    value.forEach((row, index) => assertNoCanonicalBranding(row, `${path}[${index}]`));
    return;
  }
  if (!isRecord(value)) return;
  for (const [key, nested] of Object.entries(value)) {
    requireCondition(
      !FORBIDDEN_CANONICAL_KEYS.has(normalizedKey(key)),
      'CANONICAL_BRANDING_FORBIDDEN',
      `canonical surface contains provider or branding key ${key} at ${path}`,
    );
    assertNoCanonicalBranding(nested, `${path}.${key}`);
  }
}

export function validateRegistry(registry) {
  requireCondition(
    isRecord(registry) && registry.schema === 'standards-mating-surface-registry/1',
    'REGISTRY_SCHEMA_INVALID',
    'standards registry schema is invalid',
  );
  requireCondition(isRecord(registry.policies), 'REGISTRY_POLICY_INVALID', 'registry policies are missing');
  requireCondition(
    registry.policies.canonicalTerms === 'registered_standard_only',
    'REGISTRY_POLICY_INVALID',
    'canonical terms must come from registered standards',
  );
  requireCondition(Array.isArray(registry.standards) && registry.standards.length > 0, 'REGISTRY_EMPTY', 'registry has no standards');
  const byId = new Map();
  for (const standard of registry.standards) {
    requireCondition(isRecord(standard), 'STANDARD_INVALID', 'standard entry must be an object');
    requireCondition(typeof standard.id === 'string' && standard.id, 'STANDARD_ID_INVALID', 'standard ID is missing');
    requireCondition(!byId.has(standard.id), 'STANDARD_ID_DUPLICATE', `duplicate standard ${standard.id}`);
    requireCondition(typeof standard.title === 'string' && standard.title, 'STANDARD_TITLE_INVALID', `standard ${standard.id} has no title`);
    requireCondition(typeof standard.authority === 'string' && standard.authority, 'STANDARD_AUTHORITY_INVALID', `standard ${standard.id} has no authority`);
    requireCondition(Array.isArray(standard.roles) && standard.roles.length > 0, 'STANDARD_ROLE_INVALID', `standard ${standard.id} has no roles`);
    requireCondition(typeof standard.officialLocator === 'string' && standard.officialLocator.startsWith('https://'), 'STANDARD_LOCATOR_INVALID', `standard ${standard.id} has no official HTTPS locator`);
    requireCondition(typeof standard.artifactPolicy === 'string' && standard.artifactPolicy, 'STANDARD_ARTIFACT_POLICY_INVALID', `standard ${standard.id} has no artifact policy`);
    requireCondition(typeof standard.payloadPolicy === 'string' && standard.payloadPolicy, 'STANDARD_PAYLOAD_POLICY_INVALID', `standard ${standard.id} has no payload policy`);
    byId.set(standard.id, standard);
  }
  return { registry, byId, registryId: digest('standardsregistry1', registry) };
}

export function validateVenueProfile(profile, registry) {
  const validatedRegistry = validateRegistry(registry);
  requireCondition(
    isRecord(profile) && profile.schema === 'standards-mating-surface-venue/1',
    'VENUE_SCHEMA_INVALID',
    'venue profile schema is invalid',
  );
  requireCondition(typeof profile.profileId === 'string' && profile.profileId, 'VENUE_ID_INVALID', 'venue profile ID is missing');
  requireCondition(profile.canonicalVocabulary === 'selected_standard_artifacts', 'VENUE_CANONICALITY_INVALID', 'venue profile does not use selected standard artifacts');
  requireCondition(profile.providerVocabulary === 'edge_only', 'VENUE_PROVIDER_BOUNDARY_INVALID', 'provider vocabulary must remain at the edge');
  requireCondition(profile.surfaceBranding === 'none', 'VENUE_BRANDING_INVALID', 'operational surface must not carry product branding');
  requireCondition(Array.isArray(profile.ports) && profile.ports.length > 0, 'VENUE_PORTS_INVALID', 'venue profile has no ports');
  assertNoCanonicalBranding(profile.ports);

  const ports = new Map();
  for (const port of profile.ports) {
    requireCondition(isRecord(port), 'VENUE_PORT_INVALID', 'venue port must be an object');
    requireCondition(typeof port.id === 'string' && port.id, 'VENUE_PORT_ID_INVALID', 'venue port ID is missing');
    requireCondition(!ports.has(port.id), 'VENUE_PORT_DUPLICATE', `duplicate venue port ${port.id}`);
    requireCondition(Array.isArray(port.allowedStandards) && port.allowedStandards.length > 0, 'VENUE_STANDARD_INVALID', `port ${port.id} has no allowed standards`);
    for (const standardId of port.allowedStandards) {
      requireCondition(validatedRegistry.byId.has(standardId), 'VENUE_STANDARD_UNKNOWN', `port ${port.id} cites unknown standard ${standardId}`);
    }
    requireCondition(Array.isArray(port.requirements) && port.requirements.length > 0, 'VENUE_REQUIREMENTS_INVALID', `port ${port.id} has no requirements`);
    ports.set(port.id, port);
  }

  requireCondition(Array.isArray(profile.sidecars) && profile.sidecars.length > 0, 'VENUE_SIDECAR_INVALID', 'venue profile has no sidecars');
  for (const sidecar of profile.sidecars) {
    requireCondition(isRecord(sidecar), 'VENUE_SIDECAR_INVALID', 'sidecar must be an object');
    requireCondition(sidecar.mayDefineDomainSemantics === false, 'VENUE_SIDECAR_SEMANTICS_INVALID', 'sidecar may not define domain semantics');
    requireCondition(Array.isArray(sidecar.binds) && sidecar.binds.length > 0, 'VENUE_SIDECAR_INVALID', 'sidecar has no bindings');
  }

  const body = {
    registryId: validatedRegistry.registryId,
    profile,
  };
  return {
    registryId: validatedRegistry.registryId,
    surfaceId: digest('standardsurface1', body),
    profile,
    ports,
    standards: validatedRegistry.byId,
  };
}

function assertSha256(value, code, label) {
  requireCondition(typeof value === 'string' && SHA256.test(value), code, `${label} must be a lowercase SHA-256 digest`);
}

export function bindStandardMessage(binding, profile, registry) {
  const surface = validateVenueProfile(profile, registry);
  requireCondition(
    isRecord(binding) && binding.schema === 'standards-mating-surface-binding/1',
    'BINDING_SCHEMA_INVALID',
    'standard binding schema is invalid',
  );
  const port = surface.ports.get(binding.portId);
  requireCondition(port, 'BINDING_PORT_UNKNOWN', `unknown venue port ${binding.portId}`);
  requireCondition(port.allowedStandards.includes(binding.standardId), 'BINDING_STANDARD_NOT_ALLOWED', `standard ${binding.standardId} is not allowed on port ${binding.portId}`);
  const standard = surface.standards.get(binding.standardId);
  requireCondition(typeof binding.standardRevision === 'string' && binding.standardRevision.trim(), 'BINDING_REVISION_INVALID', 'standard revision or program profile is required');
  requireCondition(typeof binding.validatorId === 'string' && binding.validatorId.trim(), 'BINDING_VALIDATOR_INVALID', 'validator identity is required');
  assertSha256(binding.artifactDigest, 'BINDING_ARTIFACT_INVALID', 'artifactDigest');
  assertSha256(binding.payloadDigest, 'BINDING_PAYLOAD_INVALID', 'payloadDigest');
  requireCondition(typeof binding.messageIdentity === 'string' && binding.messageIdentity.trim(), 'BINDING_MESSAGE_ID_INVALID', 'standard message identity is required');
  requireCondition(typeof binding.sourceSystemId === 'string' && binding.sourceSystemId.trim(), 'BINDING_SOURCE_INVALID', 'source system identity is required');
  requireCondition(!Object.prototype.hasOwnProperty.call(binding, 'payload'), 'BINDING_PAYLOAD_INLINE_FORBIDDEN', 'standard payload must remain external or encoded by its official codec');
  if (standard.access === 'controlled_distribution' || standard.access === 'program_or_government_sponsor') {
    requireCondition(typeof binding.authorizationReference === 'string' && binding.authorizationReference.trim(), 'BINDING_AUTHORIZATION_REQUIRED', 'controlled standard binding requires an authorization reference');
  }
  const body = {
    surfaceId: surface.surfaceId,
    portId: binding.portId,
    standardId: binding.standardId,
    standardRevision: binding.standardRevision.trim(),
    artifactDigest: binding.artifactDigest,
    validatorId: binding.validatorId.trim(),
    payloadDigest: binding.payloadDigest,
    messageIdentity: binding.messageIdentity.trim(),
    sourceSystemId: binding.sourceSystemId.trim(),
    authorizationReference: binding.authorizationReference ?? null,
    observedAt: binding.observedAt ?? null,
  };
  if (body.observedAt !== null) {
    requireCondition(Number.isFinite(Date.parse(body.observedAt)), 'BINDING_TIME_INVALID', 'observedAt is invalid');
    body.observedAt = new Date(Date.parse(body.observedAt)).toISOString();
  }
  return {
    schema: 'standards-mating-surface-bound-message/1',
    bindingId: digest('standardbinding1', body),
    ...body,
    claimBoundary: 'This receipt binds an externally encoded standard message to an exact standard artifact and validator. It does not redefine the standard or grant command authority.',
  };
}

export function validateProviderAdapter(adapter, profile, registry) {
  const surface = validateVenueProfile(profile, registry);
  requireCondition(
    isRecord(adapter) && adapter.schema === 'standards-mating-surface-provider-adapter/1',
    'ADAPTER_SCHEMA_INVALID',
    'provider adapter schema is invalid',
  );
  requireCondition(typeof adapter.providerId === 'string' && adapter.providerId.trim(), 'ADAPTER_PROVIDER_INVALID', 'provider ID is required');
  requireCondition(!Object.prototype.hasOwnProperty.call(adapter, 'ui'), 'ADAPTER_UI_FORBIDDEN', 'provider adapter may not define the operational UI');
  requireCondition(!Object.prototype.hasOwnProperty.call(adapter, 'canonicalFields'), 'ADAPTER_CANONICAL_FIELDS_FORBIDDEN', 'provider adapter may not define canonical venue fields');
  requireCondition(Array.isArray(adapter.ports) && adapter.ports.length > 0, 'ADAPTER_PORTS_INVALID', 'provider adapter has no ports');
  const seen = new Set();
  for (const binding of adapter.ports) {
    requireCondition(isRecord(binding), 'ADAPTER_PORT_INVALID', 'provider port binding must be an object');
    requireCondition(typeof binding.portId === 'string' && surface.ports.has(binding.portId), 'ADAPTER_PORT_UNKNOWN', `unknown provider port ${binding.portId}`);
    requireCondition(surface.ports.get(binding.portId).allowedStandards.includes(binding.standardId), 'ADAPTER_STANDARD_NOT_ALLOWED', `provider standard ${binding.standardId} is not allowed on ${binding.portId}`);
    requireCondition(PROVIDER_MODES.has(binding.mode), 'ADAPTER_MODE_INVALID', `unsupported provider adapter mode ${binding.mode}`);
    const key = `${binding.portId}\0${binding.standardId}`;
    requireCondition(!seen.has(key), 'ADAPTER_PORT_DUPLICATE', `duplicate provider binding ${key}`);
    seen.add(key);
    if (binding.mode === 'pass_through' || binding.mode === 'official_codegen') {
      assertSha256(binding.artifactDigest, 'ADAPTER_ARTIFACT_INVALID', 'provider artifactDigest');
    }
    if (binding.mode === 'loss_accounted_gateway') {
      requireCondition(Array.isArray(binding.declaredLosses), 'ADAPTER_LOSSES_REQUIRED', 'loss-accounted gateway requires declared losses');
      requireCondition(typeof binding.gatewayDescriptorId === 'string' && binding.gatewayDescriptorId.trim(), 'ADAPTER_GATEWAY_DESCRIPTOR_REQUIRED', 'loss-accounted gateway requires a gateway descriptor');
    }
  }
  const body = {
    surfaceId: surface.surfaceId,
    providerId: adapter.providerId.trim(),
    nativeImplementation: adapter.nativeImplementation ?? null,
    ports: adapter.ports,
  };
  return {
    schema: 'standards-mating-surface-provider-admission/1',
    adapterId: digest('provideradapter1', body),
    ...body,
    claimBoundary: 'The provider remains an edge implementation. Canonical semantics belong to the selected venue standards.',
  };
}

async function main(argv) {
  if (argv.length !== 2) {
    console.error('usage: registry.mjs <registry.json> <venue-profile.json>');
    return 2;
  }
  const [registryPath, profilePath] = argv;
  const registry = JSON.parse(await readFile(registryPath, 'utf8'));
  const profile = JSON.parse(await readFile(profilePath, 'utf8'));
  const receipt = validateVenueProfile(profile, registry);
  process.stdout.write(`${JSON.stringify({
    schema: 'standards-mating-surface-profile-receipt/1',
    status: 'pass',
    registryId: receipt.registryId,
    surfaceId: receipt.surfaceId,
    profileId: receipt.profile.profileId,
    ports: [...receipt.ports.keys()],
  }, null, 2)}\n`);
  return 0;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  process.exitCode = await main(process.argv.slice(2));
}

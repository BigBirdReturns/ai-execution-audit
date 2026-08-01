#!/usr/bin/env node
import { createHash } from 'node:crypto';
import { readFile, writeFile } from 'node:fs/promises';
import { pathToFileURL } from 'node:url';
import {
  bindStandardMessage,
  canonicalJson,
  validateRegistry,
  validateVenueProfile,
} from './registry.mjs';

const SHA1 = /^[0-9a-f]{40}$/;
const SHA256 = /^[0-9a-f]{64}$/;
const ARTIFACT_CLASSES = new Set([
  'official_authority_artifact',
  'official_authority_mirror',
  'program_authorized_controlled',
  'reference_implementation_snapshot',
  'synthetic_fixture',
]);
const USE_BOUNDARIES = new Set([
  'operational_and_test',
  'program_authorized_only',
  'simulation_and_test_only',
  'test_only',
]);
const USE_MODES = new Set(['operational', 'rehearsal', 'test']);
const MAX_ARTIFACT_BYTES = 64 * 1024 * 1024;

export class ArtifactError extends Error {
  constructor(code, message) {
    super(message);
    this.name = 'ArtifactError';
    this.code = code;
  }
}

function requireCondition(condition, code, message) {
  if (!condition) throw new ArtifactError(code, message);
}

function isRecord(value) {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) return false;
  const prototype = Object.getPrototypeOf(value);
  return prototype === Object.prototype || prototype === null;
}

function digest(prefix, value) {
  return `${prefix}_${createHash('sha256').update(canonicalJson(value), 'utf8').digest('hex')}`;
}

function assertLowerHex(value, pattern, code, label) {
  requireCondition(typeof value === 'string' && pattern.test(value), code, `${label} is invalid`);
}

function manifestIdentityBody(manifest) {
  const { claimBoundary: _claimBoundary, ...body } = manifest;
  return body;
}

export function deriveArtifactManifestId(manifest) {
  return digest('standardartifactmanifest1', manifestIdentityBody(manifest));
}

export function computeGitBlobSha(bytes) {
  requireCondition(Buffer.isBuffer(bytes), 'ARTIFACT_BYTES_INVALID', 'artifact bytes must be a Buffer');
  const header = Buffer.from(`blob ${bytes.length}\0`, 'utf8');
  return createHash('sha1').update(header).update(bytes).digest('hex');
}

export function computeSha256(bytes) {
  requireCondition(Buffer.isBuffer(bytes), 'ARTIFACT_BYTES_INVALID', 'artifact bytes must be a Buffer');
  return createHash('sha256').update(bytes).digest('hex');
}

export function validateArtifactManifest(manifest, registry) {
  const validatedRegistry = validateRegistry(registry);
  requireCondition(
    isRecord(manifest) && manifest.schema === 'standards-mating-surface-artifact-manifest/1',
    'ARTIFACT_MANIFEST_SCHEMA_INVALID',
    'artifact manifest schema is invalid',
  );
  requireCondition(
    typeof manifest.artifactId === 'string' && manifest.artifactId.trim(),
    'ARTIFACT_ID_INVALID',
    'artifactId is required',
  );
  requireCondition(
    typeof manifest.standardId === 'string' && validatedRegistry.byId.has(manifest.standardId),
    'ARTIFACT_STANDARD_UNKNOWN',
    `artifact cites unknown standard ${manifest.standardId}`,
  );
  requireCondition(
    typeof manifest.standardRevision === 'string' && manifest.standardRevision.trim(),
    'ARTIFACT_REVISION_INVALID',
    'standardRevision is required',
  );
  requireCondition(
    ARTIFACT_CLASSES.has(manifest.artifactClass),
    'ARTIFACT_CLASS_INVALID',
    'artifactClass is invalid',
  );
  requireCondition(
    USE_BOUNDARIES.has(manifest.useBoundary),
    'ARTIFACT_USE_BOUNDARY_INVALID',
    'useBoundary is invalid',
  );
  if (
    manifest.artifactClass === 'reference_implementation_snapshot'
    || manifest.artifactClass === 'synthetic_fixture'
  ) {
    requireCondition(
      manifest.useBoundary === 'simulation_and_test_only' || manifest.useBoundary === 'test_only',
      'ARTIFACT_USE_BOUNDARY_INVALID',
      'reference and synthetic artifacts may not claim an operational use boundary',
    );
  }

  requireCondition(isRecord(manifest.source), 'ARTIFACT_SOURCE_INVALID', 'artifact source is missing');
  requireCondition(
    typeof manifest.source.repository === 'string'
      && /^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(manifest.source.repository),
    'ARTIFACT_SOURCE_INVALID',
    'source repository must be owner/name',
  );
  assertLowerHex(manifest.source.commit, SHA1, 'ARTIFACT_SOURCE_INVALID', 'source commit');
  requireCondition(
    typeof manifest.source.path === 'string'
      && manifest.source.path.length > 0
      && manifest.source.path.length <= 1024
      && !manifest.source.path.startsWith('/')
      && !manifest.source.path.split('/').includes('..'),
    'ARTIFACT_SOURCE_INVALID',
    'source path is invalid',
  );
  assertLowerHex(manifest.source.gitBlobSha, SHA1, 'ARTIFACT_SOURCE_INVALID', 'source Git blob SHA');

  requireCondition(
    manifest.mediaType === 'application/xml',
    'ARTIFACT_MEDIA_TYPE_INVALID',
    'this artifact lane currently admits application/xml only',
  );
  requireCondition(manifest.format === 'xsd', 'ARTIFACT_FORMAT_INVALID', 'this artifact lane currently admits XSD only');
  requireCondition(isRecord(manifest.expected), 'ARTIFACT_EXPECTED_INVALID', 'expected XML identity is missing');
  for (const key of ['rootLocalName', 'rootNamespace', 'targetNamespace']) {
    requireCondition(
      typeof manifest.expected[key] === 'string' && manifest.expected[key],
      'ARTIFACT_EXPECTED_INVALID',
      `expected.${key} is required`,
    );
  }
  requireCondition(
    typeof manifest.expected.forbidDoctype === 'boolean',
    'ARTIFACT_EXPECTED_INVALID',
    'expected.forbidDoctype must be boolean',
  );

  requireCondition(isRecord(manifest.validator), 'ARTIFACT_VALIDATOR_INVALID', 'validator declaration is missing');
  requireCondition(
    manifest.validator.kind === 'xml_well_formedness',
    'ARTIFACT_VALIDATOR_INVALID',
    'validator kind is unsupported',
  );
  requireCondition(
    typeof manifest.validator.validatorId === 'string' && manifest.validator.validatorId.trim(),
    'ARTIFACT_VALIDATOR_INVALID',
    'validatorId is required',
  );
  requireCondition(
    manifest.validator.semanticSchemaValidation === false,
    'ARTIFACT_VALIDATOR_INVALID',
    'this lane must not claim full XSD semantic validation',
  );
  requireCondition(isRecord(manifest.license), 'ARTIFACT_LICENSE_INVALID', 'artifact license is missing');
  requireCondition(
    typeof manifest.license.spdx === 'string' && manifest.license.spdx.trim(),
    'ARTIFACT_LICENSE_INVALID',
    'license SPDX identifier is required',
  );

  return {
    manifest,
    manifestId: deriveArtifactManifestId(manifest),
    standard: validatedRegistry.byId.get(manifest.standardId),
  };
}

function stripLeadingXmlPreamble(text) {
  let value = text.replace(/^\uFEFF/, '');
  value = value.replace(/^\s*<\?xml[\s\S]*?\?>/i, '');
  while (/^\s*<!--/.test(value)) {
    value = value.replace(/^\s*<!--[\s\S]*?-->/, '');
  }
  return value;
}

function extractAttribute(attributes, name) {
  const escaped = name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const match = attributes.match(new RegExp(`(?:^|\\s)${escaped}\\s*=\\s*(["'])([\\s\\S]*?)\\1`));
  return match ? match[2] : null;
}

function inspectXsd(text, expected) {
  requireCondition(!text.includes('\u0000'), 'ARTIFACT_XML_INVALID', 'XML artifact contains NUL bytes');
  requireCondition(!text.includes('\uFFFD'), 'ARTIFACT_ENCODING_INVALID', 'XML artifact is not valid UTF-8');
  if (expected.forbidDoctype) {
    requireCondition(!/<!DOCTYPE\b/i.test(text), 'ARTIFACT_DOCTYPE_FORBIDDEN', 'XML artifact contains a forbidden DOCTYPE');
  }
  const significant = stripLeadingXmlPreamble(text);
  const root = significant.match(/^\s*<(?:(?<prefix>[A-Za-z_][\w.-]*):)?(?<local>[A-Za-z_][\w.-]*)\b(?<attributes>[\s\S]*?)>/);
  requireCondition(root?.groups, 'ARTIFACT_XML_ROOT_INVALID', 'XML root element is missing');
  requireCondition(
    root.groups.local === expected.rootLocalName,
    'ARTIFACT_XML_ROOT_INVALID',
    `XML root local name ${root.groups.local} does not match ${expected.rootLocalName}`,
  );
  const prefix = root.groups.prefix ?? '';
  const namespaceAttribute = prefix ? `xmlns:${prefix}` : 'xmlns';
  const rootNamespace = extractAttribute(root.groups.attributes, namespaceAttribute);
  requireCondition(
    rootNamespace === expected.rootNamespace,
    'ARTIFACT_XML_NAMESPACE_INVALID',
    `XML root namespace ${rootNamespace ?? '<missing>'} does not match ${expected.rootNamespace}`,
  );
  const targetNamespace = extractAttribute(root.groups.attributes, 'targetNamespace');
  requireCondition(
    targetNamespace === expected.targetNamespace,
    'ARTIFACT_TARGET_NAMESPACE_INVALID',
    `targetNamespace ${targetNamespace ?? '<missing>'} does not match ${expected.targetNamespace}`,
  );
  return {
    rootLocalName: root.groups.local,
    rootNamespace,
    targetNamespace,
  };
}

function validateValidatorReceipt(receipt, manifest, artifactSha256) {
  requireCondition(
    isRecord(receipt) && receipt.schema === 'standards-xml-wellformedness-receipt/1',
    'ARTIFACT_VALIDATOR_RECEIPT_INVALID',
    'XML validator receipt schema is invalid',
  );
  requireCondition(receipt.status === 'pass', 'ARTIFACT_VALIDATOR_FAILED', 'XML validator did not pass');
  requireCondition(
    receipt.validatorId === manifest.validator.validatorId,
    'ARTIFACT_VALIDATOR_RECEIPT_INVALID',
    'validator receipt uses another validator identity',
  );
  requireCondition(
    receipt.artifactSha256 === artifactSha256,
    'ARTIFACT_VALIDATOR_RECEIPT_INVALID',
    'validator receipt covers another artifact',
  );
  requireCondition(
    receipt.semanticSchemaValidation === false,
    'ARTIFACT_VALIDATOR_RECEIPT_INVALID',
    'well-formedness receipt may not claim semantic schema validation',
  );
  return receipt;
}

export function verifyArtifactBytes(manifest, registry, bytes, validatorReceipt) {
  const validated = validateArtifactManifest(manifest, registry);
  requireCondition(Buffer.isBuffer(bytes), 'ARTIFACT_BYTES_INVALID', 'artifact bytes must be a Buffer');
  requireCondition(bytes.length > 0, 'ARTIFACT_BYTES_INVALID', 'artifact is empty');
  requireCondition(bytes.length <= MAX_ARTIFACT_BYTES, 'ARTIFACT_BYTES_INVALID', 'artifact exceeds the 64 MiB custody bound');

  const gitBlobSha = computeGitBlobSha(bytes);
  requireCondition(
    gitBlobSha === manifest.source.gitBlobSha,
    'ARTIFACT_GIT_BLOB_MISMATCH',
    'artifact bytes do not match the pinned Git blob identity',
  );
  const artifactSha256 = computeSha256(bytes);
  const xml = inspectXsd(bytes.toString('utf8'), manifest.expected);
  const validator = validateValidatorReceipt(validatorReceipt, manifest, artifactSha256);
  const body = {
    manifestId: validated.manifestId,
    artifactId: manifest.artifactId,
    standardId: manifest.standardId,
    standardRevision: manifest.standardRevision,
    artifactClass: manifest.artifactClass,
    useBoundary: manifest.useBoundary,
    source: manifest.source,
    bytes: bytes.length,
    gitBlobSha,
    artifactSha256,
    xml,
    validator: {
      validatorId: validator.validatorId,
      validatorVersion: validator.validatorVersion,
      semanticSchemaValidation: false,
    },
    license: manifest.license,
  };
  return {
    schema: 'standards-mating-surface-artifact-admission/1',
    admissionId: digest('standardartifactadmission1', body),
    ...body,
    claimBoundary:
      'This receipt proves exact custody and XML well-formedness for one pinned artifact. It does not prove that the artifact is an official standards-authority distribution, does not perform full XSD semantic validation, and grants no operational authority.',
  };
}

export function admitArtifactUse(request, admission, profile, registry) {
  const surface = validateVenueProfile(profile, registry);
  requireCondition(
    isRecord(request) && request.schema === 'standards-mating-surface-artifact-use-request/1',
    'ARTIFACT_USE_SCHEMA_INVALID',
    'artifact use request schema is invalid',
  );
  requireCondition(USE_MODES.has(request.mode), 'ARTIFACT_USE_MODE_INVALID', 'artifact use mode is invalid');
  requireCondition(request.profileId === profile.profileId, 'ARTIFACT_USE_PROFILE_MISMATCH', 'artifact use cites another venue profile');
  const port = surface.ports.get(request.portId);
  requireCondition(port, 'ARTIFACT_USE_PORT_UNKNOWN', `unknown venue port ${request.portId}`);
  requireCondition(request.standardId === admission.standardId, 'ARTIFACT_USE_STANDARD_MISMATCH', 'artifact use standard differs from the admitted artifact');
  requireCondition(port.allowedStandards.includes(admission.standardId), 'ARTIFACT_USE_STANDARD_NOT_ALLOWED', 'artifact standard is not allowed on the selected port');
  requireCondition(request.admissionId === admission.admissionId, 'ARTIFACT_USE_ADMISSION_MISMATCH', 'artifact use cites another admission receipt');

  const testMode = request.mode === 'test' || request.mode === 'rehearsal';
  if (!testMode) {
    requireCondition(
      admission.useBoundary === 'operational_and_test'
        || admission.useBoundary === 'program_authorized_only',
      'ARTIFACT_OPERATIONAL_USE_FORBIDDEN',
      'the admitted artifact is not authorized for operational use',
    );
    requireCondition(
      admission.artifactClass === 'official_authority_artifact'
        || admission.artifactClass === 'official_authority_mirror'
        || admission.artifactClass === 'program_authorized_controlled',
      'ARTIFACT_OPERATIONAL_CLASS_FORBIDDEN',
      'reference and synthetic artifacts cannot satisfy an operational port',
    );
  }
  if (request.mode === 'rehearsal') {
    requireCondition(
      request.portId === 'simulation-and-rehearsal',
      'ARTIFACT_REHEARSAL_PORT_INVALID',
      'rehearsal artifacts must remain on the simulation-and-rehearsal port',
    );
  }

  const body = {
    surfaceId: surface.surfaceId,
    profileId: profile.profileId,
    mode: request.mode,
    portId: request.portId,
    standardId: admission.standardId,
    admissionId: admission.admissionId,
    artifactSha256: admission.artifactSha256,
  };
  return {
    schema: 'standards-mating-surface-artifact-use/1',
    useId: digest('standardartifactuse1', body),
    ...body,
    claimBoundary:
      'This receipt admits one exact artifact for one venue port and use mode. It does not widen the artifact class, alter the standard, or grant command authority.',
  };
}

export function bindAdmittedStandardMessage(binding, admission, useReceipt, profile, registry) {
  requireCondition(
    isRecord(useReceipt) && useReceipt.schema === 'standards-mating-surface-artifact-use/1',
    'BOUND_ARTIFACT_USE_INVALID',
    'artifact use receipt is invalid',
  );
  requireCondition(useReceipt.admissionId === admission.admissionId, 'BOUND_ARTIFACT_USE_INVALID', 'artifact use receipt cites another admission');
  requireCondition(binding.portId === useReceipt.portId, 'BOUND_ARTIFACT_PORT_MISMATCH', 'message binding uses another port');
  requireCondition(binding.standardId === useReceipt.standardId, 'BOUND_ARTIFACT_STANDARD_MISMATCH', 'message binding uses another standard');
  requireCondition(binding.standardRevision === admission.standardRevision, 'BOUND_ARTIFACT_REVISION_MISMATCH', 'message binding uses another standard revision');
  requireCondition(binding.artifactDigest === admission.artifactSha256, 'BOUND_ARTIFACT_DIGEST_MISMATCH', 'message binding uses another artifact digest');
  requireCondition(binding.validatorId === admission.validator.validatorId, 'BOUND_ARTIFACT_VALIDATOR_MISMATCH', 'message binding uses another validator');
  const bound = bindStandardMessage(binding, profile, registry);
  const body = {
    boundMessageId: bound.bindingId,
    admissionId: admission.admissionId,
    useId: useReceipt.useId,
  };
  return {
    schema: 'standards-mating-surface-admitted-message/1',
    receiptId: digest('standardadmittedmessage1', body),
    ...body,
    boundMessage: bound,
    claimBoundary:
      'This receipt binds an external standard message to one admitted artifact and venue use receipt. The payload remains standard-shaped and external; this receipt does not grant authority.',
  };
}

async function main(argv) {
  if (argv.length !== 7) {
    console.error('usage: artifacts.mjs <registry.json> <venue.json> <manifest.json> <artifact> <validator-receipt.json> <use-request.json> <output.json>');
    return 2;
  }
  const [registryPath, venuePath, manifestPath, artifactPath, validatorPath, usePath, outputPath] = argv;
  const [registry, venue, manifest, artifact, validatorReceipt, useRequest] = await Promise.all([
    readFile(registryPath, 'utf8').then(JSON.parse),
    readFile(venuePath, 'utf8').then(JSON.parse),
    readFile(manifestPath, 'utf8').then(JSON.parse),
    readFile(artifactPath),
    readFile(validatorPath, 'utf8').then(JSON.parse),
    readFile(usePath, 'utf8').then(JSON.parse),
  ]);
  const admission = verifyArtifactBytes(manifest, registry, artifact, validatorReceipt);
  const use = admitArtifactUse({ ...useRequest, admissionId: admission.admissionId }, admission, venue, registry);
  const receipt = {
    schema: 'standards-mating-surface-artifact-transaction/1',
    status: 'pass',
    manifestId: admission.manifestId,
    admission,
    use,
  };
  await writeFile(outputPath, `${JSON.stringify(receipt, null, 2)}\n`, 'utf8');
  process.stdout.write(`${JSON.stringify({
    status: receipt.status,
    admissionId: admission.admissionId,
    useId: use.useId,
    artifactSha256: admission.artifactSha256,
    bytes: admission.bytes,
    output: outputPath,
  }, null, 2)}\n`);
  return 0;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  process.exitCode = await main(process.argv.slice(2));
}

import assert from 'node:assert/strict';
import test from 'node:test';
import { readFile } from 'node:fs/promises';
import {
  admitArtifactUse,
  bindAdmittedStandardMessage,
  computeGitBlobSha,
  computeSha256,
  verifyArtifactBytes,
} from '../core/artifacts.mjs';

const registry = JSON.parse(
  await readFile(new URL('../standards/registry.json', import.meta.url), 'utf8'),
);
const venue = JSON.parse(
  await readFile(new URL('../venues/joint-edge-command-authority.json', import.meta.url), 'utf8'),
);

function xsd(targetNamespace = 'http://www.sisostds.org/schemas/C2SIM/1.1') {
  return Buffer.from(`<?xml version="1.0" encoding="UTF-8"?>\n<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" targetNamespace="${targetNamespace}" elementFormDefault="qualified">\n  <xs:element name="C2SIMMessage" type="xs:string"/>\n</xs:schema>\n`, 'utf8');
}

function manifest(bytes, overrides = {}) {
  return {
    schema: 'standards-mating-surface-artifact-manifest/1',
    artifactId: 'fixture-c2sim-reference',
    standardId: 'siso-std-019-2020-c2sim',
    standardRevision: 'C2SIM 1.0.1 / namespace 1.1',
    artifactClass: 'reference_implementation_snapshot',
    useBoundary: 'simulation_and_test_only',
    source: {
      repository: 'OpenC2SIM/OpenC2SIM.github.io',
      commit: '1'.repeat(40),
      path: 'C2SIM_SMX_LOX_V1.0.1.xsd',
      gitBlobSha: computeGitBlobSha(bytes),
    },
    mediaType: 'application/xml',
    format: 'xsd',
    expected: {
      rootLocalName: 'schema',
      rootNamespace: 'http://www.w3.org/2001/XMLSchema',
      targetNamespace: 'http://www.sisostds.org/schemas/C2SIM/1.1',
      forbidDoctype: true,
    },
    validator: {
      kind: 'xml_well_formedness',
      validatorId: 'xmllint',
      semanticSchemaValidation: false,
    },
    license: { spdx: 'MIT', source: 'https://example.invalid/source' },
    claimBoundary: 'fixture only',
    ...overrides,
  };
}

function validatorReceipt(bytes, overrides = {}) {
  return {
    schema: 'standards-xml-wellformedness-receipt/1',
    status: 'pass',
    validatorId: 'xmllint',
    validatorVersion: 'fixture xmllint',
    artifactSha256: computeSha256(bytes),
    bytes: bytes.length,
    networkAccess: 'disabled_by_nonet',
    semanticSchemaValidation: false,
    claimBoundary: 'fixture only',
    ...overrides,
  };
}

function admit(bytes = xsd(), overrides = {}) {
  return verifyArtifactBytes(
    manifest(bytes, overrides),
    registry,
    bytes,
    validatorReceipt(bytes),
  );
}

function rehearsalUse(admission) {
  return admitArtifactUse(
    {
      schema: 'standards-mating-surface-artifact-use-request/1',
      profileId: venue.profileId,
      mode: 'rehearsal',
      portId: 'simulation-and-rehearsal',
      standardId: admission.standardId,
      admissionId: admission.admissionId,
    },
    admission,
    venue,
    registry,
  );
}

test('admits exact XSD bytes and preserves the artifact claim boundary', () => {
  const admission = admit();
  assert.equal(admission.schema, 'standards-mating-surface-artifact-admission/1');
  assert.equal(admission.gitBlobSha, manifest(xsd()).source.gitBlobSha);
  assert.equal(admission.xml.targetNamespace, 'http://www.sisostds.org/schemas/C2SIM/1.1');
  assert.equal(admission.validator.semanticSchemaValidation, false);
  assert.match(admission.claimBoundary, /does not perform full XSD semantic validation/);
});

test('rejects altered bytes before namespace or use evaluation', () => {
  const original = xsd();
  const altered = Buffer.concat([original, Buffer.from('<!-- altered -->\n')]);
  assert.throws(
    () => verifyArtifactBytes(manifest(original), registry, altered, validatorReceipt(altered)),
    (error) => error.code === 'ARTIFACT_GIT_BLOB_MISMATCH',
  );
});

test('rejects a forbidden DOCTYPE even when the manifest pins those bytes', () => {
  const bytes = Buffer.from(`<?xml version="1.0"?><!DOCTYPE schema [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" targetNamespace="http://www.sisostds.org/schemas/C2SIM/1.1"/>`, 'utf8');
  assert.throws(
    () => verifyArtifactBytes(manifest(bytes), registry, bytes, validatorReceipt(bytes)),
    (error) => error.code === 'ARTIFACT_DOCTYPE_FORBIDDEN',
  );
});

test('rejects a target namespace mismatch', () => {
  const bytes = xsd('urn:invented:c2sim');
  assert.throws(
    () => verifyArtifactBytes(manifest(bytes), registry, bytes, validatorReceipt(bytes)),
    (error) => error.code === 'ARTIFACT_TARGET_NAMESPACE_INVALID',
  );
});

test('rejects a validator receipt that covers another artifact', () => {
  const bytes = xsd();
  assert.throws(
    () => verifyArtifactBytes(
      manifest(bytes),
      registry,
      bytes,
      validatorReceipt(bytes, { artifactSha256: '0'.repeat(64) }),
    ),
    (error) => error.code === 'ARTIFACT_VALIDATOR_RECEIPT_INVALID',
  );
});

test('admits a public reference snapshot only on the rehearsal port', () => {
  const admission = admit();
  const use = rehearsalUse(admission);
  assert.equal(use.mode, 'rehearsal');
  assert.equal(use.portId, 'simulation-and-rehearsal');
  assert.equal(use.admissionId, admission.admissionId);

  assert.throws(
    () => admitArtifactUse(
      {
        schema: 'standards-mating-surface-artifact-use-request/1',
        profileId: venue.profileId,
        mode: 'operational',
        portId: 'simulation-and-rehearsal',
        standardId: admission.standardId,
        admissionId: admission.admissionId,
      },
      admission,
      venue,
      registry,
    ),
    (error) => error.code === 'ARTIFACT_OPERATIONAL_USE_FORBIDDEN',
  );
});

test('binds an opaque standard message to the exact admitted artifact', () => {
  const admission = admit();
  const use = rehearsalUse(admission);
  const receipt = bindAdmittedStandardMessage(
    {
      schema: 'standards-mating-surface-binding/1',
      portId: 'simulation-and-rehearsal',
      standardId: admission.standardId,
      standardRevision: admission.standardRevision,
      artifactDigest: admission.artifactSha256,
      validatorId: admission.validator.validatorId,
      payloadDigest: '2'.repeat(64),
      messageIdentity: 'synthetic-c2sim-message-fixture-1',
      sourceSystemId: 'test-host-1',
      observedAt: '2026-08-01T00:00:00Z',
    },
    admission,
    use,
    venue,
    registry,
  );
  assert.equal(receipt.schema, 'standards-mating-surface-admitted-message/1');
  assert.equal(receipt.boundMessage.payloadDigest, '2'.repeat(64));
  assert.equal('payload' in receipt.boundMessage, false);
});

test('refuses message binding through another artifact or validator', () => {
  const admission = admit();
  const use = rehearsalUse(admission);
  const base = {
    schema: 'standards-mating-surface-binding/1',
    portId: 'simulation-and-rehearsal',
    standardId: admission.standardId,
    standardRevision: admission.standardRevision,
    artifactDigest: admission.artifactSha256,
    validatorId: admission.validator.validatorId,
    payloadDigest: '3'.repeat(64),
    messageIdentity: 'fixture-2',
    sourceSystemId: 'test-host-1',
  };
  assert.throws(
    () => bindAdmittedStandardMessage(
      { ...base, artifactDigest: '4'.repeat(64) },
      admission,
      use,
      venue,
      registry,
    ),
    (error) => error.code === 'BOUND_ARTIFACT_DIGEST_MISMATCH',
  );
  assert.throws(
    () => bindAdmittedStandardMessage(
      { ...base, validatorId: 'invented-validator' },
      admission,
      use,
      venue,
      registry,
    ),
    (error) => error.code === 'BOUND_ARTIFACT_VALIDATOR_MISMATCH',
  );
});

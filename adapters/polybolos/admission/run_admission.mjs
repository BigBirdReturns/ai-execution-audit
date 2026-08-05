#!/usr/bin/env node
import { createHash, generateKeyPairSync } from 'node:crypto';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  promoteConfirmedMap,
  signMapAttestation,
  translateAdmittedExternal,
} from './admission.mjs';
import { profileExternalShape } from './shape_profile.mjs';

const ROOT = dirname(dirname(fileURLToPath(import.meta.url)));

function load(relative) {
  return JSON.parse(readFileSync(join(ROOT, relative), 'utf8'));
}

function sha256(path) {
  return createHash('sha256').update(readFileSync(path)).digest('hex');
}

const outputDir = resolve(process.argv[2] ?? join(ROOT, 'qualification', 'shape-admission'));
mkdirSync(outputDir, { recursive: true });
const external = load('fixtures/public-known-minimum/provisional-input.json');
const map = load('contract/provisional-shape-map.json');
const losses = load('contract/declared-losses.json');
const profile = profileExternalShape(external);
const { privateKey, publicKey } = generateKeyPairSync('ed25519');
const privateKeyPem = privateKey.export({ type: 'pkcs8', format: 'pem' });
const publicKeyPem = publicKey.export({ type: 'spki', format: 'pem' });
const trustStore = {
  schema: 'axm-polybolos-maintainer-trust/1',
  keys: [{
    keyId: 'synthetic-polybolos-maintainer-key',
    maintainer: 'Synthetic Polybolos Maintainer',
    organization: 'Polybolos fixture authority',
    algorithm: 'Ed25519',
    publicKeyPem,
  }],
};
const preliminary = {
  maintainer: 'Synthetic Polybolos Maintainer',
  organization: 'Polybolos fixture authority',
  externalShape: map.externalShape,
  profileId: profile.profileId,
  confirmationTargetId: null,
  reviewedAt: '2026-08-01T00:00:00.000Z',
  expiresAt: '2026-09-01T00:00:00.000Z',
  limitations: [
    'Synthetic fixture only',
    'No operational Polybolos schema claim',
    'No private implementation evidence',
  ],
};
const { prepareConfirmedMap } = await import('./admission.mjs');
const target = prepareConfirmedMap(map, profile);
preliminary.confirmationTargetId = target.confirmationTargetId;
const attestation = signMapAttestation(
  preliminary,
  'synthetic-polybolos-maintainer-key',
  privateKeyPem,
);
const promotion = promoteConfirmedMap(
  map,
  profile,
  attestation,
  trustStore,
  '2026-08-02T00:00:00.000Z',
);
const admitted = translateAdmittedExternal(
  external,
  promotion.confirmedMap,
  losses,
  attestation,
  trustStore,
  '2026-08-02T00:00:00.000Z',
);

const receipt = {
  schema: 'ai-execution-audit/polybolos-shape-admission@1',
  status: 'pass',
  synthetic: true,
  profile,
  confirmationTarget: target,
  attestation,
  trustStore,
  promotion,
  admittedTranslation: admitted,
  sourceHashes: {
    map: sha256(join(ROOT, 'contract/provisional-shape-map.json')),
    losses: sha256(join(ROOT, 'contract/declared-losses.json')),
    fixture: sha256(join(ROOT, 'fixtures/public-known-minimum/provisional-input.json')),
  },
  claimBoundary:
    'This receipt proves the signed structural admission mechanism with an ephemeral synthetic maintainer key. It does not confirm a real Polybolos schema, maintainer, implementation, or operational capability.',
};
for (const [name, value] of [
  ['shape-profile.json', profile],
  ['confirmation-target.json', target],
  ['map-attestation.json', attestation],
  ['maintainer-trust.json', trustStore],
  ['confirmed-map.json', promotion.confirmedMap],
  ['admitted-translation.json', admitted],
  ['shape-admission-receipt.json', receipt],
]) {
  writeFileSync(join(outputDir, name), `${JSON.stringify(value, null, 2)}\n`, 'utf8');
}
process.stdout.write(`${JSON.stringify({
  status: receipt.status,
  profileId: profile.profileId,
  confirmationTargetId: target.confirmationTargetId,
  attestationId: attestation.attestationId,
  confirmedMapId: promotion.confirmedMap.mapId,
  projectionId: admitted.projection.projectionId,
  outputDir,
}, null, 2)}\n`);

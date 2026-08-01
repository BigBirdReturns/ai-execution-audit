import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import {
  SurfaceError,
  bindStandardMessage,
  validateProviderAdapter,
  validateRegistry,
  validateVenueProfile,
} from '../core/registry.mjs';

const registry = JSON.parse(readFileSync(new URL('../standards/registry.json', import.meta.url), 'utf8'));
const profile = JSON.parse(readFileSync(new URL('../venues/joint-edge-command-authority.json', import.meta.url), 'utf8'));
const digest = (character) => character.repeat(64);

test('compiles one provider-independent standards surface', () => {
  const first = validateVenueProfile(profile, registry);
  const second = validateVenueProfile(structuredClone(profile), structuredClone(registry));
  assert.equal(first.surfaceId, second.surfaceId);
  assert.equal(first.profile.surfaceBranding, 'none');
  assert.equal(first.profile.providerVocabulary, 'edge_only');
  assert(first.ports.has('mission-command'));
  assert(first.ports.has('simulation-and-rehearsal'));
});

test('registry contains venue standards instead of product schemas', () => {
  const receipt = validateRegistry(registry);
  for (const standardId of [
    'afrl-oams-uci',
    'omg-dds',
    'usg-tak-cot',
    'mil-std-6016',
    'mil-std-6017',
    'mil-std-2525',
    'siso-std-019-2020-c2sim',
    'siso-std-007-2008-msdl',
    'siso-std-014.1-2018-gdl',
    'siso-std-014.2-2018-gfl',
    'army-cmoss',
    'face-technical-standard',
  ]) {
    assert(receipt.byId.has(standardId), standardId);
  }
  assert.equal(receipt.byId.has('polybolos'), false);
  assert.equal(receipt.byId.has('axm'), false);
  assert.equal(receipt.byId.has('dandelion'), false);
});

test('canonical venue ports refuse product branding and provider terms', () => {
  const altered = structuredClone(profile);
  altered.ports[0].brand = 'provider-product';
  assert.throws(
    () => validateVenueProfile(altered, registry),
    (error) => error instanceof SurfaceError && error.code === 'CANONICAL_BRANDING_FORBIDDEN',
  );

  const alteredTwo = structuredClone(profile);
  alteredTwo.ports[0].nativeFields = ['privateThing'];
  assert.throws(
    () => validateVenueProfile(alteredTwo, registry),
    (error) => error instanceof SurfaceError && error.code === 'CANONICAL_BRANDING_FORBIDDEN',
  );
});

test('controlled standards require an authorized artifact reference', () => {
  const binding = {
    schema: 'standards-mating-surface-binding/1',
    portId: 'mission-command',
    standardId: 'mil-std-6016',
    standardRevision: 'H',
    artifactDigest: digest('a'),
    validatorId: 'controlled-link16-validator',
    payloadDigest: digest('b'),
    messageIdentity: 'tdl-message-fixture-1',
    sourceSystemId: 'provider-fixture',
    observedAt: '2026-08-01T00:00:00.000Z',
  };
  assert.throws(
    () => bindStandardMessage(binding, profile, registry),
    (error) => error instanceof SurfaceError && error.code === 'BINDING_AUTHORIZATION_REQUIRED',
  );
  binding.authorizationReference = 'program-controlled-artifact-receipt-1';
  const receipt = bindStandardMessage(binding, profile, registry);
  assert.match(receipt.bindingId, /^standardbinding1_[0-9a-f]{64}$/);
  assert.equal(receipt.standardId, 'mil-std-6016');
});

test('a public standard binding carries identity but not an invented inline payload', () => {
  const binding = {
    schema: 'standards-mating-surface-binding/1',
    portId: 'joint-symbology',
    standardId: 'mil-std-2525',
    standardRevision: 'E Change 1',
    artifactDigest: digest('c'),
    validatorId: 'mil-std-2525-e1-validator',
    payloadDigest: digest('d'),
    messageIdentity: 'symbol-set-fixture-1',
    sourceSystemId: 'operator-surface-fixture',
  };
  const receipt = bindStandardMessage(binding, profile, registry);
  assert.equal(receipt.portId, 'joint-symbology');
  assert.equal('payload' in receipt, false);

  assert.throws(
    () => bindStandardMessage({ ...binding, payload: { guessed: true } }, profile, registry),
    (error) => error instanceof SurfaceError && error.code === 'BINDING_PAYLOAD_INLINE_FORBIDDEN',
  );
});

test('provider adapters remain edge implementations bound to standard ports', () => {
  const adapter = {
    schema: 'standards-mating-surface-provider-adapter/1',
    providerId: 'external-c2-engine',
    nativeImplementation: 'private and provider-owned',
    ports: [
      {
        portId: 'real-time-data-plane',
        standardId: 'omg-dds',
        mode: 'official_codegen',
        artifactDigest: digest('e'),
      },
      {
        portId: 'mission-command',
        standardId: 'afrl-oams-uci',
        mode: 'official_codegen',
        artifactDigest: digest('f'),
      },
    ],
  };
  const receipt = validateProviderAdapter(adapter, profile, registry);
  assert.equal(receipt.providerId, 'external-c2-engine');
  assert.match(receipt.adapterId, /^provideradapter1_[0-9a-f]{64}$/);
});

test('a provider cannot make its private schema canonical or define the surface UI', () => {
  const base = {
    schema: 'standards-mating-surface-provider-adapter/1',
    providerId: 'external-c2-engine',
    ports: [
      {
        portId: 'real-time-data-plane',
        standardId: 'omg-dds',
        mode: 'pass_through',
        artifactDigest: digest('1'),
      },
    ],
  };
  assert.throws(
    () => validateProviderAdapter({ ...base, canonicalFields: ['nativeTrack'] }, profile, registry),
    (error) => error instanceof SurfaceError && error.code === 'ADAPTER_CANONICAL_FIELDS_FORBIDDEN',
  );
  assert.throws(
    () => validateProviderAdapter({ ...base, ui: { logo: 'provider' } }, profile, registry),
    (error) => error instanceof SurfaceError && error.code === 'ADAPTER_UI_FORBIDDEN',
  );
});

test('loss-accounted gateways require a descriptor and visible losses', () => {
  const adapter = {
    schema: 'standards-mating-surface-provider-adapter/1',
    providerId: 'legacy-provider',
    ports: [
      {
        portId: 'mission-command',
        standardId: 'mil-std-6017',
        mode: 'loss_accounted_gateway',
        authorizationReference: 'program-controlled-artifact-receipt-1',
      },
    ],
  };
  assert.throws(
    () => validateProviderAdapter(adapter, profile, registry),
    (error) => error instanceof SurfaceError && error.code === 'ADAPTER_LOSSES_REQUIRED',
  );
  adapter.ports[0].declaredLosses = ['native diagnostic field is not represented in VMF'];
  assert.throws(
    () => validateProviderAdapter(adapter, profile, registry),
    (error) => error instanceof SurfaceError && error.code === 'ADAPTER_GATEWAY_DESCRIPTOR_REQUIRED',
  );
  adapter.ports[0].gatewayDescriptorId = 'siso-gdl-fixture-1';
  const receipt = validateProviderAdapter(adapter, profile, registry);
  assert.equal(receipt.ports[0].mode, 'loss_accounted_gateway');
});

test('MAME and MotionDeck remain replaceable test hosts rather than standards', () => {
  const surface = validateVenueProfile(profile, registry);
  const simulationPort = surface.ports.get('simulation-and-rehearsal');
  assert(simulationPort.allowedStandards.includes('siso-std-019-2020-c2sim'));
  assert(simulationPort.allowedStandards.includes('siso-std-007-2008-msdl'));
  assert(simulationPort.allowedStandards.includes('ieee-1278-dis'));
  assert.equal(simulationPort.allowedStandards.includes('mame'), false);
  assert.equal(simulationPort.allowedStandards.includes('motiondeck'), false);
});

test('an unregistered proprietary message family cannot become a venue port', () => {
  const altered = structuredClone(profile);
  altered.ports[0].allowedStandards.push('provider-private-command-core');
  assert.throws(
    () => validateVenueProfile(altered, registry),
    (error) => error instanceof SurfaceError && error.code === 'VENUE_STANDARD_UNKNOWN',
  );
});

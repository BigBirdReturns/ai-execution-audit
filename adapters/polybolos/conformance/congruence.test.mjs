import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import {
  CongruenceError,
  canonicalJson,
  deriveMapId,
  projectAxmStatus,
  reconstructMappedExternal,
  toBoundedCandidateRequest,
  translateExternalProposal,
  validateShapeMap,
  verifyMappedRoundTrip,
} from '../translation/congruence.mjs';

const ROOT = dirname(dirname(fileURLToPath(import.meta.url)));

function load(relative) {
  return JSON.parse(readFileSync(join(ROOT, relative), 'utf8'));
}

function fixture() {
  return {
    map: load('contract/provisional-shape-map.json'),
    losses: load('contract/declared-losses.json'),
    external: load('fixtures/public-known-minimum/provisional-input.json'),
  };
}

function confirmedMap(map) {
  const copy = structuredClone(map);
  copy.status = 'confirmed';
  copy.mapId = null;
  copy.mappings = copy.mappings.map((field) => ({ ...field, status: 'confirmed' }));
  return copy;
}

test('provisional mapping runs only as a synthetic fixture and cannot enter live mode', () => {
  const { map, losses, external } = fixture();
  const projection = translateExternalProposal(external, map, losses, { mode: 'fixture' });
  assert.equal(projection.mappingStatus, 'provisional');
  assert.equal(projection.mode, 'fixture');
  assert.throws(
    () => translateExternalProposal(external, map, losses, { mode: 'live' }),
    (error) => error instanceof CongruenceError && error.code === 'MAPPING_NOT_CONFIRMED',
  );
});

test('confirmed copy may enter live mode without changing the neutral semantics', () => {
  const { map, losses, external } = fixture();
  const confirmed = confirmedMap(map);
  const projection = translateExternalProposal(external, confirmed, losses, { mode: 'live' });
  assert.equal(projection.mode, 'live');
  assert.equal(projection.mappingStatus, 'confirmed');
  assert.equal(projection.schema, 'axm-polybolos-candidate-input/1');
});

test('translation is deterministic, bounded, and closes payload evidence to entity references', () => {
  const { map, losses, external } = fixture();
  const first = translateExternalProposal(external, map, losses);
  const second = translateExternalProposal(structuredClone(external), structuredClone(map), structuredClone(losses));
  assert.equal(first.projectionId, second.projectionId);
  assert.equal(first.sourceShapeId, second.sourceShapeId);
  assert.deepEqual(first.entityIds, ['synthetic-track-0001', 'synthetic-track-0002']);
  assert.deepEqual(first.payload.entityIds, first.entityIds);
  assert.equal(first.payload.priority, 7);
  assert.equal(first.trace.decisionDurationUs, 412);
  assert.equal(first.trace.inputSequence, 5000);
  assert.deepEqual(first.trace.reasonCodes, [
    'SYNTHETIC_GEOMETRY_OK',
    'SYNTHETIC_RESOURCE_AVAILABLE',
  ]);
});

test('unmapped native details remain visible but are not copied into the neutral candidate', () => {
  const { map, losses, external } = fixture();
  const projection = translateExternalProposal(external, map, losses);
  assert.deepEqual(projection.unknownTopLevelFields, ['native_kinematics', 'private_extension']);
  const serialized = canonicalJson(projection);
  assert.equal(serialized.includes('intentionally-unmapped-synthetic-example'), false);
  assert.equal(serialized.includes('not-copied-into-neutral-candidate'), false);
  assert.match(projection.unknownTopLevelDigest, /^polybolosunknown1_[0-9a-f]{64}$/);
  assert.deepEqual(
    projection.declaredLosses.map((row) => row.id),
    ['entity-order-normalized', 'native-details-not-copied', 'return-shape-is-neutral'],
  );
});

test('changing an unmapped field changes the omission receipt rather than silently disappearing', () => {
  const { map, losses, external } = fixture();
  const first = translateExternalProposal(external, map, losses);
  const changed = structuredClone(external);
  changed.private_extension.opaque = 'changed-but-still-unmapped';
  const second = translateExternalProposal(changed, map, losses);
  assert.notEqual(first.unknownTopLevelDigest, second.unknownTopLevelDigest);
  assert.notEqual(first.sourceShapeId, second.sourceShapeId);
  assert.notEqual(first.projectionId, second.projectionId);
  assert.equal(first.requestId, second.requestId);
});

test('neutral projection feeds the existing bounded candidate endpoint without importing Polybolos internals', () => {
  const { map, losses, external } = fixture();
  const projection = translateExternalProposal(external, map, losses);
  const bounded = toBoundedCandidateRequest(projection);
  assert.equal(bounded.request.producer, 'polybolos-command-core');
  assert.equal(bounded.request.actionClass, 'track-priority-candidate');
  assert.deepEqual(bounded.request.entityIds, projection.entityIds);
  assert.deepEqual(bounded.request.payload.entityIds, projection.entityIds);
  assert.equal(bounded.custody.producerBuildId, projection.producerBuildId);
  assert.equal(bounded.custody.deadlineAt, projection.deadlineAt);
  assert.equal(Object.prototype.hasOwnProperty.call(bounded.request, 'producerBuildId'), false);
  assert.equal(Object.prototype.hasOwnProperty.call(bounded.request, 'deadlineAt'), false);
  assert.equal(Object.prototype.hasOwnProperty.call(bounded.request, 'native_kinematics'), false);
  assert.match(bounded.requestId, /^polybolosboundedrequest1_[0-9a-f]{64}$/);
});

test('mapped fields satisfy the declared round-trip promises', () => {
  const { map, losses, external } = fixture();
  const projection = translateExternalProposal(external, map, losses);
  const reconstructed = reconstructMappedExternal(projection, map);
  const receipt = verifyMappedRoundTrip(external, projection, map);
  assert.equal(receipt.pass, true);
  assert.deepEqual(receipt.mismatches, []);
  assert.equal(reconstructed.request_id, external.request_id);
  assert.deepEqual(reconstructed.entity_ids, ['synthetic-track-0001', 'synthetic-track-0002']);
  assert.equal(reconstructed.created_at, '2026-08-01T00:00:01.000Z');
});

test('candidate data cannot promote itself into authority', () => {
  const { map, losses } = fixture();
  const malicious = load('fixtures/negative/self-authorizing-input.json');
  assert.throws(
    () => translateExternalProposal(malicious, map, losses),
    (error) => error instanceof CongruenceError && error.code === 'CANDIDATE_SELF_AUTHORIZATION',
  );
});

test('required external semantics fail closed instead of receiving guessed defaults', () => {
  const { map, losses } = fixture();
  const incomplete = load('fixtures/negative/missing-required-input.json');
  assert.throws(
    () => translateExternalProposal(incomplete, map, losses),
    (error) => error instanceof CongruenceError && error.code === 'MAPPED_FIELD_MISSING',
  );
});

test('mapping identity changes when the translation contract changes', () => {
  const { map } = fixture();
  const first = deriveMapId(map);
  const changed = structuredClone(map);
  changed.mapId = null;
  changed.mappings.find((field) => field.target === '/payload/priority').target = '/payload/score';
  const second = deriveMapId(changed);
  assert.notEqual(first, second);
  assert.equal(validateShapeMap(map).mapId, first);
});

test('AXM dispositions return through a neutral status projection without inventing Polybolos workflow state', () => {
  const context = { requestId: 'fixture-request-0001', evidenceRef: 'sha256:fixture-evidence' };
  const cases = [
    ['allow', 'eligible'],
    ['hold', 'hold'],
    ['refuse', 'refused'],
    ['safe_state', 'safe_state'],
  ];
  for (const [disposition, expected] of cases) {
    const status = projectAxmStatus({
      schema: 'axm-checkpoint-partition-authority-decision/1',
      decisionId: `decision-${disposition}`,
      disposition,
      reason: { code: `reason-${disposition}` },
      candidateId: 'candidate-1',
      checkpointId: 'checkpoint-1',
      authorityId: 'authority-1',
      epochId: 'epoch-1',
    }, context);
    assert.equal(status.status, expected);
    assert.equal(status.reasonCode, `reason-${disposition}`);
    assert.equal(Object.prototype.hasOwnProperty.call(status, 'payload'), false);
    assert.match(status.statusProjectionId, /^polybolosstatus1_[0-9a-f]{64}$/);
  }
});

test('reconciliation remains explicit and unknown return states fail closed', () => {
  const context = { requestId: 'fixture-request-0001' };
  const human = projectAxmStatus({
    schema: 'axm-partition-reconciliation/1',
    reconciliationId: 'reconciliation-human',
    disposition: 'human_required',
    priorAuthorityId: 'authority-1',
    returningAuthorityId: 'authority-2',
    epochId: 'epoch-1',
  }, context);
  assert.equal(human.status, 'human_required');
  const reconciled = projectAxmStatus({
    schema: 'axm-partition-reconciliation/1',
    reconciliationId: 'reconciliation-explicit',
    disposition: 'explicitly_superseded',
    priorAuthorityId: 'authority-1',
    returningAuthorityId: 'authority-2',
    epochId: 'epoch-1',
  }, context);
  assert.equal(reconciled.status, 'reconciled');
  assert.throws(
    () => projectAxmStatus({ schema: 'unknown', disposition: 'green' }, context),
    (error) => error instanceof CongruenceError && error.code === 'RETURN_DISPOSITION_INVALID',
  );
});

#!/usr/bin/env node
import { createHash } from 'node:crypto';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  projectAxmStatus,
  toBoundedCandidateRequest,
  translateExternalProposal,
  verifyMappedRoundTrip,
} from '../translation/congruence.mjs';

const ROOT = dirname(dirname(fileURLToPath(import.meta.url)));

function load(relative) {
  return JSON.parse(readFileSync(join(ROOT, relative), 'utf8'));
}

function sha256(value) {
  return createHash('sha256').update(value).digest('hex');
}

const output = resolve(process.argv[2] ?? join(ROOT, 'qualification', 'congruence-receipt.json'));
const map = load('contract/provisional-shape-map.json');
const losses = load('contract/declared-losses.json');
const external = load('fixtures/public-known-minimum/provisional-input.json');
const projection = translateExternalProposal(external, map, losses, { mode: 'fixture' });
const roundTrip = verifyMappedRoundTrip(external, projection, map);
const bounded = toBoundedCandidateRequest(projection);
const statuses = ['allow', 'hold', 'refuse', 'safe_state'].map((disposition) => projectAxmStatus({
  schema: 'axm-checkpoint-partition-authority-decision/1',
  decisionId: `fixture-${disposition}`,
  disposition,
  reason: { code: `fixture_${disposition}` },
  candidateId: 'fixture-candidate',
  checkpointId: 'fixture-checkpoint',
  authorityId: 'fixture-authority',
  epochId: disposition === 'allow' ? 'fixture-epoch' : null,
}, { requestId: projection.requestId, evidenceRef: 'fixture-evidence' }));

const receipt = {
  schema: 'ai-execution-audit/polybolos-congruent-shape@1',
  status: roundTrip.pass ? 'pass' : 'fail',
  mappingStatus: projection.mappingStatus,
  livePromotionBlocked: projection.mappingStatus !== 'confirmed',
  projection,
  boundedCandidateRequest: bounded,
  roundTrip,
  statusProjections: statuses,
  sourceHashes: {
    map: sha256(readFileSync(join(ROOT, 'contract/provisional-shape-map.json'))),
    losses: sha256(readFileSync(join(ROOT, 'contract/declared-losses.json'))),
    fixture: sha256(readFileSync(join(ROOT, 'fixtures/public-known-minimum/provisional-input.json'))),
  },
  claimBoundary:
    'This receipt proves the provisional adapter conformance mechanics only. It does not assert Polybolos private schemas, source, Command Intelligence, COMMAND CORE behavior, or operational qualification.',
};
mkdirSync(dirname(output), { recursive: true });
writeFileSync(output, `${JSON.stringify(receipt, null, 2)}\n`, 'utf8');
process.stdout.write(`${JSON.stringify({
  status: receipt.status,
  mappingStatus: receipt.mappingStatus,
  livePromotionBlocked: receipt.livePromotionBlocked,
  projectionId: projection.projectionId,
  boundedRequestId: bounded.requestId,
  output,
}, null, 2)}\n`);
if (receipt.status !== 'pass') process.exitCode = 1;

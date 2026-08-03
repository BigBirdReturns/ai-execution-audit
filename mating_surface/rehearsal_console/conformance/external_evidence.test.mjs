import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import { fileURLToPath } from 'node:url';
import {
  ExternalEvidenceError,
  createExternalEvidenceQualification,
  verifyExternalEvidenceQualification,
} from '../external_evidence.mjs';

const retainedPath = fileURLToPath(new URL(
  '../evidence/external/standing-orders-admin-inject-20260802.json',
  import.meta.url,
));

function baseInput({
  evidenceTier = 'synthetic_fixture',
  rawSourceCommitted = false,
  claimResult = 'pass',
  closure = null,
} = {}) {
  return {
    source: {
      evidenceTier,
      classification: 'UNCLASSIFIED_SYNTHETIC_TEST',
      rawSourceCommitted,
      artifacts: [
        {
          artifactId: 'fixture-log',
          role: 'controlling_event_log',
          bytes: 128,
          sha256: 'a'.repeat(64),
        },
      ],
      custodyStatement: 'Synthetic fixture used only to exercise the admission contract.',
    },
    testContext: {
      sessionLabel: 'fixture-session',
      sourceMode: 'synthetic_fixture',
      testVenue: 'unit_test',
      canonicalRuntimeExecuted: false,
      physicalNetworkPartitionTested: false,
      signedAuthorityTested: false,
    },
    observations: [
      {
        observationId: 'fixture-observation',
        name: 'Fixture observation',
        value: 1,
        unit: 'count',
        sourceArtifactId: 'fixture-log',
        interpretation: 'Synthetic bounded observation.',
      },
    ],
    claimDispositions: [
      {
        claimId: 'fixture-claim',
        name: 'Fixture claim',
        result: claimResult,
        requiredForAcceptance: true,
        evidenceObservationIds: ['fixture-observation'],
        rationale: 'Synthetic claim used to test automatic status derivation.',
        nextEvidence: 'No external consequence; this is a unit fixture.',
      },
    ],
    producerReportReview: {
      reviewed: true,
      sourceArtifactId: 'fixture-log',
      dispositionCounts: { VERIFIED: 1 },
      controllingCorrection: 'Synthetic fixture report review.',
    },
    canonicalClosure: closure ?? {
      sourceEvidenceSetId: null,
      scenarioCatalogId: null,
      scenarioDefinitionId: null,
      sessionReceiptId: null,
      sessionVerificationId: null,
      detachedReplayStatus: 'absent',
    },
    nextEvidence: ['Join a canonical replay-verified session before acceptance.'],
  };
}

test('retained private-source qualification verifies but remains automatically incomplete', async () => {
  const retained = JSON.parse(await readFile(retainedPath, 'utf8'));
  const verification = verifyExternalEvidenceQualification(retained.qualification);
  assert.deepEqual(verification, retained.verification);
  assert.equal(retained.qualification.source.evidenceTier, 'private_digest_only');
  assert.equal(retained.qualification.source.rawSourceCommitted, false);
  assert.equal(retained.qualification.automaticEvaluation.status, 'incomplete');
  assert.equal(retained.qualification.automaticEvaluation.acceptanceEligible, false);
  assert.equal(retained.qualification.automaticEvaluation.requiredPassCount, 1);
  assert.equal(retained.qualification.automaticEvaluation.requiredIncompleteCount, 7);
  assert.match(
    retained.qualification.producerReportReview.controllingCorrection,
    /end-to-end denied-communications authority acceptance remains incomplete/i,
  );
});

test('digest tampering and self-asserted automatic promotion fail closed', async () => {
  const retained = JSON.parse(await readFile(retainedPath, 'utf8'));
  const changedDigest = structuredClone(retained.qualification);
  changedDigest.source.artifacts[0].sha256 = 'b'.repeat(64);
  assert.throws(
    () => verifyExternalEvidenceQualification(changedDigest),
    (error) => error instanceof ExternalEvidenceError
      && error.code === 'EXTERNAL_EVIDENCE_SET_ID_MISMATCH',
  );

  const promoted = structuredClone(retained.qualification);
  promoted.automaticEvaluation.status = 'pass';
  promoted.automaticEvaluation.acceptanceEligible = true;
  assert.throws(
    () => verifyExternalEvidenceQualification(promoted),
    (error) => error instanceof ExternalEvidenceError
      && error.code === 'EXTERNAL_AUTOMATIC_EVALUATION_MISMATCH',
  );
});

test('private digest-only evidence refuses raw-source publication or source paths', () => {
  assert.throws(
    () => createExternalEvidenceQualification(baseInput({
      evidenceTier: 'private_digest_only',
      rawSourceCommitted: true,
    })),
    (error) => error instanceof ExternalEvidenceError
      && error.code === 'EXTERNAL_PRIVATE_BYTES_REFUSED',
  );

  const input = baseInput({ evidenceTier: 'private_digest_only' });
  input.source.artifacts[0].path = '/private/source.log';
  assert.throws(
    () => createExternalEvidenceQualification(input),
    (error) => error instanceof ExternalEvidenceError
      && error.code === 'EXTERNAL_ARTIFACT_INVALID',
  );
});

test('a required pass without cited observations is refused', () => {
  const input = baseInput();
  input.claimDispositions[0].evidenceObservationIds = [];
  assert.throws(
    () => createExternalEvidenceQualification(input),
    (error) => error instanceof ExternalEvidenceError
      && error.code === 'EXTERNAL_CLAIM_EVIDENCE_MISSING',
  );
});

test('all required claims still remain incomplete without canonical closure', () => {
  const receipt = createExternalEvidenceQualification(baseInput());
  assert.equal(receipt.automaticEvaluation.requiredPassCount, 1);
  assert.equal(receipt.automaticEvaluation.canonicalClosureComplete, false);
  assert.equal(receipt.automaticEvaluation.status, 'incomplete');
  assert.equal(receipt.automaticEvaluation.acceptanceEligible, false);
});

test('exact source-set binding and detached canonical replay are required for automatic pass', () => {
  const provisional = createExternalEvidenceQualification(baseInput());
  const receipt = createExternalEvidenceQualification(baseInput({
    closure: {
      sourceEvidenceSetId: provisional.sourceEvidenceSetId,
      scenarioCatalogId: 'standardrehearsalscenariocatalog1_' + '1'.repeat(64),
      scenarioDefinitionId: 'standardrehearsalscenario1_' + '2'.repeat(64),
      sessionReceiptId: 'standardsinteractiverehearsal2_' + '3'.repeat(64),
      sessionVerificationId: 'standardsinteractiverehearsalverification2_' + '4'.repeat(64),
      detachedReplayStatus: 'pass',
    },
  }));
  const verification = verifyExternalEvidenceQualification(receipt);
  assert.equal(receipt.automaticEvaluation.status, 'pass');
  assert.equal(receipt.automaticEvaluation.canonicalClosureComplete, true);
  assert.equal(receipt.automaticEvaluation.acceptanceEligible, true);
  assert.equal(verification.status, 'pass');
});

test('another source evidence set cannot borrow a canonical session closure', () => {
  const first = createExternalEvidenceQualification(baseInput());
  const input = baseInput({
    closure: {
      sourceEvidenceSetId: first.sourceEvidenceSetId,
      scenarioCatalogId: 'catalog-one',
      scenarioDefinitionId: 'definition-one',
      sessionReceiptId: 'session-one',
      sessionVerificationId: 'verification-one',
      detachedReplayStatus: 'pass',
    },
  });
  input.observations[0].value = 2;
  const second = createExternalEvidenceQualification(input);
  assert.notEqual(second.sourceEvidenceSetId, first.sourceEvidenceSetId);
  assert.equal(second.automaticEvaluation.status, 'incomplete');
  assert.equal(second.automaticEvaluation.canonicalClosureComplete, false);
  assert.equal(second.automaticEvaluation.acceptanceEligible, false);
});

test('undeclared receipt fields are refused rather than ignored', () => {
  const receipt = createExternalEvidenceQualification(baseInput());
  receipt.hiddenAuthority = true;
  assert.throws(
    () => verifyExternalEvidenceQualification(receipt),
    (error) => error instanceof ExternalEvidenceError
      && error.code === 'EXTERNAL_EVIDENCE_INVALID',
  );
});

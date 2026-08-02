import assert from 'node:assert/strict';
import test from 'node:test';
import {
  EvaluatorDispositionError,
  EvaluatorDispositionRegistry,
  createAcceptancePackage,
  createLocalEvaluatorSigner,
  verifyEvaluatorDisposition,
} from '../evaluator_disposition.mjs';

function sessionFixture(evaluationStatus = 'pass') {
  const sessionReceipt = {
    schema: 'standards-interactive-rehearsal-receipt/2',
    receiptId: 'standardsinteractiverehearsal2_' + '1'.repeat(64),
    scenarioCatalogId: 'standardrehearsalscenariocatalog1_' + '2'.repeat(64),
    scenarioId: 'baseline-explicit-return',
    scenarioDefinitionId: 'standardrehearsalscenario1_' + '3'.repeat(64),
    finalStateId: 'standardsinteractivestate2_' + '4'.repeat(64),
    evaluationId: 'standardrehearsalevaluation1_' + '5'.repeat(64),
    evaluationStatus,
  };
  const sessionVerification = {
    schema: 'standards-interactive-rehearsal-verification/2',
    status: 'pass',
    receiptId: sessionReceipt.receiptId,
    evaluationId: sessionReceipt.evaluationId,
    evaluationStatus,
  };
  return { sessionReceipt, sessionVerification };
}

function evaluator() {
  return {
    evaluatorId: 'test-evaluator-01',
    role: 'V&V reviewer',
    organization: 'Synthetic qualification fixture',
  };
}

function signer() {
  return createLocalEvaluatorSigner({
    clock: () => new Date('2026-08-02T20:00:00.000Z'),
  });
}

test('a replay-verified automatic pass can receive a separate accept disposition', () => {
  const inputs = sessionFixture('pass');
  const receipt = signer().issue({
    ...inputs,
    evaluator: evaluator(),
    disposition: 'accept',
    rationale: 'Observed behavior and detached replay match the qualified case.',
  });
  const verification = verifyEvaluatorDisposition(receipt, inputs);
  assert.equal(receipt.disposition, 'accept');
  assert.equal(receipt.automaticEvaluationStatus, 'pass');
  assert.equal(verification.status, 'pass');
  assert.equal(verification.signatureVerified, true);
  assert.match(receipt.signer.keyId, /^ed25519:[0-9a-f]{64}$/);
  assert.match(receipt.claimBoundary, /does not independently authenticate the evaluator/);
});

test('accept cannot override fail, incomplete, or deviated automatic evidence', () => {
  for (const evaluationStatus of ['fail', 'incomplete', 'deviated']) {
    assert.throws(
      () => signer().issue({
        ...sessionFixture(evaluationStatus),
        evaluator: evaluator(),
        disposition: 'accept',
      }),
      (error) => error instanceof EvaluatorDispositionError
        && error.code === 'AUTOMATIC_PASS_REQUIRED',
    );
  }
});

test('reject and defer require an explicit rationale', () => {
  for (const disposition of ['reject', 'defer']) {
    assert.throws(
      () => signer().issue({
        ...sessionFixture('pass'),
        evaluator: evaluator(),
        disposition,
      }),
      (error) => error instanceof EvaluatorDispositionError
        && error.code === 'EVALUATOR_RATIONALE_REQUIRED',
    );
  }
});

test('a disposition cannot be moved onto another session or automatic evaluation', () => {
  const inputs = sessionFixture('pass');
  const receipt = signer().issue({
    ...inputs,
    evaluator: evaluator(),
    disposition: 'defer',
    rationale: 'Representative-user observation is still pending.',
  });
  const another = sessionFixture('pass');
  another.sessionReceipt.receiptId = 'standardsinteractiverehearsal2_' + '9'.repeat(64);
  another.sessionVerification.receiptId = another.sessionReceipt.receiptId;
  assert.throws(
    () => verifyEvaluatorDisposition(receipt, another),
    (error) => error instanceof EvaluatorDispositionError
      && error.code === 'EVALUATOR_SESSION_MISMATCH',
  );
});

test('signature and evaluator-content tampering fail closed', () => {
  const inputs = sessionFixture('pass');
  const receipt = signer().issue({
    ...inputs,
    evaluator: evaluator(),
    disposition: 'reject',
    rationale: 'The run requires investigation before acceptance.',
  });
  const alteredRationale = structuredClone(receipt);
  alteredRationale.rationale = 'Changed after signature.';
  assert.throws(
    () => verifyEvaluatorDisposition(alteredRationale, inputs),
    (error) => error instanceof EvaluatorDispositionError
      && error.code === 'EVALUATOR_SIGNATURE_INVALID',
  );

  const alteredIdentity = structuredClone(receipt);
  alteredIdentity.evaluator.role = 'Acceptance authority';
  assert.throws(
    () => verifyEvaluatorDisposition(alteredIdentity, inputs),
    (error) => error instanceof EvaluatorDispositionError
      && error.code === 'EVALUATOR_SIGNATURE_INVALID',
  );
});

test('registry permits one immutable disposition per session', () => {
  const registry = new EvaluatorDispositionRegistry(signer());
  const inputs = sessionFixture('pass');
  registry.issue({
    ...inputs,
    evaluator: evaluator(),
    disposition: 'accept',
  });
  assert.throws(
    () => registry.issue({
      ...inputs,
      evaluator: evaluator(),
      disposition: 'reject',
      rationale: 'Attempted replacement.',
    }),
    (error) => error instanceof EvaluatorDispositionError
      && error.code === 'EVALUATOR_DISPOSITION_EXISTS',
  );
  assert.equal(registry.get(inputs.sessionReceipt.receiptId).disposition, 'accept');
});

test('acceptance package preserves automation, replay verification, and human disposition separately', () => {
  const inputs = sessionFixture('pass');
  const receipt = signer().issue({
    ...inputs,
    evaluator: evaluator(),
    disposition: 'accept',
  });
  const verification = verifyEvaluatorDisposition(receipt, inputs);
  const packageReceipt = createAcceptancePackage({
    ...inputs,
    dispositionReceipt: receipt,
    dispositionVerification: verification,
  });
  assert.equal(packageReceipt.sessionReceipt.evaluationStatus, 'pass');
  assert.equal(packageReceipt.dispositionReceipt.disposition, 'accept');
  assert.equal(packageReceipt.dispositionVerification.status, 'pass');
  assert.match(
    packageReceipt.acceptancePackageId,
    /^standardsrehearsalacceptancepackage1_[0-9a-f]{64}$/,
  );
  assert.match(packageReceipt.claimBoundary, /separate local evaluator disposition/);
});

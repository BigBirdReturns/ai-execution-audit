import {
  createHash,
  createPublicKey,
  generateKeyPairSync,
  sign as signBytes,
  verify as verifyBytes,
} from 'node:crypto';
import { canonicalJson } from '../semantic/authority_sidecar.mjs';

const DISPOSITIONS = new Set(['accept', 'reject', 'defer']);
const MAX_IDENTITY_LENGTH = 160;
const MAX_RATIONALE_LENGTH = 4_000;

export class EvaluatorDispositionError extends Error {
  constructor(code, message) {
    super(message);
    this.name = 'EvaluatorDispositionError';
    this.code = code;
  }
}

function requireCondition(condition, code, message) {
  if (!condition) throw new EvaluatorDispositionError(code, message);
}

function isRecord(value) {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) return false;
  const prototype = Object.getPrototypeOf(value);
  return prototype === Object.prototype || prototype === null;
}

function digest(prefix, value) {
  return `${prefix}_${createHash('sha256').update(canonicalJson(value), 'utf8').digest('hex')}`;
}

function boundedString(value, code, label, maximum = MAX_IDENTITY_LENGTH) {
  requireCondition(typeof value === 'string', code, `${label} must be a string`);
  const normalized = value.trim();
  requireCondition(
    normalized.length > 0 && normalized.length <= maximum,
    code,
    `${label} is empty or exceeds ${maximum} characters`,
  );
  return normalized;
}

function optionalString(value, code, label, maximum = MAX_IDENTITY_LENGTH) {
  if (value === undefined || value === null || value === '') return null;
  return boundedString(value, code, label, maximum);
}

function normalizedEvaluator(value) {
  requireCondition(isRecord(value), 'EVALUATOR_IDENTITY_INVALID', 'evaluator must be an object');
  const allowed = new Set(['evaluatorId', 'role', 'organization']);
  const unknown = Object.keys(value).filter((key) => !allowed.has(key)).sort();
  requireCondition(
    unknown.length === 0,
    'EVALUATOR_IDENTITY_INVALID',
    `unsupported evaluator field ${unknown[0]}`,
  );
  return {
    evaluatorId: boundedString(
      value.evaluatorId,
      'EVALUATOR_IDENTITY_INVALID',
      'evaluatorId',
    ),
    role: boundedString(value.role, 'EVALUATOR_IDENTITY_INVALID', 'role'),
    organization: optionalString(
      value.organization,
      'EVALUATOR_IDENTITY_INVALID',
      'organization',
    ),
  };
}

function validateSessionInputs(sessionReceipt, sessionVerification) {
  requireCondition(
    isRecord(sessionReceipt)
      && sessionReceipt.schema === 'standards-interactive-rehearsal-receipt/2'
      && typeof sessionReceipt.receiptId === 'string',
    'SESSION_RECEIPT_INVALID',
    'session receipt is invalid',
  );
  requireCondition(
    isRecord(sessionVerification)
      && sessionVerification.schema === 'standards-interactive-rehearsal-verification/2'
      && sessionVerification.status === 'pass',
    'SESSION_VERIFICATION_INVALID',
    'session verification did not pass',
  );
  requireCondition(
    sessionVerification.receiptId === sessionReceipt.receiptId,
    'SESSION_VERIFICATION_MISMATCH',
    'session verification covers another session receipt',
  );
  requireCondition(
    sessionVerification.evaluationId === sessionReceipt.evaluationId
      && sessionVerification.evaluationStatus === sessionReceipt.evaluationStatus,
    'SESSION_VERIFICATION_MISMATCH',
    'session verification covers another automatic evaluation',
  );
}

function signerIdentity(key) {
  const publicKey = key?.type === 'public' ? key : createPublicKey(key);
  const der = publicKey.export({ type: 'spki', format: 'der' });
  return {
    keyId: `ed25519:${createHash('sha256').update(der).digest('hex')}`,
    publicKeySpkiBase64: der.toString('base64'),
  };
}

function dispositionBody({
  sessionReceipt,
  sessionVerification,
  evaluator,
  disposition,
  rationale,
  issuedAt,
  signer,
}) {
  return {
    sessionReceiptId: sessionReceipt.receiptId,
    scenarioCatalogId: sessionReceipt.scenarioCatalogId,
    scenarioId: sessionReceipt.scenarioId,
    scenarioDefinitionId: sessionReceipt.scenarioDefinitionId,
    automaticEvaluationId: sessionReceipt.evaluationId,
    automaticEvaluationStatus: sessionReceipt.evaluationStatus,
    detachedVerificationSchema: sessionVerification.schema,
    detachedVerificationStatus: sessionVerification.status,
    finalStateId: sessionReceipt.finalStateId,
    evaluator,
    disposition,
    rationale,
    issuedAt,
    signer,
  };
}

function signaturePayload(receipt) {
  const {
    schema: _schema,
    dispositionReceiptId: _dispositionReceiptId,
    signature: _signature,
    claimBoundary: _claimBoundary,
    ...body
  } = receipt;
  return Buffer.from(canonicalJson(body), 'utf8');
}

export function createLocalEvaluatorSigner({ clock = () => new Date() } = {}) {
  const { publicKey, privateKey } = generateKeyPairSync('ed25519');
  const signer = {
    schema: 'standards-local-evaluator-signer/1',
    ...signerIdentity(publicKey),
    trustClass: 'local_process_integrity_only',
  };

  return {
    publicIdentity: structuredClone(signer),
    issue({
      sessionReceipt,
      sessionVerification,
      evaluator: evaluatorInput,
      disposition,
      rationale = '',
    }) {
      validateSessionInputs(sessionReceipt, sessionVerification);
      requireCondition(
        DISPOSITIONS.has(disposition),
        'EVALUATOR_DISPOSITION_INVALID',
        'disposition must be accept, reject, or defer',
      );
      if (disposition === 'accept') {
        requireCondition(
          sessionReceipt.evaluationStatus === 'pass',
          'AUTOMATIC_PASS_REQUIRED',
          'acceptance requires a replay-verified automatic pass',
        );
      }
      const evaluator = normalizedEvaluator(evaluatorInput);
      const normalizedRationale = optionalString(
        rationale,
        'EVALUATOR_RATIONALE_INVALID',
        'rationale',
        MAX_RATIONALE_LENGTH,
      );
      if (disposition !== 'accept') {
        requireCondition(
          normalizedRationale !== null,
          'EVALUATOR_RATIONALE_REQUIRED',
          'reject and defer dispositions require a rationale',
        );
      }
      const now = clock();
      requireCondition(
        now instanceof Date && Number.isFinite(now.getTime()),
        'EVALUATOR_CLOCK_INVALID',
        'clock did not return a valid Date',
      );
      const body = dispositionBody({
        sessionReceipt,
        sessionVerification,
        evaluator,
        disposition,
        rationale: normalizedRationale,
        issuedAt: now.toISOString(),
        signer,
      });
      const receipt = {
        schema: 'standards-evaluator-disposition/1',
        dispositionReceiptId: digest('standardsevaluatordisposition1', body),
        ...body,
        signature: null,
        claimBoundary:
          'This local Ed25519 signature proves receipt integrity for one rehearsal-host process. It does not independently authenticate the evaluator, establish program acceptance, or grant operational authority.',
      };
      receipt.signature = signBytes(
        null,
        signaturePayload(receipt),
        privateKey,
      ).toString('base64');
      return receipt;
    },
  };
}

export function verifyEvaluatorDisposition(
  receipt,
  { sessionReceipt, sessionVerification },
) {
  validateSessionInputs(sessionReceipt, sessionVerification);
  requireCondition(
    isRecord(receipt) && receipt.schema === 'standards-evaluator-disposition/1',
    'EVALUATOR_RECEIPT_INVALID',
    'evaluator disposition receipt schema is invalid',
  );
  requireCondition(
    DISPOSITIONS.has(receipt.disposition),
    'EVALUATOR_DISPOSITION_INVALID',
    'evaluator disposition is invalid',
  );
  const evaluator = normalizedEvaluator(receipt.evaluator);
  requireCondition(
    canonicalJson(evaluator) === canonicalJson(receipt.evaluator),
    'EVALUATOR_IDENTITY_INVALID',
    'evaluator identity is not normalized',
  );
  requireCondition(
    receipt.sessionReceiptId === sessionReceipt.receiptId
      && receipt.scenarioCatalogId === sessionReceipt.scenarioCatalogId
      && receipt.scenarioId === sessionReceipt.scenarioId
      && receipt.scenarioDefinitionId === sessionReceipt.scenarioDefinitionId
      && receipt.automaticEvaluationId === sessionReceipt.evaluationId
      && receipt.automaticEvaluationStatus === sessionReceipt.evaluationStatus
      && receipt.finalStateId === sessionReceipt.finalStateId,
    'EVALUATOR_SESSION_MISMATCH',
    'evaluator disposition covers another session or evaluation',
  );
  requireCondition(
    receipt.detachedVerificationSchema === sessionVerification.schema
      && receipt.detachedVerificationStatus === sessionVerification.status,
    'EVALUATOR_VERIFICATION_MISMATCH',
    'evaluator disposition covers another detached verification result',
  );
  if (receipt.disposition === 'accept') {
    requireCondition(
      sessionReceipt.evaluationStatus === 'pass',
      'AUTOMATIC_PASS_REQUIRED',
      'acceptance requires a replay-verified automatic pass',
    );
  } else {
    boundedString(
      receipt.rationale,
      'EVALUATOR_RATIONALE_REQUIRED',
      'rationale',
      MAX_RATIONALE_LENGTH,
    );
  }
  requireCondition(
    isRecord(receipt.signer)
      && receipt.signer.schema === 'standards-local-evaluator-signer/1'
      && receipt.signer.trustClass === 'local_process_integrity_only',
    'EVALUATOR_SIGNER_INVALID',
    'evaluator signer declaration is invalid',
  );
  const publicKeyDer = Buffer.from(receipt.signer.publicKeySpkiBase64, 'base64');
  const publicKey = createPublicKey({
    key: publicKeyDer,
    type: 'spki',
    format: 'der',
  });
  requireCondition(
    signerIdentity(publicKey).keyId === receipt.signer.keyId,
    'EVALUATOR_SIGNER_INVALID',
    'evaluator signer key identity does not match the public key',
  );
  requireCondition(
    typeof receipt.signature === 'string'
      && verifyBytes(
        null,
        signaturePayload(receipt),
        publicKey,
        Buffer.from(receipt.signature, 'base64'),
      ),
    'EVALUATOR_SIGNATURE_INVALID',
    'evaluator disposition signature is invalid',
  );
  const body = dispositionBody({
    sessionReceipt,
    sessionVerification,
    evaluator: receipt.evaluator,
    disposition: receipt.disposition,
    rationale: receipt.rationale,
    issuedAt: receipt.issuedAt,
    signer: receipt.signer,
  });
  requireCondition(
    receipt.dispositionReceiptId === digest('standardsevaluatordisposition1', body),
    'EVALUATOR_RECEIPT_ID_INVALID',
    'evaluator disposition identity does not match its contents',
  );
  return {
    schema: 'standards-evaluator-disposition-verification/1',
    status: 'pass',
    dispositionReceiptId: receipt.dispositionReceiptId,
    sessionReceiptId: receipt.sessionReceiptId,
    automaticEvaluationId: receipt.automaticEvaluationId,
    automaticEvaluationStatus: receipt.automaticEvaluationStatus,
    evaluatorDisposition: receipt.disposition,
    signerKeyId: receipt.signer.keyId,
    signatureVerified: true,
    sessionClosureVerified: true,
    claimBoundary:
      'This receipt verifies local disposition integrity and closure to one replay-verified rehearsal session. It does not authenticate organizational authority or constitute program acceptance.',
  };
}

export function createAcceptancePackage({
  sessionReceipt,
  sessionVerification,
  dispositionReceipt,
  dispositionVerification,
}) {
  validateSessionInputs(sessionReceipt, sessionVerification);
  requireCondition(
    isRecord(dispositionReceipt)
      && isRecord(dispositionVerification)
      && dispositionVerification.status === 'pass'
      && dispositionVerification.dispositionReceiptId
        === dispositionReceipt.dispositionReceiptId,
    'ACCEPTANCE_PACKAGE_DISPOSITION_INVALID',
    'verified evaluator disposition is required',
  );
  const body = {
    sessionReceipt,
    sessionVerification,
    dispositionReceipt,
    dispositionVerification,
  };
  return {
    schema: 'standards-rehearsal-acceptance-package/1',
    acceptancePackageId: digest('standardsrehearsalacceptancepackage1', body),
    ...body,
    claimBoundary:
      'This package preserves the automatic result, detached replay verification, and separate local evaluator disposition. It does not elevate the local signer into program acceptance authority.',
  };
}

export class EvaluatorDispositionRegistry {
  constructor(signer) {
    requireCondition(
      signer && typeof signer.issue === 'function',
      'EVALUATOR_SIGNER_INVALID',
      'registry requires an evaluator signer',
    );
    this.signer = signer;
    this.receipts = new Map();
  }

  issue(input) {
    const sessionReceiptId = input?.sessionReceipt?.receiptId;
    requireCondition(
      typeof sessionReceiptId === 'string',
      'SESSION_RECEIPT_INVALID',
      'session receipt identity is required',
    );
    requireCondition(
      !this.receipts.has(sessionReceiptId),
      'EVALUATOR_DISPOSITION_EXISTS',
      'this session already has an immutable evaluator disposition',
    );
    const receipt = this.signer.issue(input);
    this.receipts.set(sessionReceiptId, receipt);
    return receipt;
  }

  get(sessionReceiptId) {
    return this.receipts.get(sessionReceiptId) ?? null;
  }
}

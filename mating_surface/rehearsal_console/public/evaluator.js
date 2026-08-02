const elements = {
  refreshButton: document.querySelector('#refreshButton'),
  scenarioValue: document.querySelector('#scenarioValue'),
  automaticValue: document.querySelector('#automaticValue'),
  verificationValue: document.querySelector('#verificationValue'),
  sessionValue: document.querySelector('#sessionValue'),
  dispositionState: document.querySelector('#dispositionState'),
  form: document.querySelector('#dispositionForm'),
  evaluatorId: document.querySelector('#evaluatorId'),
  evaluatorRole: document.querySelector('#evaluatorRole'),
  evaluatorOrganization: document.querySelector('#evaluatorOrganization'),
  dispositionSelect: document.querySelector('#dispositionSelect'),
  rationale: document.querySelector('#rationale'),
  issueButton: document.querySelector('#issueButton'),
  formStatus: document.querySelector('#formStatus'),
  verifyButton: document.querySelector('#verifyButton'),
  exportButton: document.querySelector('#exportButton'),
  receiptDisposition: document.querySelector('#receiptDisposition'),
  receiptEvaluator: document.querySelector('#receiptEvaluator'),
  receiptSigner: document.querySelector('#receiptSigner'),
  receiptId: document.querySelector('#receiptId'),
  receiptJson: document.querySelector('#receiptJson'),
};

let currentState = null;
let currentVerification = null;
let currentDisposition = null;

function titleCase(value) {
  return String(value ?? 'none')
    .replaceAll('_', ' ')
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function shortId(value) {
  if (!value) return 'None';
  if (value.length < 30) return value;
  return `${value.slice(0, 14)}…${value.slice(-12)}`;
}

async function requestJson(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {
      ...(options.body ? { 'Content-Type': 'application/json' } : {}),
      ...(options.headers ?? {}),
    },
  });
  const value = await response.json();
  if (!response.ok) {
    const error = new Error(value.message ?? `Request failed with status ${response.status}`);
    error.code = value.error ?? 'REQUEST_FAILED';
    throw error;
  }
  return value;
}

function renderDisposition() {
  const receipt = currentDisposition?.receipt ?? null;
  elements.dispositionState.textContent = receipt ? 'Issued' : 'Not issued';
  elements.receiptDisposition.textContent = receipt ? titleCase(receipt.disposition) : 'None';
  elements.receiptEvaluator.textContent = receipt
    ? `${receipt.evaluator.evaluatorId} · ${receipt.evaluator.role}`
    : 'None';
  elements.receiptSigner.textContent = receipt
    ? titleCase(receipt.signer.trustClass)
    : 'Local process integrity only';
  elements.receiptId.textContent = receipt ? shortId(receipt.dispositionReceiptId) : 'None';
  elements.receiptId.title = receipt?.dispositionReceiptId ?? '';
  elements.receiptJson.textContent = receipt
    ? JSON.stringify(receipt, null, 2)
    : 'No disposition has been issued.';
  const issued = Boolean(receipt);
  for (const field of [
    elements.evaluatorId,
    elements.evaluatorRole,
    elements.evaluatorOrganization,
    elements.dispositionSelect,
    elements.rationale,
    elements.issueButton,
  ]) field.disabled = issued;
  elements.verifyButton.disabled = !issued;
  elements.exportButton.disabled = !issued;
  elements.formStatus.textContent = issued
    ? 'This disposition is immutable for the current session receipt.'
    : 'One disposition may be issued for the current session receipt.';
}

function render() {
  elements.scenarioValue.textContent = currentState?.scenario?.name ?? 'Unavailable';
  elements.automaticValue.textContent = titleCase(currentState?.evaluation?.status ?? 'unavailable');
  elements.verificationValue.textContent = currentVerification?.status === 'pass'
    ? 'Replay verified'
    : 'Unavailable';
  elements.sessionValue.textContent = shortId(currentVerification?.receiptId);
  elements.sessionValue.title = currentVerification?.receiptId ?? '';
  const automaticPass = currentState?.evaluation?.status === 'pass';
  const acceptOption = elements.dispositionSelect.querySelector('option[value="accept"]');
  acceptOption.disabled = !automaticPass;
  if (!automaticPass && elements.dispositionSelect.value === 'accept') {
    elements.dispositionSelect.value = 'defer';
  }
  renderDisposition();
}

async function refresh() {
  elements.refreshButton.disabled = true;
  try {
    [currentState, currentVerification, currentDisposition] = await Promise.all([
      requestJson('/api/state'),
      requestJson('/api/verify'),
      requestJson('/api/disposition'),
    ]);
    render();
  } catch (error) {
    elements.formStatus.textContent = `${error.code ?? 'REFUSED'}: ${error.message}`;
  } finally {
    elements.refreshButton.disabled = false;
  }
}

async function issueDisposition(event) {
  event.preventDefault();
  elements.issueButton.disabled = true;
  elements.formStatus.textContent = 'Issuing disposition…';
  try {
    const receipt = await requestJson('/api/disposition', {
      method: 'POST',
      body: JSON.stringify({
        evaluator: {
          evaluatorId: elements.evaluatorId.value,
          role: elements.evaluatorRole.value,
          organization: elements.evaluatorOrganization.value,
        },
        disposition: elements.dispositionSelect.value,
        rationale: elements.rationale.value,
      }),
    });
    currentDisposition = {
      schema: 'standards-evaluator-disposition-state/1',
      status: 'issued',
      sessionReceiptId: receipt.sessionReceiptId,
      receipt,
    };
    renderDisposition();
  } catch (error) {
    elements.formStatus.textContent = `${error.code ?? 'REFUSED'}: ${error.message}`;
    elements.issueButton.disabled = false;
  }
}

async function verifyDisposition() {
  elements.verifyButton.disabled = true;
  try {
    const receipt = await requestJson('/api/disposition/verify');
    elements.formStatus.textContent = `Disposition verified · ${shortId(receipt.dispositionReceiptId)}`;
  } catch (error) {
    elements.formStatus.textContent = `${error.code ?? 'REFUSED'}: ${error.message}`;
  } finally {
    elements.verifyButton.disabled = false;
  }
}

async function exportPackage() {
  elements.exportButton.disabled = true;
  try {
    const packageReceipt = await requestJson('/api/acceptance-package');
    const blob = new Blob([`${JSON.stringify(packageReceipt, null, 2)}\n`], {
      type: 'application/json',
    });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `rehearsal-acceptance-${packageReceipt.acceptancePackageId.slice(-12)}.json`;
    link.click();
    URL.revokeObjectURL(link.href);
    elements.formStatus.textContent = 'Acceptance package exported.';
  } catch (error) {
    elements.formStatus.textContent = `${error.code ?? 'REFUSED'}: ${error.message}`;
  } finally {
    elements.exportButton.disabled = false;
  }
}

elements.refreshButton.addEventListener('click', refresh);
elements.form.addEventListener('submit', issueDisposition);
elements.verifyButton.addEventListener('click', verifyDisposition);
elements.exportButton.addEventListener('click', exportPackage);
elements.dispositionSelect.addEventListener('change', () => {
  const required = elements.dispositionSelect.value !== 'accept';
  elements.rationale.required = required;
  elements.rationale.setAttribute('aria-required', String(required));
});

refresh();

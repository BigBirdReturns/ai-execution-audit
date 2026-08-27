import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  KEYS,
  FabricExecutionError,
  assertIdentity,
  digest,
  exactKeys,
  exactObject,
  requireCondition,
} from './fabric_execution_support.mjs';
import {
  runFabricExecutionCampaign,
  validateFabricRun,
  verifyFabricRun,
} from './fabric_run.mjs';

export {
  FabricExecutionError,
  createFallbackRouteAndLease,
  createIndependentVerifierEvidence,
  createPrimarySeatLossEvidence,
  validateIndependentVerifierEvidence,
  validatePrimarySeatLossEvidence,
} from './fabric_execution_support.mjs';
export {
  createCompletionCandidate,
  createCompletionRefusal,
  validateCompletionCandidate,
  validateCompletionRefusal,
} from './fabric_completion.mjs';
export {
  runFabricExecutionCampaign,
  validateFabricRun,
  verifyFabricRun,
} from './fabric_run.mjs';

const HERE = dirname(fileURLToPath(import.meta.url));
const DEFAULT_PROFILE = resolve(HERE, 'fabric-profile-01.json');
const DEFAULT_REGISTRY = resolve(HERE, 'fixtures/mp01-invented-seat-registry.json');

export function buildFabricExecutionProjection(run) {
  validateFabricRun(run);
  const accepted = run.candidates.find((row) => row.candidateId === run.acceptedCandidateId);
  const body = {
    schema: 'spectra-anchor-node-fabric-execution-projection/1',
    fabricRunId: run.fabricRunId,
    sourceRoutingSliceId: run.sourceRoutingSliceId,
    routes: [
      {
        role: 'primary',
        routeSelectionId: run.primaryRouteSelection.routeSelectionId,
        leaseId: run.primaryWorkerLease.leaseId,
        terminalState: 'lost_and_superseded',
      },
      {
        role: 'fallback',
        routeSelectionId: run.fallbackRouteSelection.routeSelectionId,
        leaseId: run.fallbackWorkerLease.leaseId,
        terminalState: 'completed_exactly_once',
      },
    ],
    leases: [
      {
        leaseId: run.primaryWorkerLease.leaseId,
        generation: run.primarySeatLossEvidence.leaseGeneration,
        state: 'superseded_after_inaccessibility_evidence',
      },
      {
        leaseId: run.fallbackWorkerLease.leaseId,
        generation: run.fallbackWorkerLease.generation,
        state: 'terminal_completion_accepted',
      },
    ],
    candidateSummary: run.dispositions.map((row) => ({
      candidateId: row.candidateId,
      disposition: row.disposition,
      refusalId: row.refusalId,
    })),
    refusalSummary: run.refusals.map((row) => ({
      refusalId: row.refusalId,
      candidateId: row.candidateId,
      reasons: row.reasons,
    })),
    acceptedCompletion: {
      candidateId: accepted.candidateId,
      seatId: accepted.seatId,
      leaseGeneration: accepted.leaseGeneration,
      outputDigest: accepted.outputDigest,
      verifierIdentity: accepted.verificationEvidence.verifierIdentity,
    },
    canonicalStateUnchanged: run.canonicalStateUnchanged,
    jobCustodyPreserved: run.jobCustodyPreserved,
    authority: 'none',
    claimBoundary:
      'Destructible receipt-only projection of the synthetic fabric run. It is not canonical mission state, an execution authority surface, or physical-field qualification.',
  };
  return { ...body, projectionId: digest('estatefabricexecutionprojection1', body) };
}

export function validateFabricExecutionProjection(projection, run) {
  exactKeys(projection, KEYS.projection, 'FABRIC_EXECUTION_PROJECTION_INVALID', 'fabric execution projection');
  requireCondition(projection.schema === 'spectra-anchor-node-fabric-execution-projection/1', 'FABRIC_EXECUTION_PROJECTION_SCHEMA_INVALID', 'projection schema differs');
  requireCondition(projection.authority === 'none' && projection.canonicalStateUnchanged === true && projection.jobCustodyPreserved === true, 'FABRIC_EXECUTION_PROJECTION_CLAIM_INVALID', 'projection widens its claim');
  assertIdentity(projection, 'estatefabricexecutionprojection1', 'projectionId', 'FABRIC_EXECUTION_PROJECTION_ID_INVALID');
  if (run !== undefined) {
    exactObject(projection, buildFabricExecutionProjection(run), 'FABRIC_EXECUTION_PROJECTION_REPLAY_MISMATCH', 'fabric execution projection replay');
  }
  return projection;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

export function renderFabricExecutionHtml(projection) {
  validateFabricExecutionProjection(projection);
  const rows = projection.candidateSummary
    .map((row) => `<tr><td>${escapeHtml(row.candidateId)}</td><td>${escapeHtml(row.disposition)}</td><td>${escapeHtml(row.refusalId ?? '')}</td></tr>`)
    .join('');
  const refusals = projection.refusalSummary
    .map((row) => `<li><code>${escapeHtml(row.refusalId)}</code>: ${escapeHtml(row.reasons.join(', '))}</li>`)
    .join('');
  return `<!doctype html>\n<html lang="en"><head><meta charset="utf-8"><title>MP01 Estate Fabric Terminal Receipt</title></head><body><main><h1>MP01 Estate Fabric Terminal Receipt</h1><p>Fabric run: <code>${escapeHtml(projection.fabricRunId)}</code></p><p>Accepted candidate: <code>${escapeHtml(projection.acceptedCompletion.candidateId)}</code></p><p>Accepted seat: <code>${escapeHtml(projection.acceptedCompletion.seatId)}</code>, generation ${projection.acceptedCompletion.leaseGeneration}</p><p>Canonical state unchanged: ${projection.canonicalStateUnchanged}</p><p>Job custody preserved: ${projection.jobCustodyPreserved}</p><h2>Candidate denominator</h2><table><thead><tr><th>Candidate</th><th>Disposition</th><th>Refusal</th></tr></thead><tbody>${rows}</tbody></table><h2>Refusals</h2><ul>${refusals}</ul><p>${escapeHtml(projection.claimBoundary)}</p></main></body></html>\n`;
}

async function writeJson(path, value) {
  await mkdir(dirname(path), { recursive: true });
  await writeFile(path, `${JSON.stringify(value, null, 2)}\n`, 'utf8');
}

async function loadDefaults() {
  const [fabricProfileText, registryText] = await Promise.all([
    readFile(DEFAULT_PROFILE, 'utf8'),
    readFile(DEFAULT_REGISTRY, 'utf8'),
  ]);
  return {
    fabricProfile: JSON.parse(fabricProfileText),
    registry: JSON.parse(registryText),
  };
}

async function main(argv) {
  const command = argv[2];
  if (command === 'run') {
    const [bundleText, routingText, defaults] = await Promise.all([
      readFile(resolve(argv[3]), 'utf8'),
      readFile(resolve(argv[4]), 'utf8'),
      loadDefaults(),
    ]);
    const outputPath = resolve(argv[5]);
    const run = runFabricExecutionCampaign({
      bundle: JSON.parse(bundleText),
      routingSlice: JSON.parse(routingText),
      ...defaults,
    });
    await writeJson(outputPath, run);
    process.stdout.write(`${JSON.stringify({ status: 'PASS', fabricRunId: run.fabricRunId, acceptedCandidateId: run.acceptedCandidateId, refusalCount: run.refusals.length, outputPath }, null, 2)}\n`);
    return;
  }
  if (command === 'verify') {
    const [bundleText, routingText, runText, defaults] = await Promise.all([
      readFile(resolve(argv[3]), 'utf8'),
      readFile(resolve(argv[4]), 'utf8'),
      readFile(resolve(argv[5]), 'utf8'),
      loadDefaults(),
    ]);
    const outputPath = resolve(argv[6]);
    const verification = verifyFabricRun(JSON.parse(runText), {
      bundle: JSON.parse(bundleText),
      routingSlice: JSON.parse(routingText),
      ...defaults,
    });
    await writeJson(outputPath, verification);
    process.stdout.write(`${JSON.stringify(verification, null, 2)}\n`);
    return;
  }
  if (command === 'project') {
    const run = JSON.parse(await readFile(resolve(argv[3]), 'utf8'));
    const projectionPath = resolve(argv[4]);
    const htmlPath = resolve(argv[5]);
    const projection = buildFabricExecutionProjection(run);
    await writeJson(projectionPath, projection);
    await mkdir(dirname(htmlPath), { recursive: true });
    await writeFile(htmlPath, renderFabricExecutionHtml(projection), 'utf8');
    process.stdout.write(`${JSON.stringify({ status: 'PASS', projectionId: projection.projectionId, projectionPath, htmlPath }, null, 2)}\n`);
    return;
  }
  throw new FabricExecutionError(
    'COMMAND_INVALID',
    'usage: fabric_execution.mjs run <vertical-slice.json> <routing-slice.json> <fabric-run.json> | verify <vertical-slice.json> <routing-slice.json> <fabric-run.json> <verification.json> | project <fabric-run.json> <projection.json> <review.html>',
  );
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  main(process.argv).catch((error) => {
    process.stderr.write(`${error instanceof FabricExecutionError ? error.code : 'UNEXPECTED_ERROR'}: ${error.message}\n`);
    process.exitCode = 1;
  });
}

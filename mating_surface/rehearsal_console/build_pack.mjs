#!/usr/bin/env node
import { createHash } from 'node:crypto';
import {
  cpSync,
  mkdirSync,
  readFileSync,
  readdirSync,
  rmSync,
  statSync,
  writeFileSync,
} from 'node:fs';
import { dirname, join, relative, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { canonicalJson } from '../semantic/authority_sidecar.mjs';
import { verifyExternalEvidenceQualification } from './external_evidence.mjs';
import { REHEARSAL_SCENARIO_CATALOG } from './scenarios.mjs';

const EXTERNAL_EVIDENCE_PATH =
  'mating_surface/rehearsal_console/evidence/external/standing-orders-admin-inject-20260802.json';

function requireCondition(condition, message) {
  if (!condition) throw new Error(message);
}

function sha256File(path) {
  return createHash('sha256').update(readFileSync(path)).digest('hex');
}

function copyFile(source, destination) {
  mkdirSync(dirname(destination), { recursive: true });
  cpSync(source, destination);
}

function copyTree(source, destination) {
  mkdirSync(dirname(destination), { recursive: true });
  cpSync(source, destination, { recursive: true });
}

function listFiles(root) {
  const result = [];
  function walk(path) {
    for (const name of readdirSync(path).sort()) {
      const child = join(path, name);
      const stat = statSync(child);
      if (stat.isDirectory()) walk(child);
      else if (stat.isFile()) result.push(child);
    }
  }
  walk(root);
  return result;
}

function readJson(path) {
  return JSON.parse(readFileSync(path, 'utf8'));
}

function writeJson(path, value) {
  writeFileSync(path, `${JSON.stringify(value, null, 2)}\n`, 'utf8');
}

function loadExternalEvidence(repository) {
  const path = join(repository, EXTERNAL_EVIDENCE_PATH);
  const bundle = readJson(path);
  requireCondition(bundle && typeof bundle === 'object', 'external evidence bundle is missing');
  const verification = verifyExternalEvidenceQualification(bundle.qualification);
  requireCondition(
    canonicalJson(verification) === canonicalJson(bundle.verification),
    'external evidence verification does not reconstruct',
  );
  requireCondition(
    bundle.qualification.source.evidenceTier === 'private_digest_only'
      && bundle.qualification.source.rawSourceCommitted === false,
    'external evidence violated the private digest-only source boundary',
  );
  requireCondition(
    bundle.qualification.automaticEvaluation.status === 'incomplete'
      && bundle.qualification.automaticEvaluation.acceptanceEligible === false,
    'external evidence was promoted beyond the retained incomplete result',
  );
  return bundle;
}

export function buildRehearsalConsolePack({
  qualificationRoot,
  repositoryRoot,
  outputDir,
  sourceCommit,
}) {
  const qualification = resolve(qualificationRoot);
  const repository = resolve(repositoryRoot);
  const output = resolve(outputDir);
  const semanticVerification = readJson(
    join(qualification, 'semantic-rehearsal-verification.json'),
  );
  requireCondition(
    semanticVerification.status === 'pass',
    'semantic rehearsal verification did not pass',
  );
  requireCondition(
    typeof sourceCommit === 'string' && /^[0-9a-f]{40}$/.test(sourceCommit),
    'sourceCommit must be a 40-character lowercase Git SHA',
  );
  const externalEvidence = loadExternalEvidence(repository);

  rmSync(output, { recursive: true, force: true });
  mkdirSync(output, { recursive: true });

  const sourceFiles = [
    'mating_surface/rehearsal_console/README.md',
    'mating_surface/rehearsal_console/scenarios.mjs',
    'mating_surface/rehearsal_console/session.mjs',
    'mating_surface/rehearsal_console/evaluator_disposition.mjs',
    'mating_surface/rehearsal_console/external_evidence.mjs',
    EXTERNAL_EVIDENCE_PATH,
    'mating_surface/rehearsal_console/server.mjs',
    'mating_surface/rehearsal_console/public/index.html',
    'mating_surface/rehearsal_console/public/styles.css',
    'mating_surface/rehearsal_console/public/app.js',
    'mating_surface/rehearsal_console/public/evaluator.html',
    'mating_surface/rehearsal_console/public/evaluator.css',
    'mating_surface/rehearsal_console/public/evaluator.js',
    'mating_surface/rehearsal_console/START_STANDARDS_REHEARSAL.cmd',
    'mating_surface/rehearsal_console/start-standards-rehearsal.sh',
    'mating_surface/semantic/authority_sidecar.mjs',
    'mating_surface/semantic/run_semantic_rehearsal.mjs',
    'mating_surface/test_hosts/core/fault_machine.mjs',
    'mating_surface/test_hosts/core/fault_verifier.mjs',
  ];
  for (const path of sourceFiles) {
    const source = join(repository, path);
    requireCondition(statSync(source).isFile(), `missing source file ${path}`);
    copyFile(source, join(output, path));
  }
  copyTree(
    join(repository, 'mating_surface/rehearsal_console/docs'),
    join(output, 'mating_surface/rehearsal_console/docs'),
  );

  copyFile(
    join(repository, 'mating_surface/rehearsal_console/START_STANDARDS_REHEARSAL.cmd'),
    join(output, 'START_STANDARDS_REHEARSAL.cmd'),
  );
  copyFile(
    join(repository, 'mating_surface/rehearsal_console/start-standards-rehearsal.sh'),
    join(output, 'start-standards-rehearsal.sh'),
  );

  const evidenceFiles = [
    'artifact-transaction.json',
    'xsd11-catalog.json',
    'semantic-rehearsal-verification.json',
  ];
  for (const path of evidenceFiles) {
    copyFile(join(qualification, path), join(output, 'evidence', path));
  }
  copyTree(
    join(qualification, 'semantic-conversation'),
    join(output, 'evidence', 'semantic-conversation'),
  );
  copyTree(
    join(qualification, 'semantic-rehearsal'),
    join(output, 'evidence', 'semantic-rehearsal'),
  );

  writeJson(join(output, 'package.json'), {
    name: 'standards-denied-communications-rehearsal',
    version: '1.4.1',
    private: true,
    type: 'module',
    scripts: {
      start:
        'node mating_surface/rehearsal_console/server.mjs --evidence evidence --build-manifest build-manifest.json --host 127.0.0.1 --port 8787',
    },
    engines: {
      node: '>=24',
    },
  });

  writeFileSync(
    join(output, 'README.md'),
    `# Denied Communications Authority Rehearsal\n\n`
      + `This local pack runs a neutral standards-based acceptance and rehearsal station against the exact source and evidence listed in \`build-manifest.json\`.\n\n`
      + `On Windows, run \`START_STANDARDS_REHEARSAL.cmd\`. On Linux or macOS, run \`./start-standards-rehearsal.sh\`. Node.js 24 or newer is required.\n\n`
      + `The operator workflow is Plan, Run, Evaluate, Evidence, and Guide. Role-specific support documentation is packaged under \`mating_surface/rehearsal_console/docs\` and served locally from \`/docs/\`.\n\n`
      + `Qualified scenario definitions, procedures, and acceptance checks are source-controlled in \`mating_surface/rehearsal_console/scenarios.mjs\` and evaluated server-side. Browser presentation cannot redefine a pass. A changed configuration or off-procedure action is retained as an exploratory deviation.\n\n`
      + `The separate evaluator workspace is available at \`/evaluator.html\`. It preserves the automatic result and detached replay receipt, then issues one immutable local accept, reject, or defer disposition. The local process signature protects receipt integrity but does not authenticate organizational authority or constitute program acceptance.\n\n`
      + `One private-source external test is retained as a digest-only, automatically incomplete evidence receipt. Its raw log and producer-report bytes are not packaged. External-evidence admission has no acceptance-closure authority and refuses self-asserted canonical session identifiers or replay status. See \`mating_surface/rehearsal_console/docs/EXTERNAL_EVIDENCE_ADMISSION.md\`.\n\n`
      + `The host binds only to \`127.0.0.1\`. The browser contains presentation and API calls; authority decisions, scenario evaluation, and evaluator-disposition integrity execute in packaged server-side modules.\n\n`
      + `This is a rehearsal-only reference profile. It grants no operational command, targeting, engagement, effector, execution, or weapons authority.\n`,
    'utf8',
  );

  const filesBeforeManifest = listFiles(output);
  const manifestBody = {
    sourceCommit,
    semanticConversationId: readJson(
      join(output, 'evidence/semantic-conversation/conversation.json'),
    ).semanticConversationId,
    semanticVerificationId: semanticVerification.verificationId,
    scenarioCatalogId: REHEARSAL_SCENARIO_CATALOG.catalogId,
    runtimeMode: 'server_side_direct_import',
    authorityImplementation: 'MessageAuthorityRuntime',
    acceptanceEvaluation: 'server_side_source_controlled',
    evaluatorDisposition: 'separate_local_signed_receipt',
    externalEvidenceQualificationId:
      externalEvidence.qualification.receiptId,
    externalEvidenceSourceEvidenceSetId:
      externalEvidence.qualification.sourceEvidenceSetId,
    externalEvidenceAutomaticStatus:
      externalEvidence.qualification.automaticEvaluation.status,
    externalEvidenceAcceptanceEligible:
      externalEvidence.qualification.automaticEvaluation.acceptanceEligible,
    externalEvidencePrivateSourceBytesCommitted:
      externalEvidence.qualification.source.rawSourceCommitted,
    interactionModel: 'plan_run_evaluate_evidence_guide',
    supportDocumentation: true,
    loopbackOnly: true,
    files: Object.fromEntries(
      filesBeforeManifest.map((path) => {
        const name = relative(output, path).replaceAll('\\', '/');
        return [name, {
          bytes: statSync(path).size,
          sha256: sha256File(path),
        }];
      }),
    ),
  };
  const manifest = {
    schema: 'standards-rehearsal-console-build/1',
    buildId: `standardsrehearsalconsole1_${createHash('sha256')
      .update(canonicalJson(manifestBody), 'utf8')
      .digest('hex')}`,
    ...manifestBody,
    manifestSelfExcluded: true,
    claimBoundary:
      'This manifest binds the local console source, scenario catalog, evaluator-disposition module, digest-only external-evidence admission, support documentation, and generated rehearsal evidence. External-evidence admission has no canonical-closure authority; the retained receipt remains incomplete and acceptance-ineligible. The manifest does not establish evaluator identity, program acceptance authority, target-host, human-performance, accessibility, or operational qualification.',
  };
  writeJson(join(output, 'build-manifest.json'), manifest);
  return manifest;
}

function main(argv) {
  if (argv.length !== 4) {
    console.error(
      'usage: build_pack.mjs <qualification-root> <repository-root> <output-dir> <source-commit>',
    );
    return 2;
  }
  const [qualificationRoot, repositoryRoot, outputDir, sourceCommit] = argv;
  const manifest = buildRehearsalConsolePack({
    qualificationRoot,
    repositoryRoot,
    outputDir,
    sourceCommit,
  });
  process.stdout.write(`${JSON.stringify({
    status: 'pass',
    buildId: manifest.buildId,
    sourceCommit: manifest.sourceCommit,
    scenarioCatalogId: manifest.scenarioCatalogId,
    evaluatorDisposition: manifest.evaluatorDisposition,
    externalEvidenceAutomaticStatus: manifest.externalEvidenceAutomaticStatus,
    externalEvidenceAcceptanceEligible: manifest.externalEvidenceAcceptanceEligible,
    files: Object.keys(manifest.files).length,
    outputDir: resolve(outputDir),
  }, null, 2)}\n`);
  return 0;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  process.exitCode = main(process.argv.slice(2));
}

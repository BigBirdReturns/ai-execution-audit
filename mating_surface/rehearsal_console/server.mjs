#!/usr/bin/env node
import { createHash } from 'node:crypto';
import { createServer } from 'node:http';
import { readFileSync, statSync } from 'node:fs';
import { dirname, extname, join, normalize, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import {
  EvaluatorDispositionError,
  EvaluatorDispositionRegistry,
  createAcceptancePackage,
  createLocalEvaluatorSigner,
  verifyEvaluatorDisposition,
} from './evaluator_disposition.mjs';
import {
  RehearsalSessionError,
  StandardsRehearsalSession,
  loadRehearsalFixture,
  verifySessionReceipt,
} from './session.mjs';
import {
  REHEARSAL_SCENARIO_CATALOG,
  publicScenarioCatalog,
} from './scenarios.mjs';

const MODULE_DIR = dirname(fileURLToPath(import.meta.url));
const DEFAULT_PUBLIC_DIR = join(MODULE_DIR, 'public');
const DEFAULT_DOCS_DIR = join(MODULE_DIR, 'docs');
const MAX_REQUEST_BYTES = 64 * 1024;
const MIME = new Map([
  ['.html', 'text/html; charset=utf-8'],
  ['.css', 'text/css; charset=utf-8'],
  ['.js', 'text/javascript; charset=utf-8'],
  ['.json', 'application/json; charset=utf-8'],
  ['.md', 'text/markdown; charset=utf-8'],
  ['.svg', 'image/svg+xml'],
]);

class HostBoundaryError extends Error {
  constructor(status, code, message) {
    super(message);
    this.name = 'HostBoundaryError';
    this.status = status;
    this.code = code;
  }
}

function sha256File(path) {
  return createHash('sha256').update(readFileSync(path)).digest('hex');
}

function readJson(path) {
  return JSON.parse(readFileSync(path, 'utf8'));
}

function parseArgs(argv) {
  const result = {
    host: '127.0.0.1',
    port: 8787,
    evidenceRoot: process.env.REHEARSAL_EVIDENCE_ROOT ?? null,
    buildManifest: process.env.REHEARSAL_BUILD_MANIFEST ?? null,
  };
  for (let index = 0; index < argv.length; index += 1) {
    const key = argv[index];
    const value = argv[index + 1];
    if (key === '--host') {
      result.host = value;
      index += 1;
    } else if (key === '--port') {
      result.port = Number.parseInt(value, 10);
      index += 1;
    } else if (key === '--evidence') {
      result.evidenceRoot = value;
      index += 1;
    } else if (key === '--build-manifest') {
      result.buildManifest = value;
      index += 1;
    } else {
      throw new Error(`unknown argument ${key}`);
    }
  }
  if (!result.evidenceRoot) {
    result.evidenceRoot = resolve(
      MODULE_DIR,
      '../../qualification/c2sim-public-reference',
    );
  }
  if (!Number.isSafeInteger(result.port) || result.port < 1 || result.port > 65535) {
    throw new Error('port must be an integer between 1 and 65535');
  }
  if (
    result.host !== '127.0.0.1'
    && result.host !== '::1'
    && result.host !== 'localhost'
  ) {
    throw new Error('the rehearsal console may bind only to the loopback interface');
  }
  return result;
}

function buildProvenance({ buildManifestPath = null } = {}) {
  const root = resolve(MODULE_DIR, '..');
  const paths = {
    authorityRuntime: join(root, 'semantic', 'authority_sidecar.mjs'),
    semanticFixtureVerifier: join(root, 'semantic', 'run_semantic_rehearsal.mjs'),
    transportRuntime: join(root, 'test_hosts', 'core', 'fault_machine.mjs'),
    interactiveSession: join(MODULE_DIR, 'session.mjs'),
    evaluatorDisposition: join(MODULE_DIR, 'evaluator_disposition.mjs'),
    httpHost: join(MODULE_DIR, 'server.mjs'),
    scenarioCatalog: join(MODULE_DIR, 'scenarios.mjs'),
  };
  const sources = Object.fromEntries(
    Object.entries(paths).map(([key, path]) => [key, {
      path: path.replace(`${resolve(MODULE_DIR, '../..')}/`, ''),
      sha256: sha256File(path),
    }]),
  );
  let build = null;
  if (buildManifestPath) {
    const path = resolve(buildManifestPath);
    statSync(path);
    build = readJson(path);
  }
  return {
    schema: 'standards-rehearsal-console-provenance/1',
    runtimeMode: 'server_side_direct_import',
    authorityImplementation: 'MessageAuthorityRuntime',
    sourceCommit: build?.sourceCommit ?? process.env.GITHUB_SHA ?? null,
    sources,
    build,
    claimBoundary:
      'Authority decisions and evaluator-disposition integrity execute server-side in the named repository modules. The browser contains presentation and API calls only.',
  };
}

function securityHeaders(contentType = 'application/json; charset=utf-8') {
  return {
    'Content-Type': contentType,
    'Cache-Control': 'no-store',
    'Content-Security-Policy':
      "default-src 'self'; connect-src 'self'; img-src 'self'; style-src 'self'; script-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'",
    'Cross-Origin-Opener-Policy': 'same-origin',
    'Cross-Origin-Resource-Policy': 'same-origin',
    'Referrer-Policy': 'no-referrer',
    'X-Content-Type-Options': 'nosniff',
    'X-Frame-Options': 'DENY',
  };
}

function writeJson(response, status, value) {
  response.writeHead(status, securityHeaders());
  response.end(`${JSON.stringify(value, null, 2)}\n`);
}

function writeError(response, status, code, message) {
  writeJson(response, status, {
    schema: 'standards-rehearsal-console-error/1',
    status: 'refuse',
    error: code,
    message,
  });
}

async function readRequestJson(request) {
  const contentType = String(request.headers['content-type'] ?? '')
    .split(';', 1)[0]
    .trim()
    .toLowerCase();
  if (contentType !== 'application/json') {
    throw new HostBoundaryError(
      415,
      'CONTENT_TYPE_REFUSED',
      'state-changing requests require application/json',
    );
  }
  let size = 0;
  const chunks = [];
  for await (const chunk of request) {
    size += chunk.length;
    if (size > MAX_REQUEST_BYTES) {
      throw new RehearsalSessionError(
        'REQUEST_TOO_LARGE',
        'request exceeds 64 KiB',
      );
    }
    chunks.push(chunk);
  }
  if (chunks.length === 0) return {};
  const value = JSON.parse(Buffer.concat(chunks).toString('utf8'));
  if (value === null || typeof value !== 'object' || Array.isArray(value)) {
    throw new RehearsalSessionError(
      'REQUEST_INVALID',
      'request body must be a JSON object',
    );
  }
  return value;
}

function resolveStaticPath(publicDir, pathname) {
  const requested = pathname === '/' ? '/index.html' : pathname;
  const relative = normalize(requested).replace(/^([/\\])+/, '');
  const path = resolve(publicDir, relative);
  const root = resolve(publicDir);
  if (path !== root && !path.startsWith(`${root}/`)) return null;
  return path;
}

function allowedRequestBoundary(host, port) {
  const authorities = new Set([
    `127.0.0.1:${port}`,
    `localhost:${port}`,
    `[::1]:${port}`,
  ]);
  if (host === 'localhost') authorities.add(`localhost:${port}`);
  if (host === '::1') authorities.add(`[::1]:${port}`);
  const origins = new Set(
    [...authorities].map((authority) => `http://${authority}`),
  );
  return { authorities, origins };
}

function enforceRequestBoundary(request, boundary) {
  const authority = String(request.headers.host ?? '').toLowerCase();
  if (!boundary.authorities.has(authority)) {
    throw new HostBoundaryError(
      421,
      'HOST_HEADER_REFUSED',
      'request Host is outside the loopback rehearsal boundary',
    );
  }
  const origin = request.headers.origin;
  if (origin && !boundary.origins.has(String(origin).toLowerCase())) {
    throw new HostBoundaryError(
      403,
      'ORIGIN_REFUSED',
      'cross-origin access to the rehearsal host is refused',
    );
  }
  const fetchSite = String(request.headers['sec-fetch-site'] ?? '').toLowerCase();
  if (fetchSite && fetchSite !== 'same-origin' && fetchSite !== 'none') {
    throw new HostBoundaryError(
      403,
      'FETCH_SITE_REFUSED',
      'cross-site access to the rehearsal host is refused',
    );
  }
}

export function createRehearsalHttpServer({
  evidenceRoot,
  publicDir = DEFAULT_PUBLIC_DIR,
  docsDir = DEFAULT_DOCS_DIR,
  buildManifestPath = null,
  host = '127.0.0.1',
  port = 8787,
  evaluatorSigner = createLocalEvaluatorSigner(),
}) {
  const fixture = loadRehearsalFixture(evidenceRoot);
  const provenance = buildProvenance({ buildManifestPath });
  const scenarioCatalog = REHEARSAL_SCENARIO_CATALOG;
  const session = new StandardsRehearsalSession({
    fixture,
    provenance,
    scenarioCatalog,
  });
  const dispositionRegistry = new EvaluatorDispositionRegistry(evaluatorSigner);
  const boundary = allowedRequestBoundary(host, port);

  function currentSessionEvidence() {
    const sessionReceipt = session.exportReceipt();
    const sessionVerification = verifySessionReceipt(sessionReceipt, {
      fixture,
      provenance,
      scenarioCatalog,
    });
    return { sessionReceipt, sessionVerification };
  }

  function currentDisposition() {
    const evidence = currentSessionEvidence();
    const receipt = dispositionRegistry.get(evidence.sessionReceipt.receiptId);
    return { ...evidence, receipt };
  }

  const server = createServer(async (request, response) => {
    try {
      enforceRequestBoundary(request, boundary);
      const authority = String(request.headers.host).toLowerCase();
      const url = new URL(request.url ?? '/', `http://${authority}`);
      if (url.pathname === '/api/health' && request.method === 'GET') {
        writeJson(response, 200, {
          schema: 'standards-rehearsal-console-health/1',
          status: 'ready',
          authorityRuntime: provenance.authorityImplementation,
          fixture: fixture.fixtureIdentity,
          scenarioCatalogId: scenarioCatalog.catalogId,
          evaluatorSigner: evaluatorSigner.publicIdentity,
          requestBoundary: {
            loopbackOnly: true,
            allowedAuthorities: [...boundary.authorities].sort(),
          },
        });
        return;
      }
      if (url.pathname === '/api/scenarios' && request.method === 'GET') {
        writeJson(response, 200, publicScenarioCatalog(scenarioCatalog));
        return;
      }
      if (url.pathname === '/api/state' && request.method === 'GET') {
        writeJson(response, 200, session.publicState());
        return;
      }
      if (url.pathname === '/api/provenance' && request.method === 'GET') {
        writeJson(response, 200, provenance);
        return;
      }
      if (url.pathname === '/api/export' && request.method === 'GET') {
        writeJson(response, 200, session.exportReceipt());
        return;
      }
      if (url.pathname === '/api/verify' && request.method === 'GET') {
        writeJson(response, 200, currentSessionEvidence().sessionVerification);
        return;
      }
      if (url.pathname === '/api/disposition' && request.method === 'GET') {
        const { sessionReceipt, receipt } = currentDisposition();
        writeJson(response, 200, {
          schema: 'standards-evaluator-disposition-state/1',
          sessionReceiptId: sessionReceipt.receiptId,
          status: receipt ? 'issued' : 'none',
          receipt,
          signer: evaluatorSigner.publicIdentity,
          claimBoundary:
            'A local disposition is separate from automatic evaluation and does not constitute program acceptance authority.',
        });
        return;
      }
      if (url.pathname === '/api/disposition' && request.method === 'POST') {
        const body = await readRequestJson(request);
        const evidence = currentSessionEvidence();
        const receipt = dispositionRegistry.issue({
          ...evidence,
          evaluator: body.evaluator,
          disposition: body.disposition,
          rationale: body.rationale,
        });
        writeJson(response, 201, receipt);
        return;
      }
      if (url.pathname === '/api/disposition/verify' && request.method === 'GET') {
        const evidence = currentDisposition();
        if (!evidence.receipt) {
          throw new EvaluatorDispositionError(
            'EVALUATOR_DISPOSITION_MISSING',
            'the current session has no evaluator disposition',
          );
        }
        writeJson(
          response,
          200,
          verifyEvaluatorDisposition(evidence.receipt, evidence),
        );
        return;
      }
      if (url.pathname === '/api/acceptance-package' && request.method === 'GET') {
        const evidence = currentDisposition();
        if (!evidence.receipt) {
          throw new EvaluatorDispositionError(
            'EVALUATOR_DISPOSITION_MISSING',
            'the current session has no evaluator disposition',
          );
        }
        const dispositionVerification = verifyEvaluatorDisposition(
          evidence.receipt,
          evidence,
        );
        writeJson(response, 200, createAcceptancePackage({
          sessionReceipt: evidence.sessionReceipt,
          sessionVerification: evidence.sessionVerification,
          dispositionReceipt: evidence.receipt,
          dispositionVerification,
        }));
        return;
      }
      if (url.pathname === '/api/action' && request.method === 'POST') {
        const body = await readRequestJson(request);
        if (typeof body.action !== 'string') {
          throw new RehearsalSessionError(
            'ACTION_INVALID',
            'action must be a string',
          );
        }
        const state = session.apply(body.action, body.input ?? {});
        writeJson(response, 200, state);
        return;
      }
      if (request.method !== 'GET' && request.method !== 'HEAD') {
        writeError(response, 405, 'METHOD_NOT_ALLOWED', 'method not allowed');
        return;
      }
      const documentationRequest = url.pathname === '/docs' || url.pathname.startsWith('/docs/');
      const staticRoot = documentationRequest ? docsDir : publicDir;
      const staticPathname = documentationRequest
        ? (url.pathname === '/docs' || url.pathname === '/docs/'
          ? '/README.md'
          : url.pathname.slice('/docs'.length))
        : url.pathname;
      const path = resolveStaticPath(staticRoot, staticPathname);
      if (!path) {
        writeError(response, 404, 'NOT_FOUND', 'resource not found');
        return;
      }
      let bytes;
      try {
        bytes = readFileSync(path);
      } catch {
        writeError(response, 404, 'NOT_FOUND', 'resource not found');
        return;
      }
      const headers = securityHeaders(
        MIME.get(extname(path)) ?? 'application/octet-stream',
      );
      headers['Cache-Control'] = 'no-cache';
      response.writeHead(200, headers);
      if (request.method === 'HEAD') response.end();
      else response.end(bytes);
    } catch (error) {
      if (error instanceof SyntaxError) {
        writeError(response, 400, 'JSON_INVALID', 'request body is not valid JSON');
      } else if (error instanceof HostBoundaryError) {
        writeError(response, error.status, error.code, error.message);
      } else if (
        error instanceof RehearsalSessionError
        || error instanceof EvaluatorDispositionError
      ) {
        writeError(response, 409, error.code, error.message);
      } else {
        writeError(
          response,
          500,
          'HOST_FAILURE',
          error instanceof Error ? error.message : 'host failure',
        );
      }
    }
  });

  return {
    server,
    session,
    fixture,
    provenance,
    boundary,
    evaluatorSigner,
    dispositionRegistry,
  };
}

export async function startRehearsalServer(options) {
  const {
    server,
    session,
    fixture,
    provenance,
    boundary,
    evaluatorSigner,
    dispositionRegistry,
  } = createRehearsalHttpServer(options);
  await new Promise((resolvePromise, rejectPromise) => {
    server.once('error', rejectPromise);
    server.listen(options.port, options.host, () => {
      server.off('error', rejectPromise);
      resolvePromise();
    });
  });
  return {
    server,
    session,
    fixture,
    provenance,
    boundary,
    evaluatorSigner,
    dispositionRegistry,
  };
}

async function main(argv) {
  const args = parseArgs(argv);
  const started = await startRehearsalServer({
    evidenceRoot: args.evidenceRoot,
    publicDir: DEFAULT_PUBLIC_DIR,
    buildManifestPath: args.buildManifest,
    host: args.host,
    port: args.port,
  });
  const address = `http://${args.host === '::1' ? '[::1]' : args.host}:${args.port}`;
  process.stdout.write(`${JSON.stringify({
    schema: 'standards-rehearsal-console-start/1',
    status: 'ready',
    address,
    fixture: started.fixture.fixtureIdentity,
    provenance: started.provenance,
    evaluatorSigner: started.evaluatorSigner.publicIdentity,
    requestBoundary: {
      loopbackOnly: true,
      allowedAuthorities: [...started.boundary.authorities].sort(),
    },
  }, null, 2)}\n`);
  const close = () => started.server.close(() => process.exit(0));
  process.once('SIGINT', close);
  process.once('SIGTERM', close);
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main(process.argv.slice(2)).catch((error) => {
    process.stderr.write(`${JSON.stringify({
      schema: 'standards-rehearsal-console-start/1',
      status: 'refuse',
      error: error instanceof Error ? error.message : 'startup failed',
    }, null, 2)}\n`);
    process.exitCode = 1;
  });
}

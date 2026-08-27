import { mkdir, readFile, readdir, rm } from 'node:fs/promises';
import { homedir } from 'node:os';
import {
  basename,
  dirname,
  isAbsolute,
  join,
  relative,
  resolve,
  sep,
} from 'node:path';
import { canonicalJson } from '../semantic/authority_sidecar.mjs';
import {
  ALLOWED_OUTPUT_ENTRIES,
  FILES,
  HERE,
  PACK_FAMILY,
  PACK_NAME,
  REPOSITORY_ROOT,
  SOURCE_PATHS,
  digest,
  digestBytes,
  pathState,
  readJson,
  requireCondition,
  writeJson,
} from './fabric_pack_common_v1_1.mjs';
import { bindSourceCommit } from './fabric_pack_checkout_v1_1.mjs';

function isSameOrAncestor(candidate, target) {
  const relation = relative(candidate, target);
  return relation === '' || (!relation.startsWith(`..${sep}`) && relation !== '..' && !isAbsolute(relation));
}

function validateDestinationShape(outDir) {
  const resolved = resolve(outDir);
  requireCondition(PACK_NAME.test(basename(resolved)), 'OUTPUT_DIRECTORY_UNSAFE', 'pack output directory must use the cold-successor-pack-* name');
  const protectedPaths = [
    resolve('/'),
    resolve(process.cwd()),
    resolve(homedir()),
    REPOSITORY_ROOT,
    HERE,
    dirname(HERE),
    resolve(HERE, 'fixtures'),
    resolve(REPOSITORY_ROOT, '.git'),
  ];
  for (const protectedPath of protectedPaths) {
    requireCondition(
      !isSameOrAncestor(resolved, protectedPath),
      'OUTPUT_DIRECTORY_UNSAFE',
      `pack output directory may not equal or contain protected path ${protectedPath}`,
    );
  }
  const repoRelation = relative(REPOSITORY_ROOT, resolved);
  const insideRepository =
    repoRelation !== '' &&
    !repoRelation.startsWith(`..${sep}`) &&
    repoRelation !== '..' &&
    !isAbsolute(repoRelation);
  if (insideRepository) {
    requireCondition(
      repoRelation === 'qualification' || repoRelation.startsWith(`qualification${sep}`),
      'OUTPUT_DIRECTORY_UNSAFE',
      'repository-local packs must be children of qualification/',
    );
  }
  return resolved;
}

export function outputMarker() {
  const body = {
    schema: 'spectra-anchor-node-pack-output-root/1',
    packFamily: PACK_FAMILY,
    sourceRepository: 'BigBirdReturns/ai-execution-audit',
    authority: 'none',
    claimBoundary:
      'Marker for one dedicated generated pack directory. It grants no deletion authority outside this exact directory and is not part of mission or command state.',
  };
  return { ...body, markerId: digest('estatefabricterminalpackroot1', body) };
}

export function validateOutputMarker(marker) {
  requireCondition(
    marker !== null && typeof marker === 'object' && !Array.isArray(marker),
    'OUTPUT_DIRECTORY_NOT_DEDICATED',
    'pack output marker is absent or invalid',
  );
  requireCondition(
    canonicalJson(marker) === canonicalJson(outputMarker()),
    'OUTPUT_DIRECTORY_NOT_DEDICATED',
    'pack output marker belongs to another generator or claim boundary',
  );
  return marker;
}

export async function preparePackOutputDirectory(outDir) {
  const resolved = validateDestinationShape(outDir);
  const parent = dirname(resolved);
  const parentState = await pathState(parent);
  requireCondition(parentState?.isDirectory(), 'OUTPUT_DIRECTORY_UNSAFE', 'pack output parent must already exist and be a directory');
  const currentState = await pathState(resolved);
  if (currentState === null) {
    await mkdir(resolved);
  } else {
    requireCondition(currentState.isDirectory(), 'OUTPUT_DIRECTORY_UNSAFE', 'pack output destination is not a directory');
    const entries = await readdir(resolved);
    if (entries.length > 0) {
      requireCondition(entries.includes(FILES.outputMarker), 'OUTPUT_DIRECTORY_NOT_DEDICATED', 'non-empty pack directory lacks the exact generator marker');
      validateOutputMarker(await readJson(join(resolved, FILES.outputMarker)));
      const unknown = entries.filter((name) => !ALLOWED_OUTPUT_ENTRIES.has(name));
      requireCondition(unknown.length === 0, 'OUTPUT_DIRECTORY_NOT_DEDICATED', `pack directory contains undeclared entries: ${unknown.join(', ')}`);
      for (const name of entries) {
        const target = join(resolved, name);
        const metadata = await pathState(target);
        requireCondition(metadata?.isFile(), 'OUTPUT_DIRECTORY_NOT_DEDICATED', `pack output entry is not a regular file: ${name}`);
        await rm(target, { force: true });
      }
    }
  }
  await writeJson(join(resolved, FILES.outputMarker), outputMarker());
  return resolved;
}

async function sourceEntry(relativePath) {
  const bytes = await readFile(resolve(REPOSITORY_ROOT, relativePath));
  return {
    path: relativePath,
    bytes: bytes.length,
    sha256: digestBytes(bytes),
  };
}

export async function buildSourceClosure(sourceCommit) {
  await bindSourceCommit(sourceCommit);
  const files = [];
  for (const relativePath of SOURCE_PATHS) files.push(await sourceEntry(relativePath));
  const body = {
    schema: 'spectra-anchor-node-estate-fabric-terminal-source-closure/1',
    sourceRepository: 'BigBirdReturns/ai-execution-audit',
    sourceCommit,
    files,
    fileCount: files.length,
    authority: 'none',
    claimBoundary:
      'Exact source-byte closure for the generator and transitive local inputs used to build one synthetic terminal pack. It is provenance only and grants no execution, deletion, mission, or command authority.',
  };
  return { ...body, sourceClosureId: digest('estatefabricterminalsourceclosure1', body) };
}

export async function verifySourceClosure(closure) {
  requireCondition(
    closure !== null && typeof closure === 'object' && !Array.isArray(closure),
    'SOURCE_CLOSURE_INVALID',
    'source closure must be an object',
  );
  const expectedKeys = [
    'schema',
    'sourceClosureId',
    'sourceRepository',
    'sourceCommit',
    'files',
    'fileCount',
    'authority',
    'claimBoundary',
  ];
  requireCondition(
    canonicalJson(Object.keys(closure).sort()) === canonicalJson(expectedKeys.sort()),
    'SOURCE_CLOSURE_INVALID',
    'source closure fields differ',
  );
  requireCondition(
    closure.schema === 'spectra-anchor-node-estate-fabric-terminal-source-closure/1' &&
      closure.sourceRepository === 'BigBirdReturns/ai-execution-audit' &&
      closure.authority === 'none',
    'SOURCE_CLOSURE_INVALID',
    'source closure schema, repository, or authority differs',
  );
  await bindSourceCommit(closure.sourceCommit);
  requireCondition(
    Array.isArray(closure.files) &&
      closure.fileCount === SOURCE_PATHS.length &&
      closure.files.length === SOURCE_PATHS.length &&
      canonicalJson(closure.files.map((row) => row.path)) === canonicalJson(SOURCE_PATHS),
    'SOURCE_CLOSURE_DENOMINATOR_INVALID',
    'source closure file denominator differs',
  );
  for (const [index, row] of closure.files.entries()) {
    requireCondition(
      row !== null &&
        typeof row === 'object' &&
        !Array.isArray(row) &&
        canonicalJson(Object.keys(row).sort()) === canonicalJson(['bytes', 'path', 'sha256']),
      'SOURCE_CLOSURE_ENTRY_INVALID',
      'source closure entry differs',
    );
    const expected = await sourceEntry(SOURCE_PATHS[index]);
    requireCondition(canonicalJson(row) === canonicalJson(expected), 'SOURCE_CLOSURE_MISMATCH', `source bytes differ: ${row.path}`);
  }
  const body = structuredClone(closure);
  delete body.sourceClosureId;
  requireCondition(
    closure.sourceClosureId === digest('estatefabricterminalsourceclosure1', body),
    'SOURCE_CLOSURE_ID_INVALID',
    'source closure identity differs',
  );
  return closure;
}

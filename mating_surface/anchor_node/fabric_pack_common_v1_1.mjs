import { createHash } from 'node:crypto';
import { readFile, stat, writeFile } from 'node:fs/promises';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { canonicalJson } from '../semantic/authority_sidecar.mjs';

export const HERE = dirname(fileURLToPath(import.meta.url));
export const REPOSITORY_ROOT = resolve(HERE, '../..');
export const PROFILE_PATH = resolve(HERE, 'fabric-profile-01.json');
export const REGISTRY_PATH = resolve(HERE, 'fixtures/mp01-invented-seat-registry.json');
export const OBSERVATION_PATH = resolve(HERE, 'fixtures/mp01-observation-package.json');
export const PACK_FAMILY = 'spectra-anchor-node/mp01-estate-fabric-terminal';
export const PACK_NAME = /^cold-successor-pack-[a-z0-9][a-z0-9._-]*$/i;

export const SOURCE_PATHS = Object.freeze([
  'mating_surface/semantic/authority_sidecar.mjs',
  'mating_surface/anchor_node/validate_fabric_profile.mjs',
  'mating_surface/anchor_node/fabric-profile-01.json',
  'mating_surface/anchor_node/fixtures/mp01-invented-seat-registry.json',
  'mating_surface/anchor_node/fixtures/mp01-observation-package.json',
  'mating_surface/anchor_node/vertical_slice.mjs',
  'mating_surface/anchor_node/fabric_runtime.mjs',
  'mating_surface/anchor_node/fabric_execution_support.mjs',
  'mating_surface/anchor_node/fabric_completion.mjs',
  'mating_surface/anchor_node/fabric_terminal_schedule_v1_1.mjs',
  'mating_surface/anchor_node/fabric_terminal_run_v1_1.mjs',
  'mating_surface/anchor_node/fabric_terminal_verify_v1_1.mjs',
  'mating_surface/anchor_node/fabric_terminal_v1_1.mjs',
  'mating_surface/anchor_node/fabric_run.mjs',
  'mating_surface/anchor_node/fabric_execution_v1_1.mjs',
  'mating_surface/anchor_node/fabric_execution.mjs',
  'mating_surface/anchor_node/fabric_pack_common_v1_1.mjs',
  'mating_surface/anchor_node/fabric_pack_checkout_v1_1.mjs',
  'mating_surface/anchor_node/fabric_pack_storage_v1_1.mjs',
  'mating_surface/anchor_node/fabric_pack_build_v1_1.mjs',
  'mating_surface/anchor_node/fabric_pack_verify_v1_1.mjs',
  'mating_surface/anchor_node/fabric_execution_pack_v1_1.mjs',
  'mating_surface/anchor_node/fabric_execution_pack.mjs',
]);

export const FILES = Object.freeze({
  outputMarker: 'PACK-ROOT.json',
  sourceClosure: 'source-closure.json',
  profile: 'fabric-profile.json',
  registry: 'invented-seat-registry.json',
  observations: 'synthetic-observations.json',
  verticalSlice: 'vertical-slice.json',
  routingSlice: 'routing-slice.json',
  routingVerification: 'routing-verification.json',
  fabricRun: 'fabric-run.json',
  terminalVerification: 'terminal-verification.json',
  projection: 'receipt-only-projection.json',
  reviewHtml: 'receipt-only-review.html',
  sixQuestions: 'six-question-answer.json',
});
export const PACK_FILE_NAMES = Object.freeze(Object.values(FILES));
export const ALLOWED_OUTPUT_ENTRIES = new Set([...PACK_FILE_NAMES, 'manifest.json']);

export class FabricExecutionPackError extends Error {
  constructor(code, message) {
    super(message);
    this.name = 'FabricExecutionPackError';
    this.code = code;
  }
}

export function requireCondition(condition, code, message) {
  if (!condition) throw new FabricExecutionPackError(code, message);
}

export function digest(prefix, value) {
  return `${prefix}_${createHash('sha256').update(canonicalJson(value), 'utf8').digest('hex')}`;
}

export function digestBytes(bytes) {
  return createHash('sha256').update(bytes).digest('hex');
}

export function canonicalPretty(value) {
  return `${JSON.stringify(value, null, 2)}\n`;
}

export async function readJson(path) {
  return JSON.parse(await readFile(path, 'utf8'));
}

export async function writeJson(path, value) {
  const content = canonicalPretty(value);
  await writeFile(path, content, 'utf8');
  return Buffer.from(content, 'utf8');
}

export function validateSourceCommitSyntax(sourceCommit) {
  requireCondition(
    /^[0-9a-f]{40}$/.test(sourceCommit),
    'SOURCE_COMMIT_INVALID',
    'source commit must be a full lowercase Git SHA-1',
  );
  return sourceCommit;
}

export async function pathState(path) {
  try {
    return await stat(path);
  } catch (error) {
    if (error?.code === 'ENOENT') return null;
    throw error;
  }
}

export async function manifestEntry(outDir, fileName) {
  const bytes = await readFile(join(outDir, fileName));
  return {
    path: fileName,
    bytes: bytes.length,
    sha256: digestBytes(bytes),
  };
}

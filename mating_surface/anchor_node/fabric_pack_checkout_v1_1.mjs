import { readFile } from 'node:fs/promises';
import { join, resolve } from 'node:path';
import {
  FabricExecutionPackError,
  REPOSITORY_ROOT,
  pathState,
  requireCondition,
  validateSourceCommitSyntax,
} from './fabric_pack_common_v1_1.mjs';

async function resolveGitDirectory(repositoryRoot = REPOSITORY_ROOT) {
  const dotGit = join(repositoryRoot, '.git');
  const metadata = await pathState(dotGit);
  requireCondition(metadata !== null, 'SOURCE_CHECKOUT_UNAVAILABLE', 'repository has no .git metadata');
  if (metadata.isDirectory()) return dotGit;
  requireCondition(metadata.isFile(), 'SOURCE_CHECKOUT_UNAVAILABLE', '.git metadata is neither file nor directory');
  const pointer = (await readFile(dotGit, 'utf8')).trim();
  requireCondition(pointer.startsWith('gitdir:'), 'SOURCE_CHECKOUT_UNAVAILABLE', '.git file does not contain a gitdir pointer');
  return resolve(repositoryRoot, pointer.slice('gitdir:'.length).trim());
}

async function readRef(gitDir, refName) {
  const direct = join(gitDir, ...refName.split('/'));
  try {
    return (await readFile(direct, 'utf8')).trim();
  } catch (error) {
    if (error?.code !== 'ENOENT') throw error;
  }
  let commonDir = gitDir;
  try {
    commonDir = resolve(gitDir, (await readFile(join(gitDir, 'commondir'), 'utf8')).trim());
    try {
      return (await readFile(join(commonDir, ...refName.split('/')), 'utf8')).trim();
    } catch (error) {
      if (error?.code !== 'ENOENT') throw error;
    }
  } catch (error) {
    if (error?.code !== 'ENOENT') throw error;
  }
  for (const root of new Set([gitDir, commonDir])) {
    try {
      const lines = (await readFile(join(root, 'packed-refs'), 'utf8')).split(/\r?\n/);
      const row = lines.find((line) => line.endsWith(` ${refName}`));
      if (row) return row.slice(0, 40);
    } catch (error) {
      if (error?.code !== 'ENOENT') throw error;
    }
  }
  throw new FabricExecutionPackError('SOURCE_CHECKOUT_UNAVAILABLE', `cannot resolve Git ref ${refName}`);
}

export async function readCheckoutCommit(repositoryRoot = REPOSITORY_ROOT) {
  const gitDir = await resolveGitDirectory(repositoryRoot);
  const head = (await readFile(join(gitDir, 'HEAD'), 'utf8')).trim();
  let commit;
  if (/^[0-9a-f]{40}$/.test(head)) commit = head;
  else {
    requireCondition(head.startsWith('ref:'), 'SOURCE_CHECKOUT_UNAVAILABLE', 'HEAD is neither detached commit nor symbolic ref');
    commit = await readRef(gitDir, head.slice('ref:'.length).trim());
  }
  validateSourceCommitSyntax(commit);
  const environmentCommit = process.env.GITHUB_SHA;
  if (environmentCommit !== undefined && /^[0-9a-f]{40}$/.test(environmentCommit)) {
    requireCondition(environmentCommit === commit, 'SOURCE_CHECKOUT_MISMATCH', 'GITHUB_SHA differs from checked-out HEAD');
  }
  return commit;
}

export async function bindSourceCommit(sourceCommit) {
  validateSourceCommitSyntax(sourceCommit);
  const checkoutCommit = await readCheckoutCommit();
  requireCondition(
    sourceCommit === checkoutCommit,
    'SOURCE_COMMIT_MISMATCH',
    `declared source commit ${sourceCommit} differs from checked-out source ${checkoutCommit}`,
  );
  return checkoutCommit;
}

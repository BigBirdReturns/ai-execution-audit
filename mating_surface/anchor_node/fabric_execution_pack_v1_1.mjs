import { resolve } from 'node:path';
import {
  FabricExecutionPackError,
  writeJson,
} from './fabric_pack_common_v1_1.mjs';
export {
  bindSourceCommit,
  readCheckoutCommit,
} from './fabric_pack_checkout_v1_1.mjs';
export {
  buildSourceClosure,
  preparePackOutputDirectory,
  verifySourceClosure,
} from './fabric_pack_storage_v1_1.mjs';
export {
  buildFabricExecutionColdSuccessorPack,
  sixQuestionAnswer,
} from './fabric_pack_build_v1_1.mjs';
export { verifyFabricExecutionColdSuccessorPack } from './fabric_pack_verify_v1_1.mjs';

import { buildFabricExecutionColdSuccessorPack } from './fabric_pack_build_v1_1.mjs';
import { verifyFabricExecutionColdSuccessorPack } from './fabric_pack_verify_v1_1.mjs';

export { FabricExecutionPackError };

export async function runFabricExecutionPackCli(argv) {
  const command = argv[2];
  if (command === 'build') {
    const outDir = resolve(argv[3]);
    const manifest = await buildFabricExecutionColdSuccessorPack(outDir, {
      sourceCommit: argv[4],
    });
    process.stdout.write(`${JSON.stringify({ status: 'PASS', packId: manifest.packId, outDir }, null, 2)}\n`);
    return;
  }
  if (command === 'verify') {
    const outDir = resolve(argv[3]);
    const outputPath = resolve(argv[4]);
    const verification = await verifyFabricExecutionColdSuccessorPack(outDir);
    await writeJson(outputPath, verification);
    process.stdout.write(`${JSON.stringify(verification, null, 2)}\n`);
    return;
  }
  throw new FabricExecutionPackError(
    'COMMAND_INVALID',
    'usage: fabric_execution_pack.mjs build <out-dir> <source-commit> | verify <out-dir> <verification.json>',
  );
}

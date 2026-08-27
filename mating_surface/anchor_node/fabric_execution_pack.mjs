import { fileURLToPath } from 'node:url';
import {
  FabricExecutionPackError,
  runFabricExecutionPackCli,
} from './fabric_execution_pack_v1_1.mjs';

export * from './fabric_execution_pack_v1_1.mjs';

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  runFabricExecutionPackCli(process.argv).catch((error) => {
    process.stderr.write(`${error instanceof FabricExecutionPackError ? error.code : 'UNEXPECTED_ERROR'}: ${error.message}\n`);
    process.exitCode = 1;
  });
}

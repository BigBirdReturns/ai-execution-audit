import { fileURLToPath } from 'node:url';
import {
  FabricExecutionError,
  runFabricExecutionCli,
} from './fabric_execution_v1_1.mjs';

export * from './fabric_execution_v1_1.mjs';

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  runFabricExecutionCli(process.argv).catch((error) => {
    process.stderr.write(`${error instanceof FabricExecutionError ? error.code : 'UNEXPECTED_ERROR'}: ${error.message}\n`);
    process.exitCode = 1;
  });
}

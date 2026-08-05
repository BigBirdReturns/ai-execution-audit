#!/usr/bin/env node
import { createHash } from 'node:crypto';
import { readFile, writeFile } from 'node:fs/promises';
import { spawnSync } from 'node:child_process';
import { pathToFileURL } from 'node:url';

function sha256(bytes) {
  return createHash('sha256').update(bytes).digest('hex');
}

function runXmllint(path) {
  const versionRun = spawnSync('xmllint', ['--version'], {
    encoding: 'utf8',
    maxBuffer: 1024 * 1024,
  });
  if (versionRun.error) throw versionRun.error;
  if (versionRun.status !== 0) {
    throw new Error(`xmllint --version failed: ${(versionRun.stderr || versionRun.stdout).trim()}`);
  }
  const validationRun = spawnSync('xmllint', ['--noout', '--nonet', path], {
    encoding: 'utf8',
    maxBuffer: 4 * 1024 * 1024,
  });
  if (validationRun.error) throw validationRun.error;
  if (validationRun.status !== 0) {
    throw new Error(`xmllint rejected the artifact: ${(validationRun.stderr || validationRun.stdout).trim()}`);
  }
  const versionText = `${versionRun.stdout ?? ''}\n${versionRun.stderr ?? ''}`
    .split(/\r?\n/)
    .map((line) => line.trim())
    .find((line) => /using libxml version/i.test(line))
    ?? 'xmllint version reported without a parseable libxml version';
  return versionText;
}

async function main(argv) {
  if (argv.length !== 2) {
    console.error('usage: xml_wellformedness.mjs <artifact.xml> <receipt.json>');
    return 2;
  }
  const [artifactPath, outputPath] = argv;
  const bytes = await readFile(artifactPath);
  if (bytes.length === 0) throw new Error('artifact is empty');
  const validatorVersion = runXmllint(artifactPath);
  const receipt = {
    schema: 'standards-xml-wellformedness-receipt/1',
    status: 'pass',
    validatorId: 'xmllint',
    validatorVersion,
    artifactSha256: sha256(bytes),
    bytes: bytes.length,
    networkAccess: 'disabled_by_nonet',
    semanticSchemaValidation: false,
    claimBoundary:
      'xmllint --noout --nonet established XML well-formedness only. This receipt does not claim XSD 1.1 semantic validation, standards-authority approval, or operational suitability.',
  };
  await writeFile(outputPath, `${JSON.stringify(receipt, null, 2)}\n`, 'utf8');
  process.stdout.write(`${JSON.stringify({
    status: receipt.status,
    artifactSha256: receipt.artifactSha256,
    bytes: receipt.bytes,
    validatorVersion: receipt.validatorVersion,
    output: outputPath,
  }, null, 2)}\n`);
  return 0;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  process.exitCode = await main(process.argv.slice(2));
}

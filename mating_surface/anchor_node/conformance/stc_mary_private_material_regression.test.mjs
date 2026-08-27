import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';
import {
  StcMaryPhysicalFlightError,
  buildPublicPhysicalFlightDisposition,
  runSyntheticStcMaryPhysicalFlight,
  validatePublicPhysicalFlightDisposition,
} from '../stc_mary_physical_flight.mjs';

const HERE = dirname(fileURLToPath(import.meta.url));
const PROFILE_PATH = resolve(HERE, '../stc-mary-physical-flight-profile-01.json');
const FIXTURE_PATH = resolve(HERE, '../fixtures/stc-mary-physical-flight-synthetic-01.json');

test('public disposition refuses an explicit home-directory path', async () => {
  const [profile, fixture] = await Promise.all([
    readFile(PROFILE_PATH, 'utf8').then(JSON.parse),
    readFile(FIXTURE_PATH, 'utf8').then(JSON.parse),
  ]);
  const disposition = buildPublicPhysicalFlightDisposition(runSyntheticStcMaryPhysicalFlight({ profile, fixture }));
  disposition.claimBoundary = '/home/private/evidence';
  assert.throws(
    () => validatePublicPhysicalFlightDisposition(disposition),
    (error) => error instanceof StcMaryPhysicalFlightError && error.code === 'PUBLIC_PHYSICAL_FLIGHT_DISPOSITION_PRIVATE_MATERIAL',
  );
});

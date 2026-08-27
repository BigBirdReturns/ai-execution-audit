import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

import {
  buildPublicPhysicalFlightDisposition,
  runSyntheticStcMaryPhysicalFlight,
  validatePhysicalFlightObservation,
  validatePublicPhysicalFlightDisposition,
} from '../stc_mary_physical_flight.mjs';
import * as privatePacket from '../stc_mary_private_flight_packet.mjs';

const HERE = dirname(fileURLToPath(import.meta.url));
const PROFILE_PATH = resolve(HERE, '../stc-mary-physical-flight-profile-01.json');
const FIXTURE_PATH = resolve(HERE, '../fixtures/stc-mary-physical-flight-synthetic-01.json');

async function loadInputs() {
  const [profileText, fixtureText] = await Promise.all([
    readFile(PROFILE_PATH, 'utf8'),
    readFile(FIXTURE_PATH, 'utf8'),
  ]);
  return {
    profile: JSON.parse(profileText),
    fixture: JSON.parse(fixtureText),
  };
}

test('private packet imports the public observation validator from the admitted harness', () => {
  assert.equal(typeof validatePhysicalFlightObservation, 'function');
  assert.equal(typeof privatePacket.initializePrivateFlightPacket, 'function');
});

test('public physical-flight disposition builds and validates without recursive replay', async () => {
  const { profile, fixture } = await loadInputs();
  const run = runSyntheticStcMaryPhysicalFlight({ profile, fixture });
  const disposition = buildPublicPhysicalFlightDisposition(run);
  assert.equal(disposition.schema, 'stc-mary-public-physical-flight-disposition/1');
  assert.equal(validatePublicPhysicalFlightDisposition(disposition, run), disposition);
  assert.equal(disposition.physicalEstateQualified, false);
  assert.equal(disposition.authority, 'none');
});

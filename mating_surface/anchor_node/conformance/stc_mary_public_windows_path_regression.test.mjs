import assert from 'node:assert/strict';
import test from 'node:test';
import {
  StcMaryPhysicalFlightError,
  validatePublicPhysicalFlightDisposition,
} from '../stc_mary_physical_flight.mjs';

test('public disposition identifies a Windows drive path as private material before identity replay', () => {
  const disposition = {
    schema: 'stc-mary-public-physical-flight-disposition/1',
    dispositionId: `stcmarypublicphysicalflightdisposition1_${'0'.repeat(64)}`,
    runId: `stcmaryphysicalflightrun1_${'1'.repeat(64)}`,
    profileId: 'spectra-anchor-node/stc-mary-physical-flight/0.1',
    flightMode: 'private_physical_attested',
    stageReceiptIds: Array.from({ length: 16 }, (_, index) => `stcmaryphysicalflightstage1_${String(index + 1).padStart(64, '0')}`),
    stageCount: 16,
    successfulStageCount: 15,
    humanRequiredStageCount: 1,
    evidenceDigestRoot: `stcmarypublicevidenceroot1_${'2'.repeat(64)}`,
    privatePhysicalEvidenceBodyCount: 16,
    publicEvidenceBodyCount: 0,
    privatePhysicalFlightCompleted: true,
    selfAttestationOnly: true,
    physicalEstateQualified: false,
    representativeOperatorQualified: false,
    fieldNetworkQualified: false,
    operationalC2Qualified: false,
    productionLatticeQualified: false,
    authority: 'none',
    claimBoundary: 'C:\\private\\evidence',
  };
  assert.throws(
    () => validatePublicPhysicalFlightDisposition(disposition),
    (error) => error instanceof StcMaryPhysicalFlightError && error.code === 'PUBLIC_PHYSICAL_FLIGHT_DISPOSITION_PRIVATE_MATERIAL',
  );
});

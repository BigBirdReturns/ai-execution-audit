import { describe, expect, it } from 'vitest';
import { runCommandIntelligenceCabinet } from './cabinet';
import {
  projectCommandIntelligenceCabinetFrame,
  verifyCommandIntelligenceCabinetFrame,
} from './cabinetProjection';
import { verifyCommandCandidateBinding } from './candidate';
import { PolybolosClient } from './PolybolosClient';
import { runCommandIntelligenceScenario } from './scenario';
import { ThreatLevel } from './types';

const OBSERVED_AT = '2026-08-01T00:00:00.000Z';

function normalizedFixture() {
  const client = new PolybolosClient({ osirisBaseUrl: 'http://localhost' });
  const result = client.ingestOsirisData({
    commercial_flights: [
      {
        icao24: 'abc123',
        callsign: 'REPLAY ONE',
        lat: 34.1478,
        lng: -118.1445,
        alt: 9144,
        heading: 90,
        speed_knots: 320,
        timestamp: OBSERVED_AT,
      },
    ],
  });
  const entities = client.getEntities();
  client.destroy();
  expect(result).toMatchObject({ accepted: 1, rejected: 0 });
  expect(entities).toHaveLength(1);
  return entities;
}

function runPipeline() {
  const entities = normalizedFixture();
  const run = runCommandIntelligenceCabinet(
    [
      {
        id: 'load-osiris-flight',
        type: 'replace_feed',
        at: OBSERVED_AT,
        provider: 'osiris',
        feed: 'flights-commercial',
        entities,
      },
      {
        id: 'capture-qualified-state',
        type: 'capture',
        at: '2026-08-01T00:00:01.000Z',
        label: 'qualified-state',
      },
    ],
    {
      staleAfterMs: 60_000,
      requireAllEventsApplied: true,
      requireCapture: true,
    },
    {
      producer: 'COMMAND-HOTL-FIXTURE',
      createdAt: '2026-08-01T00:00:01.001Z',
      actionClass: 'candidate-only',
      payload: { trackId: entities[0].id, requestedEffect: 'observe' },
    },
  );
  const snapshot = run.scenario.captures[0].snapshot;
  const frame = projectCommandIntelligenceCabinetFrame(snapshot, {
    minimumThreat: ThreatLevel.NONE,
    limit: 16,
    persistence: 'process_memory',
    persistenceDiagnostics: { durable: false },
  });
  return { run, snapshot, frame };
}

describe('Command Intelligence deterministic replay and provider removal', () => {
  it('reconstructs the same candidate, snapshot, and cabinet state twice', () => {
    const first = runPipeline();
    const second = runPipeline();

    expect(first.run.status).toBe('PASS');
    expect(first.run.candidate).not.toBeNull();
    expect(first.snapshot.snapshotId).toBe(second.snapshot.snapshotId);
    expect(first.run.candidate?.candidateId).toBe(second.run.candidate?.candidateId);
    expect(first.frame.stateId).toBe(second.frame.stateId);
    expect(first.frame.frameId).toBe(second.frame.frameId);
    expect(verifyCommandIntelligenceCabinetFrame(first.frame)).toBe(true);
    expect(
      first.run.candidate &&
        verifyCommandCandidateBinding(first.run.candidate, first.snapshot),
    ).toBe(true);
    expect(first.frame.claimBoundary).toContain('no command');
  });

  it('removes a provider-owned track when the next complete feed omits it', () => {
    const entities = normalizedFixture();
    const run = runCommandIntelligenceScenario(
      [
        {
          id: 'provider-up',
          type: 'replace_feed',
          at: OBSERVED_AT,
          provider: 'osiris',
          feed: 'flights-commercial',
          entities,
        },
        {
          id: 'capture-before-removal',
          type: 'capture',
          at: '2026-08-01T00:00:01.000Z',
          label: 'before-removal',
        },
        {
          id: 'provider-empty-snapshot',
          type: 'replace_feed',
          at: '2026-08-01T00:00:02.000Z',
          provider: 'osiris',
          feed: 'flights-commercial',
          entities: [],
        },
        {
          id: 'capture-after-removal',
          type: 'capture',
          at: '2026-08-01T00:00:03.000Z',
          label: 'after-removal',
        },
      ],
      60_000,
    );

    expect(run.receipts.every((receipt) => receipt.status === 'applied')).toBe(true);
    expect(run.captures[0].snapshot.entityCount).toBe(1);
    expect(run.captures[1].snapshot.entityCount).toBe(0);
    expect(run.captures[1].diffFromPrior?.removed).toEqual(['osiris-air-abc123']);
  });

  it('rejects candidate and cabinet tampering after a valid run', () => {
    const transaction = runPipeline();
    const candidate = transaction.run.candidate!;
    const tamperedCandidate = {
      ...candidate,
      payload: { ...candidate.payload, requestedEffect: 'changed-after-receipt' },
    };
    expect(verifyCommandCandidateBinding(tamperedCandidate, transaction.snapshot)).toBe(false);

    const tamperedFrame = structuredClone(transaction.frame);
    tamperedFrame.entities[0].name = 'CHANGED AFTER FRAME ID';
    expect(verifyCommandIntelligenceCabinetFrame(tamperedFrame)).toBe(false);
  });
});

import { describe, expect, it } from 'vitest';
import { CommandIntelligenceStore } from './entityStore';
import {
  createCommandCandidate,
  verifyCommandCandidateBinding,
  type CommandCandidateReceipt,
} from './candidate';
import { createCommandIntelligenceSnapshot } from './snapshot';

function snapshot() {
  return createCommandIntelligenceSnapshot(
    new CommandIntelligenceStore(),
    '2026-08-01T00:00:00.000Z',
  );
}

describe('Command Intelligence candidate custody', () => {
  it('is deterministic across object key order and bound to one snapshot', () => {
    const observed = snapshot();
    const first = createCommandCandidate(observed, {
      producer: 'command-core-fixture',
      createdAt: '2026-08-01T00:00:01.000Z',
      actionClass: 'priority-candidate',
      payload: { entityId: 'track-1', score: 7, explanation: { b: 2, a: 1 } },
    });
    const second = createCommandCandidate(observed, {
      producer: 'command-core-fixture',
      createdAt: '2026-08-01T00:00:01.000Z',
      actionClass: 'priority-candidate',
      payload: { explanation: { a: 1, b: 2 }, score: 7, entityId: 'track-1' },
    });

    expect(second.candidateId).toBe(first.candidateId);
    expect(verifyCommandCandidateBinding(first, observed)).toBe(true);
  });

  it.each([
    { authorized: true },
    { nested: { commandAuthority: 'self' } },
    { nested: [{ executionApproved: true }] },
    { release_authority: 'candidate' },
  ])('rejects self-authorization fields from any payload depth: %j', (payload) => {
    expect(() => createCommandCandidate(snapshot(), {
      producer: 'fixture',
      createdAt: '2026-08-01T00:00:01.000Z',
      actionClass: 'fixture-candidate',
      payload,
    })).toThrow(/may not carry authority field/);
  });

  it('returns false rather than throwing for a tampered candidate', () => {
    const observed = snapshot();
    const candidate = createCommandCandidate(observed, {
      producer: 'fixture',
      createdAt: '2026-08-01T00:00:01.000Z',
      actionClass: 'fixture-candidate',
      payload: { entityId: 'track-1' },
    });
    const tampered = {
      ...candidate,
      payload: { ...candidate.payload, authorized: true },
    } as CommandCandidateReceipt;

    expect(verifyCommandCandidateBinding(tampered, observed)).toBe(false);
  });

  it('rejects candidates that predate the observation state', () => {
    expect(() => createCommandCandidate(snapshot(), {
      producer: 'fixture',
      createdAt: '2026-07-31T23:59:59.999Z',
      actionClass: 'fixture-candidate',
      payload: {},
    })).toThrow(/cannot predate/);
  });
});

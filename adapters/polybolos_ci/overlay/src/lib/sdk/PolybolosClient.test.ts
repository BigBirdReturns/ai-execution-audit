import { describe, expect, it } from 'vitest';
import {
  PolybolosClient,
  translateFlights,
  translateFires,
} from './PolybolosClient';

function client() {
  return new PolybolosClient({ osirisBaseUrl: '' });
}

describe('Command Intelligence feed normalization', () => {
  it('uses deterministic fallback identities when a feed omits an id', () => {
    const input = [{ lat: 0, lng: 0, model: 'fixture', registration: 'N/A' }];
    const first = translateFlights(input, 'commercial');
    const second = translateFlights(input, 'commercial');
    expect(first).toHaveLength(1);
    expect(second).toHaveLength(1);
    expect(first[0].id).toBe(second[0].id);
    expect(first[0].id).not.toContain('undefined');
  });

  it('uses source observations rather than array position for fire identity', () => {
    const a = translateFires([
      { lat: 34.1, lng: -118.2, acq_date: '2026-07-31', acq_time: '1200' },
      { lat: 35.1, lng: -117.2, acq_date: '2026-07-31', acq_time: '1201' },
    ]);
    const b = translateFires([
      { lat: 35.1, lng: -117.2, acq_date: '2026-07-31', acq_time: '1201' },
      { lat: 34.1, lng: -118.2, acq_date: '2026-07-31', acq_time: '1200' },
    ]);
    expect(new Set(a.map((entity) => entity.id))).toEqual(
      new Set(b.map((entity) => entity.id)),
    );
  });

  it('refuses invalid coordinates before they enter the COP', () => {
    expect(
      translateFlights(
        [
          { icao24: 'good', lat: 34, lng: -118 },
          { icao24: 'bad-lat', lat: 134, lng: -118 },
          { icao24: 'nan', lat: Number.NaN, lng: -118 },
        ],
        'commercial',
      ).map((entity) => entity.source.originalId),
    ).toEqual(['good']);
  });

  it('replaces feed snapshots instead of retaining vanished tracks forever', () => {
    const sdk = client();
    sdk.ingestOsirisData({
      commercial_flights: [
        { icao24: 'a', lat: 34, lng: -118 },
        { icao24: 'b', lat: 35, lng: -117 },
      ],
    });
    expect(sdk.getEntities()).toHaveLength(2);

    sdk.ingestOsirisData({
      commercial_flights: [{ icao24: 'b', lat: 35, lng: -117 }],
    });
    expect(sdk.getEntities().map((entity) => entity.source.originalId)).toEqual(['b']);
  });

  it('reports the actual number of populated feeds', () => {
    const sdk = client();
    sdk.ingestOsirisData({
      commercial_flights: [{ icao24: 'a', lat: 34, lng: -118 }],
      earthquakes: [{ id: 'eq-1', lat: 33, lng: -117, magnitude: 4.1 }],
    });
    expect(sdk.getStatus().feedCount).toBe(2);
  });

  it('does not claim a connected transport before one opens', () => {
    const sdk = client();
    sdk.ingestOsirisData({
      commercial_flights: [{ icao24: 'a', lat: 34, lng: -118 }],
    });
    expect(sdk.getStatus().connected).toBe(false);
  });

  it('emits only valid coordinates into GeoJSON', () => {
    const sdk = client();
    sdk.ingestOsirisData({
      cameras: [
        { id: 'zero', lat: 0, lng: 0 },
        { id: 'bad', lat: 95, lng: 0 },
      ],
    });
    const geojson = sdk.toGeoJSON();
    expect(geojson.features).toHaveLength(1);
    expect(geojson.features[0].geometry).toEqual({
      type: 'Point',
      coordinates: [0, 0],
    });
  });
});

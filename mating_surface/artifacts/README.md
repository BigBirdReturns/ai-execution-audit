# Standard artifact custody

The standards registry names authorities and standard families. This directory admits the exact machine-readable artifacts used by a venue instance.

An artifact is not trusted because its file name resembles a standard. Admission binds the bytes to a source repository, immutable commit, Git blob identity, content digest, format identity, validator receipt, license, and use boundary.

## Artifact classes

- `official_authority_artifact`: obtained directly from the standards authority and eligible for the uses authorized by the venue.
- `official_authority_mirror`: an exact mirror whose authority provenance and digest are independently established.
- `program_authorized_controlled`: a controlled artifact supplied or authorized by the sponsoring program.
- `reference_implementation_snapshot`: a public implementation or project snapshot useful for simulation, tooling, and conformance development but not automatically authoritative.
- `synthetic_fixture`: a generated test object that cannot enter an operational port.

Reference and synthetic artifacts are mechanically confined to test or rehearsal use. Renaming one, copying it into this repository, or adding an impressive provenance paragraph cannot promote it.

## First public artifact

`public-reference/c2sim-v1.0.1.json` pins the OpenC2SIM composite XSD at one immutable upstream commit and Git blob. The source is valuable public C2SIM implementation material. The manifest deliberately classifies it as a `reference_implementation_snapshot`, rather than claiming it is the official SISO distribution artifact.

The qualification lane proves:

- exact upstream commit and Git blob identity;
- content SHA-256;
- XML well-formedness with network access disabled;
- expected XSD root and C2SIM target namespace;
- no `DOCTYPE` or external-entity declaration;
- rehearsal-only admission on the simulation port;
- refusal of operational use;
- exact artifact and validator closure for later opaque message receipts.

The current XML receipt does not claim XSD 1.1 semantic validation. A program that requires formal schema validation must load the exact authorized artifact and approved validator profile.

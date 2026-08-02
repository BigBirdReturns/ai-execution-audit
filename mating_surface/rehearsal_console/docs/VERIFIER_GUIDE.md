# Verifier Guide

## 1. Verification objective

Establish that the displayed and exported result is bound to the exact source, standard artifact, semantic conversation, action ledger, authority receipts, transport receipts, and final state identity claimed by the station.

## 2. Evidence chain

```text
source commit
  -> authority runtime digest
  -> admitted C2SIM reference artifact
  -> XSD 1.1 structural catalog
  -> source-controlled scenario catalog and definition
  -> four schema-valid message receipts
  -> payload-opaque transport packets
  -> authority decisions and tickets
  -> deliveries and replay refusal
  -> partition closure and return classification
  -> interactive session receipt
  -> detached replay verification
```

## 3. Browser checks

Open **Evidence** and confirm:

- authority implementation name and SHA-256;
- scenario catalog, scenario definition, and evaluation identities;
- semantic conversation identity;
- artifact admission identity and revision;
- event order and reason codes;
- current state identity;
- absence of C2SIM XML payloads from browser state.

## 4. Session export

The exported receipt includes:

- fixture identity;
- scenario catalog ID, scenario ID, and scenario definition ID;
- initial configuration;
- recorded test-conductor actions and inputs;
- state-core, evaluation, and final state IDs;
- authority decision IDs;
- receiver receipt IDs;
- reconciliation or return-notice identity;
- transport run identity;
- source provenance.

The receipt does not contain the standard XML payloads or private keys.

## 5. Detached replay

Select **Verify current session** or submit the exported receipt to the local verification function. A passing result means that replaying the same scenario definition, actions, and initial configuration through the same source identities reproduces the same evaluation ID, receipt ID, and final state ID.

A replay failure must be treated as an evidence-custody failure even when the visible state appears plausible.

## 6. Negative checks

Verify refusal of:

- changed source, scenario catalog, scenario definition, or artifact digest;
- altered action order or action input;
- changed initial configuration;
- duplicate message acceptance;
- unrecognized Host header;
- foreign Origin;
- cross-site request context;
- non-JSON state-changing request;
- continued action after the session closes;
- invented reconciliation when returning authority is absent.

## 7. Claim boundary

Detached replay proves deterministic identity closure for the retained local rehearsal. It does not prove operational suitability, tactical correctness, field-network performance, operator effectiveness, or weapons safety.

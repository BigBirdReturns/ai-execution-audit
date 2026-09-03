# Issue #105 Current Rejoin Preparation 02

This private packet is the cloud-only successor to the stale one-runner and range-custody handoffs. It binds repository `main` `3c11dbca48ae777137675bb9bf485f0c42daf7a4`, Package 03 release `axmbrowserphysicalflightrelease_48bded1a98f703e2a044765bcd786b82eb9c097c26a43bc420945f97f074e566`, and prepared transaction `axmbrowserphysicalrun_b90f76feb0a7324dac7fbd8780a7079a8123c85cdf4a06233467e675803722dc` into identity join `axmissue105currentidentityjoin_b937b9a84ceda29665ed35b086b977b71009f57f8565260deb9d3f996b9e6a0e`.

First run `Verify-Packet.cmd`. The verifier must return `PASS`. No host contact, range custody, browser operation, supplier contact, or inference occurred while this packet was built.

When local preparation is separately authorized, run `Run-Prepare-Both-Hosts.cmd` on W01. It prepares the current Package 03 controller and seat-02 on W01, transfers only the exact current carrier and preparer to the already pinned `OCTO-L01` alias, prepares seat-01 into a persistent L01 root outside the disposable SSH transport stage, retrieves the L01 receipt, and runs the receipt join. Both host receipts require post-preparation verification of the persistent material. It does not download model ranges or launch either browser.

The maximum permitted terminal is `READY_FOR_EXACT_RANGE_CUSTODY`. The four required returns are:

```text
ISSUE105-CURRENT-IDENTITY-JOIN.json
ISSUE105-W01-PREPARATION-RECEIPT.json
ISSUE105-L01-PREPARATION-RECEIPT.json
ISSUE105-TWO-SEAT-PREPARATION-JOIN.json
```

Distinct opaque host references are required for the preparation join. They do not by themselves prove physical uniqueness, and the join preserves `physicalUniquenessProved: false`. Every object in the embedded `SUPERSESSION.json` and every ref in `DISPOSABLE-REF-RETIREMENT.json` remains stale and must not be resumed.

## One-runner two-host preparation checkpoint

The new private object is a host-preparation package, not a route result. It gives W01 one verified entrypoint that prepares its controller and seat-02 roles, transfers the exact Bootstrap 03 and exact host preparer through the already-pinned `OCTO-L01` OpenSSH alias, prepares L01 seat-01, retrieves the L01 receipt, requires distinct host references, and independently joins the two receipts. Its only success terminal is `READY_FOR_EXACT_RANGE_CUSTODY`.

```text
package:
AXM-Issue-105-One-Runner-Two-Host-Prepare-01.zip

package identity:
axmissue105onerunnertwohostpackage_5e1e0c5b97c266acf264e41622d00c2c6212c7672738c8d3a096f7c93c5d978a

state:
READY_FOR_ONE_RUNNER_TWO_HOST_PREPARATION

archive bytes:
33069857

archive SHA-256:
792a2ae6bbace4d13da00fd9cb3dbc33e6a6381acf166183d195c0c24ef6b5cd

archive members:
19

checksum entries:
18
```

The five controlling components are byte-bound: Bootstrap 03 at 33,026,569 bytes and `sha256:435a44defad35aa3abd7b67c281f543aae7225efc0351bae05f5d7ae378b98c0`; the one-runner wrapper at 16,481 bytes and `sha256:2458428dcb92a11bdebad6e785aa768958b99fab087d7236efc0997057f3ee21`; the strict W01-to-L01 preparer at 17,737 bytes and `sha256:a9937cb50426a7308a0c3c37c4119cff206b228c58ab0a75a74c4e0b40f4eb80`; the role-specific final-host preparer at 10,360 bytes and `sha256:6f7001104498a95183df36cdd26ed71b4739f929a821fa83208fdfdec9592fd9`; and the independent receipt join at 7,790 bytes and `sha256:47ca14974ea4299fd28211e30ba4f52926de14af2fff77fbd9435c9762d31ef2`.

The direct wrapper was reconstructed and exercised on hosted Windows in run `33671102301`; its hosted job passed and its self-hosted job remains queued. The exact wrapper export passed in run `33671280297`. The exact cross-host preparer export passed in run `33671482903`. The predecessor self-hosted preparation run `33668124010` was cancelled by the shared concurrency law, leaving one current self-hosted transaction. The complete private package was uploaded to Drive and fetched back at the same 33,069,857-byte length and SHA-256.

Independent verification bound all 18 checksum entries, all five controlling components, the 22-member Bootstrap denominator, the nested Bootstrap verifier, the exact success and intermediate terminals, strict host-key checking, batch authentication, disabled forwarding, and the zero-authority boundary. Both Python members compiled. Every text-bearing member decoded as UTF-8 with no carriage returns and no forbidden control bytes. Independent extraction and deterministic repacking reproduced the canonical archive byte-for-byte.

The package also carries separate W01-only and L01-only fallback entrypoints. Those do not weaken the join law. A combined success still requires `W01_CONTROLLER_AND_SEAT02_PREPARED`, `L01_SEAT01_PREPARED`, `W01_AND_L01_HOSTS_PREPARED`, and then `READY_FOR_EXACT_RANGE_CUSTODY` with distinct host references.

```text
W01 final-host receipt accepted:             false
L01 final-host receipt accepted:             false
host references proven distinct:             false
browser seats physically operated:          0 / 2
browser launched:                           false
supplier endpoint contacted:                false
model downloaded by this transaction:       false
seat range shards downloaded:               0 / 2
peer connection formed:                     false
inference executed:                         false
physical-member evidence accepted:           0 / 2
raw captures accepted:                       0 / 2
named-human confirmation supplied:           false
route terminal produced:                    false
actual supplier qualified:                   false
physical Estate qualified:                   false
mission authority:                          none
command authority:                          none
```

The remaining control question is whether W01 can execute the single verified entrypoint against the existing strict-key `OCTO-L01` lane and return two exact, distinct-host preparation receipts, allowing the transaction to advance to `READY_FOR_EXACT_RANGE_CUSTODY` without treating host preparation as evidence of model retrieval or route execution.

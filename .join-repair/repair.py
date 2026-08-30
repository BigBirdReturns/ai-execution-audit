from __future__ import annotations
import copy, hashlib, json, re
from pathlib import Path

A=Path('mating_surface/anchor_node')
PROFILE=A/'axm-head-physical-long-haul-join-profile-01.json'
FIX=A/'fixtures/axm-head-physical-long-haul-join-cases-01.json'
VER=A/'verify_axm_head_physical_long_haul_join.py'
TOOL=A/'axm_head_physical_long_haul_join.py'
TEST=A/'conformance/test_axm_head_physical_long_haul_join.py'
DOC=A/'AXM-HEAD-PHYSICAL-LONG-HAUL-JOIN-01.md'
WF=Path('.github/workflows/axm-head-physical-long-haul-join-01.yml')
ACTIVE={
 'repository':'BigBirdReturns/ai-execution-audit',
 'commit':'dd486472a8c610a20ee062dd6746c86fe8ede4b4',
 'tree':'d17a6d9554ee60aa692985af4e6771a4ee00ef85',
 'archiveSha256':'ff415d5b6f0033a1bdb9ae3b5f49828766e61ce668a8213ef3ad176908bd30dc',
 'predecessorCommits':[
  '772ce582e1b19b7a2060c50be8ebf40c1f8723b2',
  'ccc6f1bb817614d0948900499c80f4f91e8bade0',
  '1047b90d2c2077cff297b9d5e24e333fe7dcf8cc',
  'a99c1c76daf383edd31ada2e3a8f8bf5c57a7888',
 ],
 'status':'admitted_bounded_single_action_operator',
}
def cj(v): return (json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)+'\n').encode()
def sha(b): return hashlib.sha256(b).hexdigest()
def cid(prefix, body): return prefix+'_'+sha(cj(body))
def body_without(obj,key): return {k:v for k,v in obj.items() if k!=key}
def rep1(s,o,n,label):
    c=s.count(o)
    if c!=1: raise SystemExit(f'{label}: expected 1 anchor, got {c}')
    return s.replace(o,n,1)

profile=json.loads(PROFILE.read_text(encoding='utf-8'))
profile['sourceBindings']['admittedConductor']=copy.deepcopy(ACTIVE)
PROFILE.write_text(json.dumps(profile,sort_keys=True,indent=2,ensure_ascii=False)+'\n',encoding='utf-8',newline='\n')
profile_sha=sha(cj(profile))

catalog=json.loads(FIX.read_text(encoding='utf-8'))
for case in catalog['cases']:
    sb=case['input']['sourceBinding']
    sb['publicSources']['admittedConductor']=copy.deepcopy(ACTIVE)
    if sb.get('preflightDisposition') is not None:
        pf=sb['preflightDisposition']
        pf['receiptId']=cid('axmheadpreflightdisposition1', body_without(pf,'receiptId'))
    sb['sourceBindingId']=cid('axmheadphysicalflightsourcebinding2', body_without(sb,'sourceBindingId'))
FIX.write_text(json.dumps(catalog,sort_keys=True,indent=2,ensure_ascii=False)+'\n',encoding='utf-8',newline='\n')
fixture_sha=sha(cj(catalog))

v=VER.read_text(encoding='utf-8')
v=rep1(v,'PROFILE_CANONICAL_SHA256 = "4ea4fef34168eafa8e7e64fdd5d4b05725240b7cc12bca5fd068d3cc25cd3bfc"',f'PROFILE_CANONICAL_SHA256 = "{profile_sha}"','profile digest')
v=rep1(v,'FIXTURE_CATALOG_CANONICAL_SHA256 = "34cd78ccc87b2e566c84bf3ee3c57f0e134608d0f3fa627725324a1b404e93fc"',f'FIXTURE_CATALOG_CANONICAL_SHA256 = "{fixture_sha}"','fixture digest')
old='''    "admittedConductor": {
        "repository": "BigBirdReturns/ai-execution-audit",
        "commit": "772ce582e1b19b7a2060c50be8ebf40c1f8723b2",
        "tree": "3f708c52782784e687cf1f0b68fd7d37a507ef4c",
        "archiveSha256": "88ebac8db2e1107faf3a9aa6f0f543149c308212e2d113da6b060d4047d2f241",
        "status": "admitted_operator_layer",
    },'''
new='''    "admittedConductor": {
        "repository": "BigBirdReturns/ai-execution-audit",
        "commit": "dd486472a8c610a20ee062dd6746c86fe8ede4b4",
        "tree": "d17a6d9554ee60aa692985af4e6771a4ee00ef85",
        "archiveSha256": "ff415d5b6f0033a1bdb9ae3b5f49828766e61ce668a8213ef3ad176908bd30dc",
        "predecessorCommits": [
            "772ce582e1b19b7a2060c50be8ebf40c1f8723b2",
            "ccc6f1bb817614d0948900499c80f4f91e8bade0",
            "1047b90d2c2077cff297b9d5e24e333fe7dcf8cc",
            "a99c1c76daf383edd31ada2e3a8f8bf5c57a7888",
        ],
        "status": "admitted_bounded_single_action_operator",
    },'''
v=rep1(v,old,new,'conductor expected block')
v=rep1(v,
'''        "conductorCommit": EXPECTED_PUBLIC_SOURCES["admittedConductor"]["commit"],
        "conductorTree": EXPECTED_PUBLIC_SOURCES["admittedConductor"]["tree"],''',
'''        "conductorCommit": EXPECTED_PUBLIC_SOURCES["admittedConductor"]["commit"],
        "conductorTree": EXPECTED_PUBLIC_SOURCES["admittedConductor"]["tree"],
        "conductorArchiveSha256": EXPECTED_PUBLIC_SOURCES["admittedConductor"]["archiveSha256"],
        "conductorPredecessorCommits": EXPECTED_PUBLIC_SOURCES["admittedConductor"]["predecessorCommits"],''','source summary')
VER.write_text(v,encoding='utf-8',newline='\n')
ver_sha=sha(VER.read_bytes())

t=TOOL.read_text(encoding='utf-8')
t=rep1(t,'STANDALONE_VERIFIER_SHA256 = "5964493f9d037ac0ce8b3660c4a590bdd6f795224a39b151c9314ba6398f97a2"',f'STANDALONE_VERIFIER_SHA256 = "{ver_sha}"','tool verifier digest')
TOOL.write_text(t,encoding='utf-8',newline='\n')

tt=TEST.read_text(encoding='utf-8')
tt=rep1(tt,'self.assertEqual(sources["admittedConductor"]["commit"], "772ce582e1b19b7a2060c50be8ebf40c1f8723b2")','self.assertEqual(sources["admittedConductor"]["commit"], "dd486472a8c610a20ee062dd6746c86fe8ede4b4")','active assertion')
anchor='''    def test_fixture_catalog_is_closed_and_synthetic_only(self) -> None:\n'''
newtests='''    def test_final_conductor_source_and_lineage_are_exact(self) -> None:
        conductor = self.profile["sourceBindings"]["admittedConductor"]
        self.assertEqual(conductor["commit"], "dd486472a8c610a20ee062dd6746c86fe8ede4b4")
        self.assertEqual(conductor["tree"], "d17a6d9554ee60aa692985af4e6771a4ee00ef85")
        self.assertEqual(conductor["archiveSha256"], "ff415d5b6f0033a1bdb9ae3b5f49828766e61ce668a8213ef3ad176908bd30dc")
        self.assertEqual(conductor["predecessorCommits"], [
            "772ce582e1b19b7a2060c50be8ebf40c1f8723b2",
            "ccc6f1bb817614d0948900499c80f4f91e8bade0",
            "1047b90d2c2077cff297b9d5e24e333fe7dcf8cc",
            "a99c1c76daf383edd31ada2e3a8f8bf5c57a7888",
        ])

    def test_predecessor_conductor_cannot_be_substituted_as_active(self) -> None:
        for predecessor in self.profile["sourceBindings"]["admittedConductor"]["predecessorCommits"]:
            with self.subTest(predecessor=predecessor):
                altered = copy.deepcopy(self.profile)
                altered["sourceBindings"]["admittedConductor"]["commit"] = predecessor
                with self.assertRaises(mod.JoinError) as context:
                    mod.validate_profile_value(altered)
                self.assertEqual(context.exception.code, "PROFILE_SOURCE_BINDINGS_INVALID")

    def test_input_active_conductor_tree_and_archive_drift_are_refused(self) -> None:
        for key, replacement in (("tree", "0" * 40), ("archiveSha256", "0" * 64)):
            with self.subTest(key=key):
                value = self.case("prepared-exact-public-sources-no-private-flight")
                value["sourceBinding"]["publicSources"]["admittedConductor"][key] = replacement
                self.refresh_source(value)
                with self.assertRaises(mod.JoinError) as context:
                    mod.validate_input_value(value)
                self.assertEqual(context.exception.code, "SOURCE_BINDING_COORDINATES_INVALID")

    def test_input_mixed_conductor_source_cannot_rebind_campaign(self) -> None:
        value = self.complete()
        old_source_id = value["sourceBinding"]["sourceBindingId"]
        value["sourceBinding"]["publicSources"]["admittedConductor"]["commit"] = (
            value["sourceBinding"]["publicSources"]["admittedConductor"]["predecessorCommits"][-1]
        )
        self.refresh_source(value)
        self.assertNotEqual(value["sourceBinding"]["sourceBindingId"], old_source_id)
        with self.assertRaises(mod.JoinError) as context:
            mod.validate_input_value(value)
        self.assertEqual(context.exception.code, "SOURCE_BINDING_COORDINATES_INVALID")

    def test_conductor_predecessor_lineage_drift_is_refused(self) -> None:
        mutations = (
            lambda rows: rows[:-1],
            lambda rows: list(reversed(rows)),
            lambda rows: rows + [rows[-1]],
            lambda rows: ["0" * 40, *rows[1:]],
        )
        for mutate in mutations:
            altered = copy.deepcopy(self.profile)
            rows = altered["sourceBindings"]["admittedConductor"]["predecessorCommits"]
            altered["sourceBindings"]["admittedConductor"]["predecessorCommits"] = mutate(rows)
            with self.assertRaises(mod.JoinError) as context:
                mod.validate_profile_value(altered)
            self.assertEqual(context.exception.code, "PROFILE_SOURCE_BINDINGS_INVALID")

'''+anchor
tt=rep1(tt,anchor,newtests,'test insertion')
TEST.write_text(tt,encoding='utf-8',newline='\n')

w=WF.read_text(encoding='utf-8')
w=rep1(w,'Ran 76 tests','Ran 81 tests','workflow count')
WF.write_text(w,encoding='utf-8',newline='\n')

d=DOC.read_text(encoding='utf-8')
pat=re.compile(r'## Exact admitted source graph\n\n.*?\n## Closed ten-object denominator\n',re.S)
replacement='''## Exact admitted source graph

The profile freezes five public roles. The active conductor is one exact admitted successor with an exact predecessor chain:

```text
AXM removable-volume supplier
  commit b452bb32e26249deab90db124f157bc62ad0850d
  tree   c557bddc17ad62f6ad36bac5a6ef57338429a951

STC MARY active bounded single-action conductor
  commit dd486472a8c610a20ee062dd6746c86fe8ede4b4
  tree   d17a6d9554ee60aa692985af4e6771a4ee00ef85
  archive sha256 ff415d5b6f0033a1bdb9ae3b5f49828766e61ce668a8213ef3ad176908bd30dc
  predecessors
    772ce582e1b19b7a2060c50be8ebf40c1f8723b2
    ccc6f1bb817614d0948900499c80f4f91e8bade0
    1047b90d2c2077cff297b9d5e24e333fe7dcf8cc
    a99c1c76daf383edd31ada2e3a8f8bf5c57a7888

frozen physical-flight execution floor
  commit d31e59f5fd30e57b1917c00832b189ee2ea3e12f
  tree   2a6a155e9615eb847781f87566bac32d4c9dc126

admitted preflight review-card contract
  commit ec61bc3488cb5ae06ed9db2862a9f6910d310a79
  tree   d2daba1d32a8de744b8b90f6cd42f7c4bff4fa67

private-flight ledger
  issue #37
```

The join independently reconstructs this source law. A predecessor substituted as active, a mixed campaign source, an altered active tree or archive, or any missing, reordered, duplicated, or rewritten predecessor terminates `HOLD`. The frozen execution floor remains separate and unchanged.

## Closed ten-object denominator
'''
d,count=pat.subn(replacement,d,count=1)
if count!=1: raise SystemExit(f'doc source section: {count}')
d=d.replace('76 methods','81 methods').replace('76 / 76','81 / 81')
DOC.write_text(d,encoding='utf-8',newline='\n')

print(json.dumps({'profile':profile_sha,'fixture':fixture_sha,'verifier':ver_sha},indent=2))

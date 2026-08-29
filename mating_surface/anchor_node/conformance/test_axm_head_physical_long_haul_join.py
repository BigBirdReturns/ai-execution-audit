from __future__ import annotations
import copy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = ROOT / "axm_head_physical_long_haul_join.py"
PROFILE = ROOT / "axm-head-physical-long-haul-join-profile-01.json"
FIXTURES = ROOT / "fixtures" / "axm-head-physical-long-haul-join-cases-01.json"
VERIFIER = ROOT / "verify_axm_head_physical_long_haul_join.py"
spec = importlib.util.spec_from_file_location("join_tool", TOOL_PATH); tool = importlib.util.module_from_spec(spec); assert spec and spec.loader; spec.loader.exec_module(tool)

def load(path): return json.loads(path.read_text(encoding="utf-8"))
def private_input():
    value = copy.deepcopy(next(row["input"] for row in load(FIXTURES)["cases"] if row["caseId"] == "synthetic-complete-private-shape"))
    for component in (value["route"], value["continuity"], value["twoCell"], value["successor"], value["privateDisposition"]): component["evidenceTier"] = "private_local_attested"
    value["privateDisposition"]["authorization"]["evidenceTier"] = "private_local_attested"
    for row in value["privateDisposition"]["stageReceipts"]: row["evidenceTier"] = "private_local_attested"
    return value

class JoinV2Tests(unittest.TestCase):
    def setUp(self): self.profile = tool.validate_exact_profile(PROFILE); self.catalog = tool.validate_exact_catalog(self.profile, FIXTURES)
    def build(self, value=None):
        td = tempfile.TemporaryDirectory(); out = Path(td.name) / "carrier"; tool.write_carrier(self.profile, self.catalog, value or private_input(), out); return td, out
    def direct(self, carrier): return subprocess.run([sys.executable, str(VERIFIER), str(carrier)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    def resign_manifest(self, carrier):
        m = load(carrier / "MANIFEST.json"); rows=[]
        for rel in sorted(tool.EXPECTED_MEMBER_PATHS):
            data=(carrier/rel).read_bytes(); rows.append({"path":rel,"size":len(data),"sha256":tool.sha256_bytes(data)})
        m["files"]=rows; m["carrierId"]=tool.content_id("axmheadphysicallonghaulcarrier2", {k:v for k,v in m.items() if k!="carrierId"}); (carrier/"MANIFEST.json").write_bytes(tool.canonical_json_bytes(m))
    def mutate_object(self, carrier, rel, mutate, id_key, prefix):
        value=load(carrier/rel); mutate(value); value[id_key]=tool.content_id(prefix,{k:v for k,v in value.items() if k!=id_key}); (carrier/rel).write_bytes(tool.canonical_json_bytes(value)); self.resign_manifest(carrier)
    def assert_refused(self, carrier, code=None):
        r=self.direct(carrier); self.assertEqual(r.returncode,2); body=json.loads(r.stdout); self.assertEqual(body["status"],"REFUSED");
        if code: self.assertEqual(body["errorCode"],code)

    def test_profile_valid(self): self.assertEqual(self.profile["profileId"], tool.PROFILE_ID)
    def test_fixture_catalog_valid(self): self.assertEqual(len(self.catalog["cases"]),4)
    def test_fixture_catalog_contains_no_private_tier(self): self.assertFalse(any(r["input"]["privateDisposition"]["evidenceTier"]=="private_local_attested" for r in self.catalog["cases"]))
    def test_prepared_terminal(self): self.assertEqual(tool.build_objects(self.profile, self.catalog["cases"][0]["input"])["join"]["terminal"],"PREPARED_NOT_ARMED")
    def test_synthetic_complete_holds(self): self.assertEqual(tool.build_objects(self.profile, self.catalog["cases"][1]["input"])["join"]["terminal"],"HOLD")
    def test_private_complete_self_attests(self): self.assertEqual(tool.build_objects(self.profile,private_input())["join"]["terminal"],"PRIVATE_SELF_ATTESTED")
    def test_supplier_commit_drift_refuses(self):
        v=private_input(); v["sourceBinding"]["publicSources"]["axmRemovableVolumeSupplier"]["commit"]="0"*40
        with self.assertRaises(tool.JoinError): tool.build_objects(self.profile,v)
    def test_supplier_tree_drift_refuses(self):
        v=private_input(); v["sourceBinding"]["publicSources"]["preflightReviewCard"]["tree"]="0"*40
        with self.assertRaises(tool.JoinError): tool.build_objects(self.profile,v)
    def test_preflight_terminal_substitution_refuses(self):
        v=private_input(); v["sourceBinding"]["preflight"]["terminal"]="PREPARED_NOT_ARMED"
        with self.assertRaises(tool.JoinError): tool.build_objects(self.profile,v)
    def test_preflight_authorized_action_refuses(self):
        v=private_input(); v["sourceBinding"]["preflight"]["authorizedActionCount"]=1
        with self.assertRaises(tool.JoinError): tool.build_objects(self.profile,v)
    def test_missing_stage_holds(self):
        v=private_input(); v["privateDisposition"]["stageReceipts"].pop(); v["privateDisposition"]["privateEvidenceBodyCount"]-=1
        self.assertEqual(tool.build_objects(self.profile,v)["join"]["terminal"],"HOLD")
    def test_duplicate_stage_holds(self):
        v=private_input(); v["privateDisposition"]["stageReceipts"][2]=copy.deepcopy(v["privateDisposition"]["stageReceipts"][1])
        self.assertEqual(tool.build_objects(self.profile,v)["join"]["terminal"],"HOLD")
    def test_reordered_stage_holds(self):
        v=private_input(); v["privateDisposition"]["stageReceipts"][2:4]=reversed(v["privateDisposition"]["stageReceipts"][2:4])
        self.assertEqual(tool.build_objects(self.profile,v)["join"]["terminal"],"HOLD")
    def test_wrong_conflict_terminal_holds(self):
        v=private_input(); v["privateDisposition"]["stageReceipts"][11]["terminal"]="PASS"
        self.assertEqual(tool.build_objects(self.profile,v)["join"]["terminal"],"HOLD")
    def test_broken_predecessor_chain_holds(self):
        v=private_input(); v["privateDisposition"]["stageReceipts"][5]["previousReceiptId"]=tool.SHA256_REF.pattern.replace('^','') if False else tool.SOURCE_DIGESTS["axmProfileCanonicalSha256"]
        v["privateDisposition"]["stageReceipts"][5]["previousReceiptId"]="sha256:"+"0"*64
        self.assertEqual(tool.build_objects(self.profile,v)["join"]["terminal"],"HOLD")
    def test_action_before_authorization_holds(self):
        v=private_input(); v["privateDisposition"]["stageReceipts"][0]["previousReceiptId"]="sha256:"+"0"*64
        self.assertEqual(tool.build_objects(self.profile,v)["join"]["terminal"],"HOLD")
    def test_public_evidence_body_holds(self):
        v=private_input(); v["privateDisposition"]["publicEvidenceBodyCount"]=1
        self.assertEqual(tool.build_objects(self.profile,v)["join"]["terminal"],"HOLD")
    def test_zero_private_evidence_holds(self):
        v=private_input(); v["privateDisposition"]["privateEvidenceBodyCount"]=0
        for r in v["privateDisposition"]["stageReceipts"]: r["evidenceBodyCount"]=0
        self.assertEqual(tool.build_objects(self.profile,v)["join"]["terminal"],"HOLD")
    def test_resident_memory_holds(self):
        v=private_input(); v["route"]["residentRoute"]["memoryMiB"]=1
        self.assertEqual(tool.build_objects(self.profile,v)["join"]["terminal"],"HOLD")
    def test_accelerator_semantic_mismatch_holds(self):
        v=private_input(); v["route"]["acceleratorRoute"]["outputSha256"]="sha256:"+"0"*64
        self.assertEqual(tool.build_objects(self.profile,v)["join"]["terminal"],"HOLD")
    def test_nonaccelerating_route_holds(self):
        v=private_input(); v["route"]["acceleratorRoute"]["throughputMilliItemsPerSecond"]=1
        self.assertEqual(tool.build_objects(self.profile,v)["join"]["terminal"],"HOLD")
    def test_memory_pooling_holds(self):
        v=private_input(); v["route"]["memoryPoolingUsed"]=True
        self.assertEqual(tool.build_objects(self.profile,v)["join"]["terminal"],"HOLD")
    def test_post_removal_output_mismatch_holds(self):
        v=private_input(); v["continuity"]["postRemovalOutputSha256"]="sha256:"+"0"*64
        self.assertEqual(tool.build_objects(self.profile,v)["join"]["terminal"],"HOLD")
    def test_lattice_dependency_holds(self):
        v=private_input(); v["continuity"]["latticeAbsentDuringLocalContinuity"]=False
        self.assertEqual(tool.build_objects(self.profile,v)["join"]["terminal"],"HOLD")
    def test_same_host_holds(self):
        v=private_input(); v["twoCell"]["rightHostClassSha256"]=v["twoCell"]["leftHostClassSha256"]
        self.assertEqual(tool.build_objects(self.profile,v)["join"]["terminal"],"HOLD")
    def test_automatic_merge_holds(self):
        v=private_input(); v["twoCell"]["automaticMergeAllowed"]=True
        self.assertEqual(tool.build_objects(self.profile,v)["join"]["terminal"],"HOLD")
    def test_same_head_class_holds(self):
        v=private_input(); v["successor"]["replacementHeadClassSha256"]=v["successor"]["originalHeadClassSha256"]
        self.assertEqual(tool.build_objects(self.profile,v)["join"]["terminal"],"HOLD")
    def test_successor_answer_forgery_holds(self):
        v=private_input(); v["successor"]["answers"]["nextSafeAction"]="sha256:"+"0"*64
        self.assertEqual(tool.build_objects(self.profile,v)["join"]["terminal"],"HOLD")
    def test_sealed_failure_holds(self):
        v=private_input(); v["privateDisposition"]["sealedVerificationTerminal"]="FAIL"
        self.assertEqual(tool.build_objects(self.profile,v)["join"]["terminal"],"HOLD")
    def test_authority_promotion_shape_refuses(self):
        v=private_input(); v["privateDisposition"]["authority"]="hardware"
        with self.assertRaises(tool.JoinError): tool.build_objects(self.profile,v)
    def test_private_windows_path_refuses(self):
        v=private_input(); v["successor"]["missionId"]="C:\\private\\mission"
        with self.assertRaises(tool.JoinError): tool.build_objects(self.profile,v)
    def test_private_endpoint_refuses(self):
        v=private_input(); v["successor"]["missionId"]="https://private.invalid"
        with self.assertRaises(tool.JoinError): tool.build_objects(self.profile,v)
    def test_deterministic_build(self):
        a,outa=self.build(); b,outb=self.build(); self.assertEqual((outa/"MANIFEST.json").read_bytes(),(outb/"MANIFEST.json").read_bytes()); a.cleanup(); b.cleanup()
    def test_direct_verifier_is_unauthenticated(self):
        td,c=self.build(); r=self.direct(c); self.assertEqual(r.returncode,0); self.assertFalse(json.loads(r.stdout)["bootstrapAuthenticated"]); td.cleanup()
    def test_external_bootstrap_authenticates(self):
        td,c=self.build(); out=Path(td.name)/"verdict.json"; receipt=tool.bootstrap_verify(c,out); self.assertTrue(receipt["bootstrapAuthenticated"]); self.assertEqual(out.read_bytes(),tool.canonical_json_bytes(receipt)); td.cleanup()
    def test_malicious_verifier_substitution_refuses_before_execution(self):
        td,c=self.build(); (c/"RECOVERY/verify_join.py").write_text("raise SystemExit('EXECUTED')\n");
        with self.assertRaises(tool.JoinError) as cm: tool.bootstrap_verify(c,None)
        self.assertEqual(cm.exception.code,"BOOTSTRAP_SOURCE_AUTHENTICATION_FAILED"); td.cleanup()
    def test_unmanifested_file_refuses(self):
        td,c=self.build(); (c/"EXTRA").write_text("x"); self.assert_refused(c,"FILE_DENOMINATOR_INVALID"); td.cleanup()
    @unittest.skipIf(os.name == "nt", "symlink privilege is not portable on Windows")
    def test_symlink_refuses(self):
        td,c=self.build(); target=c/"JOIN/source-binding.json"; link=c/"LINK"; link.symlink_to(target); self.assert_refused(c,"SYMLINK_MEMBER_REFUSED"); td.cleanup()
    def test_verdict_output_inside_carrier_refuses(self):
        td,c=self.build(); r=subprocess.run([sys.executable,str(VERIFIER),str(c),"--out",str(c/"verdict.json")],stdout=subprocess.PIPE); self.assertEqual(r.returncode,2); self.assertEqual(json.loads(r.stdout)["errorCode"],"VERDICT_OUTPUT_OVERLAP_REFUSED"); td.cleanup()
    def test_public_claim_promotion_after_resigning_refuses(self):
        td,c=self.build();
        def mut(v): v["strongerClaims"]["physicalEstateQualified"]=True
        self.mutate_object(c,"PUBLIC/status.json",mut,"publicStatusId","axmheadphysicallonghaulpublicstatus2"); self.assert_refused(c,"RECONSTRUCTION_MISMATCH"); td.cleanup()
    def test_join_authority_promotion_after_resigning_refuses(self):
        td,c=self.build();
        def mut(v): v["authority"]="hardware"
        self.mutate_object(c,"JOIN/join.json",mut,"joinId","axmheadphysicallonghauljoin2"); self.assert_refused(c,"RECONSTRUCTION_MISMATCH"); td.cleanup()
    def test_boolean_integer_substitution_after_resigning_refuses(self):
        td,c=self.build();
        def mut(v): v["predicates"]["physicalExecutionStartedByJoin"]=0
        self.mutate_object(c,"JOIN/join.json",mut,"joinId","axmheadphysicallonghauljoin2"); self.assert_refused(c,"RECONSTRUCTION_MISMATCH"); td.cleanup()
    def test_lf_only_authoritative_json(self):
        td,c=self.build();
        for rel in ("MANIFEST.json",*tool.EXPECTED_MEMBER_PATHS):
            if rel.endswith(".json"): self.assertNotIn(b"\r\n",(c/rel).read_bytes())
        td.cleanup()
    def test_foreign_working_directory(self):
        td,c=self.build(); other=tempfile.TemporaryDirectory(); r=subprocess.run([sys.executable,str(VERIFIER),str(c)],cwd=other.name,stdout=subprocess.PIPE); self.assertEqual(r.returncode,0); other.cleanup(); td.cleanup()
    def test_bootstrap_output_inside_repository_refuses(self):
        td,c=self.build();
        with self.assertRaises(tool.JoinError) as cm: tool.bootstrap_verify(c,ROOT/"forbidden-verdict.json")
        self.assertEqual(cm.exception.code,"REPOSITORY_OUTPUT_REFUSED"); td.cleanup()
    def test_fqdn_refuses(self):
        v=private_input(); v["successor"]["missionId"]="private-host.example.com"
        with self.assertRaises(tool.JoinError): tool.build_objects(self.profile,v)
    def test_ipv4_refuses(self):
        v=private_input(); v["successor"]["missionId"]="10.20.30.40"
        with self.assertRaises(tool.JoinError): tool.build_objects(self.profile,v)
    def test_noncanonical_member_refuses_after_resigning(self):
        td,c=self.build(); value=load(c/"PUBLIC/status.json"); (c/"PUBLIC/status.json").write_text(json.dumps(value,sort_keys=True,indent=2)+"\n",encoding="utf-8"); self.resign_manifest(c); self.assert_refused(c,"NON_CANONICAL_MEMBER_BYTES"); td.cleanup()
    def test_hardlinked_verdict_output_refuses(self):
        td,c=self.build(); outside=Path(td.name)/"outside-hardlink.json"; os.link(c/"MANIFEST.json",outside); r=subprocess.run([sys.executable,str(VERIFIER),str(c),"--out",str(outside)],stdout=subprocess.PIPE); self.assertEqual(r.returncode,2); self.assertEqual(json.loads(r.stdout)["errorCode"],"VERDICT_OUTPUT_OVERLAP_REFUSED"); td.cleanup()
    @unittest.skipIf(os.name == "nt", "symlink privilege is not portable on Windows")
    def test_bootstrap_refuses_symlinked_recovery_source(self):
        td,c=self.build(); original=c/"RECOVERY/verify_join.py"; backup=c/"RECOVERY/verify_join.real"; original.rename(backup); original.symlink_to(backup)
        with self.assertRaises(tool.JoinError) as cm: tool.bootstrap_verify(c,None)
        self.assertEqual(cm.exception.code,"SYMLINK_MEMBER_REFUSED"); td.cleanup()
    def test_partial_private_denominator_holds(self):
        v=private_input(); v["successor"]["present"]=False; v["successor"]["evidenceTier"]="none"
        for key in ("originalHeadClassSha256","replacementHeadClassSha256","missionId","canonicalStateSha256","proofRootSha256","namedHumanAuthorityClass","nextSafeActionSha256","verificationTerminal","receiptId"): v["successor"][key]=None
        v["successor"]["unresolvedObligationCount"]=0; v["successor"]["answers"]={}; v["successor"]["dependenciesAbsent"]=[]; v["successor"]["independentlyVerified"]=False
        self.assertEqual(tool.build_objects(self.profile,v)["join"]["terminal"],"HOLD")
    def test_no_workers_listeners_or_authority(self):
        o=tool.build_objects(self.profile,private_input()); self.assertEqual(o["public"]["workersLaunched"],0); self.assertEqual(o["public"]["listenersCreated"],0); self.assertEqual(o["public"]["authority"],"none")
if __name__ == "__main__": unittest.main()

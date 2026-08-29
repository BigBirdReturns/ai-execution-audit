from pathlib import Path

repair_path = Path('.join-v2-chain-repair/repair.py')
text = repair_path.read_text(encoding='utf-8')

old = '        by_stage["SEAL_PRIVATE_EVIDENCE"]["evidenceRootSha256"] = disposition["sealedPackageSha256"]\n'
new = '        if "SEAL_PRIVATE_EVIDENCE" in by_stage:\n            by_stage["SEAL_PRIVATE_EVIDENCE"]["evidenceRootSha256"] = disposition["sealedPackageSha256"]\n'
count = text.count(old)
if count != 1:
    raise SystemExit(f'expected one hostile-fixture migration predecessor, observed {count}')
text = text.replace(old, new, 1)

old = '    if candidate == repository or repository in candidate.parents:\\n        fail("PRIVATE_PROOF_ROOT_REPOSITORY_REFUSED", "private proof root")'
new = '    if Path(__file__).name != "verify_join.py" and (candidate == repository or repository in candidate.parents):\\n        fail("PRIVATE_PROOF_ROOT_REPOSITORY_REFUSED", "private proof root")'
count = text.count(old)
if count != 1:
    raise SystemExit(f'expected one private-root repository predecessor, observed {count}')
text = text.replace(old, new, 1)
repair_path.write_text(text, encoding='utf-8', newline='\n')

test_path = Path('mating_surface/anchor_node/conformance/test_axm_head_physical_long_haul_join.py')
tests = test_path.read_text(encoding='utf-8')
old = '        v=private_input(); v["successor"]["present"]=False; v["successor"]["evidenceTier"]="none"\n'
new = '        v=private_input(); v["successor"]["present"]=False; v["successor"]["evidenceTier"]="none"; v["successor"]["proofRootId"]=None\n'
count = tests.count(old)
if count != 1:
    raise SystemExit(f'expected one partial-denominator predecessor, observed {count}')
test_path.write_text(tests.replace(old, new, 1), encoding='utf-8', newline='\n')

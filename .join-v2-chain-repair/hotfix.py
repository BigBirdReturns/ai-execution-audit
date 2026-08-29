from pathlib import Path

path = Path('.join-v2-chain-repair/repair.py')
text = path.read_text(encoding='utf-8')
old = '        by_stage["SEAL_PRIVATE_EVIDENCE"]["evidenceRootSha256"] = disposition["sealedPackageSha256"]\n'
new = '        if "SEAL_PRIVATE_EVIDENCE" in by_stage:\n            by_stage["SEAL_PRIVATE_EVIDENCE"]["evidenceRootSha256"] = disposition["sealedPackageSha256"]\n'
count = text.count(old)
if count != 1:
    raise SystemExit(f'expected one hostile-fixture migration predecessor, observed {count}')
path.write_text(text.replace(old, new, 1), encoding='utf-8', newline='\n')

PYTHON ?= python

.PHONY: test demo pack replay verify clean

test:
	pytest -q

demo:
	$(PYTHON) -m reference_impl.axm_runtime --ir ir/demo_ir.json --input "Refund request" --outdir out

pack:
	$(PYTHON) tools/pack_replay_bundle.py out

verify:
	$(PYTHON) tools/verify.py out

replay:
	$(PYTHON) tools/replay.py out

clean:
	rm -rf out artifacts/*.zip artifacts/*report*.json provenance/*.jsonl

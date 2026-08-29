from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().with_name("reclassify_axm_head_preflight_review_card_01.py")
spec = importlib.util.spec_from_file_location("preflight_reclassifier", SCRIPT)
if spec is None or spec.loader is None:
    raise SystemExit("unable to load the reclassification program")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.REPLACEMENTS = module.REPLACEMENTS + (("physical-long-haul", "physical-flight-preflight"),)
raise SystemExit(module.main())

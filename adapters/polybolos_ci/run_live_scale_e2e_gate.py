#!/usr/bin/env python3
"""Run the 5,000-entity gate against the cabinet's qualified boundary.

The shared cabinet sidecar requests a 16-entity read-only projection. This entry
point binds the scale harness to that same limit and requires refusal cases to
return explicit, machine-readable ``CI_*`` error codes through the real cabinet
route. A generic HTTP failure or silent process exit does not satisfy the gate.
"""
from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import run_live_scale_e2e as scale

QUALIFIED_CABINET_LIMIT = 16
BOUNDED_ERROR = re.compile(r"^CI_[A-Z0-9_]+(?::|$)")
_LAST_REFUSAL: dict[str, Any] | None = None


def wait_for_bounded_refusal(
    base_url: str,
    process: Any,
    *,
    timeout: float = 20.0,
) -> None:
    global _LAST_REFUSAL
    _LAST_REFUSAL = None
    deadline = time.monotonic() + timeout
    url = (
        f"{base_url}/api/sdk/cabinet"
        f"?staleAfterMs={scale.STALE_AFTER_MS}&limit={QUALIFIED_CABINET_LIMIT}"
    )

    while time.monotonic() < deadline:
        if process.poll() is not None:
            if process.returncode == 0:
                raise RuntimeError("refusal server exited successfully instead of refusing state")
            raise RuntimeError(
                f"refusal server exited before returning a bounded response: {process.returncode}"
            )

        request = urllib.request.Request(
            url,
            headers={"Accept": "application/json", "Cache-Control": "no-cache"},
        )
        try:
            with urllib.request.urlopen(request, timeout=1.0) as response:
                body = response.read().decode("utf-8", errors="replace")
                raise RuntimeError(
                    f"conflicting provider became readable: HTTP {response.status} {body}"
                )
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            text = raw.decode("utf-8", errors="replace")
            try:
                parsed = json.loads(text) if text else None
            except json.JSONDecodeError as parse_error:
                raise RuntimeError(
                    f"conflicting provider returned non-JSON refusal: HTTP {exc.code} {text!r}"
                ) from parse_error
            error_text = parsed.get("error") if isinstance(parsed, dict) else None
            if exc.code < 400 or not isinstance(error_text, str):
                raise RuntimeError(
                    f"conflicting provider returned an unbounded refusal: HTTP {exc.code} {parsed!r}"
                )
            if BOUNDED_ERROR.match(error_text) is None:
                raise RuntimeError(
                    f"conflicting provider returned no bounded CI error: HTTP {exc.code} {parsed!r}"
                )
            _LAST_REFUSAL = {
                "status": exc.code,
                "url": url,
                "body": parsed,
            }
            return
        except urllib.error.URLError:
            time.sleep(0.2)
            continue

    raise RuntimeError("provider never returned a bounded CI refusal")


def require_bounded_refusal(path: Path, token: str) -> None:
    if _LAST_REFUSAL is None:
        raise RuntimeError("bounded provider refusal was not captured")
    body = _LAST_REFUSAL.get("body")
    error_text = body.get("error") if isinstance(body, dict) else None
    if not isinstance(error_text, str) or token not in error_text:
        raise RuntimeError(f"expected refusal token {token!r} is absent from response evidence")
    with path.open("a", encoding="utf-8") as handle:
        handle.write("\nBOUNDED_REFUSAL_RESPONSE\n")
        handle.write(json.dumps(_LAST_REFUSAL, indent=2, sort_keys=True))
        handle.write("\n")


def main() -> int:
    scale.CABINET_LIMIT = QUALIFIED_CABINET_LIMIT
    scale.wait_for_refusal = wait_for_bounded_refusal
    scale.require_log_token = require_bounded_refusal
    return scale.main()


if __name__ == "__main__":
    raise SystemExit(main())

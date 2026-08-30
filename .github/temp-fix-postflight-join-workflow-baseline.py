from __future__ import annotations

from pathlib import Path

WORKFLOW = Path(".github/workflows/axm-head-physical-long-haul-join-01.yml")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one anchor, found {count}")
    return text.replace(old, new, 1)


text = WORKFLOW.read_text(encoding="utf-8")
text = replace_once(
    text,
    '''          EVENT_SHA: ${{ github.sha }}
          PR_HEAD_SHA: ${{ github.event.pull_request.head.sha }}
          PLATFORM: ${{ matrix.os }}
''',
    '''          EVENT_SHA: ${{ github.sha }}
          PR_HEAD_SHA: ${{ github.event.pull_request.head.sha }}
          PR_BASE_SHA: ${{ github.event.pull_request.base.sha }}
          PLATFORM: ${{ matrix.os }}
''',
    "pull-request base coordinate",
)
text = replace_once(
    text,
    '''          if [ "$EVENT_NAME" = "pull_request" ]; then
            printf 'head\\t%s\\nmerge\\t%s\\n' "$PR_HEAD_SHA" "$EVENT_SHA" > "$COORDINATES"
          else
            printf 'source\\t%s\\n' "$EVENT_SHA" > "$COORDINATES"
          fi

          REPO_ROOT="$GITHUB_WORKSPACE"
''',
    '''          if [ "$EVENT_NAME" = "pull_request" ]; then
            printf 'head\\t%s\\nmerge\\t%s\\n' "$PR_HEAD_SHA" "$EVENT_SHA" > "$COORDINATES"
            PRODUCT_BASE_SHA="$PR_BASE_SHA"
          else
            printf 'source\\t%s\\n' "$EVENT_SHA" > "$COORDINATES"
            PRODUCT_BASE_SHA="$(git -C "$GITHUB_WORKSPACE" rev-parse "$EVENT_SHA^1")"
          fi

          REPO_ROOT="$GITHUB_WORKSPACE"
''',
    "event-specific product baseline",
)
text = replace_once(
    text,
    '''            python - "$REPO_ROOT" "$OBSERVED_SHA" "${PRODUCT_PATHS[@]}" <<'PY'
          from pathlib import Path
          import ast
          import re
          import subprocess
          import sys

          repository = Path(sys.argv[1])
          observed_sha = sys.argv[2]
          product_paths = [Path(value) for value in sys.argv[3:]]
''',
    '''            python - "$REPO_ROOT" "$PRODUCT_BASE_SHA" "$OBSERVED_SHA" "${PRODUCT_PATHS[@]}" <<'PY'
          from pathlib import Path
          import ast
          import re
          import subprocess
          import sys

          repository = Path(sys.argv[1])
          product_base_sha = sys.argv[2]
          observed_sha = sys.argv[3]
          product_paths = [Path(value) for value in sys.argv[4:]]
''',
    "baseline argument plumbing",
)
text = replace_once(
    text,
    '''                  "git", "-C", str(repository), "diff", "--name-only",
                  "ec61bc3488cb5ae06ed9db2862a9f6910d310a79", observed_sha,
''',
    '''                  "git", "-C", str(repository), "diff", "--name-only",
                  product_base_sha, observed_sha,
''',
    "product denominator range",
)
text = replace_once(
    text,
    '''            grep -F "Ran 25 tests" "$DEST/inherited-conductor-tests.txt"
''',
    '''            grep -F "Ran 32 tests" "$DEST/inherited-conductor-tests.txt"
''',
    "current conductor witness denominator",
)
WORKFLOW.write_text(text, encoding="utf-8", newline="\n")

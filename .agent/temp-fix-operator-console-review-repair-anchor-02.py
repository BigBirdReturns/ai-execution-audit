from pathlib import Path

path = Path(".agent/temp-repair-browser-physical-audition-operator-console-review-02.py")
text = path.read_text(encoding="utf-8")

old_anchor = '''replace_once(
    worker,
    \'\'\'      const inspection = await executeInMain(message.tabId, inspectProbeInPage, [
        CONTRACT.METHODS,
        CONTRACT.MAX_CAPTURE_BYTES,
      ]);
\'\'\',
    \'\'\'      const execution = await executeInMain(message.tabId, inspectProbeInPage, [
        CONTRACT.METHODS,
        CONTRACT.MAX_CAPTURE_BYTES,
      ]);
      const inspection = execution.result;
\'\'\',
)
'''
new_anchor = '''replace_once(
    worker,
    \'\'\'      const inspection = await executeInMain(message.tabId, inspectProbeInPage, [
        CONTRACT.METHODS,
        CONTRACT.MAX_CAPTURE_BYTES,
      ]);
      if (!inspection || inspection.status !== "PASS") {
\'\'\',
    \'\'\'      const execution = await executeInMain(message.tabId, inspectProbeInPage, [
        CONTRACT.METHODS,
        CONTRACT.MAX_CAPTURE_BYTES,
      ]);
      const inspection = execution.result;
      if (!inspection || inspection.status !== "PASS") {
\'\'\',
)
'''
if text.count(old_anchor) != 1:
    raise SystemExit(f"repair-script anchor differs: {text.count(old_anchor)}")
text = text.replace(old_anchor, new_anchor)

old_open = "extra_tests = textwrap.dedent(r'''\n"
new_open = "extra_tests = r'''\n"
old_close = "''')\nreplace_once(tests, '\\n\\ndef _fixture_test(row: dict, group: str):\\n', extra_tests"
new_close = "'''\nreplace_once(tests, '\\n\\ndef _fixture_test(row: dict, group: str):\\n', extra_tests"
if text.count(old_open) != 1 or text.count(old_close) != 1:
    raise SystemExit(
        f"repair witness indentation anchors differ: open={text.count(old_open)} close={text.count(old_close)}"
    )
text = text.replace(old_open, new_open).replace(old_close, new_close)
path.write_text(text, encoding="utf-8", newline="\n")

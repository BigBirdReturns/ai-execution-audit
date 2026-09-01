from pathlib import Path

path = Path(".agent/temp-repair-browser-physical-audition-operator-console-review-02.py")
text = path.read_text(encoding="utf-8")
old = '''replace_once(
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
new = '''replace_once(
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
if text.count(old) != 1:
    raise SystemExit(f"repair-script anchor differs: {text.count(old)}")
path.write_text(text.replace(old, new), encoding="utf-8", newline="\n")

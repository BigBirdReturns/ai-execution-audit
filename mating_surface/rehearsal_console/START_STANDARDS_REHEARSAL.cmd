@echo off
setlocal
set "HERE=%~dp0"
if exist "%HERE%mating_surface\rehearsal_console\server.mjs" (
  set "ROOT=%HERE%"
) else (
  set "ROOT=%HERE%..\..\"
)
set "EVIDENCE=%ROOT%evidence"
set "MANIFEST=%ROOT%build-manifest.json"

where node >nul 2>nul
if errorlevel 1 (
  echo Node.js 24 or newer is required.
  exit /b 1
)

if not exist "%ROOT%mating_surface\rehearsal_console\server.mjs" (
  echo Rehearsal console source is missing.
  exit /b 1
)
if not exist "%EVIDENCE%\semantic-conversation\conversation.json" (
  echo Rehearsal evidence is missing.
  exit /b 1
)

start "" cmd /c "ping -n 3 127.0.0.1 >nul & start http://127.0.0.1:8787"
node "%ROOT%mating_surface\rehearsal_console\server.mjs" --evidence "%EVIDENCE%" --build-manifest "%MANIFEST%" --host 127.0.0.1 --port 8787
set "CODE=%ERRORLEVEL%"
endlocal & exit /b %CODE%

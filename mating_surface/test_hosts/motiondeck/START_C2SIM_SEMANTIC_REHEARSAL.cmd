@echo off
setlocal EnableExtensions

set "ROOT=%~dp0"
set "SURFACE=%ROOT%c2sim-semantic-rehearsal.html"

if not exist "%SURFACE%" (
  echo C2SIM semantic rehearsal surface is missing: "%SURFACE%" 1>&2
  exit /b 2
)

where msedge.exe >nul 2>nul
if not errorlevel 1 (
  start "C2SIM Semantic Rehearsal" msedge.exe --app="file:///%SURFACE:\=/%" --start-maximized
  exit /b 0
)

where chrome.exe >nul 2>nul
if not errorlevel 1 (
  start "C2SIM Semantic Rehearsal" chrome.exe --app="file:///%SURFACE:\=/%" --start-maximized
  exit /b 0
)

start "C2SIM Semantic Rehearsal" "%SURFACE%"
exit /b 0

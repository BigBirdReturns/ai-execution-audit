@echo off
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0Prepare-Both-Hosts.ps1" %*
exit /b %ERRORLEVEL%

@echo off
python "%~dp0verify_current_rejoin_packet.py" "%~dp0"
exit /b %ERRORLEVEL%

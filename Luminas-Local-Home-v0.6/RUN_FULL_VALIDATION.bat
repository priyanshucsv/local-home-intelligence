@echo off
cd /d "%~dp0"
REM Runs the SAME validation logic as `python main.py --validate`
REM (unit tests + primary Digital Twin demo + security/protocol +
REM  failure scenarios + local-only validation) via security/validation.py.
python main.py --validate
if errorlevel 1 exit /b 1
pause

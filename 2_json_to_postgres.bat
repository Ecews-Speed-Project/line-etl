@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    python -m venv .venv
    if errorlevel 1 goto failure
)
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto failure
if not defined PGHOST set "PGHOST=localhost"
if not defined PGPORT set "PGPORT=5432"
if not defined PGDATABASE set "PGDATABASE=ecews"
if not defined PGUSER set "PGUSER=postgres"
rem The Python uploader prompts securely when PGPASSWORD is unset.
set "JSON_FILE=%~1"
if not defined JSON_FILE set "JSON_FILE=%~dp0linelist.json"
set /p "REPORT_PERIOD=Reporting period date (YYYY-MM-DD): "
".venv\Scripts\python.exe" upload_json.py "%JSON_FILE%" --period "%REPORT_PERIOD%"
if errorlevel 1 goto failure
pause
exit /b 0
:failure
echo Upload failed. See the error above.
pause
exit /b 1

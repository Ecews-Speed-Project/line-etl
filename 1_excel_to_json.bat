@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    python -m venv .venv
    if errorlevel 1 goto failure
)
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto failure
set "INPUT_FILE=%~1"
if not defined INPUT_FILE set /p "INPUT_FILE=Excel file path: "
set "INPUT_FILE=%INPUT_FILE:"=%"
".venv\Scripts\python.exe" excel_to_json.py "%INPUT_FILE%" "%~dp0linelist.json"
if errorlevel 1 goto failure
echo JSON saved to %~dp0linelist.json
pause
exit /b 0
:failure
echo Conversion failed. See the error above.
pause
exit /b 1

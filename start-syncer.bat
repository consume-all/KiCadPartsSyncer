@echo off
setlocal
REM Always run from this script's directory (so relative paths work)
pushd "%~dp0"
REM Activate the venv and start the app
call ".venv\Scripts\activate.bat"
python "run.py"
popd
endlocal
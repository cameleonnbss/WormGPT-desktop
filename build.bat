@echo off
REM ============================================================
REM  WormGPT Desktop — build script (Windows)
REM  Produces a single self-contained exe: dist\WormGPT.exe
REM
REM  Uses a project-local Python 3.12 venv (.venv) because
REM  llama-cpp-python ships its Windows wheel only as py3-none
REM  (GitHub release) and needs a Python <= 3.13.
REM ============================================================
setlocal
cd /d "%~dp0"

set PY=python
if exist ".venv\Scripts\python.exe" (
    set PY=.venv\Scripts\python.exe
) else (
    echo [0/4] Creating Python 3.12 virtual environment (.venv)...
    py -3.12 -m venv .venv
    if errorlevel 1 (
        echo   Could not create the venv. Install Python 3.12 from python.org.
        goto :fail
    )
    set PY=.venv\Scripts\python.exe
)

echo [1/4] Installing build dependencies...
%PY% -m pip install --upgrade pip
%PY% -m pip install -r requirements.txt pyinstaller
if errorlevel 1 goto :fail

echo [2/4] Generating app icon and logos...
%PY% tools\make_assets.py
if errorlevel 1 goto :fail

echo [3/4] Building WormGPT.exe (this can take a few minutes)...
%PY% -m PyInstaller --noconfirm WormGPT.spec
if errorlevel 1 goto :fail

echo [4/4] Done.
echo.
echo   Build complete: dist\WormGPT.exe  (single file, no install needed)
echo   Tip: install UPX (upx.github.io) on PATH to shrink it further.
pause
exit /b 0

:fail
echo.
echo Build failed. See messages above.
pause
exit /b 1
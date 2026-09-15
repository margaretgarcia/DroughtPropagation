@echo off
REM Launch the Arizona Drought Propagation Explorer as a local website.
REM serve.py finds a free port, opens your browser, and serves with no-cache
REM headers so you always see the current version.
cd /d "%~dp0"

REM Find a working Python. Plain "python" on PATH is the Microsoft Store stub
REM on this machine, so prefer the real Anaconda interpreter, then the py
REM launcher, then fall back to python on PATH.
set "PYEXE="
if exist "C:\ProgramData\anaconda3\python.exe" set "PYEXE=C:\ProgramData\anaconda3\python.exe"
if not defined PYEXE if exist "%LOCALAPPDATA%\anaconda3\python.exe" set "PYEXE=%LOCALAPPDATA%\anaconda3\python.exe"
if not defined PYEXE (
    where py >nul 2>nul && set "PYEXE=py"
)
if not defined PYEXE set "PYEXE=python"

echo Using Python: %PYEXE%
"%PYEXE%" serve.py
pause

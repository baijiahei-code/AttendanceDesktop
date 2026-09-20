@echo off
setlocal
cd /d "%~dp0"

rem ##########################################################################
rem  One-click build entry for the Attendance desktop app (Windows side).
rem
rem  This file is only a thin shell. The real work lives in the unified entry
rem  scripts\pack_all.py, which dispatches by platform:
rem      Windows -> scripts\pack_windows.py  (portable folder + Inno Setup installer)
rem      Linux   -> scripts\pack_deb.py      (deb package for Debian-based distros)
rem
rem  Just double-click this file for the Windows build. To pass extra args:
rem      this file              -> Windows build (default on this platform)
rem      this file deb --keep   -> rejected here by design (deb needs Linux)
rem
rem  KEEP THIS FILE PURE ASCII: a non-ASCII byte breaks the cmd parser on code
rem  pages other than 936. The Chinese documentation lives in scripts\pack_all.py.
rem ##########################################################################

set "ROOT=%~dp0"
set "PY=%ROOT%.venv\Scripts\python.exe"

if not exist "%PY%" goto err_env
if not exist "%ROOT%scripts\pack_all.py" goto err_entry

echo ==============================================================
echo  One-click build (Windows) - via scripts\pack_all.py
echo ==============================================================
echo  ROOT   = %ROOT%
echo  PYTHON = %PY%
echo ==============================================================
"%PY%" "%ROOT%scripts\pack_all.py" %*
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" goto fail

echo.
echo Build finished (exit=0).
echo Press any key to close this window...
pause >NUL
exit /b 0

:err_env
set "RC=1"
echo [ERROR] venv python not found: %PY%
echo         Setup first:
echo             python -m venv .venv
echo             .venv\Scripts\pip install -r requirements.txt
goto fail

:err_entry
set "RC=1"
echo [ERROR] unified entry not found: %ROOT%scripts\pack_all.py
goto fail

:fail
echo.
echo [FAILED] build exit code = %RC%
echo Press any key to close this window...
pause >NUL
exit /b %RC%

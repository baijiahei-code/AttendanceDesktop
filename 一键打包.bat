@echo off
setlocal EnableExtensions
cd /d "%~dp0"

rem ##########################################################################
rem  One-click build entry - Windows side (single entry for BOTH platforms).
rem
rem  Desktop app  : thin shell over the unified entry scripts\pack_all.py
rem                 (Windows -> pack_windows.py: portable folder + Inno Setup)
rem  HarmonyOS app: thin shell over harmony-app\scripts\pack_hap.ps1
rem                 (DevEco Studio + hvigor -> release\AttendanceHarmony-*.hap)
rem
rem  Usage:
rem    <this file>                      desktop Windows build (default)
rem    <this file> harmony               HarmonyOS HAP (release)
rem    <this file> harmony -Install      HarmonyOS HAP + install to device
rem    <this file> harmony -Clean        HarmonyOS HAP, clean build cache first
rem    <this file> harmony -BuildMode debug
rem    <this file> deb / rpm / all       rejected here by design (needs Linux)
rem    <this file> --help                show this help
rem
rem  KEEP THIS FILE PURE ASCII: a non-ASCII byte breaks the cmd parser on code
rem  pages other than 936. Chinese documentation lives in README.md.
rem ##########################################################################

if /i "%~1"=="--help" goto :usage
if /i "%~1"=="-h" goto :usage
if /i "%~1"=="/?" goto :usage
if /i "%~1"=="harmony" goto :harmony_shift
if /i "%~1"=="hm" goto :harmony_shift
goto :desktop

rem ---------------------------------------------------------------- HarmonyOS
:harmony_shift
shift
set "HARGS="
:collect_args
if "%~1"=="" goto :harmony_run
set "HARGS=%HARGS% "%~1""
shift
goto :collect_args

:harmony_run
set "PS1=%~dp0harmony-app\scripts\pack_hap.ps1"
if not exist "%PS1%" (
    set "RC=2"
    echo [ERROR] build script not found: %PS1%
    echo         keep this .bat in the repository root.
    goto :fail
)

echo ==============================================================
echo  One-click build - HarmonyOS (HAP)
echo ==============================================================
echo  runner = %PS1%
echo ==============================================================
powershell -NoProfile -ExecutionPolicy Bypass -File "%PS1%" %HARGS%
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" goto :fail

echo.
echo [OK] HarmonyOS build finished. See the release\ folder.
echo Press any key to close this window...
pause >NUL
exit /b 0

rem ---------------------------------------------------------------- desktop
:desktop
set "ROOT=%~dp0"
set "PY=%ROOT%.venv\Scripts\python.exe"

if not exist "%PY%" goto :err_env
if not exist "%ROOT%scripts\pack_all.py" goto :err_entry

echo ==============================================================
echo  One-click build (Windows desktop) - via scripts\pack_all.py
echo ==============================================================
echo  ROOT   = %ROOT%
echo  PYTHON = %PY%
echo ==============================================================
"%PY%" "%ROOT%scripts\pack_all.py" %*
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" goto :fail

echo.
echo Build finished (exit=0).
echo Press any key to close this window...
pause >NUL
exit /b 0

rem ---------------------------------------------------------------- helpers
:usage
echo Usage:  %~nx0  [target] [options]
echo.
echo   (nothing)               build the desktop app (Windows exe + installer)
echo   harmony                 build the HarmonyOS HAP
echo   harmony -Install        build HAP, then install to device and launch
echo   harmony -Clean          clean the HarmonyOS build cache first
echo   harmony -BuildMode debug
echo   --help                  show this help
echo.
echo Examples:
echo   %~nx0
echo   %~nx0 harmony
echo   %~nx0 harmony -Install
echo.
echo NOTE: on Linux / macOS use the .sh entry instead (deb/rpm builds are rejected here).
echo       HarmonyOS builds need DevEco Studio installed on this machine.
echo Press any key to close this window...
pause >NUL
exit /b 0

:err_env
set "RC=1"
echo [ERROR] venv python not found: %PY%
echo         Setup first:
echo             python -m venv .venv
echo             .venv\Scripts\pip install -r requirements.txt
goto :fail

:err_entry
set "RC=1"
echo [ERROR] unified entry not found: %ROOT%scripts\pack_all.py
goto :fail

:fail
echo.
echo [FAILED] build exit code = %RC%
echo Press any key to close this window...
pause >NUL
exit /b %RC%

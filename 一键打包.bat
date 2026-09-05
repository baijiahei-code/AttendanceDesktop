@echo off
setlocal
cd /d "%~dp0"

rem ##########################################################################
rem  One-click build for the Attendance desktop app (PyInstaller + Inno Setup).
rem  Output folder is ASCII "release" (kept out of git), so this file is
rem  intentionally pure ASCII - keep it that way (avoid any non-ASCII chars).
rem ##########################################################################

set "ROOT=%~dp0"
set "PUB=%ROOT%release"
set "SPEC=%ROOT%AttendanceDesktop.spec"
set "ISS=%ROOT%installer.iss"
set "PYEXE=%ROOT%.venv\Scripts\pyinstaller.exe"

rem --- locate Inno Setup 6 ISCC.exe (or override with env ISCC) ---
if not defined ISCC if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"

echo ------------------------------
echo  One-click build (Attendance desktop)
echo ------------------------------
echo  ROOT=%ROOT%
echo  ISCC=%ISCC%

if not exist "%PYEXE%" goto err_pyi
if not exist "%SPEC%"  goto err_spec
if not defined ISCC    goto err_iscc
if not exist "%ISCC%"  goto err_iscc
if not exist "%ISS%"   goto err_iss
goto step_clean

:err_pyi
echo [ERROR] PyInstaller not found: %PYEXE%
echo         Setup venv first:  python -m venv .venv
echo         then:              .venv\Scripts\pip install -r requirements.txt
goto :eof
:err_spec
echo [ERROR] Spec not found: %SPEC%
goto :eof
:err_iscc
echo [ERROR] Inno Setup 6 (ISCC.exe) not found.
echo         Install Inno Setup 6, or set env var ISCC=C:\path\to\ISCC.exe
goto :eof
:err_iss
echo [ERROR] Inno script not found: %ISS%
goto :eof

:step_clean
echo [0/3] Kill running app and clean old artifacts...
taskkill /F /IM AttendanceDesktop.exe >NUL 2>NUL
if exist "%PUB%\AttendanceDesktop" rmdir /S /Q "%PUB%\AttendanceDesktop"
if exist "%ROOT%build" rmdir /S /Q "%ROOT%build"
if exist "%ROOT%dist"  rmdir /S /Q "%ROOT%dist"

:step_pyi
echo [1/3] PyInstaller (spec)...
pushd "%ROOT%"
"%PYEXE%" --noconfirm --clean "%SPEC%"
set PYRESULT=%ERRORLEVEL%
popd
if not "%PYRESULT%"=="0" goto err_pyi_run
if not exist "%ROOT%dist\AttendanceDesktop\AttendanceDesktop.exe" goto err_exe
goto step_inno
:err_pyi_run
echo [ERROR] PyInstaller failed code=%PYRESULT%
goto :eof
:err_exe
echo [ERROR] AttendanceDesktop.exe was not produced.
goto :eof

:step_inno
echo [2/3] Inno Setup (installer)...
pushd "%ROOT%"
"%ISCC%" "%ISS%"
set INNORESULT=%ERRORLEVEL%
popd
if not "%INNORESULT%"=="0" goto err_inno
goto step_copy
:err_inno
echo [ERROR] Inno Setup failed code=%INNORESULT%
goto :eof

:step_copy
echo [3/3] Copy portable build to release folder...
if not exist "%PUB%" mkdir "%PUB%"
xcopy /E /I /H /Y "%ROOT%dist\AttendanceDesktop" "%PUB%\AttendanceDesktop" >NUL
if errorlevel 1 goto err_copy
if exist "%ROOT%build" rmdir /S /Q "%ROOT%build"
goto done
:err_copy
echo [ERROR] xcopy portable folder failed.
goto :eof

:done
echo ------------------------------
echo  Build finished.
echo  Portable : release\AttendanceDesktop\AttendanceDesktop.exe
echo  Installer: release\ (see installer.iss OutputBaseFilename)
echo ------------------------------
ping 127.0.0.1 -n 11 >NUL

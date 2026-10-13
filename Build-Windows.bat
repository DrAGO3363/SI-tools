@echo off
setlocal
cd /d "%~dp0"
title Build SEO Universal Desktop
where py >nul 2>&1
if %errorlevel%==0 (set "PY=py -3") else (set "PY=python")
%PY% -m pip install --upgrade pip
if errorlevel 1 goto failed
%PY% -m pip install -r requirements-desktop.txt
if errorlevel 1 goto failed
%PY% -m PyInstaller --noconfirm --clean --windowed --onedir --name "SEO Universal Amir Edition" --add-data "SEO-REPORT.html;." --collect-all webview desktop.py
if errorlevel 1 goto failed
echo.
echo Build complete: dist\SEO Universal Amir Edition\SEO Universal Amir Edition.exe
echo To create Setup.exe, install Inno Setup 6 and compile Installer.iss
pause
exit /b 0
:failed
echo.
echo BUILD FAILED. Read the error above.
pause
exit /b 1

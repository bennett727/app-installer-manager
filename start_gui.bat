@echo off
cd /d "%~dp0"
title App Installer GUI v1.1

echo ========================================
echo   App Installer GUI v1.1
echo ========================================
echo.

:: Set Python path
set PYTHON_EXE=D:\Python38\python.exe
if not exist "%PYTHON_EXE%" (
    echo [INFO] Using system Python...
    set PYTHON_EXE=python
)

echo [OK] Starting GUI...
echo [OK] Python: %PYTHON_EXE%
echo [OK] Directory: %cd%
echo.
echo (GUI window will appear in a few seconds)
echo.

:: Run GUI directly (same as start_simple.bat but with status info)
%PYTHON_EXE% gui_main.py 2>&1

:: Check exit code
set EXIT_CODE=%errorlevel%
echo.
if %EXIT_CODE% equ 0 (
    echo ========================================
    echo   [SUCCESS] Program exited normally
    echo ========================================
) else (
    echo ========================================
    echo   [WARNING] Program exited with code %EXIT_CODE%
    echo ========================================
)
echo.
pause
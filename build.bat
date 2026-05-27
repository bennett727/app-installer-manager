@echo off
cd /d "%~dp0"
echo ========================================
echo   App Installer Builder v1.1
echo ========================================
echo.

:: Set Python path (supports Win7/Win10/Win11)
set PYTHON_EXE=D:\Python38\python.exe
if not exist "%PYTHON_EXE%" (
    set PYTHON_EXE=python
)

:: Check PyInstaller
%PYTHON_EXE% -c "import PyInstaller" 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] PyInstaller not found, installing...
    %PYTHON_EXE% -m pip install pyinstaller
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to install PyInstaller
        pause
        exit /b 1
    )
)

echo [OK] Python: %PYTHON_EXE%
echo [OK] PyInstaller ready
echo.

:: Select build version
echo Select build version:
echo   1. GUI version (Recommended)
echo   2. Exit
echo.
set /p choice="Enter option (1/2): "

if "%choice%"=="1" goto build_gui
if "%choice%"=="2" goto end
echo [ERROR] Invalid option
pause
exit /b 1

:build_gui
echo.
echo ========================================
echo   Building GUI version...
echo ========================================
echo.
rmdir /s /q dist build 2>nul
del /f /q AppInstaller.spec 2>nul

%PYTHON_EXE% -m PyInstaller --onefile --windowed --name AppInstaller --exclude-module win32com gui_main.py
if %errorlevel% equ 0 (
    echo.
    echo [SUCCESS] Build completed!
    echo ----------------------------------------
    for %%A in ("dist\AppInstaller.exe") do (
        echo   File: dist\AppInstaller.exe
        echo   Size: %%~zA bytes
        echo   Modified: %%~tA
    )
    echo ----------------------------------------
) else (
    echo.
    echo [FAILED] Build failed!
)
goto end

:end
echo.
echo ========================================
echo   Done!
echo ========================================
pause
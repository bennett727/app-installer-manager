@echo off
cd /d "%~dp0"
echo ========================================
echo  Building GUI Version (Win7/Win10/Win11)
echo ========================================
echo.
echo Using Python 3.8 (supports Win7)...
rmdir /s /q dist build 2>nul
del /f /q AppInstaller.spec 2>nul
"D:\Python38\python.exe" -m PyInstaller --onefile --windowed --name AppInstaller --exclude-module win32com gui_main.py
if %errorlevel% equ 0 (
    echo.
    echo [SUCCESS] Build completed!
    echo [Location] dist\AppInstaller.exe
    echo.
    dir dist\AppInstaller.exe
) else (
    echo.
    echo [FAILED] Build failed!
)
echo.
pause
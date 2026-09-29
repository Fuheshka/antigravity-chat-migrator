@echo off
setlocal EnableDelayedExpansion
title Antigravity Chat Migrator - One-Click Fix
chcp 65001 >nul

echo ===================================================================
echo   Antigravity Chat Migrator - Diagnostic and Auto-Fix
echo ===================================================================
echo.

set "SCRIPT_DIR=%~dp0"
set "BIN_PATH=%SCRIPT_DIR%agy-migrator.exe"

if not exist "%BIN_PATH%" (
    echo [ERROR] agy-migrator.exe not found in "%SCRIPT_DIR%"
    echo Please make sure all files from the ZIP archive are extracted together.
    echo.
    pause
    exit /b 1
)

echo [1/3] Checking Antigravity / Gemini processes...
tasklist /FI "IMAGENAME eq Antigravity.exe" 2>nul | find /I /N "Antigravity.exe" >nul
if "%ERRORLEVEL%"=="0" (
    echo [WARNING] Antigravity is currently running!
    echo It is strongly recommended to close Antigravity before migrating chats.
    echo.
    set /p "CONT=Do you want to continue anyway? (y/N): "
    if /I not "!CONT!"=="y" (
        echo Operation cancelled by user.
        pause
        exit /b 0
    )
)

echo.
echo [2/3] Running diagnostic inspection (audit)...
echo.
"%BIN_PATH%" audit
echo.

echo ===================================================================
echo [3/3] Ready to execute automatic repair and project linking.
echo A safety backup of your conversation history will be created automatically.
echo ===================================================================
echo.
set /p "DO_FIX=Proceed with fix? (Y/n): "
if /I "!DO_FIX!"=="n" (
    echo Fix skipped by user. You can run agy-migrator.exe directly from cmd.
    pause
    exit /b 0
)

echo.
echo Running agy-migrator fix...
echo.
"%BIN_PATH%" fix

echo.
echo ===================================================================
echo Finished! You can now launch Antigravity and check your chats.
echo ===================================================================
echo.
pause

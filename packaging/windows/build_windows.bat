@echo off
setlocal EnableDelayedExpansion

set "SCRIPT_DIR=%~dp0"
pushd "%SCRIPT_DIR%..\.."
set "REPO_ROOT=%CD%"

echo ============================================================
echo  Antigravity Chat Migrator - Windows x64 Build Pipeline
echo ============================================================

set "CLEAN=0"
set "NOZIP=0"

:parse_args
if "%~1"=="" goto after_args
if /I "%~1"=="--clean" set "CLEAN=1"
if /I "%~1"=="/clean"  set "CLEAN=1"
if /I "%~1"=="-c"      set "CLEAN=1"
if /I "%~1"=="--nozip" set "NOZIP=1"
if /I "%~1"=="/nozip"  set "NOZIP=1"
shift
goto parse_args
:after_args

rem 1. Detect Python
set "PYTHON_BIN="
if exist "%REPO_ROOT%\.venv\Scripts\python.exe" (
    set "PYTHON_BIN=%REPO_ROOT%\.venv\Scripts\python.exe"
) else (
    where py >nul 2>nul
    if "!ERRORLEVEL!"=="0" (
        set "PYTHON_BIN=py -3"
    ) else (
        where python >nul 2>nul
        if "!ERRORLEVEL!"=="0" (
            set "PYTHON_BIN=python"
        )
    )
)

if "%PYTHON_BIN%"=="" (
    echo [ERROR] Python 3 not found on PATH or in .venv.
    popd
    exit /b 1
)

echo Using Python: %PYTHON_BIN%

rem 2. Check / Install PyInstaller ^& Pillow
%PYTHON_BIN% -c "import PyInstaller, PIL" >nul 2>nul
if not "%ERRORLEVEL%"=="0" (
    echo Installing PyInstaller and Pillow...
    %PYTHON_BIN% -m pip install --upgrade pyinstaller Pillow
    if not "!ERRORLEVEL!"=="0" (
        echo [ERROR] Failed to install dependencies.
        popd
        exit /b 1
    )
)

rem 3. Clean if requested
set "DIST_WIN=%REPO_ROOT%\dist\windows"
set "BUILD_WIN=%REPO_ROOT%\build\windows"
set "DIST_ROOT=%REPO_ROOT%\dist"

if "%CLEAN%"=="1" (
    echo Cleaning previous build artifacts...
    if exist "%DIST_WIN%" rmdir /s /q "%DIST_WIN%"
    if exist "%BUILD_WIN%" rmdir /s /q "%BUILD_WIN%"
)

if not exist "%DIST_WIN%" mkdir "%DIST_WIN%"
if not exist "%BUILD_WIN%" mkdir "%BUILD_WIN%"
if not exist "%REPO_ROOT%\packaging\assets" mkdir "%REPO_ROOT%\packaging\assets"

rem 4. Ensure AppIcon.ico and app.ico exist
set "ICO_PATH=%REPO_ROOT%\packaging\assets\AppIcon.ico"
set "APP_ICO_PATH=%REPO_ROOT%\packaging\assets\app.ico"
if not exist "%ICO_PATH%" (
    echo Generating AppIcon.ico and app.ico...
    %PYTHON_BIN% "%REPO_ROOT%\packaging\windows\generate_ico.py"
) else if not exist "%APP_ICO_PATH%" (
    echo Generating AppIcon.ico and app.ico...
    %PYTHON_BIN% "%REPO_ROOT%\packaging\windows\generate_ico.py"
)

rem 5. Run PyInstaller
echo Compiling standalone windowed binary (--noconsole) with PyInstaller...
%PYTHON_BIN% -m PyInstaller --distpath "%DIST_WIN%" --workpath "%BUILD_WIN%" --noconfirm --noconsole "%REPO_ROOT%\packaging\windows\migrator.spec"
if not "%ERRORLEVEL%"=="0" (
    echo [ERROR] PyInstaller compilation failed.
    popd
    exit /b 1
)

set "EXE_PATH=%DIST_WIN%\agy-migrator.exe"
if not exist "%EXE_PATH%" (
    echo [ERROR] Executable was not created at %EXE_PATH%
    popd
    exit /b 1
)
echo [OK] Executable compiled at %EXE_PATH%

rem 6. Package into Portable ZIP Archive
if not "%NOZIP%"=="1" (
    echo Assembling portable ZIP package...
    set "STAGING=%DIST_WIN%\staging\Antigravity-Chat-Migrator"
    if exist "%DIST_WIN%\staging" rmdir /s /q "%DIST_WIN%\staging"
    mkdir "!STAGING!"

    copy /y "%EXE_PATH%" "!STAGING!\agy-migrator.exe" >nul
    copy /y "%REPO_ROOT%\packaging\windows\run_fix.bat" "!STAGING!\run_fix.bat" >nul
    copy /y "%REPO_ROOT%\packaging\windows\README_WINDOWS.txt" "!STAGING!\README_WINDOWS.txt" >nul

    set "ZIP_PATH=%DIST_ROOT%\Antigravity-Chat-Migrator-Windows-x64.zip"
    if exist "!ZIP_PATH!" del /f /q "!ZIP_PATH!"

    where powershell >nul 2>nul
    if "!ERRORLEVEL!"=="0" (
        powershell -NoProfile -Command "Compress-Archive -Path '%DIST_WIN%\staging\*' -DestinationPath '!ZIP_PATH!' -Force"
    ) else (
        where tar >nul 2>nul
        if "!ERRORLEVEL!"=="0" (
            tar -a -c -f "!ZIP_PATH!" -C "%DIST_WIN%\staging" Antigravity-Chat-Migrator
        ) else (
            echo [WARNING] Neither PowerShell nor tar found. Could not create ZIP archive automatically.
        )
    )

    if exist "%DIST_WIN%\staging" rmdir /s /q "%DIST_WIN%\staging"

    if exist "!ZIP_PATH!" (
        echo ============================================================
        echo  Build and Packaging Complete!
        echo  Archive: !ZIP_PATH!
        echo ============================================================
    )
)

popd
exit /b 0

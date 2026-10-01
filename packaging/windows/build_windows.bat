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
set "NOSETUP=0"

:parse_args
if "%~1"=="" goto after_args
if /I "%~1"=="--clean"   set "CLEAN=1"
if /I "%~1"=="/clean"    set "CLEAN=1"
if /I "%~1"=="-c"        set "CLEAN=1"
if /I "%~1"=="--nozip"   set "NOZIP=1"
if /I "%~1"=="/nozip"    set "NOZIP=1"
if /I "%~1"=="--nosetup" set "NOSETUP=1"
if /I "%~1"=="/nosetup"  set "NOSETUP=1"
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

rem 2. Check / Install PyInstaller and Pillow
echo Checking PyInstaller and Pillow...
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

rem 3. Clean if requested and setup directories
set "DIST_WIN=%REPO_ROOT%\dist\windows"
set "BUILD_WIN=%REPO_ROOT%\build\windows"
set "DIST_ROOT=%REPO_ROOT%\dist"
set "SETUP_EXE=%DIST_ROOT%\Antigravity-Chat-Migrator-Windows-x64-Setup.exe"
set "ZIP_PATH=%DIST_ROOT%\Antigravity-Chat-Migrator-Windows-x64-Portable.zip"

if "%CLEAN%"=="1" (
    echo Cleaning previous build artifacts...
    if exist "%DIST_WIN%" rmdir /s /q "%DIST_WIN%"
    if exist "%BUILD_WIN%" rmdir /s /q "%BUILD_WIN%"
    if exist "!SETUP_EXE!" del /f /q "!SETUP_EXE!"
    if exist "!ZIP_PATH!" del /f /q "!ZIP_PATH!"
)

if not exist "%DIST_WIN%" mkdir "%DIST_WIN%"
if not exist "%BUILD_WIN%" mkdir "%BUILD_WIN%"
if not exist "%DIST_ROOT%" mkdir "%DIST_ROOT%"
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

rem 5. Run PyInstaller (Build dual binaries: GUI and CLI)
echo Compiling dual standalone binaries with PyInstaller...
%PYTHON_BIN% -m PyInstaller --distpath "%DIST_WIN%" --workpath "%BUILD_WIN%" --noconfirm "%REPO_ROOT%\packaging\windows\migrator.spec"
if not "%ERRORLEVEL%"=="0" (
    echo [ERROR] PyInstaller compilation failed.
    popd
    exit /b 1
)

set "GUI_EXE=%DIST_WIN%\Antigravity Chat Migrator.exe"
set "CLI_EXE=%DIST_WIN%\agy-migrator.exe"

if not exist "%GUI_EXE%" (
    echo [ERROR] GUI executable was not created at %GUI_EXE%
    popd
    exit /b 1
)
if not exist "%CLI_EXE%" (
    echo [ERROR] CLI executable was not created at %CLI_EXE%
    popd
    exit /b 1
)

echo [OK] GUI Executable: %GUI_EXE%
echo [OK] CLI Executable: %CLI_EXE%

rem 6. Inno Setup Compiler (ISCC.exe)
set "BUILT_INSTALLER=0"
if "%NOSETUP%"=="1" (
    echo Skipping Inno Setup installer compilation (--nosetup specified).
    goto after_iscc
)

echo Searching for Inno Setup compiler (ISCC.exe)...
set "ISCC_PATH="
where iscc >nul 2>nul
if "!ERRORLEVEL!"=="0" (
    for /f "delims=" %%I in ('where iscc') do (
        if not defined ISCC_PATH set "ISCC_PATH=%%I"
    )
)
if "!ISCC_PATH!"=="" if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" (
    set "ISCC_PATH=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
)
if "!ISCC_PATH!"=="" if exist "C:\Program Files\Inno Setup 6\ISCC.exe" (
    set "ISCC_PATH=C:\Program Files\Inno Setup 6\ISCC.exe"
)

if not "!ISCC_PATH!"=="" (
    echo Found Inno Setup compiler: !ISCC_PATH!
    echo Compiling Windows installer with Inno Setup...
    "!ISCC_PATH!" /O"%DIST_ROOT%" "%REPO_ROOT%\packaging\windows\setup.iss"
    if "!ERRORLEVEL!"=="0" (
        if not exist "!SETUP_EXE!" (
            if exist "%DIST_WIN%\Antigravity-Chat-Migrator-Windows-x64-Setup.exe" (
                move /y "%DIST_WIN%\Antigravity-Chat-Migrator-Windows-x64-Setup.exe" "!SETUP_EXE!" >nul
            )
        )
        if exist "!SETUP_EXE!" (
            echo [OK] Installer compiled at !SETUP_EXE!
            set "BUILT_INSTALLER=1"
        ) else (
            echo [WARNING] Inno Setup finished, but !SETUP_EXE! was not found.
        )
    ) else (
        echo [ERROR] Inno Setup compilation failed.
    )
) else (
    echo [WARNING] Inno Setup 6 (ISCC.exe) not found. Skipping installer build; only portable ZIP package will be created.
)
:after_iscc

rem 7. Package into Clean Portable ZIP Archive
set "BUILT_ZIP=0"
if "%NOZIP%"=="1" goto after_zip

echo Assembling portable ZIP package...
set "STAGING=%DIST_WIN%\staging\Antigravity-Chat-Migrator"
if exist "%DIST_WIN%\staging" rmdir /s /q "%DIST_WIN%\staging"
mkdir "!STAGING!"

copy /y "%GUI_EXE%" "!STAGING!\Antigravity Chat Migrator.exe" >nul
copy /y "%CLI_EXE%" "!STAGING!\agy-migrator.exe" >nul
copy /y "%REPO_ROOT%\packaging\windows\run_fix.bat" "!STAGING!\run_fix.bat" >nul
copy /y "%REPO_ROOT%\packaging\windows\README_WINDOWS.txt" "!STAGING!\README_WINDOWS.txt" >nul

if exist "!ZIP_PATH!" del /f /q "!ZIP_PATH!"

where powershell >nul 2>nul
if "!ERRORLEVEL!"=="0" (
    powershell -NoProfile -Command "Compress-Archive -Path '%DIST_WIN%\staging\Antigravity-Chat-Migrator' -DestinationPath '!ZIP_PATH!' -Force"
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
    echo [OK] Portable ZIP created at !ZIP_PATH!
    set "BUILT_ZIP=1"
)
:after_zip

rem 8. SHA256 Checksums
echo ============================================================
echo  Windows Build and Packaging Complete!
echo ============================================================
echo  GUI Executable: %GUI_EXE%
echo  CLI Executable: %CLI_EXE%

where powershell >nul 2>nul
if "!ERRORLEVEL!"=="0" (
    echo.
    echo Distribution Packages and SHA256 Checksums:
    if "!BUILT_INSTALLER!"=="1" if exist "!SETUP_EXE!" (
        powershell -NoProfile -Command "Write-Host '  * Antigravity-Chat-Migrator-Windows-x64-Setup.exe:' (Get-FileHash -Path '!SETUP_EXE!' -Algorithm SHA256).Hash"
    )
    if "!BUILT_ZIP!"=="1" if exist "!ZIP_PATH!" (
        powershell -NoProfile -Command "Write-Host '  * Antigravity-Chat-Migrator-Windows-x64-Portable.zip:' (Get-FileHash -Path '!ZIP_PATH!' -Algorithm SHA256).Hash"
    )
) else (
    where certutil >nul 2>nul
    if "!ERRORLEVEL!"=="0" (
        echo.
        echo Distribution Packages and SHA256 Checksums:
        if "!BUILT_INSTALLER!"=="1" if exist "!SETUP_EXE!" (
            echo   * Antigravity-Chat-Migrator-Windows-x64-Setup.exe:
            certutil -hashfile "!SETUP_EXE!" SHA256 | findstr /V ":"
        )
        if "!BUILT_ZIP!"=="1" if exist "!ZIP_PATH!" (
            echo   * Antigravity-Chat-Migrator-Windows-x64-Portable.zip:
            certutil -hashfile "!ZIP_PATH!" SHA256 | findstr /V ":"
        )
    )
)
echo ============================================================

popd
exit /b 0

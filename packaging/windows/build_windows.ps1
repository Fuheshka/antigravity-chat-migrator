<#
.SYNOPSIS
    Antigravity Chat Migrator - Windows Build & Packaging Pipeline (PowerShell)
.DESCRIPTION
    Compiles dual standalone binaries (GUI & CLI) using PyInstaller, compiles
    the Inno Setup installer (ISCC.exe) if available, packages the clean portable
    ZIP distribution, and computes SHA256 checksums.
.PARAMETER Clean
    Clean build and dist directories before compiling.
.PARAMETER NoZip
    Skip creating the portable ZIP distribution archive.
.PARAMETER NoSetup
    Skip compiling the Inno Setup installer even if ISCC.exe is available.
#>

[CmdletBinding()]
param (
    [switch]$Clean,
    [switch]$NoZip,
    [switch]$NoSetup
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = (Resolve-Path "$ScriptDir\..\..").Path
Set-Location -Path $RepoRoot

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " Antigravity Chat Migrator - Windows x64 Build Pipeline" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# 1. Detect Python Environment
$PythonBin = ""
$VenvPy = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (Test-Path $VenvPy) {
    $PythonBin = $VenvPy
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $PythonBin = "py"
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $PythonBin = "python"
} else {
    Write-Error "Python 3 was not found on PATH or in .venv. Please install Python 3.10+ (x64)."
}

Write-Host "Using Python: $PythonBin" -ForegroundColor Green

# 2. Check / Install PyInstaller & Pillow
Write-Host "--> Checking PyInstaller and Pillow..." -ForegroundColor Yellow
$CheckPyi = & $PythonBin -c "import PyInstaller, PIL" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Installing PyInstaller and Pillow..." -ForegroundColor Yellow
    & $PythonBin -m pip install --upgrade pyinstaller Pillow
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to install PyInstaller or Pillow."
    }
}

# 3. Clean if requested
$DistWin = Join-Path $RepoRoot "dist\windows"
$BuildWin = Join-Path $RepoRoot "build\windows"
$DistRoot = Join-Path $RepoRoot "dist"
$SetupExe = Join-Path $DistRoot "Antigravity-Chat-Migrator-Windows-x64-Setup.exe"
$ZipPath = Join-Path $DistRoot "Antigravity-Chat-Migrator-Windows-x64-Portable.zip"

if ($Clean) {
    Write-Host "--> Cleaning previous build artifacts..." -ForegroundColor Yellow
    if (Test-Path $DistWin) { Remove-Item -Recurse -Force $DistWin }
    if (Test-Path $BuildWin) { Remove-Item -Recurse -Force $BuildWin }
    if (Test-Path $SetupExe) { Remove-Item -Force $SetupExe }
    if (Test-Path $ZipPath) { Remove-Item -Force $ZipPath }
}

New-Item -ItemType Directory -Force -Path $DistWin | Out-Null
New-Item -ItemType Directory -Force -Path $BuildWin | Out-Null
New-Item -ItemType Directory -Force -Path $DistRoot | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $RepoRoot "packaging\assets") | Out-Null

# 4. Ensure AppIcon.ico and app.ico exist and are up to date
$IcoPath = Join-Path $RepoRoot "packaging\assets\AppIcon.ico"
$AppIcoPath = Join-Path $RepoRoot "packaging\assets\app.ico"
$PngPath = Join-Path $RepoRoot "packaging\assets\AppIcon.png"

$NeedsGen = (-not (Test-Path $IcoPath)) -or (-not (Test-Path $AppIcoPath))
if (-not $NeedsGen -and (Test-Path $PngPath)) {
    if ((Get-Item $PngPath).LastWriteTime -gt (Get-Item $IcoPath).LastWriteTime) {
        $NeedsGen = $true
    }
}

if ($NeedsGen) {
    Write-Host "--> Generating Windows AppIcon.ico & app.ico from AppIcon.png..." -ForegroundColor Yellow
    & $PythonBin (Join-Path $RepoRoot "packaging\windows\generate_ico.py")
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to generate ICO files."
    }
}

# 5. Run PyInstaller (compile dual binaries: GUI and CLI)
Write-Host "--> Compiling standalone binaries with PyInstaller (GUI & CLI)..." -ForegroundColor Yellow
$SpecPath = Join-Path $RepoRoot "packaging\windows\migrator.spec"
& $PythonBin -m PyInstaller --distpath $DistWin --workpath $BuildWin --noconfirm $SpecPath
if ($LASTEXITCODE -ne 0) {
    Write-Error "PyInstaller compilation failed."
}

$GuiExe = Join-Path $DistWin "Antigravity Chat Migrator.exe"
$CliExe = Join-Path $DistWin "agy-migrator.exe"

if (-not (Test-Path $GuiExe)) {
    Write-Error "Build failed: GUI executable not found at $GuiExe"
}
if (-not (Test-Path $CliExe)) {
    Write-Error "Build failed: CLI executable not found at $CliExe"
}

$GuiSizeMB = [math]::Round(((Get-Item $GuiExe).Length / 1MB), 2)
$CliSizeMB = [math]::Round(((Get-Item $CliExe).Length / 1MB), 2)
Write-Host "--> GUI binary compiled: $GuiExe ($GuiSizeMB MB)" -ForegroundColor Green
Write-Host "--> CLI binary compiled: $CliExe ($CliSizeMB MB)" -ForegroundColor Green

# 6. Inno Setup Compiler (ISCC.exe)
$BuiltInstaller = $false
if ($NoSetup) {
    Write-Host "--> Skipping Inno Setup installer compilation (-NoSetup specified)." -ForegroundColor Yellow
} else {
    Write-Host "--> Searching for Inno Setup compiler (ISCC.exe)..." -ForegroundColor Yellow
    $IsccBin = ""
    $IsccCmd = Get-Command iscc -ErrorAction SilentlyContinue
    if ($IsccCmd) {
        $IsccBin = $IsccCmd.Source
    } else {
        $DefaultPaths = @(
            "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
            "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
            "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
            "C:\Program Files\Inno Setup 6\ISCC.exe"
        )
        foreach ($p in $DefaultPaths) {
            if ($p -and (Test-Path $p)) {
                $IsccBin = $p
                break
            }
        }
    }

    if ($IsccBin) {
        Write-Host "Found Inno Setup compiler: $IsccBin" -ForegroundColor Green
        Write-Host "--> Compiling Windows installer with Inno Setup..." -ForegroundColor Yellow
        $IssPath = Join-Path $RepoRoot "packaging\windows\setup.iss"
        & $IsccBin "/O$DistRoot" $IssPath
        if ($LASTEXITCODE -ne 0) {
            Write-Error "Inno Setup compilation failed with exit code $LASTEXITCODE."
        }

        # Verify output in DistRoot or fallback from DistWin
        $SetupExeWin = Join-Path $DistWin "Antigravity-Chat-Migrator-Windows-x64-Setup.exe"
        if (-not (Test-Path $SetupExe) -and (Test-Path $SetupExeWin)) {
            Move-Item -Force $SetupExeWin $SetupExe
        }

        if (Test-Path $SetupExe) {
            $SetupSizeMB = [math]::Round(((Get-Item $SetupExe).Length / 1MB), 2)
            Write-Host "--> Windows installer successfully compiled: $SetupExe ($SetupSizeMB MB)" -ForegroundColor Green
            $BuiltInstaller = $true
        } else {
            Write-Warning "Inno Setup completed, but output executable was not found at $SetupExe"
        }
    } else {
        Write-Warning "Inno Setup 6 (ISCC.exe) not found on PATH or in standard directories. Skipping installer build; only portable ZIP package will be created."
    }
}

# 7. Package Portable ZIP Archive
$BuiltZip = $false
if (-not $NoZip) {
    Write-Host "--> Assembling clean portable ZIP package..." -ForegroundColor Yellow
    $StagingRoot = Join-Path $DistWin "staging"
    $StagingDir = Join-Path $StagingRoot "Antigravity-Chat-Migrator"
    if (Test-Path $StagingRoot) { Remove-Item -Recurse -Force $StagingRoot }
    New-Item -ItemType Directory -Force -Path $StagingDir | Out-Null

    Copy-Item $GuiExe -Destination (Join-Path $StagingDir "Antigravity Chat Migrator.exe")
    Copy-Item $CliExe -Destination (Join-Path $StagingDir "agy-migrator.exe")
    Copy-Item (Join-Path $RepoRoot "packaging\windows\run_fix.bat") -Destination (Join-Path $StagingDir "run_fix.bat")
    Copy-Item (Join-Path $RepoRoot "packaging\windows\README_WINDOWS.txt") -Destination (Join-Path $StagingDir "README_WINDOWS.txt")

    if (Test-Path $ZipPath) { Remove-Item -Force $ZipPath }

    Compress-Archive -Path $StagingDir -DestinationPath $ZipPath -Force
    Remove-Item -Recurse -Force $StagingRoot

    if (Test-Path $ZipPath) {
        $ZipSizeMB = [math]::Round(((Get-Item $ZipPath).Length / 1MB), 2)
        Write-Host "--> Portable ZIP package created: $ZipPath ($ZipSizeMB MB)" -ForegroundColor Green
        $BuiltZip = $true
    } else {
        Write-Error "Failed to create portable ZIP archive at $ZipPath"
    }
}

# 8. Summary & SHA256 Checksums
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " Windows Build & Packaging Summary" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " GUI Executable: $GuiExe ($GuiSizeMB MB)" -ForegroundColor White
Write-Host " CLI Executable: $CliExe ($CliSizeMB MB)" -ForegroundColor White

$Artifacts = @()
if ($BuiltInstaller -and (Test-Path $SetupExe)) {
    $Artifacts += $SetupExe
}
if ($BuiltZip -and (Test-Path $ZipPath)) {
    $Artifacts += $ZipPath
}

if ($Artifacts.Count -gt 0) {
    Write-Host "`nDistribution Packages & SHA256 Checksums:" -ForegroundColor Green
    foreach ($art in $Artifacts) {
        $artName = Split-Path -Leaf $art
        $artSize = [math]::Round(((Get-Item $art).Length / 1MB), 2)
        $hash = (Get-FileHash -Path $art -Algorithm SHA256).Hash
        Write-Host "  * $artName ($artSize MB)" -ForegroundColor Yellow
        Write-Host "    SHA256: $hash" -ForegroundColor DarkGray
    }
}
Write-Host "============================================================" -ForegroundColor Cyan

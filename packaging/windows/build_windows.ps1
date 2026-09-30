<#
.SYNOPSIS
    Antigravity Chat Migrator - Windows Build & Packaging Pipeline (PowerShell)
.DESCRIPTION
    Builds standalone agy-migrator.exe using PyInstaller and packages it with
    helper scripts into a portable ZIP distribution: Antigravity-Chat-Migrator-Windows-x64.zip
.PARAMETER Clean
    Clean build and dist directories before compiling.
.PARAMETER NoZip
    Compile executable only; skip creating the ZIP distribution archive.
#>

[CmdletBinding()]
param (
    [switch]$Clean,
    [switch]$NoZip
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

# 2. Check / Install PyInstaller & Dependencies
Write-Host "--> Checking PyInstaller and Pillow..." -ForegroundColor Yellow
$CheckPyi = & $PythonBin -c "import PyInstaller, PIL" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Installing PyInstaller and Pillow..." -ForegroundColor Yellow
    & $PythonBin -m pip install --upgrade pyinstaller Pillow
}

# 3. Clean if requested
$DistWin = Join-Path $RepoRoot "dist\windows"
$BuildWin = Join-Path $RepoRoot "build\windows"
$DistRoot = Join-Path $RepoRoot "dist"

if ($Clean) {
    Write-Host "--> Cleaning previous build artifacts..." -ForegroundColor Yellow
    if (Test-Path $DistWin) { Remove-Item -Recurse -Force $DistWin }
    if (Test-Path $BuildWin) { Remove-Item -Recurse -Force $BuildWin }
}

New-Item -ItemType Directory -Force -Path $DistWin | Out-Null
New-Item -ItemType Directory -Force -Path $BuildWin | Out-Null
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
}

# 5. Run PyInstaller
Write-Host "--> Compiling standalone windowed binary (--noconsole) with PyInstaller..." -ForegroundColor Yellow
$SpecPath = Join-Path $RepoRoot "packaging\windows\migrator.spec"
& $PythonBin -m PyInstaller --distpath $DistWin --workpath $BuildWin --noconfirm --noconsole $SpecPath

$ExePath = Join-Path $DistWin "agy-migrator.exe"
if (-not (Test-Path $ExePath)) {
    Write-Error "Build failed: $ExePath does not exist."
}

$ExeSizeMB = [math]::Round(((Get-Item $ExePath).Length / 1MB), 2)
Write-Host "--> Executable successfully compiled: $ExePath ($ExeSizeMB MB)" -ForegroundColor Green

# 6. Package into Portable ZIP Archive
if (-not $NoZip) {
    Write-Host "--> Assembling portable ZIP package..." -ForegroundColor Yellow
    $StagingDir = Join-Path $DistWin "staging\Antigravity-Chat-Migrator"
    if (Test-Path $StagingDir) { Remove-Item -Recurse -Force $StagingDir }
    New-Item -ItemType Directory -Force -Path $StagingDir | Out-Null

    Copy-Item $ExePath -Destination (Join-Path $StagingDir "agy-migrator.exe")
    Copy-Item (Join-Path $RepoRoot "packaging\windows\run_fix.bat") -Destination (Join-Path $StagingDir "run_fix.bat")
    Copy-Item (Join-Path $RepoRoot "packaging\windows\README_WINDOWS.txt") -Destination (Join-Path $StagingDir "README_WINDOWS.txt")

    $ZipPath = Join-Path $DistRoot "Antigravity-Chat-Migrator-Windows-x64.zip"
    if (Test-Path $ZipPath) { Remove-Item -Force $ZipPath }

    Compress-Archive -Path "$StagingDir\*" -DestinationPath $ZipPath -Force
    Remove-Item -Recurse -Force (Join-Path $DistWin "staging")

    $ZipSizeMB = [math]::Round(((Get-Item $ZipPath).Length / 1MB), 2)
    $Hash = (Get-FileHash -Path $ZipPath -Algorithm SHA256).Hash

    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host " Build Complete!" -ForegroundColor Green
    Write-Host " Executable: $ExePath" -ForegroundColor White
    Write-Host " ZIP Package: $ZipPath ($ZipSizeMB MB)" -ForegroundColor White
    Write-Host " SHA256:     $Hash" -ForegroundColor DarkGray
    Write-Host "============================================================" -ForegroundColor Cyan
}

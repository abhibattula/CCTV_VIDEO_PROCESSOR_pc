<#
.SYNOPSIS
    Build the Linux x86_64 AppImage using Docker on Windows.

.DESCRIPTION
    Checks Docker Desktop prerequisites, builds the Linux Docker image (using the
    two-stage base image for fast rebuilds), runs the container with a dist/ bind-mount,
    and verifies the artifact is produced.

.PARAMETER Version
    Semver version string (e.g. 1.0.0). Defaults to the contents of the VERSION file
    at the repository root.

.PARAMETER RebuildBase
    Force rebuild of cctv-linux-base:latest even if it already exists locally.

.EXAMPLE
    build/docker/build_linux.ps1 -Version 1.0.0
    build/docker/build_linux.ps1 -RebuildBase
#>
param(
    [string]$Version = "",
    [switch]$RebuildBase
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Resolve script directory and project root
$ScriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $ScriptDir "..\..") | Select-Object -ExpandProperty Path

# Read version from VERSION file if not provided
if (-not $Version) {
    $VersionFile = Join-Path $ProjectRoot "VERSION"
    if (-not (Test-Path $VersionFile)) {
        Write-Error "VERSION file not found at $VersionFile. Create it or pass -Version x.y.z."
        exit 1
    }
    $Version = (Get-Content $VersionFile -Raw).Trim()
}

Write-Host "[Linux] Building CCTV Processor v$Version AppImage..." -ForegroundColor Cyan

# Prerequisite 1: Docker Desktop running
Write-Host "[Linux] Checking Docker Desktop..." -NoNewline
$dockerInfo = docker info 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host " FAILED" -ForegroundColor Red
    Write-Error @"
ERROR: Docker Desktop is not running.
Please start Docker Desktop (https://www.docker.com/products/docker-desktop/)
and ensure it is in Linux containers mode, then retry.
"@
    exit 2
}
Write-Host " OK" -ForegroundColor Green

# Prerequisite 2: Linux containers mode
$dockerOS = docker info --format "{{.OperatingSystem}}" 2>&1
if ($dockerOS -match "Windows") {
    Write-Error @"
ERROR: Docker Desktop is in Windows containers mode.
Switch to Linux containers: right-click the Docker icon in the system tray
→ "Switch to Linux containers..." then retry.
"@
    exit 1
}

# Ensure dist/ exists for bind-mount
$DistDir = Join-Path $ProjectRoot "dist"
New-Item -ItemType Directory -Force $DistDir | Out-Null

# Build or reuse base image
$baseExists = (docker images -q cctv-linux-base:latest 2>&1) -ne ""
if ($RebuildBase -or -not $baseExists) {
    Write-Host "[Linux] Building base image (cctv-linux-base:latest)..." -ForegroundColor Yellow
    Write-Host "[Linux]   This takes 45-60 min on first run; cached on subsequent runs."
    Push-Location $ProjectRoot
    docker build -f "build/docker/Dockerfile.linux-base" -t "cctv-linux-base:latest" .
    Pop-Location
    if ($LASTEXITCODE -ne 0) {
        Write-Error "ERROR: Linux base image build failed."
        exit 1
    }
} else {
    Write-Host "[Linux] Using cached base image cctv-linux-base:latest." -ForegroundColor Green
}

# Build the source image
Write-Host "[Linux] Building source image (cctv-linux-build:latest)..."
Push-Location $ProjectRoot
docker build -f "build/docker/Dockerfile.linux" -t "cctv-linux-build:latest" .
Pop-Location
if ($LASTEXITCODE -ne 0) {
    Write-Error "ERROR: Linux build image failed."
    exit 1
}

# Run container — artifacts written to dist/ via bind-mount
Write-Host "[Linux] Running build container..."
$DistPath = $DistDir.Replace('\', '/')
docker run --rm `
    -e "APP_VERSION=$Version" `
    -v "${DistPath}:/output" `
    "cctv-linux-build:latest"
if ($LASTEXITCODE -ne 0) {
    Write-Error "ERROR: Linux container build failed. Check output above."
    exit 1
}

# Verify artifact
$Artifact = Join-Path $DistDir "CCTV-Processor-$Version-linux-x86_64.AppImage"
if (-not (Test-Path $Artifact)) {
    Write-Error "ERROR: Expected artifact not found: $Artifact"
    exit 1
}
$SizeMB = [math]::Round((Get-Item $Artifact).Length / 1MB, 1)
Write-Host "[Linux] SUCCESS → dist/CCTV-Processor-$Version-linux-x86_64.AppImage ($SizeMB MB)" -ForegroundColor Green

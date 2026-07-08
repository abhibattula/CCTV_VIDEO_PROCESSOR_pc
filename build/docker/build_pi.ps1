<#
.SYNOPSIS
    Build the Raspberry Pi ARM64 .deb using Docker + QEMU emulation on Windows.

.DESCRIPTION
    Checks Docker Desktop prerequisites, registers QEMU binfmt for ARM64 if needed,
    builds the Pi Docker image (two-stage for fast rebuilds), runs the ARM64 container
    with a dist/ bind-mount, and verifies the artifact.

.PARAMETER Version
    Semver version string (e.g. 1.0.0). Defaults to the contents of the VERSION file.

.PARAMETER RebuildBase
    Force rebuild of cctv-pi-base:latest even if it already exists locally.

.PARAMETER SkipQemuCheck
    Skip the QEMU binfmt registration check (use if already registered and check is slow).

.EXAMPLE
    build/docker/build_pi.ps1 -Version 1.0.0
    build/docker/build_pi.ps1 -RebuildBase
    build/docker/build_pi.ps1 -SkipQemuCheck
#>
param(
    [string]$Version = "",
    [switch]$RebuildBase,
    [switch]$SkipQemuCheck
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ScriptDir   = Split-Path -Parent $MyInvocation.MyCommand.Path
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

Write-Host "[Pi] Building CCTV Processor v$Version ARM64 .deb..." -ForegroundColor Cyan

# Prerequisite 1: Docker Desktop running
Write-Host "[Pi] Checking Docker Desktop..." -NoNewline
docker info 2>&1 | Out-Null
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

# Prerequisite 3: QEMU ARM64 binfmt registration
if (-not $SkipQemuCheck) {
    Write-Host "[Pi] Checking QEMU ARM64 binfmt..." -NoNewline
    $buildxOut = docker buildx inspect --bootstrap 2>&1 | Out-String
    if ($buildxOut -notmatch "linux/arm64") {
        Write-Host " not registered, registering now..." -ForegroundColor Yellow
        docker run --privileged --rm tonistiigi/binfmt --install arm64
        if ($LASTEXITCODE -ne 0) {
            Write-Error "ERROR: QEMU binfmt registration failed. Check Docker Desktop and network access."
            exit 1
        }
        # Re-verify
        $buildxOut2 = docker buildx inspect --bootstrap 2>&1 | Out-String
        if ($buildxOut2 -notmatch "linux/arm64") {
            Write-Error "ERROR: QEMU arm64 still not available after registration. Restart Docker Desktop and retry."
            exit 1
        }
        Write-Host "[Pi] QEMU ARM64 registered." -ForegroundColor Green
    } else {
        Write-Host " OK" -ForegroundColor Green
    }
}

# Ensure dist/ exists for bind-mount
$DistDir = Join-Path $ProjectRoot "dist"
New-Item -ItemType Directory -Force $DistDir | Out-Null

# Build or reuse Pi base image
$baseExists = (docker images -q cctv-pi-base:latest 2>&1) -ne ""
if ($RebuildBase -or -not $baseExists) {
    Write-Host "[Pi] Building Pi base image (cctv-pi-base:latest)..." -ForegroundColor Yellow
    Write-Host "[Pi]   This takes 60-90 min on first run (QEMU ARM64 emulation)."
    Push-Location $ProjectRoot
    docker build --platform linux/arm64 `
        -f "build/docker/Dockerfile.pi-base" `
        -t "cctv-pi-base:latest" .
    Pop-Location
    if ($LASTEXITCODE -ne 0) {
        Write-Error "ERROR: Pi base image build failed."
        exit 1
    }
} else {
    Write-Host "[Pi] Using cached base image cctv-pi-base:latest." -ForegroundColor Green
}

# Build the Pi source image
Write-Host "[Pi] Building Pi source image (cctv-pi-build:latest)..."
Push-Location $ProjectRoot
docker build --platform linux/arm64 `
    -f "build/docker/Dockerfile.pi" `
    -t "cctv-pi-build:latest" .
Pop-Location
if ($LASTEXITCODE -ne 0) {
    Write-Error "ERROR: Pi build image failed."
    exit 1
}

# Run container — artifacts written to dist/ via bind-mount
Write-Host "[Pi] Running ARM64 build container (QEMU emulation — may take 15-30 min)..."
$DistPath = $DistDir.Replace('\', '/')
docker run --rm --platform linux/arm64 `
    -e "APP_VERSION=$Version" `
    -v "${DistPath}:/output" `
    "cctv-pi-build:latest"
if ($LASTEXITCODE -ne 0) {
    Write-Error "ERROR: Pi container build failed. Check output above."
    exit 1
}

# Verify artifact
$Artifact = Join-Path $DistDir "CCTV-Processor-$Version-pi-arm64.deb"
if (-not (Test-Path $Artifact)) {
    Write-Error "ERROR: Expected artifact not found: $Artifact"
    exit 1
}
$SizeMB = [math]::Round((Get-Item $Artifact).Length / 1MB, 1)
Write-Host "[Pi] SUCCESS → dist/CCTV-Processor-$Version-pi-arm64.deb ($SizeMB MB)" -ForegroundColor Green

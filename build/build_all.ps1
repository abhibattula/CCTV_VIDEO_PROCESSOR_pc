<#
.SYNOPSIS
    Build all CCTV Video Processor platform installers from Windows.

.DESCRIPTION
    Orchestrates the complete cross-platform build pipeline:
      1. Windows x64  — PyInstaller + Inno Setup (runs locally)
      2. Linux x86_64 — Docker Desktop (builds AppImage inside Ubuntu 22.04)
      3. Pi ARM64     — Docker Desktop + QEMU (builds .deb inside arm64v8/Ubuntu 22.04)
      4. macOS        — GitHub Actions only; prints instructions for tag push

    All artifacts land in dist/ with consistent naming:
      CCTV-Processor-{version}-win64-setup.exe
      CCTV-Processor-{version}-linux-x86_64.AppImage
      CCTV-Processor-{version}-pi-arm64.deb

.PARAMETER Version
    Semver string (e.g. 1.0.0). Defaults to the VERSION file at the project root.

.PARAMETER SkipWindows
    Skip the Windows PyInstaller + Inno Setup build.

.PARAMETER SkipLinux
    Skip the Linux Docker build.

.PARAMETER SkipPi
    Skip the Pi Docker build.

.PARAMETER RebuildBase
    Force rebuild of both Docker base images (cctv-linux-base, cctv-pi-base).

.EXAMPLE
    build/build_all.ps1
    build/build_all.ps1 -Version 1.2.0 -SkipPi
    build/build_all.ps1 -RebuildBase
#>
param(
    [string]$Version     = "",
    [switch]$SkipWindows,
    [switch]$SkipLinux,
    [switch]$SkipPi,
    [switch]$RebuildBase
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ScriptDir   = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $ScriptDir "..") | Select-Object -ExpandProperty Path

# Read version from VERSION file if not provided
if (-not $Version) {
    $VersionFile = Join-Path $ProjectRoot "VERSION"
    if (-not (Test-Path $VersionFile)) {
        Write-Error "VERSION file not found at $VersionFile. Create it or pass -Version x.y.z."
        exit 1
    }
    $Version = (Get-Content $VersionFile -Raw).Trim()
}

$StartTime = Get-Date
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  CCTV Video Processor — Full Platform Build v$Version" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

$Results = [ordered]@{
    Windows = $null
    Linux   = $null
    Pi      = $null
    macOS   = "CI (see below)"
}

# ── Step 1: Windows ───────────────────────────────────────────────────────────
if (-not $SkipWindows) {
    Write-Host "[ 1/4 ] Windows x64 build..." -ForegroundColor Yellow
    try {
        Push-Location $ProjectRoot

        # PyInstaller
        python -m PyInstaller build/cctv_processor_windows.spec `
            --distpath dist --workpath build/work --noconfirm
        if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }

        # Inno Setup — try ISCC in PATH or standard install locations
        # (winget installs per-user under LOCALAPPDATA\Programs)
        $ISCC = $null
        foreach ($candidate in @(
            "ISCC.exe",
            "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
            "C:\Program Files\Inno Setup 6\ISCC.exe",
            "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
        )) {
            if (Get-Command $candidate -ErrorAction SilentlyContinue) {
                $ISCC = $candidate; break
            }
        }

        if ($ISCC) {
            & $ISCC /DAppVersion=$Version build\windows\installer.iss
            if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed" }
            $ExePath = Join-Path $ProjectRoot "dist\CCTV-Processor-$Version-win64-setup.exe"
            if (Test-Path $ExePath) {
                $Results.Windows = $ExePath
                Write-Host "[ 1/4 ] Windows: OK → dist/CCTV-Processor-$Version-win64-setup.exe" -ForegroundColor Green
            } else {
                Write-Warning "[ 1/4 ] Windows: PyInstaller OK, but installer .exe not found. Check Inno Setup output."
                $Results.Windows = "PyInstaller OK; installer .exe not found"
            }
        } else {
            Write-Warning "[ 1/4 ] Windows: PyInstaller OK. Inno Setup not found — skipping .exe packaging."
            Write-Warning "         Install from: https://jrsoftware.org/isdl.php"
            $Results.Windows = "PyInstaller OK; Inno Setup not installed"
        }
        Pop-Location
    } catch {
        Pop-Location
        Write-Warning "[ 1/4 ] Windows FAILED: $_"
        $Results.Windows = "FAILED: $_"
    }
} else {
    Write-Host "[ 1/4 ] Windows: SKIPPED (-SkipWindows)" -ForegroundColor DarkGray
    $Results.Windows = "SKIPPED"
}

# ── Step 2: Linux via Docker ──────────────────────────────────────────────────
if (-not $SkipLinux) {
    Write-Host "[ 2/4 ] Linux x86_64 AppImage via Docker..." -ForegroundColor Yellow
    try {
        $BuildLinux = Join-Path $ProjectRoot "build\docker\build_linux.ps1"
        $RebuildArg = if ($RebuildBase) { @("-RebuildBase") } else { @() }
        & powershell -NonInteractive -File $BuildLinux -Version $Version @RebuildArg
        if ($LASTEXITCODE -ne 0) { throw "build_linux.ps1 exited with code $LASTEXITCODE" }
        $AppImage = Join-Path $ProjectRoot "dist\CCTV-Processor-$Version-linux-x86_64.AppImage"
        $Results.Linux = if (Test-Path $AppImage) { $AppImage } else { "FAILED: artifact not found" }
        Write-Host "[ 2/4 ] Linux: OK → dist/CCTV-Processor-$Version-linux-x86_64.AppImage" -ForegroundColor Green
    } catch {
        Write-Warning "[ 2/4 ] Linux FAILED: $_"
        $Results.Linux = "FAILED: $_"
    }
} else {
    Write-Host "[ 2/4 ] Linux: SKIPPED (-SkipLinux)" -ForegroundColor DarkGray
    $Results.Linux = "SKIPPED"
}

# ── Step 3: Pi via Docker + QEMU ─────────────────────────────────────────────
if (-not $SkipPi) {
    Write-Host "[ 3/4 ] Raspberry Pi ARM64 .deb via Docker + QEMU (slow)..." -ForegroundColor Yellow
    try {
        $BuildPi  = Join-Path $ProjectRoot "build\docker\build_pi.ps1"
        $RebuildArg = if ($RebuildBase) { @("-RebuildBase") } else { @() }
        & powershell -NonInteractive -File $BuildPi -Version $Version @RebuildArg
        if ($LASTEXITCODE -ne 0) { throw "build_pi.ps1 exited with code $LASTEXITCODE" }
        $Deb = Join-Path $ProjectRoot "dist\CCTV-Processor-$Version-pi-arm64.deb"
        $Results.Pi = if (Test-Path $Deb) { $Deb } else { "FAILED: artifact not found" }
        Write-Host "[ 3/4 ] Pi:    OK → dist/CCTV-Processor-$Version-pi-arm64.deb" -ForegroundColor Green
    } catch {
        Write-Warning "[ 3/4 ] Pi FAILED: $_"
        $Results.Pi = "FAILED: $_"
    }
} else {
    Write-Host "[ 3/4 ] Pi: SKIPPED (-SkipPi)" -ForegroundColor DarkGray
    $Results.Pi = "SKIPPED"
}

# ── Step 4: macOS (instructions only) ────────────────────────────────────────
Write-Host "[ 4/4 ] macOS — GitHub Actions only" -ForegroundColor DarkGray

# ── Summary ───────────────────────────────────────────────────────────────────
$Elapsed = [math]::Round(((Get-Date) - $StartTime).TotalMinutes, 1)
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Build Summary — v$Version ($Elapsed min total)" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

foreach ($platform in $Results.Keys) {
    $r = $Results[$platform]
    if ($r -eq "SKIPPED") {
        Write-Host ("  {0,-10} SKIPPED" -f $platform) -ForegroundColor DarkGray
    } elseif ($r -like "FAILED:*") {
        Write-Host ("  {0,-10} FAILED" -f $platform) -ForegroundColor Red
        Write-Host ("             {0}" -f $r) -ForegroundColor Red
    } else {
        Write-Host ("  {0,-10} OK → {1}" -f $platform, $r) -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "  macOS    Push tag v$Version to GitHub → Actions builds .dmg automatically:" -ForegroundColor DarkGray
Write-Host "             git tag v$Version && git push origin v$Version" -ForegroundColor DarkGray
Write-Host ""

# Exit non-zero if any platform failed
$Failed = $Results.Values | Where-Object { $_ -like "FAILED:*" }
if ($Failed) { exit 1 }

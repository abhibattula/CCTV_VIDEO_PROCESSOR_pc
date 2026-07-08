# Quickstart: Cross-Platform Builds from Windows

**Feature**: 013-docker-platform-builds | **Date**: 2026-07-01

All scenarios run from the repo root on a Windows 11 PC. Docker Desktop must be installed
with Linux containers mode enabled for scenarios 3–5.

---

## Scenario 1 — VERSION File Present

**Prerequisite**: Repo root contains a `VERSION` file.

```powershell
Get-Content VERSION
# Expected output: 1.0.0
```

**Pass**: Outputs a valid semver string.

---

## Scenario 2 — Windows Build (PyInstaller)

**Prerequisite**: Python 3.12 + PyInstaller 6.x installed on Windows.

```powershell
python -m PyInstaller build/cctv_processor_windows.spec --distpath dist --workpath build/work --noconfirm
```

**Pass**: `dist/CCTV-Video-Processor/CCTV-Video-Processor.exe` exists and is > 10 MB.

---

## Scenario 3 — Windows Installer (Inno Setup)

**Prerequisite**: Inno Setup 6.x installed; Scenario 2 complete.

```powershell
iscc build/windows/installer.iss /DAppVersion=1.0.0
```

**Pass**: `dist/CCTV-Processor-1.0.0-win64-setup.exe` exists.

---

## Scenario 4 — Docker Mode Check

**Prerequisite**: Docker Desktop running in Linux containers mode.

```powershell
docker info --format "{{.OperatingSystem}}"
# Must NOT output "Windows"
```

**Pass**: Output is `Docker Desktop` or `linux` (not `Windows`).

---

## Scenario 5 — Linux Base Image Build

**Prerequisite**: Docker Desktop in Linux containers mode.

```powershell
docker build -f build/docker/Dockerfile.linux-base -t cctv-linux-base:latest .
```

**Pass**: Build completes with exit code 0. May take 45–60 min on first run.

---

## Scenario 6 — Linux AppImage Build

**Prerequisite**: Scenario 5 complete (base image cached).

```powershell
build/docker/build_linux.ps1 -Version 1.0.0
```

**Pass**: `dist/CCTV-Processor-1.0.0-linux-x86_64.AppImage` exists and is > 50 MB.

---

## Scenario 7 — QEMU binfmt Registration

**Prerequisite**: Docker Desktop running.

```powershell
docker run --privileged --rm tonistiigi/binfmt --install arm64
docker buildx inspect --bootstrap
# Output must contain: linux/arm64
```

**Pass**: `linux/arm64` appears in `docker buildx inspect` output.

---

## Scenario 8 — Pi Base Image Build

**Prerequisite**: Scenario 7 complete (QEMU registered).

```powershell
docker build --platform linux/arm64 -f build/docker/Dockerfile.pi-base -t cctv-pi-base:latest .
```

**Pass**: Build completes with exit code 0. May take 60–90 min (QEMU ARM64 emulation).

---

## Scenario 9 — Pi .deb Build

**Prerequisite**: Scenario 8 complete (Pi base image cached).

```powershell
build/docker/build_pi.ps1 -Version 1.0.0
```

**Pass**: `dist/CCTV-Processor-1.0.0-pi-arm64.deb` exists and is > 50 MB.

---

## Scenario 10 — build_all.ps1 Full Run

**Prerequisite**: Python 3.12 + PyInstaller installed; Docker Desktop running in Linux containers mode.

```powershell
build/build_all.ps1 -Version 1.0.0
```

**Pass**: Script prints per-platform status lines; Windows and Linux artifacts appear in `dist/`;
Pi build runs (may take long); macOS section prints GitHub Actions instructions.

---

## Scenario 11 — Idempotency Check

**Prerequisite**: Scenario 10 complete (all artifacts in `dist/`).

```powershell
build/build_all.ps1 -Version 1.0.0
```

**Pass**: Script runs without error; existing `dist/` artifacts are overwritten, not duplicated.
No error about "file already exists."

---

## Scenario 12 — Prerequisite Failure Handling

**Test**: Run Linux build with Docker Desktop stopped.

```powershell
build/docker/build_linux.ps1 -Version 1.0.0
```

**Pass**: Script exits with code 2 and prints:
`ERROR: Docker Desktop is not running. Please start Docker Desktop and try again.`

---

## Scenario 13 — macOS Build via GitHub Actions

**Prerequisite**: Repository has a GitHub remote; `v1.0.0` tag does not yet exist.

```powershell
git tag v1.0.0
git push origin v1.0.0
```

**Pass**: GitHub Actions `release.yml` triggers; `build-macos-arm` and `build-macos-intel`
jobs complete; `.dmg` artifacts appear as GitHub Release assets within 60 minutes.

---

## Scenario 14 — .dockerignore Verification

```powershell
Get-Content .dockerignore
```

**Pass**: File exists and contains entries for `dist/`, `build/work/`, `.git/`, `__pycache__/`.

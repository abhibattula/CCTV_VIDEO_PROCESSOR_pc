# Feature Specification: Cross-Platform Installer Builds from Windows PC

**Feature Branch**: `013-docker-platform-builds`  
**Created**: 2026-07-01  
**Status**: Draft  
**Input**: Phase 13 — Build all platform installers (Windows, Linux, macOS, Raspberry Pi) from a single Windows 11 PC using Docker Desktop and GitHub Actions.

## Overview

The CCTV Video Processor has build scripts and packaging specs (Phase 12) but no build was ever executed. A developer on a Windows PC must be able to produce all four platform installers without needing physical access to a Mac, a Linux desktop, or a Raspberry Pi.

---

## Clarifications

### Session 2026-07-01

- Q: How should Python dependencies be handled in Docker builds? → A: Two-stage build — a `Dockerfile.linux-base` / `Dockerfile.pi-base` bakes all Python dependencies (torch, transformers, open_clip, ultralytics) once; the build Dockerfiles (`Dockerfile.linux`, `Dockerfile.pi`) inherit from the base image and only run PyInstaller. First build ~45–60 min; subsequent source-only rebuilds ~5 min.
- Q: How should Docker-built artifacts be transferred to the Windows `dist/` folder? → A: Volume bind-mount — `docker run -v ${PWD}/dist:/output ...`; PyInstaller writes the artifact directly to `/output/` inside the container, which is bind-mounted to `dist/` on the Windows host. No container lifecycle management or `docker cp` needed.
- Q: Where does the version number come from for artifact naming? → A: A `VERSION` file at the repo root (e.g., containing `1.0.0`). `build_all.ps1` reads it automatically; an explicit `-Version x.y.z` parameter overrides it if supplied. CI/CD reads the same file for tag-triggered builds.

---

## User Scenarios & Testing

### User Story 1 — Windows Installer Built and Tested (Priority: P1)

A developer on Windows runs a single command, and a working `.exe` installer is produced in the `dist/` folder. Installing it on a clean Windows 11 machine launches the app without Python.

**Why this priority**: Windows is the primary deployment target; proves the full build pipeline end-to-end.

**Independent Test**: Run `pyinstaller build/cctv_processor_windows.spec` then `iscc build/windows/installer.iss`; install the resulting `.exe` on a clean machine; app window opens.

**Acceptance Scenarios**:

1. **Given** a Windows 11 developer machine with Python 3.12 and all deps installed, **When** `pyinstaller build/cctv_processor_windows.spec` is run, **Then** `dist/CCTV-Video-Processor/` is created with a valid executable.
2. **Given** the PyInstaller output exists, **When** `iscc build/windows/installer.iss /DAppVersion=1.0.0` is run (Inno Setup installed), **Then** `CCTV-Processor-1.0.0-win64-setup.exe` is produced in `dist/`.
3. **Given** the `.exe` installer, **When** installed on a Windows 11 machine with no Python, **Then** the app launches, the first-run wizard appears, and the main window opens after skip/complete.

---

### User Story 2 — Linux AppImage Built via Docker on Windows (Priority: P2)

A developer on Windows runs a Docker-based build command and receives a Linux `.AppImage` in `dist/` — without needing a Linux machine.

**Why this priority**: Linux is a high-value platform (servers, NAS, headless CCTV setups); Docker Desktop is already common on developer Windows machines.

**Independent Test**: Run `build/docker/build_linux.sh 1.0.0` (or `build_linux.ps1`); confirm `dist/CCTV-Processor-1.0.0-linux-x86_64.AppImage` exists and is executable on Ubuntu 22.04.

**Acceptance Scenarios**:

1. **Given** Docker Desktop installed on Windows with Linux containers mode, **When** `build/docker/build_linux.ps1 -Version 1.0.0` is executed, **Then** a Docker image is built and the AppImage is exported to `dist/`.
2. **Given** the `.AppImage` file, **When** run on Ubuntu 22.04 (`chmod +x; ./CCTV-Processor-*.AppImage`), **Then** the app launches without installing any additional packages.
3. **Given** Docker Desktop not installed, **When** the build script is run, **Then** a clear error message is displayed explaining Docker Desktop is required with a download link.

---

### User Story 3 — Raspberry Pi `.deb` Built via Docker + QEMU on Windows (Priority: P3)

A developer on Windows runs a QEMU-emulated ARM64 Docker build and receives a Pi `.deb` in `dist/` — without needing a physical Raspberry Pi.

**Why this priority**: Pi is the core embedded CCTV use case; QEMU emulation on Docker Desktop is well-supported.

**Independent Test**: Run `build/docker/build_pi.ps1 -Version 1.0.0`; confirm `dist/CCTV-Processor-1.0.0-pi-arm64.deb` exists.

**Acceptance Scenarios**:

1. **Given** Docker Desktop with QEMU binfmt support enabled, **When** `build/docker/build_pi.ps1 -Version 1.0.0` is run, **Then** an ARM64 Docker container executes the PyInstaller build and exports the `.deb` to `dist/`.
2. **Given** QEMU binfmt not yet registered, **When** the Pi build script is run, **Then** the script automatically registers QEMU binfmt via `tonistiigi/binfmt` before building.
3. **Given** the `.deb` package, **When** `sudo dpkg -i CCTV-Processor-1.0.0-pi-arm64.deb` is run on a Raspberry Pi 4 (Pi OS Bookworm, 4 GB), **Then** the app launches in YOLO-only mode.

---

### User Story 4 — macOS DMG Built via GitHub Actions (Priority: P4)

A developer pushes a `v*.*.*` git tag (or triggers a manual workflow dispatch) and GitHub Actions produces macOS `.dmg` files (arm64 + intel) as release artifacts — without any Apple hardware required.

**Why this priority**: macOS cannot be legally or technically built on non-Apple hardware; GitHub Actions provides free macOS runners.

**Independent Test**: Push tag `v0.0.1-test`; confirm GitHub Actions `release.yml` runs and uploads `.dmg` artifacts to the GitHub Release within 60 minutes.

**Acceptance Scenarios**:

1. **Given** the repository has a GitHub remote, **When** a `v*.*.*` tag is pushed, **Then** the `release.yml` workflow triggers and produces `CCTV-Processor-{version}-macos-arm64.dmg` and `CCTV-Processor-{version}-macos-intel.dmg` as release artifacts.
2. **Given** the arm64 `.dmg`, **When** opened on macOS 13+ and the app is right-clicked → Open (to bypass Gatekeeper), **Then** the first-run wizard appears.
3. **Given** no Apple Developer account, **When** the macOS build completes, **Then** the app is ad-hoc signed (not notarized) and can be opened via right-click → Open.

---

### User Story 5 — One-Command Build All (Priority: P5)

A developer runs a single PowerShell script (`build/build_all.ps1`) that orchestrates Windows, Linux, and Pi builds sequentially and prints clear status and artifact paths; macOS is triggered separately via GitHub tag.

**Why this priority**: Developer experience — reduces multi-step manual process to one command.

**Independent Test**: Run `build/build_all.ps1 -Version 1.0.0`; confirm Windows `.exe`, Linux `.AppImage`, and Pi `.deb` all appear in `dist/` after completion.

**Acceptance Scenarios**:

1. **Given** all prerequisites (Python 3.12, PyInstaller, Inno Setup, Docker Desktop + QEMU), **When** `build/build_all.ps1 -Version 1.0.0` is run, **Then** all three local builds complete and artifact paths are printed.
2. **Given** Inno Setup is not installed, **When** `build_all.ps1` is run, **Then** the Windows `.exe` step is skipped with a warning; Linux and Pi builds still proceed.
3. **Given** Docker Desktop is not running, **When** `build_all.ps1` is run, **Then** Linux and Pi steps are skipped with a clear message; Windows build still proceeds.
4. **Given** any individual build step fails, **When** `build_all.ps1` is run, **Then** the failure is reported but remaining steps continue (non-fatal per-platform errors).

---

### Edge Cases

- What happens when Docker image build fails mid-way (disk space, network error)?
- How does the Pi build handle the >45 min QEMU ARM64 emulation timeout?
- What if the `dist/` directory already contains a previous build — are files overwritten or does the build fail?
- What happens when PyInstaller collects a module that is only available on Windows (Windows-specific hidden import)?
- What if the user's Docker Desktop is in Windows containers mode (not Linux containers)?
- What if `tonistiigi/binfmt` image is not accessible (offline / firewall)?

---

## Requirements

### Functional Requirements

- **FR-001**: Two-stage Linux build image: `build/docker/Dockerfile.linux-base` installs Python 3.12, all CCTV app Python dependencies (CPU-only torch, transformers, open_clip, ultralytics, PyInstaller 6.x, imageio-ffmpeg) and `appimageTool` on Ubuntu 22.04 x86_64. `build/docker/Dockerfile.linux` inherits FROM the base image, COPYs project source, and runs PyInstaller. The base image is built once and reused for all subsequent builds.
- **FR-002**: Two-stage Pi build image: `build/docker/Dockerfile.pi-base` installs Python 3.12, all CCTV app Python dependencies (CPU-only torch for aarch64), PyInstaller 6.x, and `dpkg-deb` on `arm64v8/ubuntu:22.04`. `build/docker/Dockerfile.pi` inherits FROM the base image, COPYs project source, and runs PyInstaller + `create_deb.sh`. The base image is built once and reused.
- **FR-003**: `build/docker/build_linux.ps1` MUST build the Linux image (inheriting from the base), then run it with `-v "${PWD}/dist:/output"` bind-mount so the container writes the `.AppImage` directly to the Windows `dist/` folder. No `docker cp` step required.
- **FR-004**: `build/docker/build_pi.ps1` MUST register QEMU binfmt support if not already registered, build the Pi image (inheriting from the Pi base), then run it with `-v "${PWD}/dist:/output"` bind-mount so the container writes the `.deb` directly to the Windows `dist/` folder.
- **FR-005**: `build/build_all.ps1` MUST read the version from a `VERSION` file at the repo root by default; an optional `-Version x.y.z` parameter overrides this. The script runs Windows, Linux, and Pi builds in sequence, reports per-platform success or failure, and prints final artifact paths. A `VERSION` file MUST be created at the repo root (initial value `1.0.0`) as part of this phase.
- **FR-006**: Each Docker build MUST copy only the application source (not the `dist/`, `build/work/`, or `.git/` directories) into the container to minimize build context size.
- **FR-007**: All builds MUST be idempotent — re-running the same version produces the same output; existing files in `dist/` are overwritten without error.
- **FR-008**: The build scripts MUST print clear prerequisite error messages if Docker Desktop is not running, Docker is in Windows-container mode, or PyInstaller is not installed.
- **FR-009**: The existing `build/cctv_processor_windows.spec`, `build/linux/create_appimage.sh`, `build/pi/create_deb.sh`, and `.github/workflows/release.yml` from Phase 12 MUST be used as-is or updated only minimally (no rework of Phase 12 scripts).
- **FR-010**: `build/build_all.ps1` MUST print instructions for triggering the macOS build via GitHub Actions tag push, including the exact `git tag` and `git push` commands.
- **FR-011**: A `.dockerignore` file MUST exist in the project root excluding `dist/`, `build/work/`, `.git/`, `__pycache__/`, `*.pyc`, `.venv/`, and model cache directories from the Docker build context.
- **FR-012**: The Linux and Pi Docker images MUST install system-level Qt/OpenGL dependencies (`libgl1-mesa-glx`, `libglib2.0-0`, `libxcb-*`) required by PyQt6 on Linux.

### Key Entities

- **Build Artifact**: A platform-specific installable file (`.exe`, `.AppImage`, `.deb`, `.dmg`) placed in `dist/` with a consistent naming pattern `CCTV-Processor-{version}-{platform}.{ext}`.
- **Docker Build Image**: A Docker image encapsulating the Linux or Pi build environment; rebuilt on first run, cached on subsequent runs.
- **Build Script**: A PowerShell script (`.ps1`) on the Windows side that orchestrates docker commands, copies artifacts, and reports results.
- **QEMU binfmt**: ARM64 emulation layer registered via Docker; required for Pi builds; registered once per Docker Desktop session.
- **Build Prerequisite**: A tool that must be installed before a build step runs (Docker Desktop, Inno Setup, PyInstaller); missing prerequisites cause a skipped step with clear messaging, not a hard crash.

---

## Success Criteria

### Measurable Outcomes

- **SC-001**: A developer with Docker Desktop installed can produce a working Linux `.AppImage` from a Windows PC in under 60 minutes (including first Docker image build).
- **SC-002**: A developer can produce a working Raspberry Pi `.deb` from a Windows PC in under 90 minutes (QEMU ARM64 emulation is slow; 90 min accounts for first-time image build).
- **SC-003**: The `build_all.ps1` script completes Windows + Linux + Pi builds in under 120 minutes total on a mid-range Windows 11 PC (i5/Ryzen 5, 16 GB RAM).
- **SC-004**: The Windows `.exe` installer installs and runs on a clean Windows 11 machine (no Python, no dev tools) within 5 minutes of installer launch.
- **SC-005**: The Linux `.AppImage` runs on Ubuntu 22.04 with zero additional package installs.
- **SC-006**: Each build step produces a clear pass/fail status line and the artifact path; a developer can diagnose a build failure without reading Docker logs unless needed.
- **SC-007**: All 222+ existing automated tests continue to pass after this phase (no production code changes).

---

## Assumptions

- Docker Desktop for Windows is installed with Linux containers mode enabled (not Windows containers mode). This is a prerequisite users must satisfy manually.
- Inno Setup 6.x is installed on Windows for the `.exe` installer step; if absent, that step is skipped gracefully.
- The developer machine has at least 16 GB RAM and 20 GB free disk space (Docker images + PyInstaller output are large).
- Python 3.12 is already installed on Windows with all app dependencies (torch CPU, PyQt6, etc.) — confirmed working from Phase 12 build.
- The app's `requirements.txt` (or equivalent pip install list) is authoritative for Docker container dependency installation.
- `tonistiigi/binfmt` Docker image is accessible from Docker Hub (internet connection required for first QEMU registration).
- macOS builds remain on GitHub Actions — ad-hoc signing only, no Apple Developer account, no notarization.
- No new Python source code changes in this phase — only build infrastructure files.
- The Phase 12 PyInstaller specs (`build/cctv_processor_*.spec`) and packaging scripts (`create_appimage.sh`, `create_deb.sh`) are correct and functional; this phase adds the Docker wrapper layer only.
- Docker `buildx` with `--platform` flag is available (included with Docker Desktop 4.x+).

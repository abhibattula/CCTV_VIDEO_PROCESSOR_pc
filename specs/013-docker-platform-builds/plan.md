# Implementation Plan: Cross-Platform Builds from Windows PC

**Branch**: `013-docker-platform-builds` | **Date**: 2026-07-01 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/013-docker-platform-builds/spec.md`

## Summary

Enable building all CCTV Video Processor platform installers (Windows `.exe`, Linux `.AppImage`, Raspberry Pi `.deb`, macOS `.dmg`) from a single Windows 11 PC. Windows builds run natively via PyInstaller. Linux and Pi builds run inside Docker Desktop containers using Ubuntu 22.04 images with two-stage base images (deps baked once; source rebuilt in ~5 min). Artifacts are transferred via volume bind-mount to `dist/`. macOS builds remain on GitHub Actions. A single `build/build_all.ps1` script orchestrates all local builds. A `VERSION` file at repo root is the single version source of truth.

## Technical Context

**Language/Version**: PowerShell 5.1 (build scripts), Bash (Docker entrypoints), Python 3.12 (inside containers)
**Primary Dependencies**: Docker Desktop 4.x (Linux containers mode), PyInstaller 6.x, QEMU binfmt (ARM64 emulation), Inno Setup 6.x (Windows .exe packaging, optional), appimageTool (Linux AppImage), dpkg-deb (Pi .deb)
**Storage**: `dist/` directory for artifacts; `VERSION` file for version; Docker image layer cache (local Docker daemon)
**Testing**: No automated pytest tests (build infrastructure only — same exemption as frontend JS per Principle III); verified via quickstart.md scenarios 1–14
**Target Platform**: Windows 11 PC (developer machine); build outputs target Windows/Linux x86_64/Linux arm64
**Project Type**: Build pipeline / DevOps tooling
**Performance Goals**: Linux base image build ≤60 min (first run); subsequent Linux builds ≤10 min; Pi base image build ≤90 min; Pi subsequent builds ≤15 min; Windows build ≤30 min
**Constraints**: Docker Desktop must be in Linux containers mode; QEMU emulation is slow (~45–90 min first Pi base); no Apple hardware available — macOS via GitHub Actions only; no production Python code changes in this phase
**Scale/Scope**: 4 platform targets, 6 new Dockerfiles, 3 new PowerShell scripts, 1 new shell script, 1 new VERSION file, 1 .dockerignore, documentation updates

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

1. **Principle I (Session-First, No Persistence)**: ✅ PASS — This phase adds only build infrastructure files. No changes to `app/session.py` or any session state. No new persistence introduced.

2. **Principle II (Cross-Platform by Default)**: ✅ PASS — Build scripts target Windows (`.ps1`) and Linux (Dockerfile/`.sh`) by explicit platform design. The app's cross-platform source code is unchanged. No `pathlib` violations introduced.

3. **Principle III (Test-First)**: ✅ PASS (build infrastructure exemption) — No `app/` or `shell/` Python source changes in this phase. Build scripts (`.ps1`, `Dockerfile`, `.sh`) are infrastructure analogous to the frontend JS exemption. Verification is via quickstart.md scenarios 1–14, documented before implementation tasks begin.

4. **Principle IV (Callback-Driven)**: ✅ PASS — No detection engine changes.

5. **Principle V (Simplicity & YAGNI)**: ✅ PASS — Two-stage Docker base images add one Dockerfile per platform but save 40–55 min per build iteration. Justified by developer experience. `build_all.ps1` is the simplest orchestrator that satisfies US5.

*Post-design re-check*: All five gates pass after Phase 1 design. No violations detected.

## Project Structure

### Documentation (this feature)

```text
specs/013-docker-platform-builds/
├── plan.md              # This file
├── research.md          # Phase 0 output ✓
├── data-model.md        # Phase 1 output ✓
├── quickstart.md        # Phase 1 output ✓
├── contracts/
│   └── build-scripts.md # Phase 1 output ✓
└── tasks.md             # Phase 2 output (/speckit.tasks — NOT yet created)
```

### Source Code (repository root)

```text
VERSION                               # NEW: plain-text semver (e.g., 1.0.0)
.dockerignore                         # NEW: excludes dist/, build/work/, .git/ from Docker context

build/
├── build_all.ps1                     # NEW: one-command orchestrator (Windows + Linux + Pi)
├── docker/
│   ├── Dockerfile.linux-base         # NEW: Ubuntu 22.04 x86_64 + all Python deps + appimageTool
│   ├── Dockerfile.linux              # NEW: inherits linux-base; COPYs source; runs PyInstaller+AppImage
│   ├── Dockerfile.pi-base            # NEW: arm64v8/ubuntu:22.04 + all Python deps (aarch64)
│   ├── Dockerfile.pi                 # NEW: inherits pi-base; COPYs source; runs PyInstaller+create_deb.sh
│   ├── build_linux.ps1               # NEW: Windows-side launcher for Linux AppImage build
│   └── build_pi.ps1                  # NEW: Windows-side launcher for Pi .deb build (with QEMU)
├── cctv_processor_windows.spec       # EXISTS (Phase 12) — no changes
├── cctv_processor_linux.spec         # EXISTS (Phase 12) — used inside Docker containers
├── cctv_processor_macos.spec         # EXISTS (Phase 12) — used by GitHub Actions
├── windows/
│   └── installer.iss                 # EXISTS (Phase 12) — no changes
├── linux/
│   └── create_appimage.sh            # EXISTS (Phase 12) — called from Dockerfile.linux
├── macos/
│   └── create_dmg.sh                 # EXISTS (Phase 12) — called by GitHub Actions
└── pi/
    └── create_deb.sh                 # EXISTS (Phase 12) — called from Dockerfile.pi

.github/workflows/
├── release.yml                       # EXISTS (Phase 12) — minor update: read VERSION file
└── release-pi.yml                    # EXISTS (Phase 12) — minor update: read VERSION file

README.md                             # UPDATE: add "Building from Windows" section
USER_MANUAL.md                        # UPDATE: add build instructions for end-user context
```

## Phases

### Phase 0: Setup & Prerequisites

- Create `VERSION` file at repo root with initial value `1.0.0`
- Create `build/docker/` directory
- Create `.dockerignore`

### Phase 1: Windows Build Completion (US1)

- Verify the PyInstaller build already running completes successfully
- Verify `dist/CCTV-Video-Processor/` exists with executable
- Run Inno Setup if available to produce `.exe` installer

### Phase 2: Linux Docker Build (US2)

- `Dockerfile.linux-base`: Ubuntu 22.04 + deadsnakes Python 3.12 + all app deps + appimageTool
- `Dockerfile.linux`: inherits linux-base; COPY source; run PyInstaller + create_appimage.sh; write to /output
- `build/docker/build_linux.ps1`: prereq check → build base (if needed) → docker run with bind-mount

### Phase 3: Pi Docker Build (US3)

- `Dockerfile.pi-base`: arm64v8/ubuntu:22.04 + deadsnakes Python 3.12 + all app deps (aarch64 torch)
- `Dockerfile.pi`: inherits pi-base; COPY source; run PyInstaller + create_deb.sh; write to /output
- `build/docker/build_pi.ps1`: QEMU check/register → build base (if needed) → docker run with bind-mount

### Phase 4: Orchestrator (US5)

- `build/build_all.ps1`: reads VERSION, runs Windows/Linux/Pi in sequence, graceful skip on missing prereqs, prints macOS instructions

### Phase 5: GitHub Actions Update (US4)

- Update `.github/workflows/release.yml` to read version from `VERSION` file
- Update `.github/workflows/release-pi.yml` similarly

### Phase 6: Documentation

- Update `README.md` with "Building from Windows" section
- Update `USER_MANUAL.md` with build process notes

### Phase 7: Verification

- Run quickstart.md scenarios 1–14 in order

## Complexity Tracking

> No Constitution violations — no entries required.

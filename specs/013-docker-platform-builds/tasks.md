# Tasks: Cross-Platform Installer Builds from Windows PC

**Input**: Design documents from `specs/013-docker-platform-builds/`
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓, contracts/build-scripts.md ✓, quickstart.md ✓

**Tests**: Build infrastructure — no pytest tests for new files (exempt per Principle III). SC-007 verification (existing test suite must still pass) is covered by T005.

**Organization**: Tasks grouped by user story (US1–US5) to enable independent delivery of each platform target.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no interdependency)
- **[Story]**: User story this task belongs to

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the shared files that ALL platform builds depend on, and verify Phase 12 preconditions.

- [X] T001 Create `VERSION` file at repo root containing the single line `1.0.0` (use `Set-Content -NoNewline "C:\...\VERSION" "1.0.0"` or `"1.0.0" | Out-File -NoNewline VERSION` to avoid trailing newline)
- [X] T002 Create `.dockerignore` at repo root with these exclusions (per FR-006, FR-011, checklist CHK028): `dist/`, `build/work/`, `.git/`, `__pycache__/`, `*.pyc`, `.venv/`, `venv/`, `.cache/`, `models/`, `*.egg-info/`, `_verify_shots/`, `"OLD RASPBERRI PI VERSION/"`. Note: FR-006 (Docker COPY exclusion intent) is satisfied entirely by this `.dockerignore` file — no explicit exclusion flags are needed in the Dockerfiles themselves (L1 fix).
- [X] T003 Verify Phase 12 prerequisite files exist before any Docker build depends on them (M4 fix): confirm `build/linux/create_appimage.sh`, `build/pi/create_deb.sh`, `build/cctv_processor_linux.spec`, `build/cctv_processor_windows.spec`, and `.github/workflows/release.yml` all exist. If any are missing, stop and report which file is absent before proceeding. Then create `build/docker/` directory (`New-Item -ItemType Directory -Force build/docker`); this step is idempotent — running it after T008/T011 write files there has no effect (L2 fix).

**Checkpoint**: `VERSION`, `.dockerignore`, `build/docker/` exist and all Phase 12 prerequisite files verified present.

---

## Phase 2: Foundational (Windows Spec Fix + Test Verification — Blocks US1)

**Purpose**: Fix the confirmed `STATUS_ACCESS_VIOLATION` crash in the Windows PyInstaller build, then verify the existing test suite is unaffected. Both tasks MUST complete before any Windows build attempt.

**⚠️ CRITICAL**: The Windows build failed with exit code 3221225477 (`STATUS_ACCESS_VIOLATION`) during `find_binary_dependencies` when PyInstaller's isolated subprocess imported `onnx.reference`. These are YOLO export-only packages not needed at inference time.

- [X] T004 **Pre-verify then fix** `build/cctv_processor_windows.spec` (H1 fix): First, read the file and locate the `Analysis(...)` call — note whether an `excludes=[...]` argument already exists and its current contents. Then add `'onnx'`, `'onnxruntime'`, `'onnxslim'`, `'onnx.reference'`, `'onnxslim.third_party._sympy'` to that list (extend if exists, add `excludes=[...]` arg if absent). These packages crash PyInstaller's isolated subprocess on Windows (exit code 3221225477 = `STATUS_ACCESS_VIOLATION`) because `onnx.reference` imports C extensions that segfault during analysis. They are not needed by the running app — only for YOLO model export.
- [X] T005 Run `pytest tests/ -v` from the repo root and confirm all 222+ existing tests still pass after T004 (covers SC-007). The Windows spec fix changes only build configuration — no `app/` source — so all tests should pass. If any test regresses, stop and diagnose before proceeding to any build step.

**Checkpoint**: Windows spec patched; existing test suite green (222+ tests pass).

---

## Phase 3: User Story 1 — Windows Installer (Priority: P1) 🎯 MVP

**Goal**: Produce `dist/CCTV-Processor-1.0.0-win64-setup.exe` on Windows using PyInstaller + Inno Setup.

**Independent Test**: Run PyInstaller with the fixed spec; verify `dist/CCTV-Video-Processor/CCTV-Video-Processor.exe` exists and is > 10 MB. Then if Inno Setup installed, verify `dist/CCTV-Processor-1.0.0-win64-setup.exe` exists.

- [ ] T006 [US1] Ensure `dist/` directory exists (`New-Item -ItemType Directory -Force dist`). Then run Windows PyInstaller build: `python -m PyInstaller build/cctv_processor_windows.spec --distpath dist --workpath build/work --noconfirm`. Confirm `dist/CCTV-Video-Processor/CCTV-Video-Processor.exe` exists and its file size exceeds 10 MB (`(Get-Item "dist/CCTV-Video-Processor/CCTV-Video-Processor.exe").Length -gt 10MB`).
- [ ] T007 [US1] Check if Inno Setup is installed: `Get-Command iscc -ErrorAction SilentlyContinue`. If installed, run `iscc build/windows/installer.iss /DAppVersion=1.0.0` and confirm `dist/CCTV-Processor-1.0.0-win64-setup.exe` is produced. If not installed, print: "WARNING: Inno Setup not found — skipping .exe installer packaging. PyInstaller output is available at dist/CCTV-Video-Processor/."

**Checkpoint**: Windows platform proven — `dist/CCTV-Video-Processor/` exists (and optionally `dist/CCTV-Processor-1.0.0-win64-setup.exe`).

---

## Phase 4: User Story 2 — Linux AppImage via Docker (Priority: P2)

**Goal**: Produce `dist/CCTV-Processor-1.0.0-linux-x86_64.AppImage` on Windows via Docker Desktop.

**Independent Test**: Run `build/docker/build_linux.ps1 -Version 1.0.0`; confirm `dist/CCTV-Processor-1.0.0-linux-x86_64.AppImage` exists and is > 50 MB.

- [X] T008 [P] [US2] Create `build/docker/Dockerfile.linux-base` — Ubuntu 22.04 x86_64 base image. Include `ARG PYTHON_VERSION=3.12`. Steps: (1) `apt-get update` + install `software-properties-common curl`; (2) `add-apt-repository ppa:deadsnakes/ppa -y`; (3) `apt-get install -y python3.12 python3.12-venv python3.12-dev python3-pip`; (4) install system Qt/OpenGL libs required by PyQt6 analysis (M1 fix — full list): `libgl1-mesa-glx libglib2.0-0 libxcb-xinerama0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 libxcb-xkb1 libxkbcommon-x11-0 libegl1 libdbus-1-3 libfontconfig1`; (5) pip install with CPU-only torch: `pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu`; (6) pip install remaining deps: `transformers open_clip_torch ultralytics pyinstaller==6.21.0 imageio-ffmpeg PyQt6 fastapi uvicorn aiofiles Pillow opencv-python-headless`; (7) download appimageTool: `curl -L https://github.com/AppImage/AppImageKit/releases/download/continuous/appimageTool-x86_64.AppImage -o /usr/local/bin/appimageTool && chmod +x /usr/local/bin/appimageTool`. Tag: `cctv-linux-base:latest`.
- [X] T009 [US2] Create `build/docker/Dockerfile.linux` — inherits `FROM cctv-linux-base:latest`. Sets `WORKDIR /app`. Accepts `ENV APP_VERSION=1.0.0`. COPYs project source (`.dockerignore` handles exclusions automatically). Runs: `python -m PyInstaller build/cctv_processor_linux.spec --distpath /tmp/dist --workpath /tmp/work --noconfirm`. Then runs: `bash build/linux/create_appimage.sh` (passing `/tmp/dist` and `/output` as required by the existing script). Copies the resulting AppImage to `/output/CCTV-Processor-${APP_VERSION}-linux-x86_64.AppImage`. Container exits 0 on success.
- [X] T010 [US2] Create `build/docker/build_linux.ps1` (L4 fix: include Docker Desktop URL in error message) — PowerShell script with param block `[-Version <string>] [-RebuildBase]`. Logic: (1) if `$Version` empty, read from `Get-Content VERSION`; (2) ensure `dist/` exists; (3) run `docker info 2>&1`; if exit code non-zero, print `"ERROR: Docker Desktop is not running. Please start Docker Desktop (https://www.docker.com/products/docker-desktop/) and try again."` then `exit 2`; (4) check `docker info --format "{{.OperatingSystem}}"` — if output contains "Windows", print `"ERROR: Docker is in Windows containers mode. Right-click Docker Desktop in system tray → Switch to Linux containers."` then `exit 1`; (5) if `-RebuildBase` or `(docker images -q cctv-linux-base:latest)` is empty: `docker build -f build/docker/Dockerfile.linux-base -t cctv-linux-base:latest .`; (6) `docker build -f build/docker/Dockerfile.linux -t cctv-linux-build:latest .`; (7) `docker run --rm -e "APP_VERSION=$Version" -v "${PWD}/dist:/output" cctv-linux-build:latest`; (8) verify `dist/CCTV-Processor-$Version-linux-x86_64.AppImage` exists; exit 0 on success, 1 on build failure.

**Checkpoint**: Linux Docker pipeline complete — `dist/CCTV-Processor-1.0.0-linux-x86_64.AppImage` producible from Windows.

---

## Phase 5: User Story 3 — Raspberry Pi .deb via Docker + QEMU (Priority: P3)

**Goal**: Produce `dist/CCTV-Processor-1.0.0-pi-arm64.deb` on Windows via QEMU-emulated ARM64 Docker.

**Independent Test**: Run `build/docker/build_pi.ps1 -Version 1.0.0`; confirm `dist/CCTV-Processor-1.0.0-pi-arm64.deb` exists and is > 50 MB.

- [X] T011 [P] [US3] Create `build/docker/Dockerfile.pi-base` — `arm64v8/ubuntu:22.04` base image. Include `ARG PYTHON_VERSION=3.12`. Steps: (1) `apt-get update` + install `software-properties-common curl`; (2) `add-apt-repository ppa:deadsnakes/ppa -y`; (3) `apt-get install -y python3.12 python3.12-venv python3.12-dev python3-pip dpkg-dev dpkg`; (4) install system Qt/OpenGL libs (M1 fix — same full list as T008): `libgl1-mesa-glx libglib2.0-0 libxcb-xinerama0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 libxcb-xkb1 libxkbcommon-x11-0 libegl1 libdbus-1-3 libfontconfig1`; (5) pip install CPU-only torch for aarch64 — use: `pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu` (PyTorch's whl/cpu index includes aarch64 wheels for recent torch versions); (6) pip install: `transformers open_clip_torch ultralytics pyinstaller==6.21.0 imageio-ffmpeg PyQt6 fastapi uvicorn aiofiles Pillow opencv-python-headless`. Tag: `cctv-pi-base:latest`. Note: this image is built with `--platform linux/arm64` so all packages install as aarch64 binaries automatically.
- [X] T012 [US3] Create `build/docker/Dockerfile.pi` (M3 fix: ARM64 note) — inherits `FROM cctv-pi-base:latest`. Sets `WORKDIR /app`. Accepts `ENV APP_VERSION=1.0.0`. COPYs project source. Runs: `python -m PyInstaller build/cctv_processor_linux.spec --distpath /tmp/dist --workpath /tmp/work --noconfirm`. **Note**: reusing `build/cctv_processor_linux.spec` assumes no x86_64-specific hidden imports — if the Pi container's PyInstaller fails with import errors, inspect the spec for x86_64-only `hiddenimports` entries that may need ARM64 equivalents or exclusion. Runs: `bash build/pi/create_deb.sh` to package the PyInstaller output as a `.deb`. Copies result to `/output/CCTV-Processor-${APP_VERSION}-pi-arm64.deb`. Container exits 0 on success.
- [X] T013 [US3] Create `build/docker/build_pi.ps1` — PowerShell script with param block `[-Version <string>] [-RebuildBase] [-SkipQemuCheck]`. Logic: (1) if `$Version` empty, read from `Get-Content VERSION`; (2) ensure `dist/` exists; (3) Docker running check + Linux mode check (same as T010, exit codes 2 and 1 respectively); (4) unless `-SkipQemuCheck`: run `docker buildx inspect --bootstrap 2>&1`; if output does NOT contain "linux/arm64", run `docker run --privileged --rm tonistiigi/binfmt --install arm64` then re-verify; (5) if `-RebuildBase` or Pi base image absent locally: `docker build --platform linux/arm64 -f build/docker/Dockerfile.pi-base -t cctv-pi-base:latest .`; (6) `docker build --platform linux/arm64 -f build/docker/Dockerfile.pi -t cctv-pi-build:latest .`; (7) `docker run --rm --platform linux/arm64 -e "APP_VERSION=$Version" -v "${PWD}/dist:/output" cctv-pi-build:latest`; (8) verify `dist/CCTV-Processor-$Version-pi-arm64.deb` exists; exit 0/1/2 per contract.

**Checkpoint**: Pi Docker pipeline complete — `dist/CCTV-Processor-1.0.0-pi-arm64.deb` producible from Windows.

---

## Phase 6: User Story 4 — macOS via GitHub Actions (Priority: P4)

**Goal**: Update GitHub Actions workflows to read version from `VERSION` file for consistency with local builds.

**Independent Test**: Push tag `v1.0.0`; confirm `release.yml` triggers and produces `.dmg` artifacts.

- [X] T014 [P] [US4] Read `.github/workflows/release.yml`. Add a step early in each macOS build job to read the version: `APP_VERSION=$(cat VERSION)` (bash) and export it as an environment variable used in subsequent artifact naming steps. If version is currently hardcoded or read from a git tag, replace with `cat VERSION`. Preserve all existing `build-macos-arm` and `build-macos-intel` job structure — minimal change only.
- [X] T015 [P] [US4] Read `.github/workflows/release-pi.yml`. Apply the same `VERSION`-file-reading update as T014. Preserve existing Pi build job structure — minimal change only.

**Checkpoint**: CI/CD reads version from `VERSION` file — macOS builds consistent with local builds.

---

## Phase 7: User Story 5 — One-Command Orchestrator (Priority: P5)

**Goal**: `build/build_all.ps1` builds all three local platforms in sequence and prints clear status lines matching the contracts.

**Independent Test**: Run `build/build_all.ps1 -Version 1.0.0`; confirm Windows + Linux artifacts appear in `dist/`; Pi build runs; macOS section prints `git tag` instructions.

- [X] T016 [US5] Create `build/build_all.ps1` — top-level orchestrator. Param block: `[-Version <string>]`. Logic: (1) if `$Version` empty, read `$Version = (Get-Content "$PSScriptRoot/../VERSION").Trim()`; (2) print `"Building CCTV Video Processor v$Version — all platforms"`; (3) **Windows build**: check `Get-Command python -ErrorAction SilentlyContinue` and `Get-Command pyinstaller -ErrorAction SilentlyContinue`; if Python/PyInstaller missing, set `$winStatus = "SKIPPED → PyInstaller not installed"` else run `python -m PyInstaller build/cctv_processor_windows.spec --distpath dist --workpath build/work --noconfirm`; then check Inno Setup and run `iscc` if present; set `$winStatus` = "SUCCESS → dist/CCTV-Processor-$Version-win64-setup.exe" or "SUCCESS → dist/CCTV-Video-Processor/ (no Inno Setup)" or "FAILED → see above"; (4) **Linux build**: `& "$PSScriptRoot/docker/build_linux.ps1" -Version $Version`; capture `$LASTEXITCODE`; set `$linStatus`; (5) **Pi build**: `& "$PSScriptRoot/docker/build_pi.ps1" -Version $Version`; capture `$LASTEXITCODE`; set `$piStatus`; (6) print summary: `"[Windows] $winStatus"`, `"[Linux]   $linStatus"`, `"[Pi]      $piStatus"`, `"[macOS]   INFO    → Run: git tag v$Version && git push origin v$Version"`; (7) exit 0 if all non-SKIPPED builds succeeded, exit 1 if any FAILED. Script must be idempotent (`--noconfirm` handles overwrite; Docker bind-mount overwrites artifact files).

**Checkpoint**: Single command builds all three local platforms and reports status in contract format.

---

## Phase 8: Polish & Documentation

**Purpose**: Documentation updates and cross-cutting verification.

- [X] T017 [P] Update `README.md` — add "Building Installers from Source" section with: (a) Windows prerequisites (Python 3.12, PyInstaller 6.x, optional Inno Setup); command: `build/build_all.ps1`; expected output paths. (b) Linux/Pi prerequisites (Docker Desktop in Linux containers mode); same command. (c) QEMU registration note for Pi. (d) macOS: `git tag v1.0.0 && git push origin v1.0.0` GitHub Actions trigger. Keep concise — reference USER_MANUAL.md for full step-by-step.
- [X] T018 [P] Update `USER_MANUAL.md` — add "Building Installers" appendix with: full step-by-step Docker Desktop setup instructions, QEMU binfmt registration, running `build_all.ps1`, and troubleshooting section covering: Docker in Windows containers mode, insufficient disk space, QEMU timeout, `onnx`-related exclusion notes. Include quickstart scenario numbers as validation checklist.
- [ ] T019 Run quickstart.md verification: execute scenarios 1–14 in order and record PASS/FAIL for each. **M2 fix — timing**: for scenarios 5 (Linux base build) and 8 (Pi base build), record wall-clock time and confirm they fall within SC-001 (<60 min) and SC-002 (<90 min) budgets. For scenarios 6 and 9, record the artifact file size and confirm >50 MB. Update `specs/013-docker-platform-builds/checklists/build-pipeline.md` to mark items that were validated [X].

**Checkpoint**: All quickstart scenarios pass; documentation complete; checklist updated.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1 (spec file must exist; VERSION needed for context)
- **Phase 3 (US1 Windows)**: Depends on Phase 2 (T005 pytest must pass; T004 onnx fix must be applied)
- **Phase 4 (US2 Linux)**: Depends on Phase 1 only — independent of US1
- **Phase 5 (US3 Pi)**: Depends on Phase 1 only — independent of US1 and US2
- **Phase 6 (US4 macOS CI)**: Depends on Phase 1 only — VERSION file must exist
- **Phase 7 (US5 Orchestrator)**: Depends on Phases 3, 4, 5 (all build scripts must exist)
- **Phase 8 (Polish)**: Depends on all prior phases

### User Story Dependencies

- **US1 (Windows)**: Requires Phase 2 spec fix + test verification. Independent of US2/US3.
- **US2 (Linux)**: Independent of US1. Can run in parallel with US1 if Docker available.
- **US3 (Pi)**: Independent of US1 and US2. Can run in parallel. (60–90 min QEMU emulation.)
- **US4 (macOS CI)**: Independent of all local builds. Minimal GitHub Actions file update.
- **US5 (Orchestrator)**: T016 requires T010 (build_linux.ps1) and T013 (build_pi.ps1) to exist.

### Within Each User Story

- Base Dockerfile (T008, T011) must be created before the build Dockerfile (T009, T012) that inherits FROM it
- Build Dockerfiles (T009, T012) must exist before PS1 launchers (T010, T013) that invoke them
- T005 (pytest) must pass before T006 (Windows build run)

### Parallel Opportunities

- T008 (Dockerfile.linux-base) and T011 (Dockerfile.pi-base) can be written in parallel [P]
- T014 (release.yml) and T015 (release-pi.yml) can be updated in parallel [P]
- T017 (README) and T018 (USER_MANUAL) can be written in parallel [P]

---

## Parallel Example: Base Image Creation

```powershell
# After Phase 1 & 2, Linux and Pi base image files can be authored in parallel:
# Write build/docker/Dockerfile.linux-base (T008)
# Write build/docker/Dockerfile.pi-base (T011)

# Then base image builds can run in parallel (if disk allows):
docker build -f build/docker/Dockerfile.linux-base -t cctv-linux-base:latest .
docker build --platform linux/arm64 -f build/docker/Dockerfile.pi-base -t cctv-pi-base:latest .
```

---

## Implementation Strategy

### MVP First (US1 — Windows Build)

1. Complete Phase 1 (Setup): VERSION, .dockerignore, Phase 12 verification
2. Complete Phase 2 (Foundational): Fix onnx crash + confirm pytest still green
3. Complete Phase 3 (US1): Run Windows PyInstaller → verify exe
4. **STOP and VALIDATE**: Windows installer proven working independently
5. Proceed to US2 Linux, then US3 Pi

### Incremental Delivery

1. Phase 1 + 2 → Foundation ready (onnx fix applied, tests green)
2. Phase 3 (US1) → Windows build working → validate
3. Phase 4 (US2) → Linux build working → validate
4. Phase 5 (US3) → Pi build working (slow) → validate
5. Phase 6 (US4) → macOS CI update → validate on tag push
6. Phase 7 (US5) → Orchestrator wires everything together
7. Phase 8 → Documentation + timing verification

### Critical Path

`T001 → T003 → T004 → T005 → T006` (Windows MVP unblocked)
`T003 → T008 → T009 → T010` (Linux pipeline)
`T003 → T011 → T012 → T013` (Pi pipeline)
`T016` (Orchestrator — needs T010 and T013 to exist)

---

## Notes

- No new pytest tests in this phase (build infrastructure exemption per Principle III); existing 222+ tests verified via T005
- T004 (onnx spec fix) is the single most critical task — confirmed crash blocks all Windows builds
- Pi builds via QEMU take 60–90 min for first base image; plan accordingly  
- All PS1 scripts MUST use `"${PWD}/dist"` with double quotes to handle paths containing spaces (Windows user profiles with spaces in name)
- `--noconfirm` in PyInstaller calls is the idempotency mechanism — overwrites without prompting
- Docker bind-mount: PowerShell `${PWD}` returns Windows path; Docker Desktop transparently translates it to a Linux path inside the container
- If `pip install torch ... --index-url .../whl/cpu` fails for aarch64 in T011 base, fall back to `pip install torch torchvision` (default index) with `TORCH_CPU_ONLY=1` or the appropriate aarch64 wheel URL from PyTorch's official release page

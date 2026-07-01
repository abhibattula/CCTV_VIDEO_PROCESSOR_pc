# Tasks: Cross-Platform Installer Builds from Windows PC

**Input**: Design documents from `specs/013-docker-platform-builds/`
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓, contracts/build-scripts.md ✓, quickstart.md ✓

**Tests**: Build infrastructure — no pytest tests (exempt per Principle III). Verification via quickstart.md scenarios 1–14.

**Organization**: Tasks grouped by user story (US1–US5) to enable independent delivery of each platform target.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no interdependency)
- **[Story]**: User story this task belongs to

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the shared files that ALL platform builds depend on.

- [ ] T001 Create `VERSION` file at repo root containing the single line `1.0.0` (UTF-8, no trailing newline issues — use `Set-Content -NoNewline` or `echo 1.0.0 > VERSION`)
- [ ] T002 Create `.dockerignore` at repo root with these exclusions: `dist/`, `build/work/`, `.git/`, `__pycache__/`, `*.pyc`, `.venv/`, `venv/`, `.cache/`, `models/`, `*.egg-info/`, `_verify_shots/`, `OLD RASPBERRI PI VERSION/` (per FR-006, FR-011 and checklist CHK028)
- [ ] T003 Create directory `build/docker/` (create a `.gitkeep` placeholder if directory doesn't already exist)

**Checkpoint**: `VERSION`, `.dockerignore`, and `build/docker/` exist — shared setup complete.

---

## Phase 2: Foundational (Windows Spec Fix — Blocks US1)

**Purpose**: Fix the confirmed `STATUS_ACCESS_VIOLATION` crash in the Windows PyInstaller build before any Windows build attempt. This is a blocking prerequisite for US1.

**⚠️ CRITICAL**: The Windows build failed with exit code 3221225477 (`STATUS_ACCESS_VIOLATION`) during `find_binary_dependencies` when PyInstaller's isolated subprocess tried to import `onnx.reference`. These packages are YOLO export-only dependencies (not needed at inference time) and MUST be excluded from PyInstaller analysis.

- [ ] T004 Read `build/cctv_processor_windows.spec` and add `'onnx'`, `'onnxruntime'`, `'onnxslim'`, `'onnx.reference'`, `'onnxslim.third_party._sympy'` to the `excludes` list in the `Analysis(...)` call. If an `excludes=[]` argument already exists, extend it; otherwise add `excludes=['onnx', 'onnxruntime', 'onnxslim', 'onnx.reference', 'onnxslim.third_party._sympy']` as a new argument. These are model-export dependencies that crash PyInstaller's subprocess on Windows and are not needed for the running app.

**Checkpoint**: Windows spec has onnx excluded — Windows build can now proceed without crashing.

---

## Phase 3: User Story 1 — Windows Installer (Priority: P1) 🎯 MVP

**Goal**: Produce `dist/CCTV-Processor-1.0.0-win64-setup.exe` on Windows using PyInstaller + Inno Setup.

**Independent Test**: Run PyInstaller with the fixed spec; verify `dist/CCTV-Video-Processor/CCTV-Video-Processor.exe` exists and is > 10 MB. Then if Inno Setup is installed, verify `dist/CCTV-Processor-1.0.0-win64-setup.exe` exists.

- [ ] T005 [US1] Verify `dist/` directory exists; if not, create it with `New-Item -ItemType Directory -Force dist`. Then run Windows PyInstaller build: `python -m PyInstaller build/cctv_processor_windows.spec --distpath dist --workpath build/work --noconfirm`. Confirm `dist/CCTV-Video-Processor/CCTV-Video-Processor.exe` exists and its size exceeds 10 MB.
- [ ] T006 [US1] Check if Inno Setup is installed (`Get-Command iscc -ErrorAction SilentlyContinue`). If installed, run `iscc build/windows/installer.iss /DAppVersion=1.0.0` and verify `dist/CCTV-Processor-1.0.0-win64-setup.exe` is produced. If not installed, print a warning: "Inno Setup not found — skipping .exe installer packaging. PyInstaller output is at dist/CCTV-Video-Processor/".

**Checkpoint**: Windows platform build proven working — `dist/CCTV-Video-Processor/` and optionally `dist/CCTV-Processor-1.0.0-win64-setup.exe` exist.

---

## Phase 4: User Story 2 — Linux AppImage via Docker (Priority: P2)

**Goal**: Produce `dist/CCTV-Processor-1.0.0-linux-x86_64.AppImage` on Windows via Docker Desktop.

**Independent Test**: Run `build/docker/build_linux.ps1 -Version 1.0.0`; confirm `dist/CCTV-Processor-1.0.0-linux-x86_64.AppImage` exists and is > 50 MB.

- [ ] T007 [P] [US2] Create `build/docker/Dockerfile.linux-base` — Ubuntu 22.04 x86_64 base image that: (1) installs Python 3.12 via deadsnakes PPA, (2) installs pip, (3) pip-installs all app Python deps with CPU-only torch (`--index-url https://download.pytorch.org/whl/cpu`): torch, torchvision, transformers, open_clip_torch, ultralytics, pyinstaller==6.21.0, imageio-ffmpeg, PyQt6, fastapi, uvicorn, aiofiles, Pillow, opencv-python-headless, (4) installs system Qt/OpenGL libs: `libgl1-mesa-glx libglib2.0-0 libxcb-xinerama0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 libxcb-xkb1 libxkbcommon-x11-0 libegl1 libdbus-1-3 libfontconfig1`, (5) downloads appimageTool x86_64 binary to `/usr/local/bin/appimageTool` and marks it executable. Tag: `cctv-linux-base:latest`. Include `ARG PYTHON_VERSION=3.12`.
- [ ] T008 [US2] Create `build/docker/Dockerfile.linux` — inherits `FROM cctv-linux-base:latest`, sets WORKDIR `/app`, COPYs the project source (excluding what `.dockerignore` blocks), runs `python -m PyInstaller build/cctv_processor_linux.spec --distpath /tmp/dist --workpath /tmp/work --noconfirm`, then runs `bash build/linux/create_appimage.sh` to package the PyInstaller output into an AppImage, and copies the resulting `.AppImage` to `/output/CCTV-Processor-${APP_VERSION}-linux-x86_64.AppImage`. Accepts `ENV APP_VERSION=1.0.0`.
- [ ] T009 [US2] Create `build/docker/build_linux.ps1` — PowerShell script that: (1) checks Docker Desktop is running (`docker info` succeeds), exits with code 2 + message if not; (2) checks Docker is in Linux containers mode (`docker info --format "{{.OperatingSystem}}"` must NOT contain "Windows"), exits with code 1 + message if wrong mode; (3) creates `dist/` if absent; (4) builds base image with `docker build -f build/docker/Dockerfile.linux-base -t cctv-linux-base:latest .` only if `-RebuildBase` flag is set OR `cctv-linux-base:latest` doesn't exist locally; (5) runs build image with `docker build -f build/docker/Dockerfile.linux -t cctv-linux-build:latest .`; (6) runs container with `docker run --rm -e APP_VERSION=$Version -v "${PWD}/dist:/output" cctv-linux-build:latest`; (7) verifies artifact exists in `dist/`; (8) exits 0 on success, 1 on failure. Parameters: `[-Version <string>] [-RebuildBase]`.

**Checkpoint**: Linux Docker pipeline complete — `dist/CCTV-Processor-1.0.0-linux-x86_64.AppImage` producible from Windows.

---

## Phase 5: User Story 3 — Raspberry Pi .deb via Docker + QEMU (Priority: P3)

**Goal**: Produce `dist/CCTV-Processor-1.0.0-pi-arm64.deb` on Windows via QEMU-emulated ARM64 Docker.

**Independent Test**: Run `build/docker/build_pi.ps1 -Version 1.0.0`; confirm `dist/CCTV-Processor-1.0.0-pi-arm64.deb` exists and is > 50 MB.

- [ ] T010 [P] [US3] Create `build/docker/Dockerfile.pi-base` — `arm64v8/ubuntu:22.04` base image that: (1) installs Python 3.12 via deadsnakes PPA for arm64, (2) installs pip, (3) pip-installs all app Python deps with aarch64 CPU-only torch (use the correct aarch64 torch wheel URL or install without CUDA extras), (4) pip-installs: transformers, open_clip_torch, ultralytics, pyinstaller==6.21.0, imageio-ffmpeg, PyQt6, fastapi, uvicorn, aiofiles, Pillow, opencv-python-headless, (5) installs system libs: `libgl1-mesa-glx libglib2.0-0 libxcb-xinerama0 libxkbcommon-x11-0 libegl1 libdbus-1-3 libfontconfig1 dpkg-dev dpkg`. Tag: `cctv-pi-base:latest`. Include `ARG PYTHON_VERSION=3.12`.
- [ ] T011 [US3] Create `build/docker/Dockerfile.pi` — inherits `FROM cctv-pi-base:latest`, sets WORKDIR `/app`, COPYs project source, runs `python -m PyInstaller build/cctv_processor_linux.spec --distpath /tmp/dist --workpath /tmp/work --noconfirm` (reuse Linux spec for Pi), then runs `bash build/pi/create_deb.sh` to produce the `.deb` package, and copies the resulting `.deb` to `/output/CCTV-Processor-${APP_VERSION}-pi-arm64.deb`. Accepts `ENV APP_VERSION=1.0.0`.
- [ ] T012 [US3] Create `build/docker/build_pi.ps1` — PowerShell script that: (1) checks Docker Desktop is running, exits code 2 if not; (2) checks Linux containers mode, exits code 1 if Windows mode; (3) registers QEMU binfmt if not already: runs `docker buildx inspect --bootstrap` and if `linux/arm64` is absent in output, runs `docker run --privileged --rm tonistiigi/binfmt --install arm64`; (4) creates `dist/` if absent; (5) builds Pi base image with `docker build --platform linux/arm64 -f build/docker/Dockerfile.pi-base -t cctv-pi-base:latest .` only if `-RebuildBase` flag set OR image absent locally; (6) runs `docker build --platform linux/arm64 -f build/docker/Dockerfile.pi -t cctv-pi-build:latest .`; (7) runs `docker run --rm --platform linux/arm64 -e APP_VERSION=$Version -v "${PWD}/dist:/output" cctv-pi-build:latest`; (8) verifies artifact exists; (9) exits 0/1/2 per contract. Parameters: `[-Version <string>] [-RebuildBase] [-SkipQemuCheck]`.

**Checkpoint**: Pi Docker pipeline complete — `dist/CCTV-Processor-1.0.0-pi-arm64.deb` producible from Windows.

---

## Phase 6: User Story 4 — macOS via GitHub Actions (Priority: P4)

**Goal**: Update GitHub Actions workflows to read version from `VERSION` file so macOS builds are consistent with local builds.

**Independent Test**: Push tag `v1.0.0`; confirm `release.yml` triggers and produces `.dmg` artifacts.

- [ ] T013 [P] [US4] Read `.github/workflows/release.yml` and update the version-reading logic to use `cat VERSION` (or `Get-Content VERSION`) instead of any hardcoded version or git-tag-derived version. Ensure the `APP_VERSION` env var in the macOS build steps is set from the `VERSION` file. Preserve all existing `build-macos-arm` and `build-macos-intel` job structure — minimal change only.
- [ ] T014 [P] [US4] Read `.github/workflows/release-pi.yml` and apply the same `VERSION`-file-reading update as T013. Preserve existing job structure.

**Checkpoint**: CI/CD reads version from `VERSION` file — macOS builds consistent with local builds.

---

## Phase 7: User Story 5 — One-Command Orchestrator (Priority: P5)

**Goal**: `build/build_all.ps1` builds all three local platforms in sequence and prints clear status.

**Independent Test**: Run `build/build_all.ps1 -Version 1.0.0`; confirm Windows + Linux artifacts appear in `dist/`; Pi build runs (may take long); macOS section prints `git tag` instructions.

- [ ] T015 [US5] Create `build/build_all.ps1` — top-level orchestrator that: (1) reads version from `Get-Content "$PSScriptRoot/../VERSION"` unless `-Version` param supplied; (2) prints `Build CCTV Video Processor v{version} — all platforms`; (3) runs Windows build inline (calls PyInstaller + optional iscc, same logic as T005/T006), tracks status; (4) calls `& "$PSScriptRoot/docker/build_linux.ps1" -Version $Version` and captures exit code; (5) calls `& "$PSScriptRoot/docker/build_pi.ps1" -Version $Version` and captures exit code; (6) prints per-platform summary lines matching the contract format: `[Windows] SUCCESS → dist/CCTV-Processor-{v}-win64-setup.exe` or `[Windows] SKIPPED → Inno Setup not installed` or `[Linux] FAILED → see build output`; (7) prints macOS instructions: `[macOS]   INFO    → Run: git tag v{version} && git push origin v{version}`; (8) exits 0 if all non-skipped builds succeeded, 1 if any failed. Parameters: `[-Version <string>]`. Script must be idempotent (safe to re-run; `--noconfirm` ensures overwrite).

**Checkpoint**: Single command builds all three local platforms and reports status.

---

## Phase 8: Polish & Documentation

**Purpose**: Documentation updates and cross-cutting verification.

- [ ] T016 [P] Update `README.md` — add a "Building from Source" or "Building Installers" section that covers: (a) Windows: requirements (Python 3.12, PyInstaller, optional Inno Setup), command (`build/build_all.ps1`), expected output; (b) Linux: requirements (Docker Desktop in Linux containers mode), command, expected output; (c) Pi: requirements (Docker Desktop + QEMU binfmt), command, expected output; (d) macOS: GitHub Actions tag trigger instructions. Keep it concise — reference `USER_MANUAL.md` for details.
- [ ] T017 [P] Update `USER_MANUAL.md` — add a "Building Installers" appendix or section with: full step-by-step instructions for Docker Desktop setup, QEMU registration, running `build_all.ps1`, and troubleshooting common errors (Docker in Windows mode, disk space, QEMU timeout). Include the Quickstart scenario numbers as a validation checklist.
- [ ] T018 Run quickstart.md verification: execute scenarios 1–14 in order and mark each PASS/FAIL. For scenarios that require long Docker builds (5, 7, 8), note estimated time. Update `specs/013-docker-platform-builds/checklists/build-pipeline.md` to mark completed items [X] based on verification results.
- [ ] T019 Update memory file `C:\Users\User\.claude\projects\C--Users-User-Desktop-UTA-vs-code-CCTV-VIDEO-PROCESSOR-PC\memory\project_phase12_complete.md` (or create a new `project_phase13_complete.md`) to record Phase 13 completion, artifact count, branch, and date.

**Checkpoint**: All quickstart scenarios pass; documentation complete; memory updated.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1 (needs VERSION file and spec to exist)
- **Phase 3 (US1 Windows)**: Depends on Phase 2 (onnx fix must be in place)
- **Phase 4 (US2 Linux)**: Depends on Phase 1 only (independent of US1)
- **Phase 5 (US3 Pi)**: Depends on Phase 1 only (independent of US1 and US2)
- **Phase 6 (US4 macOS CI)**: Depends on Phase 1 only (VERSION file must exist)
- **Phase 7 (US5 Orchestrator)**: Depends on Phases 3, 4, 5 (calls all three build scripts)
- **Phase 8 (Polish)**: Depends on all prior phases

### User Story Dependencies

- **US1 (Windows)**: Requires Phase 2 spec fix. Blocks nothing — independent.
- **US2 (Linux)**: Independent of US1. Can run in parallel with US1 if Docker available.
- **US3 (Pi)**: Independent of US1 and US2. Can run in parallel. (Long — QEMU emulation.)
- **US4 (macOS CI)**: Independent of all local builds. Read-only GitHub Actions update.
- **US5 (Orchestrator)**: Depends on US1 script logic, US2 build_linux.ps1, US3 build_pi.ps1 all existing.

### Within Each User Story

- Dockerfiles (base → build) must be created before the PS1 launcher that references them
- Base Dockerfile before build Dockerfile within each platform (inherited FROM tag)

### Parallel Opportunities

- T007 (Dockerfile.linux-base) and T010 (Dockerfile.pi-base) can be written in parallel [P]
- T013 (release.yml) and T014 (release-pi.yml) can be updated in parallel [P]
- T016 (README) and T017 (USER_MANUAL) can be written in parallel [P]

---

## Parallel Example: Linux + Pi Base Images

```powershell
# After Phase 1 & 2, these two Docker base builds can run in parallel:
docker build -f build/docker/Dockerfile.linux-base -t cctv-linux-base:latest .
docker build --platform linux/arm64 -f build/docker/Dockerfile.pi-base -t cctv-pi-base:latest .
```

---

## Implementation Strategy

### MVP First (US1 — Windows Build)

1. Complete Phase 1 (Setup): VERSION, .dockerignore
2. Complete Phase 2 (Foundational): Fix onnx crash in Windows spec
3. Complete Phase 3 (US1): Run Windows PyInstaller build → verify exe
4. **STOP and VALIDATE**: Windows installer works independently
5. Proceed to US2 Linux, then US3 Pi

### Incremental Delivery

1. Phase 1 + 2 → Foundation ready (onnx fix applied)
2. Phase 3 (US1) → Windows build working → validate
3. Phase 4 (US2) → Linux build working → validate
4. Phase 5 (US3) → Pi build working (slow) → validate
5. Phase 6 (US4) → macOS CI update → validate on tag push
6. Phase 7 (US5) → Orchestrator wires everything together
7. Phase 8 → Documentation + verification

### Critical Path

`T001 → T002 → T004 → T005 → T006` (Windows MVP, unblocks everything)  
`T007 → T008 → T009` (Linux pipeline)  
`T010 → T011 → T012` (Pi pipeline)  
`T015` (Orchestrator — needs T005–T012 to exist)

---

## Notes

- No pytest tests in this phase (build infrastructure exemption per Principle III)
- T004 (onnx spec fix) is the single most critical task — confirmed crash blocks all Windows builds
- Pi builds via QEMU take 60–90 min for first base image; plan accordingly
- All PS1 scripts must handle paths with spaces (use double-quoted `"${PWD}/dist"` not single-quoted)
- `--noconfirm` in PyInstaller calls is the idempotency mechanism (overwrites without asking)
- Docker bind-mount on Windows: use `"${PWD}/dist:/output"` (PowerShell PWD returns Windows path; Docker Desktop translates to Linux path inside container)

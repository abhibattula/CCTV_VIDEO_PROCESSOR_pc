# Research: Cross-Platform Builds from Windows via Docker

**Feature**: 013-docker-platform-builds | **Date**: 2026-07-01

---

## Decision 1 — Docker Build Strategy: Two-Stage Base Images

**Decision**: Use two Dockerfile pairs per platform: `Dockerfile.linux-base` (bakes all Python deps) + `Dockerfile.linux` (inherits base, COPYs source, runs PyInstaller). Same for Pi: `Dockerfile.pi-base` + `Dockerfile.pi`.

**Rationale**: PyInstaller builds inside Docker have two distinct phases: (1) dependency installation (~45–60 min for torch 2GB + transformers 1GB) and (2) source compilation (~5–10 min). If these are in a single Dockerfile, every source change triggers a full dep reinstall. Two-stage decouples them: the base image is rebuilt only when `requirements.txt` changes; the build image is rebuilt on every source change in ~5 min.

**Alternatives considered**:
- Single Dockerfile with BuildKit `--mount=type=cache`: Faster than full reinstall but still downloads pip packages each time (cache is local to Docker daemon, not portable). Less explicit than two-stage.
- Install deps fresh each build: Simple but 45–60 min per build makes iteration impossible.

---

## Decision 2 — Artifact Transfer: Volume Bind-Mount

**Decision**: Use `docker run -v "${PWD}/dist:/output" ...` to bind-mount the Windows `dist/` directory into the container at `/output`. PyInstaller and packaging scripts write directly to `/output/`.

**Rationale**: Volume bind-mount is the simplest and most debuggable transfer mechanism. No `docker cp` lifecycle management, no BuildKit export flags. The developer can watch `dist/` populate in real time in Windows Explorer.

**Alternatives considered**:
- `docker buildx build --output type=local,dest=dist/`: Requires BuildKit and only works during `docker build`, not `docker run`. Harder to debug.
- `docker cp container_id:/app/dist/artifact dist/`: Requires container lifecycle management (start, copy, stop, rm). More steps, more error surface.

---

## Decision 3 — Version Source: `VERSION` File

**Decision**: A plain-text `VERSION` file at the repo root (e.g., `1.0.0`) is the single source of truth. `build_all.ps1` reads it via `Get-Content VERSION`. An optional `-Version` parameter overrides the file. The GitHub Actions `release.yml` reads the same file.

**Rationale**: A `VERSION` file is the simplest single source of truth for semver — no git tag dependency, no pyproject.toml parsing, no manual typing. The existing `release.yml` can be updated to read `VERSION` via `cat VERSION` in the shell step, ensuring CI and local builds use the same version.

**Alternatives considered**:
- Manual `-Version` parameter only: Error-prone (typos), no consistency guarantee between local and CI builds.
- Auto-detect from latest git tag: Fails if no tags exist; ties version to git workflow prematurely.

---

## Decision 4 — QEMU binfmt for ARM64 (Pi) Builds

**Decision**: Register ARM64 emulation via `docker run --privileged --rm tonistiigi/binfmt --install arm64` once per Docker Desktop session. `build_pi.ps1` checks whether binfmt is registered and runs this command only if needed.

**Rationale**: `tonistiigi/binfmt` is the standard Docker-recommended method for multi-arch emulation on Docker Desktop for Windows. It uses Linux kernel binfmt_misc to intercept ARM64 ELF binaries and route them to QEMU. Registration survives across container runs but resets on Docker Desktop restart.

**Check command**: `docker buildx inspect --bootstrap | Select-String arm64` — if output contains `linux/arm64`, binfmt is registered.

**Alternatives considered**:
- `--platform linux/arm64` without binfmt: Works only if Docker Desktop has QEMU built-in (4.x+), but registration is still required for some scenarios. Explicit registration is safer.
- Native Pi build via SSH: Requires a physical Pi, which defeats the purpose of this phase.

---

## Decision 5 — appimageTool in Linux Base Image

**Decision**: Pre-download `appimageTool-x86_64.AppImage` into the Linux base image during `docker build` (`RUN curl -L ... -o /usr/local/bin/appimageTool && chmod +x /usr/local/bin/appimageTool`). The existing `create_appimage.sh` already downloads it if absent — but in Docker, baking it into the base avoids per-build network downloads.

**Rationale**: appimageTool is a ~800 KB static binary. Baking it into the base image makes the build image self-contained and reproducible offline (after base image is built).

**Alternatives considered**:
- Let `create_appimage.sh` download it at runtime: Works but requires internet per build run; slower.

---

## Decision 6 — Python Version Pinning in Containers

**Decision**: Pin to Python 3.12 in all Docker base images (matches the Windows host Python 3.12.10). Use `python3.12` explicitly in `apt-get install` or build from deadsnakes PPA if ubuntu:22.04 ships an older version.

**Rationale**: Ubuntu 22.04 ships Python 3.10 by default. Using `deadsnakes/ppa` to install `python3.12` ensures version consistency between the Windows host and all containers. Mismatched Python versions can cause subtle ABI incompatibilities in compiled extensions (torch C extensions).

**Ubuntu 22.04 Python 3.12 install commands**:
```sh
add-apt-repository ppa:deadsnakes/ppa -y
apt-get install -y python3.12 python3.12-venv python3.12-dev python3-pip
```

---

## Decision 7 — Qt/Display Dependencies in Docker

**Decision**: Install headless Qt and OpenGL system libraries in the Linux base images even though PyInstaller doesn't run the app — PyInstaller's analysis phase imports PyQt6 modules which link against system libs during the `collect_all()` scan.

**Required packages** (Ubuntu 22.04):
```
libgl1-mesa-glx libglib2.0-0 libxcb-xinerama0 libxcb-icccm4 libxcb-image0
libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 libxcb-xkb1 libxkbcommon-x11-0
libegl1 libdbus-1-3 libfontconfig1
```
**Why not Xvfb**: PyInstaller analysis doesn't need a running display, only the shared libraries to be present. `DISPLAY` env var is not needed during `pyinstaller` command.

---

## Decision 8 — Inno Setup Availability Check

**Decision**: `build_all.ps1` checks for Inno Setup via `Get-Command iscc -ErrorAction SilentlyContinue`. If absent, the Windows `.exe` packaging step (only the `iscc` step — not PyInstaller) is skipped with a warning; the PyInstaller `.exe` binary is still produced in `dist/CCTV-Video-Processor/`. The developer can install Inno Setup later to package it.

**Rationale**: Inno Setup is free but not pre-installed everywhere. Separating the PyInstaller step (produces `dist/CCTV-Video-Processor/`) from the Inno Setup step (produces `CCTV-Processor-{version}-win64-setup.exe`) allows the build to be useful even without the installer packager.

---

## Decision 9 — Docker Desktop Mode Check

**Decision**: `build_linux.ps1` and `build_pi.ps1` check Docker context via `docker info --format "{{.OperatingSystem}}"`. If the output contains "Windows" (Windows containers mode), the script exits with a clear error: "Docker is in Windows containers mode. Switch to Linux containers mode in Docker Desktop system tray."

**Rationale**: A common mistake on Windows is running Docker in Windows containers mode. Linux container builds silently fail in this mode. An early, clear check saves significant debugging time.

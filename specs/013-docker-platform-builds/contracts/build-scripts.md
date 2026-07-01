# Contract: Build Script Interfaces

**Feature**: 013-docker-platform-builds | **Date**: 2026-07-01

---

## build_all.ps1

**Location**: `build/build_all.ps1`  
**Purpose**: Orchestrates all local platform builds (Windows, Linux, Pi) in sequence.

### Signature
```powershell
build_all.ps1 [-Version <string>]
```

### Parameters
| Parameter | Required | Default | Description |
|---|---|---|---|
| `-Version` | No | Reads `VERSION` file | Semver string e.g. `1.0.0` |

### Exit Codes
| Code | Meaning |
|---|---|
| 0 | All non-skipped builds succeeded |
| 1 | One or more builds failed (skipped steps do not count as failure) |

### Stdout Contract
For each platform, prints one status line:
```
[Windows] SUCCESS → dist/CCTV-Processor-1.0.0-win64-setup.exe
[Linux]   SUCCESS → dist/CCTV-Processor-1.0.0-linux-x86_64.AppImage
[Pi]      SKIPPED → Docker Desktop not running
[macOS]   INFO    → Push tag v1.0.0 to trigger GitHub Actions build
```

---

## build_linux.ps1

**Location**: `build/docker/build_linux.ps1`  
**Purpose**: Builds the Linux x86_64 AppImage using Docker.

### Signature
```powershell
build_linux.ps1 [-Version <string>] [-RebuildBase]
```

### Parameters
| Parameter | Required | Default | Description |
|---|---|---|---|
| `-Version` | No | Reads `VERSION` file | Semver string |
| `-RebuildBase` | No | `$false` | Force rebuild of `cctv-linux-base` image even if cached |

### Exit Codes
| Code | Meaning |
|---|---|
| 0 | AppImage produced at `dist/CCTV-Processor-{version}-linux-x86_64.AppImage` |
| 1 | Docker not available, Docker in Windows containers mode, or build failed |
| 2 | Prerequisites check failed (Docker Desktop not running) |

### Prerequisites Checked
1. `docker info` succeeds (Docker Desktop is running)
2. `docker info --format "{{.OperatingSystem}}"` does NOT contain "Windows" (Linux containers mode)

---

## build_pi.ps1

**Location**: `build/docker/build_pi.ps1`  
**Purpose**: Builds the Raspberry Pi ARM64 `.deb` using Docker + QEMU emulation.

### Signature
```powershell
build_pi.ps1 [-Version <string>] [-RebuildBase] [-SkipQemuCheck]
```

### Parameters
| Parameter | Required | Default | Description |
|---|---|---|---|
| `-Version` | No | Reads `VERSION` file | Semver string |
| `-RebuildBase` | No | `$false` | Force rebuild of `cctv-pi-base` image |
| `-SkipQemuCheck` | No | `$false` | Skip QEMU binfmt registration check (if already registered) |

### Exit Codes
| Code | Meaning |
|---|---|
| 0 | `.deb` produced at `dist/CCTV-Processor-{version}-pi-arm64.deb` |
| 1 | Build failed inside container |
| 2 | Docker not running or in Windows containers mode |

### QEMU Registration
Script runs `docker buildx inspect --bootstrap` and checks for `linux/arm64` in output. If absent, runs:
```
docker run --privileged --rm tonistiigi/binfmt --install arm64
```

---

## Docker Container Interface

All build containers (linux-build, pi-build) adhere to this interface:

### Volumes
| Host Path | Container Path | Purpose |
|---|---|---|
| `${PWD}/dist` | `/output` | Artifact output directory |

### Environment Variables
| Variable | Required | Description |
|---|---|---|
| `APP_VERSION` | Yes | Semver string passed as `-e APP_VERSION=1.0.0` |

### Output Contract
Container MUST write exactly one artifact to `/output/`:
- Linux: `/output/CCTV-Processor-{APP_VERSION}-linux-x86_64.AppImage`
- Pi: `/output/CCTV-Processor-{APP_VERSION}-pi-arm64.deb`

Container exit code 0 = success, non-zero = failure.

---

## Dockerfile.linux-base / Dockerfile.pi-base Interface

### Build Args
| Arg | Default | Description |
|---|---|---|
| `PYTHON_VERSION` | `3.12` | Python version to install via deadsnakes PPA |

### Baked Contents
- Python 3.12 + pip
- All app Python deps (torch CPU, transformers, open_clip, ultralytics, PyInstaller, imageio-ffmpeg, PyQt6, fastapi, uvicorn, aiofiles, Pillow, opencv-python-headless)
- System Qt/OpenGL libs (libgl1-mesa-glx, libxcb-*, etc.)
- Linux-only: appimageTool binary at `/usr/local/bin/appimageTool`
- Pi-only: dpkg-dev, dpkg

### Tag Convention
- `cctv-linux-base:latest`
- `cctv-pi-base:latest`

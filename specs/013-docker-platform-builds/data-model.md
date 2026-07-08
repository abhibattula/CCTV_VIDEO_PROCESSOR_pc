# Data Model: Cross-Platform Builds from Windows

**Feature**: 013-docker-platform-builds | **Date**: 2026-07-01

---

## Entities

### BuildArtifact

Represents a single platform installer produced by the build pipeline.

| Field | Type | Constraints |
|---|---|---|
| `platform` | enum | `windows`, `linux`, `pi`, `macos` |
| `version` | string | semver from `VERSION` file (e.g., `1.0.0`) |
| `file_name` | string | `CCTV-Processor-{version}-{platform_suffix}.{ext}` |
| `file_path` | Path | Absolute path under `dist/` |
| `file_ext` | enum | `.exe`, `.AppImage`, `.deb`, `.dmg` |
| `build_status` | enum | `pending`, `running`, `success`, `failed`, `skipped` |

**Naming pattern**:
| Platform | Suffix | Extension |
|---|---|---|
| Windows installer | `win64-setup` | `.exe` |
| Linux | `linux-x86_64` | `.AppImage` |
| Raspberry Pi | `pi-arm64` | `.deb` |
| macOS arm64 | `macos-arm64` | `.dmg` |
| macOS intel | `macos-intel` | `.dmg` |

---

### DockerImage

Represents a Docker image used in the build pipeline.

| Field | Type | Description |
|---|---|---|
| `name` | string | e.g., `cctv-linux-base`, `cctv-linux-build`, `cctv-pi-base`, `cctv-pi-build` |
| `platform` | string | `linux/amd64` or `linux/arm64` |
| `base_image` | string | `ubuntu:22.04` or `arm64v8/ubuntu:22.04` |
| `python_version` | string | `3.12` |
| `role` | enum | `base` (bakes deps), `build` (runs PyInstaller) |
| `dockerfile` | string | Path to Dockerfile relative to `build/docker/` |

**Image dependency graph**:
```
ubuntu:22.04          →  cctv-linux-base  →  cctv-linux-build
arm64v8/ubuntu:22.04  →  cctv-pi-base     →  cctv-pi-build
```

---

### BuildEnvironment

Describes the tooling requirements for each build step.

| Environment | Required Tools | Optional |
|---|---|---|
| Windows | Python 3.12, PyInstaller 6.x | Inno Setup 6.x (for `.exe` packaging) |
| Linux Docker | Docker Desktop (Linux containers), Docker buildx | — |
| Pi Docker | Docker Desktop, QEMU binfmt arm64 | — |
| macOS (CI) | GitHub Actions `macos-14`/`macos-13` runners, Xcode CLI | — |

---

### VERSION

A plain-text file at the repository root containing a single semver string.

| Field | Type | Example |
|---|---|---|
| `content` | string | `1.0.0` |
| `path` | Path | `{repo_root}/VERSION` |

**Read by**: `build_all.ps1`, `build_linux.ps1`, `build_pi.ps1`, `.github/workflows/release.yml`  
**Override**: All scripts accept an optional `-Version x.y.z` parameter that takes precedence over file content.

---

## State Transitions: BuildArtifact.build_status

```
pending → running → success
                 → failed
         skipped  (prerequisite missing: Docker not running, QEMU not available, Inno Setup absent)
```

- `skipped` is non-fatal: `build_all.ps1` continues to remaining platforms.
- `failed` is reported but non-fatal (same — `build_all.ps1` continues).
- Final summary prints one line per platform with status + artifact path (or skip/fail reason).

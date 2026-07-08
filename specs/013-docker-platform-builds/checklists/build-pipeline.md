# Build Pipeline Checklist: 013-docker-platform-builds

**Purpose**: Validate requirements quality for build pipeline reliability — Docker reproducibility, QEMU ARM64 robustness, artifact transfer, prerequisite failure handling, idempotency, and Windows spec packaging fixes.
**Created**: 2026-07-01
**Feature**: [spec.md](../spec.md)
**Audience**: Implementation reviewer

---

## Requirement Completeness

- [ ] CHK001 - Are Docker base image build time budgets documented with specific upper-bound figures for both first-run and incremental runs? [Completeness, Plan §Performance Goals]
- [ ] CHK002 - Are all Ubuntu 22.04 system library requirements needed for PyInstaller analysis of PyQt6/OpenGL fully enumerated in the contract? [Completeness, Research §7, Contracts §Dockerfile]
- [ ] CHK003 - Is the `onnx.reference` Windows segfault (exit code 3221225477 = STATUS_ACCESS_VIOLATION) documented as a known issue requiring PyInstaller `excludes` fix before the Windows build can complete? [Completeness, Gap — confirmed by failed build]
- [ ] CHK004 - Is a requirement defined for the `dist/` directory being created automatically if absent before a build runs? [Completeness, Gap]
- [ ] CHK005 - Are all `Dockerfile.linux-base` and `Dockerfile.pi-base` build-time `ARG` values documented in the contract with defaults and override instructions? [Completeness, Contracts §Dockerfile Base]
- [ ] CHK006 - Is there a requirement specifying which packages must be added to the Windows PyInstaller `excludes` list to avoid import analysis crashes (`onnx`, `onnxruntime`, `onnxslim`)? [Completeness, Gap — analysis-phase crash fix]

---

## Requirement Clarity

- [ ] CHK007 - Is the Docker OS check criterion ("does NOT contain Windows") specified with exact match semantics (case-insensitive substring vs. exact equality)? [Clarity, Quickstart §4, Contracts §build_linux.ps1]
- [ ] CHK008 - Is the QEMU registration check phrasing "output must contain linux/arm64" defined with exact string, case sensitivity, and which output stream is checked? [Clarity, Quickstart §7, Research §4]
- [ ] CHK009 - Are the artifact minimum-size pass thresholds (AppImage/deb >50 MB, Windows exe >10 MB) justified with an explanation of what too-small indicates? [Clarity, Quickstart §2, §6, §9]
- [ ] CHK010 - Is the distinction between the `-Version` PowerShell parameter and the `APP_VERSION` Docker environment variable explicitly mapped so both always carry the same value? [Clarity, Contracts §Docker Container Interface]
- [ ] CHK011 - Is "Build completes with exit code 0" the sole acceptance criterion for base image builds, or is post-build artifact presence verification also required? [Clarity, Quickstart §5, §8]
- [ ] CHK012 - Is the `cctv-linux-build` Docker image tag defined (the build-stage image produced by `Dockerfile.linux`)? The data model names it but the contracts only reference the base tag convention. [Clarity, Data Model §DockerImage vs Contracts §Dockerfile]

---

## Requirement Consistency

- [ ] CHK013 - Are exit codes for `build_linux.ps1` (codes 0/1/2) and `build_pi.ps1` (codes 0/1/2) consistent in their semantic meaning across both scripts? [Consistency, Contracts §build_linux.ps1, §build_pi.ps1]
- [ ] CHK014 - Is the macOS "INFO → push tag" stdout line in `build_all.ps1` consistent with the GitHub Actions workflow trigger requirements in the spec (US4)? [Consistency, Contracts §build_all.ps1, Spec §US4]
- [ ] CHK015 - Does the `DockerImage.dockerfile` field path convention (`build/docker/`) in the data model align with the plan's file locations for all four Dockerfiles? [Consistency, Data Model §DockerImage, Plan §Project Structure]
- [ ] CHK016 - Is the `BuildArtifact.file_name` naming pattern applied consistently in quickstart pass criteria for all four platforms? [Consistency, Data Model §BuildArtifact, Quickstart §2–§9]

---

## Acceptance Criteria Quality

- [ ] CHK017 - Is the idempotency acceptance criterion ("no error about file already exists") sufficient, or should it also require that artifact checksums are stable across identical re-runs? [Measurability, Quickstart §11]
- [ ] CHK018 - Is the macOS CI acceptance criterion (quickstart §13) measurable within the local build pipeline, or does it depend on external GitHub Actions state that cannot be validated locally? [Measurability, Quickstart §13, Gap]
- [ ] CHK019 - Is incremental build time (subsequent Linux build ≤10 min, Pi ≤15 min) expressed as a verifiable acceptance criterion in any quickstart scenario, or only as a plan annotation? [Measurability, Plan §Performance Goals, Gap]
- [ ] CHK020 - Can the `.dockerignore` verification criterion (quickstart §14) be objectively evaluated by listing required entries — or is "contains entries for dist/, build/work/, .git/, __pycache__/" the complete measurable set? [Measurability, Quickstart §14]

---

## Scenario Coverage

- [ ] CHK021 - Are requirements defined for the partial build failure scenario (e.g., Linux build succeeds but Pi base image build fails mid-way)? Does `build_all.ps1` continue or halt? [Coverage, Data Model §BuildArtifact State Transitions]
- [ ] CHK022 - Are requirements defined for the case where the `VERSION` file is missing, empty, or contains an invalid non-semver string? [Coverage, Gap, Data Model §VERSION]
- [ ] CHK023 - Are requirements defined for QEMU binfmt registration being lost between Pi base build and Pi source build (Docker Desktop restart during a long build)? [Coverage, Research §4, Gap]
- [ ] CHK024 - Are requirements defined for Docker image cache invalidation when `requirements.txt` changes between the base image build and the source build? [Coverage, Research §1, Gap]
- [ ] CHK025 - Are requirements defined for `build_all.ps1` behavior when PyInstaller is not installed on Windows (should Windows build be skipped or fail)? [Coverage, Contracts §build_all.ps1, Gap]
- [ ] CHK026 - Is there a requirement covering `build_pi.ps1 -SkipQemuCheck` behavior — specifically what guarantees the skip is safe if QEMU is not actually registered? [Coverage, Contracts §build_pi.ps1]

---

## Edge Case Coverage

- [ ] CHK027 - Is there a minimum disk space requirement documented for the Docker layer cache (torch CPU ~2 GB + transformers ~1 GB per image × 2 images = ~6 GB)? [Edge Case, Gap]
- [ ] CHK028 - Is the `.dockerignore` required to exclude large model cache directories (`.cache/huggingface/`, `models/`) that could bloat the Docker build context and cause multi-GB uploads to the daemon? [Edge Case, Gap]
- [ ] CHK029 - Is there a requirement for how `build_linux.ps1` handles the case where the `dist/` bind-mount path contains spaces (Windows user profiles like `C:\Users\User Name\`)? [Edge Case, Gap]
- [ ] CHK030 - Are requirements defined for the network dependency on pulling `tonistiigi/binfmt` from Docker Hub during QEMU registration (failure if no internet)? [Edge Case, Dependency, Gap]

---

## Non-Functional Requirements

- [ ] CHK031 - Is there a stated requirement for reproducibility — i.e., that two Linux builds from the same source at the same version produce byte-identical AppImages? [Non-Functional, Gap]
- [ ] CHK032 - Is internet access during `docker build` (for `pip install`, `deadsnakes PPA`, `appimageTool` download) explicitly documented as a non-optional build-time dependency? [Non-Functional, Gap]
- [ ] CHK033 - Is there a requirement that the base images are buildable in air-gapped environments (e.g., via offline pip cache), or is online access assumed without restriction? [Non-Functional, Assumption]

---

## Dependencies & Assumptions

- [ ] CHK034 - Is the assumption that Docker Desktop 4.x on Windows includes Linux kernel emulation sufficient for QEMU binfmt (arm64) explicitly validated? [Assumption, Research §4]
- [ ] CHK035 - Is the assumption that `deadsnakes/ppa` provides Python 3.12 for Ubuntu 22.04 validated and documented with a fallback if PPA is unavailable? [Assumption, Research §6]
- [ ] CHK036 - Is the dependency on `tonistiigi/binfmt` (an external Docker Hub image) acknowledged with a risk note about its availability or future deprecation? [Dependency, Research §4]
- [ ] CHK037 - Is it documented whether `appimageTool` baked into the base image requires a specific FUSE kernel module available in the Docker container? [Dependency, Research §5, Gap]

---

## Ambiguities & Conflicts

- [ ] CHK038 - Does the spec or plan explicitly require excluding `onnx.reference` (and transitive packages) from PyInstaller analysis to resolve the Windows `STATUS_ACCESS_VIOLATION` crash? [Ambiguity, Gap — required fix confirmed by build log]
- [ ] CHK039 - Is it clear whether `Dockerfile.linux` produces a named image tag (`cctv-linux-build:latest`) that is cached between runs, or is it always run with `docker run` from the base and discarded? [Ambiguity, Plan §Phase 2]
- [ ] CHK040 - Is the behavior of the `--noconfirm` flag in the Windows PyInstaller command documented as the idempotency mechanism (overwrite existing `dist/` without prompting)? [Ambiguity, Quickstart §2]
- [ ] CHK041 - Is there a conflict between the plan's note that "no production Python code changes" occur in this phase and the requirement to fix `build/cctv_processor_windows.spec` (a build file, not production code)? [Conflict, Plan §Constitution Check Principle III]

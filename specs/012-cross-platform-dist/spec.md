# Feature Specification: Cross-Platform Distribution

**Feature Branch**: `012-cross-platform-dist`  
**Created**: 2026-06-30  
**Status**: Draft  
**Input**: User description: "Phase 12: Cross-platform distribution — PyInstaller packaging for Windows/macOS/Linux/Raspberry Pi (including 3-4 GB RAM Pi support in YOLO-only mode), first-run AI wizard, GitHub Actions CI/CD releasing .exe/.dmg/.AppImage/.deb on v*.*.* tags. Fix 6 pre-packaging code issues. Non-technical users download and double-click, app runs without Python."

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Download and Install on Windows (Priority: P1)

A non-technical Windows user visits the project's GitHub Releases page, downloads a single installer file, double-clicks it, and follows a familiar Next → Next → Finish wizard. The CCTV Processor app appears in their Start Menu and on their Desktop. On first launch, the app detects that AI model files are not yet present, shows a friendly setup screen that downloads them automatically, and then opens the main interface — all without the user ever touching a terminal or knowing Python exists.

**Why this priority**: Windows is the most common target platform for non-technical users. A working Windows installer validates the entire packaging approach and is the fastest path to user value.

**Independent Test**: Can be fully tested by running the produced `.exe` installer on a clean Windows 11 machine with no Python installed, launching the app, completing the first-run wizard, and confirming the main UI appears and can load a video file.

**Acceptance Scenarios**:

1. **Given** a clean Windows 11 PC with no Python, **When** the user runs the `.exe` installer, **Then** the app installs silently with no errors, appears in Start Menu, and a desktop shortcut is created.
2. **Given** the app is freshly installed with no AI models present, **When** the user launches it for the first time, **Then** a setup wizard appears showing a progress bar while downloading AI models, and the main app opens when complete.
3. **Given** the setup wizard is on screen, **When** the user clicks "Skip for now", **Then** the wizard closes and the main app opens (AI features will show as unavailable).
4. **Given** the app is already set up, **When** the user launches it again, **Then** the wizard does NOT appear — it goes straight to the main interface.

---

### User Story 2 — Install on Raspberry Pi (Priority: P2)

A home-security enthusiast with a Raspberry Pi 4 (4 GB RAM model) or Raspberry Pi 5 downloads a `.deb` package and installs it with a single command (`sudo dpkg -i cctv-processor.deb`). The app launches, detects that this is a Pi with limited RAM, and automatically runs in "YOLO-only" mode — motion detection and video export work fully, but AI image descriptions in reports are gracefully disabled with a clear explanation. On a Pi 5 with 8 GB RAM, all AI features are available.

**Why this priority**: The Raspberry Pi is a core deployment target for home CCTV systems. Ensuring it works on 3–4 GB RAM models makes the app accessible to the most common Pi configuration.

**Independent Test**: Install the `.deb` on a Pi 4 4 GB running Pi OS 64-bit (Bookworm). Confirm the app launches, detects YOLO-only mode, successfully processes a video clip, and exports clips and a report (with AI descriptions correctly shown as unavailable).

**Acceptance Scenarios**:

1. **Given** a Pi 4 with 4 GB RAM running Pi OS 64-bit, **When** the user installs the `.deb` and launches the app, **Then** the app starts, YOLO detection is available, and a message confirms AI descriptions are disabled due to insufficient RAM.
2. **Given** the Pi app is running, **When** the user processes a video and exports clips, **Then** the video export, heatmap, and report (without AI descriptions) are produced correctly.
3. **Given** a Pi 5 with 8 GB RAM, **When** the user launches the app, **Then** all AI features are available including Florence-2 image descriptions.
4. **Given** the first-run wizard appears on a 3–4 GB Pi, **When** setup runs, **Then** only the YOLOv8n model (6 MB) is downloaded; Florence-2 and CLIP downloads are skipped with a clear explanation.

---

### User Story 3 — Install on macOS (Priority: P3)

A macOS user (Apple Silicon or Intel) downloads a `.dmg` file, drags the app to Applications, and launches it. On first launch, macOS may show a security warning ("unidentified developer") which the user can bypass with right-click → Open. The setup wizard runs and the app functions identically to Windows.

**Why this priority**: macOS support expands reach significantly but requires no code logic changes beyond the build configuration. The security bypass (no Apple Developer Account) is a known limitation, clearly documented.

**Independent Test**: Open the `.dmg` on macOS 13+ (arm64 and intel separately), copy to Applications, launch via right-click → Open, complete the first-run wizard, load a video.

**Acceptance Scenarios**:

1. **Given** a macOS 13+ machine (arm64), **When** the user opens the `.dmg` and drags the app to Applications, **Then** the app appears in Applications and can be launched.
2. **Given** first-time launch on macOS, **When** macOS shows a "cannot verify developer" dialog, **Then** the user can right-click → Open to bypass it, and the app proceeds normally.
3. **Given** the app is running on macOS, **When** the user clicks the system tray icon, **Then** the window shows or hides correctly (single-click restore, not double-click, on macOS 13+).

---

### User Story 4 — Install on Linux (Priority: P4)

A Linux user downloads a self-contained `.AppImage`, marks it executable, and double-clicks to run — no installation or dependencies required. The app works on any modern x86_64 Linux distribution.

**Why this priority**: AppImage provides the broadest Linux compatibility without distro-specific packaging. Lower priority than Pi since Pi gets a dedicated `.deb`.

**Independent Test**: Download the `.AppImage` on Ubuntu 22.04, mark executable (`chmod +x`), double-click, complete wizard.

**Acceptance Scenarios**:

1. **Given** Ubuntu 22.04 x86_64, **When** the user marks the AppImage executable and runs it, **Then** the app launches with no installation required.
2. **Given** the app is running on Linux, **When** the user processes a video, **Then** all detection and export features work correctly.

---

### User Story 5 — Developer Publishes a Release (Priority: P5)

A developer pushes a git tag (`v1.0.0`) to GitHub. GitHub Actions automatically builds installers for all four platforms in parallel and publishes them as assets on a new GitHub Release — no manual build steps, no local build machines required for Windows, macOS, Linux, or Pi.

**Why this priority**: Automated CI/CD ensures every release is reproducible and eliminates manual build errors. Lower priority only because it doesn't affect end-users directly — but it enables all other stories to be distributed.

**Independent Test**: Push a `v0.0.1-test` tag to GitHub, confirm all 5 installer artifacts appear on the GitHub Release within 60 minutes.

**Acceptance Scenarios**:

1. **Given** a git tag `v*.*.*` is pushed, **When** GitHub Actions runs, **Then** Windows `.exe`, macOS arm64 `.dmg`, macOS intel `.dmg`, Linux `.AppImage`, and Pi `.deb` are all built and attached to the GitHub Release.
2. **Given** any build job fails, **When** the failure is reported, **Then** the other platform builds continue (failures are isolated per platform).
3. **Given** all builds succeed, **When** the Release is published, **Then** release notes are auto-generated from commit messages since the last tag.

---

### Edge Cases

- What happens if the user's internet drops mid-download in the setup wizard? The wizard shows an error message with a Retry button; no partial files are left on disk.
- What happens if the user has less than 2 GB of free disk space during setup? The wizard checks available disk space before downloading and shows a warning if insufficient.
- What happens if a model download fails (server unreachable)? The wizard shows which models failed and allows retrying; YOLOv8n failure is treated as critical (blocks usage), Florence-2/CLIP failure is treated as non-critical (app continues without AI features).
- What happens if the user runs the installer while an older version of the app is already installed? The installer replaces the existing version in-place. User data in `~/.cctv_processor/` is preserved.
- What happens if the app is already running when the user tries to launch a second instance? A second instance detects the running backend on port 5151 and reuses it, or shows a "already running" notification.
- What happens on a Pi 4 2 GB model (1.7 GB usable)? The app still launches, but detection resolution is automatically reduced to 160×90 by the existing RAM-scaling logic. A warning banner is shown in the UI.

---

## Requirements *(mandatory)*

### Functional Requirements

**Packaging**

- **FR-001**: The app MUST be distributed as a self-contained installer on Windows that requires no Python, pip, or developer tools to install.
- **FR-002**: The app MUST be distributed as a `.dmg` on macOS that requires only dragging to Applications to install (ad-hoc signed; users bypass Gatekeeper via right-click → Open).
- **FR-003**: The app MUST be distributed as a self-contained `.AppImage` on Linux x86_64 that requires no installation (mark executable and run).
- **FR-004**: The app MUST be distributed as a `.deb` package on Raspberry Pi ARM64 (Pi OS 64-bit Bookworm) installable via `sudo dpkg -i`.
- **FR-005**: All distributables MUST include the complete Python runtime, all libraries, and the application code — users never interact with Python directly.
- **FR-006**: All distributables MUST include FFmpeg bundled (via the existing `imageio-ffmpeg` package) so no separate FFmpeg installation is required.

**First-Run Setup Wizard**

- **FR-007**: On first launch, the app MUST show a setup wizard before the main interface appears.
- **FR-008**: The setup wizard MUST show a system check step (RAM, platform, FFmpeg availability) with clear pass/fail indicators.
- **FR-009**: The setup wizard MUST download AI model files (YOLOv8n, Florence-2, CLIP) with a progress bar showing download percentage and file sizes.
- **FR-010**: On devices with less than 5 GB RAM, the setup wizard MUST skip Florence-2 and CLIP downloads and display a clear message explaining which features are unavailable and why (RAM requirement).
- **FR-011**: On Raspberry Pi devices with 3–4 GB RAM specifically, the wizard MUST display a Pi-specific message: motion detection (YOLO) works fully, AI image descriptions are not available on this device.
- **FR-012**: The setup wizard MUST provide a "Skip for now" option on every step; skipping records that setup was completed so the wizard does not reappear on next launch.
- **FR-013**: If a model download fails, the wizard MUST show the error clearly, distinguish between critical failures (YOLOv8n) and non-critical failures (Florence-2, CLIP), and offer a Retry button.
- **FR-014**: The setup wizard MUST check available disk space before beginning downloads and warn the user if less than 3 GB is free.

**Code Fixes (Pre-Packaging)**

- **FR-015**: All application resource paths (web frontend files, HTML templates) MUST resolve correctly when the app runs from a frozen/installed bundle, not just from the development source tree.
- **FR-016**: The Florence-2 AI model availability check MUST respect the `HF_HOME` and `HUGGINGFACE_HUB_CACHE` environment variables (not assume a hardcoded default cache path).
- **FR-017**: The CLIP model availability check MUST verify the model weight file is physically present on disk before reporting the model as available (not just check that the library is installed).
- **FR-018**: The macOS system tray icon MUST restore the main window on a single click on macOS 13 Ventura and later (where double-click is no longer forwarded by the OS).

**CI/CD**

- **FR-019**: A GitHub Actions workflow MUST automatically build all platform installers when a git tag matching `v*.*.*` is pushed.
- **FR-020**: Each platform's build job MUST be independent — a failure on one platform MUST NOT prevent the other platforms from building.
- **FR-021**: Successfully built installers MUST be automatically published as assets on a GitHub Release.
- **FR-022**: The Raspberry Pi build MUST be available as a separate manually-triggered workflow to avoid blocking regular releases (Pi QEMU build takes 45–90 minutes).

### Key Entities

- **Installer**: Platform-specific distributable file that non-technical users download and run to get the app.
- **Setup Wizard**: First-run UI that downloads AI model weight files and configures the app environment.
- **Setup Sentinel**: A marker file (`~/.cctv_processor/.setup_complete`) that records whether the first-run wizard has been completed, preventing it from appearing again.
- **AI Model Weight**: Binary file containing trained model parameters (YOLOv8n ~6 MB, Florence-2 ~444 MB, CLIP ~578 MB) downloaded separately from the installer.
- **GitHub Release**: A versioned publication of all platform installers triggered by a `v*.*.*` git tag.
- **Frozen Bundle**: The output of PyInstaller packaging — a directory containing the Python runtime, all libraries, and the app code, usable without a Python installation.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A non-technical user on a clean Windows 11 PC (no Python installed) can go from downloading the installer to having the app fully functional in under 10 minutes, without using a terminal.
- **SC-002**: A non-technical user on a Raspberry Pi 4 (4 GB RAM) can install the app via a single `dpkg` command and have YOLO-based motion detection working within 5 minutes.
- **SC-003**: On first launch after installation, the setup wizard completes model downloads without user intervention beyond clicking "Download" — no configuration files to edit, no paths to set.
- **SC-004**: On a device with less than 5 GB RAM, the user receives a clear, jargon-free explanation of which features are unavailable before they attempt to use them.
- **SC-005**: Pushing a `v*.*.*` git tag produces all four platform installers as GitHub Release assets within 90 minutes (including Pi build) without any manual intervention.
- **SC-006**: All existing app features (video detection, clip export, heatmap, reports) work identically in the installed version as in the development version.
- **SC-007**: If a model download is interrupted and retried, the app recovers cleanly — no corrupted partial files, no manual cleanup required by the user.
- **SC-008**: The installed app on all platforms passes the existing 208+ automated tests when the test suite is run against the installed bundle's code.

---

## Assumptions

- Users have internet access at least once (for the first-run model download). After that, the app works fully offline.
- Windows target: Windows 10 (64-bit) and Windows 11. No 32-bit Windows support.
- macOS target: macOS 12 Monterey and later. No Apple Developer Account available; users must right-click → Open on first launch.
- Linux target: Ubuntu 20.04+ or any modern x86_64 Linux with glibc 2.31+. Wayland is supported via Qt's XWayland fallback.
- Raspberry Pi target: Pi 4 (4 GB or 8 GB RAM) and Pi 5 (4 GB or 8 GB RAM), running Pi OS 64-bit (Debian Bookworm). Pi 4 2 GB and Pi 3 are best-effort — the app may launch but will be very slow.
- The app does not auto-update; users download new releases manually from GitHub.
- Model weight files are downloaded directly from HuggingFace Hub and Ultralytics CDN — these URLs are controlled by third parties and may change.
- The macOS `.dmg` ships two separate files (arm64 and intel) rather than a single universal binary, since combining them would double the download size for each architecture.
- Florence-2 peak inference RAM is 2.5–3 GB; the 5 GB threshold for `AI_FEATURES_ENABLED` is intentionally conservative to leave OS and app headroom and must not be lowered.
- The Raspberry Pi build is compiled via QEMU ARM64 emulation in GitHub Actions; this takes 45–90 minutes and is therefore a separate manually-triggered workflow.

---

## Clarifications

### Session 2026-06-30

- Q: Who are the target users? → A: General public / non-technical users — no Python knowledge required
- Q: How important is Raspberry Pi support? → A: Must-have, Pi 4 (4 GB+) and Pi 5
- Q: Should AI be bundled or downloaded first-run? → A: First-run wizard downloads model weights; installer bundles Python + torch but not model weights
- Q: macOS code signing? → A: No Apple Developer Account — ad-hoc signing + right-click Open instructions
- Q: 3 GB RAM Pi support? → A: Pi 4 4 GB model (~3.7 GB usable) must work in YOLO-only mode; Florence-2 remains disabled below 5 GB

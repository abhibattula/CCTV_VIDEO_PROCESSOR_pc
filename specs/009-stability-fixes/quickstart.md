# Quickstart / Smoke-Test Scenarios — Phase 9 Stability Fixes

> Constitution Principle III (frontend exemption): JS changes in `static/js/pages/` are
> verified by driving the running application as described below, NOT by automated tests.
> Qt shell changes (`launcher.py`, `shell/main_window.py`) follow the same pattern.

Run `python launcher.py` from the project root before each scenario.

---

## S1 — Browse Abort Token (home.js)

**Tests**: FR-001, SC-001

1. Open the home page.
2. Click **Browse** twice within 500 ms (double-click speed).
3. **Expected**: Exactly one file dialog appears. After selecting a file, it loads once;
   no double dispatch.
4. Click **Browse**, wait for the dialog, then click **Browse** again without closing the first
   dialog.
5. **Expected**: The second click opens a new dialog; the first poll chain is silently
   abandoned.
6. Disconnect from the local network and click **Browse**.
7. **Expected**: After ~1 s an error message appears near the Browse button ("Browse failed —
   backend unreachable…"), not a silent hang.

---

## S2 — Quick Report PDF Feedback (export.js)

**Tests**: FR-007, FR-008, SC-003

**Pre-condition — no job**:
1. Open the Export page (no video loaded).
2. Click **Quick Report (PDF)**.
3. **Expected**: Inline error "No active job — run detection first." — button re-enables, no PDF generated.

**Pre-condition — detection in progress**:
1. Load a video and start detection.
2. Click **Quick Report (PDF)** while the progress bar is active.
3. **Expected**: Inline error "Detection in progress — wait for it to finish."

**Pre-condition — no included events**:
1. Complete detection. On the Timeline page, exclude ALL events.
2. Open the Export page and click **Quick Report (PDF)**.
3. **Expected**: Inline error "No included events — include at least one on the Timeline page."

**Happy path**:
1. Complete detection with at least one included event.
2. Click **Quick Report (PDF)**.
3. **Expected**: Button shows "Generating…"; after a few seconds (depending on CPU), button
   transitions to "✅ Saved: incident_report_YYYYMMDD_HHMMSS.pdf". File exists in the output
   folder (or Desktop if no folder set).

**Failure path** (simulate):
1. Lock the Desktop folder or set `output_dir` to a read-only path.
2. Click **Quick Report (PDF)**.
3. **Expected**: Button shows "❌ PDF save failed — check that detection is complete." after
   the PDF printing timeout.

---

## S3 — SIGINT / Ctrl+C (launcher.py)

**Tests**: FR-009, SC-004

1. Launch the app from a terminal: `python launcher.py`.
2. Press **Ctrl+C** in the terminal.
3. **Expected**: The Qt window closes and the terminal prompt returns within 3 seconds. No
   zombie Python process visible in Task Manager.

---

## S4 — Stop Button Auto-Quit (shell/main_window.py)

**Tests**: FR-011

1. Launch the app from the UI (no terminal required).
2. Click the **Stop** button in the top bar.
3. **Expected**: The backend spinner stops. About 2 seconds later the Qt window closes
   automatically without requiring a manual window close or Ctrl+C.

---

## S5 — Close Window Behaviour (shell/main_window.py)

**Tests**: FR-010

**Idle state**:
1. Launch the app. Do not start detection.
2. Click the window **close (X) button**.
3. **Expected**: Application quits fully (not hidden to tray). Verify via Task Manager —
   no python.exe process remains.

**Active detection**:
1. Launch the app and start MOG2 detection on a video.
2. While the progress bar is running, click the window **close (X) button**.
3. **Expected**: The window hides to the system tray. Detection continues.
4. Click the tray icon to restore the window.
5. **Expected**: Detection progress is visible and still running.

---

## S6 — Desktop Path on OneDrive (app/api/job.py, shell/main_window.py)

**Tests**: FR-005, SC-002

1. Run detection, complete it, and leave `output_dir` at its default (null).
2. Export a video clip or click Quick Report.
3. **Expected**: The exported file appears in the folder shown as "Desktop" in Windows
   Explorer (which may be `C:\Users\User\OneDrive\Desktop`, not `C:\Users\User\Desktop`).
4. The status message shows the full path of the saved file.

---

## S7 — output_dir Persists Across Video Loads (app/session.py)

**Tests**: FR-004, SC-002

1. Load any video and complete detection.
2. On the Export page, click **Choose Output Folder** and select a non-Desktop folder (e.g.,
   `C:\Users\User\Documents\CCTV_Test`).
3. Drag-drop or Browse a different video onto the home screen.
4. Complete detection on the new video.
5. Export a clip or click Quick Report.
6. **Expected**: The exported file appears in `C:\Users\User\Documents\CCTV_Test`, not on the
   Desktop — the output_dir was preserved across the video load/reset.

---

## S8 — No Terminal Noise During AI Report (app/core/frame_analyzer.py)

**Tests**: FR-012, SC-006

*Requires Florence-2 model weights installed.*

1. Launch the app and complete detection on a video.
2. On the Export page, click **Generate Intelligence Report** and confirm.
3. Watch the terminal / stdout.
4. **Expected**: No "MISSING" keys table printed. No `FutureWarning` lines from
   `transformers`. Legitimate logging lines (INFO, WARNING from the app's own logger) are
   still visible.

---

## S9 — Detection Poll Speed (app/core/frame_analyzer.py, app/api/job.py)

**Tests**: FR-013, SC-005

1. Launch the app and start MOG2 detection.
2. Open browser DevTools → Network → filter to `/api/job`.
3. **Expected**: The first poll after clicking Start takes < 1 s; all subsequent polls
   complete in < 100 ms with no multi-second stalls.

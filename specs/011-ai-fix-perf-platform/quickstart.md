# Quickstart: Phase 11 Manual Verification Scenarios

**Branch**: `011-ai-fix-perf-platform`  
**Purpose**: Frontend JavaScript scenarios per Constitution Principle III frontend exemption.  
All backend (`app/core/`, `app/api/`) changes are covered by automated tests in `tests/`.

---

## S1 — Florence-2 Caption Quality

**Setup**: Device must have Florence-2 model cached (`~/.cache/huggingface/hub/models--microsoft--Florence-2-base/`) and ≥5 GB RAM.

**Steps**:
1. `python launcher.py`
2. Load any CCTV video file (>30s, any resolution).
3. Start MOG2 detection with "medium" sensitivity.
4. After detection completes, click "Generate Intelligence Report".
5. Inspect the Timeline section, Scene Breakdown, and Key Moments captions.

**Pass criteria**:
- Every caption is a readable English sentence (≥3 words, starts with capital letter).
- Zero occurrences of `</s>`, `<s>`, `<pad>`, or `<loc_` in any visible text.
- Caption is not "A dark image" or description of a black frame.

---

## S2 — Terminal Noise Suppression

**Setup**: Same as S1.

**Steps**:
1. Run `python launcher.py` from terminal window.
2. Complete an AI report generation run (full cycle).
3. Inspect the terminal output.

**Pass criteria**:
- Zero lines matching `UserWarning` from `torch` or `transformers`.
- Zero lines matching `DeprecationWarning` from `numpy` or `PIL`.
- `RuntimeError` or `ValueError` from inference still appear if a genuine failure occurs (do not suppress these).

---

## S3 — Log Panel SSE Reconnect

**Setup**: Any video with a detection run in progress (at least 30 seconds long).

**Steps**:
1. Start detection.
2. While log entries are appearing, open a different browser tab for 10 seconds.
3. Switch back to the processing tab.
4. Observe log panel.

**Pass criteria**:
- Log panel is not blank on return.
- Log entries visible before tab switch are still visible (or at minimum the last ~100 entries are present).
- A "reconnecting" warning appears in the log if SSE actually dropped, followed by resumed log messages.
- Progress bar is still updating (not frozen).

**Failure scenario to verify fix**: Before the fix, the panel would go blank and show "SSE connection lost — switching to polling" with no further log messages.

---

## S4 — QSystemTray Guard (Linux / GNOME)

**Platform**: Linux with GNOME desktop (Wayland or X11 without libappindicator).

**Steps**:
1. Start detection (`python launcher.py`).
2. While detection is running, close the Qt window (X button).

**Pass criteria**:
- Window closes cleanly.
- App does NOT silently hide to an invisible tray.
- Backend continues running (accessible at `http://localhost:5151`) only if that is the expected behaviour; OR the app quits cleanly.

**Windows / macOS**: tray hide continues to work if `QSystemTrayIcon.isSystemTrayAvailable()` returns `True`.

---

## S5 — YOLO Warm-up Responsiveness

**Setup**: ultralytics installed, any video file.

**Steps**:
1. Load a video file.
2. Immediately click Start with YOLO mode selected (within 2 seconds of file load).
3. Note the time between clicking Start and the first progress update.

**Pass criteria**:
- First progress update appears within 10 seconds (not 30-40s as before warm-up fix).
- If warm-up has already completed (model cached), first progress appears within 3 seconds.

---

## S6 — Raspberry Pi (if Pi hardware available)

**Steps**:
1. Install per README Raspberry Pi section.
2. `python launcher.py`
3. Load a video file, select MOG2, start detection.
4. Observe progress bar during a 60+ second clip.

**Pass criteria**:
- Progress bar advances at least once per 3 seconds (not frozen for 100+ frames).
- AI Analysis option is shown as "Not available" in the Intelligence Report section (auto-disabled on ≤4 GB RAM).
- No OOM crash during detection.

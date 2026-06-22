# Quickstart Integration Scenarios: Phase 3

**Date**: 2026-06-21
**Branch**: `003-phase3-deferred-items`

These scenarios describe the complete user-facing flows to verify during manual
smoke testing. There is no frontend test runner in this stack (unchanged from
Phase 2) — verify by driving the real app directly (a temporary script launching
the real `shell.main_window.MainWindow` against the real backend, deleted after
use — the pattern established throughout Phase 2 and the debug-log-panel work).

---

## Scenario 1: Save, Reuse, and Delete a Custom Export Preset (US1)

**Pre-condition**: A completed job with at least one event, on the Export page.

1. Set Output Type = Individual Clips, Quality = 720p, enable Burn-in, set Label
   Scope to a specific label (or leave All if MOG2 mode).
2. Click **Save as Preset**, enter the name "Weekly Person Report".
3. **Expected**: A new preset button "Weekly Person Report" appears after the 3
   built-in presets.
4. Fully close the app (`taskkill` / quit) and relaunch `python launcher.py`.
5. Load a job, navigate to Export.
6. **Expected**: "Weekly Person Report" still appears in the preset row.
7. Click it.
8. **Expected**: Output Type, Quality, Burn-in, and Label Scope are all set back to
   the saved values in one click.
9. Try saving a new preset named "Security Report" (a built-in name).
10. **Expected**: Rejected with an error message; no new button appears.
11. Try saving a second preset also named "Weekly Person Report".
12. **Expected**: Rejected as a duplicate.
13. Click the delete control on "Weekly Person Report".
14. **Expected**: The button disappears; the 3 built-in presets are still present
    and unaffected.

**Verify via API directly** (faster than UI round-trips for confirming persistence):
`GET /api/presets` reflects the current state at each step above.

---

## Scenario 2: Multi-Level Undo (US2)

**Pre-condition**: Timeline page loaded with at least 6 events, all included.

1. Ctrl+click events #1–#2, click **Exclude**.
2. **Expected**: Events #1–#2 excluded. Undo button enabled.
3. Ctrl+click events #3–#4, click **Exclude**.
4. **Expected**: Events #3–#4 also excluded (in addition to #1–#2). Undo still
   enabled.
5. Press **Escape** to clear the current selection.
6. **Expected**: Selection clears (no blue ring on any card), but the Undo button
   remains enabled — confirms FR-P3-007 (clearing selection does not clear undo
   history).
7. Press **Ctrl+Z** (or click Undo).
8. **Expected**: Only events #3–#4 revert to included; #1–#2 remain excluded. Undo
   still enabled (one more step available).
9. Press **Ctrl+Z** again.
10. **Expected**: Events #1–#2 also revert to included. All 6 events now included.
    Undo button now disabled.
11. Press **Ctrl+Z** a third time.
12. **Expected**: Nothing happens; button stays disabled.

---

## Scenario 3: Light Theme Toggle Persistence (US3)

**Pre-condition**: App running, dark theme active (default).

1. On any page, click the theme toggle in the nav bar.
2. **Expected**: The entire visible page switches to light colours immediately, no
   reload, no flash of unstyled content.
3. Navigate to a different page (e.g. Home → Timeline).
4. **Expected**: The new page also renders in light theme.
5. Open an event preview modal (if events exist).
6. **Expected**: The modal is also light-themed; confidence badges and label pills
   still show the same semantic colours as in dark theme (FR-P3-010).
7. Fully close the app and relaunch `python launcher.py`.
8. **Expected**: The app opens already in light theme, with no re-selection needed
   (SC-P3-005).
9. Toggle back to dark theme and confirm it switches back cleanly.

---

## Backend Test Suite

After implementation, `python -m pytest tests/ -v` must show all existing tests
plus the new `tests/test_api_presets.py` passing — expect a count higher than the
current `60 passed, 2 skipped` baseline (presets-specific tests added). The new
test module must monkeypatch `PRESETS_FILE` to a `tmp_path` so it never reads or
writes the real `~/.cctv_processor/presets.json` on the developer machine.

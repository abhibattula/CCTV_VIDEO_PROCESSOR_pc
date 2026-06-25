# Quickstart Integration Scenarios: Phase 2

**Date**: 2026-06-19
**Branch**: `002-ui-tag-filter`

These scenarios describe the complete user-facing flows to verify during manual smoke testing. Each scenario starts from the Timeline page (detection already complete).

---

## Scenario 1: Label Filter + Quick Export (US1 + US5)

**Pre-condition**: YOLO detection has finished on a video with Person and Car events. The timeline shows 312 events.

1. Open the Timeline page.
2. Observe the label filter bar above the event list: chips "Person", "Car", "Unlabelled" are visible.
3. Observe the toolbar shows "312 events · N selected · …".
4. Click the **"Person"** chip.
5. **Expected**: Event list shows only Person events. Toolbar shows "17 shown / 312 total". Canvas strip shows Person blocks at full opacity, Car blocks at ~20% opacity.
6. Drag the **score threshold slider** to 0.6.
7. **Expected**: Events with score < 0.6 disappear from the list. Counter updates.
8. Click **"Select All"**.
9. **Expected**: Only the currently visible (filtered) events are selected. Toolbar shows "N selected".
10. Click **"Quick Export"**.
11. **Expected**: Navigate to Export page. Export runs with currently included events.

**Verify**: The exported merged MP4 contains only the Person clips that passed the score threshold.

---

## Scenario 2: Multi-Select Bulk Exclude + Undo (US2)

**Pre-condition**: Timeline page loaded with ≥ 5 events.

1. Ctrl+click on event card #1.
2. **Expected**: Card #1 gets a blue selection ring. Toolbar shows "1 selected". Bulk action bar appears.
3. Ctrl+click on event cards #3 and #5.
4. **Expected**: 3 cards selected. Toolbar shows "3 selected".
5. Click **"Exclude Selected"** in the bulk action bar.
6. **Expected**: All 3 cards toggle to excluded (grey). Bulk action bar shows "3 events excluded". "Undo" button activates.
7. Press **Ctrl+Z**.
8. **Expected**: All 3 cards revert to included. "Undo" button deactivates.

---

## Scenario 3: Keyboard-Only Review Workflow (US3)

**Pre-condition**: Timeline page loaded with ≥ 10 events.

1. Click once on any event card to give the event list focus.
2. Press **Arrow Down** twice.
3. **Expected**: Focus moves to event card #3. Page scrolls to keep it visible.
4. Press **Space**.
5. **Expected**: Event card #3 toggles to excluded.
6. Press **Enter**.
7. **Expected**: Preview modal opens for event #3.
8. Press **Escape** to close the preview.
9. Press **Ctrl+A**.
10. **Expected**: All visible events are selected.
11. Press **Ctrl+D**.
12. **Expected**: Selection cleared.
13. Press **Ctrl+E**.
14. **Expected**: Navigate to Export page.

---

## Scenario 4: Evidence Pack Preset with Burn-In (US4)

**Pre-condition**: Export page loaded. Events are included.

1. Click **"Evidence Pack"** preset button.
2. **Expected**: Output type switches to "Individual Clips", quality switches to "Original", burn-in toggle stays off.
3. Click **"Security Report"** preset button.
4. **Expected**: Output type switches to "Merged MP4", label filter set to "Person only", burn-in toggle turns ON.
5. Click **"Export Now"**.
6. **Expected**: Export runs. When complete, open the output file in a media player.
7. **Verify**: In the bottom-left corner of each clip, a semi-transparent black bar shows white text like `"08:35:12 • Person"`.

---

## Scenario 5: Live Detection Dashboard (US5)

**Pre-condition**: Home page. YOLO mode selected.

1. Load a video file and start detection in YOLO mode.
2. Navigate to the **Processing** page immediately.
3. **Expected**:
   - A mini bar chart labelled "Detection Activity" appears below the progress bar.
   - As events are found, bars for "Person", "Car", etc. appear and grow.
   - An "Events/min: N.N" counter updates every 10 seconds.
4. Wait for detection to complete.
5. Navigate to the **Timeline** page.
6. **Expected**: The timeline toolbar shows a compact label summary: "Person×12  Car×47" (or whatever counts were detected).

---

## Scenario 6: Filter Persistence Across Navigation (Clarification Q3)

**Pre-condition**: Timeline page, YOLO detection complete.

1. Activate the **"Person"** filter chip.
2. Set score threshold to **0.5**.
3. Navigate to the **Export** page via the Export button.
4. Navigate back to the **Timeline** page via the back button or nav.
5. **Expected**: The "Person" chip is still active. The score threshold slider is still at 0.5. The event list shows the same filtered view as before navigation.

---

## Scenario 7: New Job Resets Filter State

**Pre-condition**: Timeline page, label filter active ("Person" chip on).

1. Navigate to the **Home** page.
2. Load a new video file and click **"Start Detection"**.
3. **Expected**: Label filter and score threshold reset to defaults (all chips inactive, slider at 0.0).
4. Navigate to Timeline after detection.
5. **Expected**: All events visible, no filter active.

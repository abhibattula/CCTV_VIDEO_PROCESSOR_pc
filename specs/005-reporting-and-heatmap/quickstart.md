# Phase 1 Quickstart: Phase 5 — Professional Reporting & Activity Insights

Per Constitution Principle III's frontend/Qt exemption, the scenarios below
are how `shell/main_window.py`'s Qt-only code and all `static/js/` changes
are verified — driving the real running app, not pytest. Each scenario must
be confirmed (manually, or via a temporary driving script deleted after use,
per this project's established pattern) before the corresponding task is
marked complete.

## Setup

```bash
python launcher.py
```
Use the bundled test video at
`OLD RASPBERRI PI VERSION/Test Video/20260507_012210 (1).mp4` (or any local
video with visible motion in a known region) for all scenarios below.

## Scenario 1: Heatmap appears after MOG2 detection

1. Load the test video, run detection in MOG2 mode (no `ultralytics` needed).
2. Once complete, return to the Home page and load the *same* file again
   (re-triggers the ROI-drawing screen for this job).
3. Confirm a "Show Activity Heatmap" toggle is present and **unchecked** by
   default.
4. Check it — confirm a color-mapped overlay appears aligned with the
   preview frame underneath, concentrated in the region where the test
   video's motion actually occurs.
5. Confirm polygon-drawing still works normally with the overlay visible
   (clicks reach the canvas, not absorbed by the heatmap layer).

## Scenario 2: Heatmap also appears after YOLO detection

1. Repeat Scenario 1, but run detection in Object Detection (YOLO) mode this
   time (`ultralytics` installed).
2. Confirm the heatmap toggle and overlay behave identically — same
   alignment, same default-off state. This is the direct check for FR-P5-010
   (heatmap must not silently fail to work in one detection mode).
3. Via `GET /api/job/events`, confirm every returned event has a non-null
   `event_index` field (the regression check for the YOLO `event_index` bug
   fixed in this phase).
4. Without loading a different video, click Start Detection again on the
   *same* file (same job). Once it completes, confirm the heatmap overlay
   now reflects only this second run's activity pattern — not a combination
   of the first and second runs (FR-P5-014's "replaces, not accumulates"
   requirement).

## Scenario 3: No heatmap shown when there's nothing to show

1. Load a fresh video file with **no prior detection run** for it yet.
2. Confirm the heatmap toggle/overlay is simply absent — no error, no
   broken-image icon.
3. Run detection on a video with zero actual motion (e.g. a static test
   clip), let it complete.
4. Confirm the heatmap is still absent afterward (FR-P5-011) — not a blank
   or solid-color image.

## Scenario 4: PDF report generates and contains the right content

This is the highest-priority scenario — it's the one part of the design
(`QWebEnginePage.printToPdf` on a hidden, never-shown page) that can't be
fully confirmed by reading Python bindings alone; it must be observed
producing a real, non-blank PDF on the actual Windows target.

1. Complete a detection run with at least 4-5 events; exclude 1-2 of them on
   the Timeline page.
2. On the Export page, choose an output folder, then click "Generate PDF
   Report."
3. Within a few seconds, confirm a `incident_report_<timestamp>.pdf` file
   appears in that folder.
4. Open it in a real PDF viewer. Confirm:
   - It is **not blank** (the core risk this scenario exists to catch).
   - The summary section shows the correct "N of M events included" count
     matching the Timeline page's filter.
   - Only the included events appear in the thumbnail grid — the excluded
     ones are absent (FR-P5-003).
   - Each thumbnail card shows a real (non-broken) image, label, time range,
     and confidence score.
   - If this job had a heatmap available (Scenario 1/2), it appears in the
     report too (FR-P5-013).
5. Repeat the click — confirm a **second**, distinctly-named PDF appears
   rather than overwriting the first (FR-P5-018).

## Scenario 5: Chain-of-custody section before and after export

1. On a freshly completed detection run with **no video exported yet**,
   generate the PDF report. Confirm the chain-of-custody section clearly
   states no export has been produced yet (FR-P5-006) — not a blank or
   broken hash field.
2. Now export a video clip for the same job.
3. Generate the PDF report again. Confirm the chain-of-custody section now
   shows two hash values — one for the source file, one for the exported
   file.

## Scenario 6: Zero included events refuses cleanly

1. On a completed detection run, exclude every single event on the Timeline
   page.
2. Attempt to generate the PDF report. Confirm the system clearly indicates
   there's nothing to report (FR-P5-008) rather than producing an empty or
   broken document.
3. Attempt the CSV and JSON event-log exports in the same state. Confirm
   both are refused with a clear message (FR-P5-017), not an empty file.

## Scenario 7: CSV/JSON exports match the included set

1. On a completed detection run with some events excluded, click "Event Log
   (CSV)." Confirm a `.csv` file appears in the output folder; open it and
   confirm the row count exactly matches the included-event count shown on
   the Timeline page, and that excluded events are absent.
2. Click "Event Log (JSON)." Confirm a `.json` file appears with the same
   record count and content, in JSON form.
3. Confirm both save directly into the already-chosen output folder with no
   additional save-location prompt (FR-P5-016).
4. Click "Event Log (CSV)" a second time without changing anything. Confirm
   a second, distinctly-named `.csv` file appears rather than the first
   being overwritten (FR-P5-018) — repeat the same check once for JSON.

## Scenario 8: Report generation doesn't disturb the rest of the app

1. While a PDF report is being generated (Scenario 4), confirm the visible
   app window remains fully responsive — no freeze, no visible navigation
   away from the Export page (the hidden `QWebEnginePage` must not affect
   the visible `QWebEngineView`).
2. After the report finishes, confirm the theme toggle and other nav-bar
   controls still work normally (sanity check that the hidden page sharing
   the same Chromium profile didn't disturb `theme.js`'s `localStorage`
   state, per the plan's Open Risk #4).

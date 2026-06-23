# Quickstart: ROI Selection, Stop Application, New Project

Manual verification scenarios — run via `python launcher.py` against the real
app, since `static/js/` has no automated test runner (constitution Principle
III's frontend exemption). Each scenario should be driven directly, or via a
temporary diagnostic script launching the real `shell.main_window.MainWindow`
against the real backend, deleted after use.

## Scenario 1 — ROI Selection (US1)

1. Launch the app, load a synthetic test video that has motion in two
   distinct areas of the frame (e.g. movement in the top-left and the
   bottom-right, nothing elsewhere).
2. Confirm a first-frame preview appears on the Home page after the file
   loads.
3. Draw a region (click ≥3 points, close near the first point) around only
   the top-left motion area.
4. Start detection. Confirm via `GET /api/job/events` that all reported
   events correspond to the top-left activity and none to the bottom-right.
5. Load the *same* video again from scratch (or a different file). Confirm
   the previously-drawn region is gone and a fresh, empty preview is shown.
6. Run detection again with **no** region drawn. Confirm events are now
   reported from both areas — full-frame behavior is unchanged from before
   this feature.
7. Draw two separate regions, one around each motion area, and confirm both
   areas now produce events while a third, deliberately-staged still area
   does not.
8. Delete one region via its chip's × control, confirm only that region's
   outline disappears from the canvas; click "Clear All," confirm the canvas
   is empty.

## Scenario 2 — Stop Application (US2)

1. Launch the app, load a video, start detection so it's actively running.
2. Click "Stop" in the nav bar. Confirm a dialog appears warning that
   in-progress work will be cancelled.
3. Click Cancel on that dialog. Confirm the app keeps running normally (check
   `GET /api/health` still succeeds, detection keeps progressing).
4. Click "Stop" again, this time confirm. Confirm the UI shows a "Stopping…"
   state, then within ~15 seconds shows "Application stopped — you can close
   this window now."
5. While that's resolving, confirm (via the debug log or a direct
   `GET /api/health` poll from outside the app) that the backend has actually
   stopped responding — not just that the UI claims so.
6. Confirm the Qt window itself is still open, responsive (not frozen), and
   only closes when you click its native close button.
7. Repeat with no detection running (idle state) — confirm the same flow
   works and nothing errors due to there being nothing to cancel.

## Scenario 3 — New Project (US3)

1. Launch the app, load a video, run detection to completion, do **not**
   export.
2. Navigate to the Timeline page. Click "New Project." Confirm a warning
   appears mentioning the uncollected events; cancel it and confirm you're
   still on Timeline with the job untouched.
3. Click "New Project" again, confirm this time. Confirm you land on a clean
   Home upload form.
4. Load a new video. Confirm no leftover events, label filters, score
   threshold, multi-selection, or undo history from the previous job are
   present (check `GET /api/job/events` is empty until detection runs, and
   that the Timeline page's filter UI is reset).
5. Start detection on the new video, and — while it's actively running —
   navigate to Export and click "New Project." Confirm the warning text this
   time mentions the *running operation* (not uncollected events), confirm
   it cancels cleanly on confirm.
6. From a freshly-loaded, not-yet-started job (idle/ready state), click "New
   Project." Confirm it returns to the upload form **immediately, with no
   warning dialog** — this state has nothing to lose.

## Combined pass (run after all three stories are implemented)

Repeat the spirit of all three scenarios in one continuous session: load a
video, draw a region, start detection, let it finish, export, click New
Project, load a second video with a different region, run detection again,
then click Stop and confirm the whole thing winds down cleanly. This catches
any cross-feature interaction the per-story scenarios above might miss.

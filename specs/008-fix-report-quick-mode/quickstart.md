# Quickstart: Phase 8 — Manual Test Scenarios

**Date**: 2026-06-29

These scenarios verify the frontend changes (export.js — Quick Report button) per Constitution III frontend exemption. They must be completed before the export.js task is marked done.

---

## Scenario 1: Quick Report Button Appears and Works

**Prerequisites**: App running (`python launcher.py`). A video has been processed (at least 1 included event on the Timeline page).

**Steps**:
1. Navigate to the Export page (`/export`).
2. Scroll to the "Video Intelligence Report" section.
3. Verify: Two buttons appear side-by-side:
   - "Quick Report (PDF)" with subtitle "Instant · rule-based synthesis"
   - The existing "Generate Intelligence Report" button with subtitle "~5–20 min · Florence-2"
4. Click "Quick Report (PDF)".
5. Verify: A system save dialog appears (Qt PDF save dialog) within 2 seconds.
6. Save the PDF to Desktop.
7. Open the PDF.
8. Verify: PDF contains event thumbnails, timestamps, confidence scores, and heatmap — identical to what the existing "Generate PDF Report" button produces.

**Pass criteria**: Steps 3, 5, 8 all pass.

---

## Scenario 2: Intelligence Report Button Still Works

**Prerequisites**: Same as Scenario 1, plus Florence-2 model weights cached.

**Steps**:
1. On the Export page, click "Generate Intelligence Report" (NOT Quick Report).
2. Verify: The 4-stage progress UI appears (Thumbnails → AI Analysis → Writing Report → Generating PDF).
3. Wait for completion (may take several minutes on CPU).
4. Verify: A "Report ready" success card appears with paths to .md and .pdf files.
5. Open the .md file. Verify at least one event has a non-empty AI description.

**Pass criteria**: Steps 2, 4, 5 pass.

---

## Scenario 3: No Terminal Errors During Quick Report

**Prerequisites**: Same as Scenario 1.

**Steps**:
1. Open the terminal where `python launcher.py` is running.
2. Click "Quick Report (PDF)" in the app.
3. Complete or cancel the save dialog.
4. Verify: No `ERROR` or `WARNING:asyncio:socket.send() raised exception` lines appear in the terminal.

**Pass criteria**: No new error lines in terminal.

---

## Scenario 4: SSE Disconnect Does Not Crash Terminal

**Prerequisites**: App running, video processed.

**Steps**:
1. Open browser DevTools → Network tab.
2. Click "Generate Intelligence Report".
3. While the Thumbnails or AI Analysis stage is in progress, close the browser tab (or navigate away).
4. Observe the terminal.
5. Verify: No unhandled exception traceback (`WARNING:asyncio:socket.send()` or similar) appears.
6. Verify: The report generation continues in the terminal (job.py keeps running) and completes.

**Pass criteria**: Steps 5, 6 pass.

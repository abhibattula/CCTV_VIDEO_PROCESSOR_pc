# Quickstart & Manual Test Scenarios: Video Intelligence Export (Phase 6)

**Date**: 2026-06-25 | **Branch**: `006-video-intel-export`

This file documents manual test scenarios for frontend (`export.js`) and shell
(`main_window.py`) changes, substituting for automated pytest coverage per the
Constitution III frontend exemption. Scenarios MUST be verified before any related
task is marked complete.

---

## Setup

```bash
# Start the app
python launcher.py

# Open browser at http://localhost:8765 (or whatever port is configured)
# Load a test video and run detection (MOG2 or YOLO) to completion
```

---

## Scenario 1: Generate Report — MOG2 Mode, No Moondream

**Pre-conditions**:
- Detection run complete (MOG2 mode), at least 3 included events
- Moondream NOT installed (`pip show moondream` → not found)

**Steps**:
1. Navigate to the Export page
2. Verify "Video Intelligence" card is visible
3. Verify a notice appears: "Install moondream for visual descriptions"
4. Click "Generate Intelligence Report (Markdown + PDF)"
5. Wait for status message to appear

**Expected**:
- Status shows "Markdown saved to `C:\Users\...\{stem}_intelligence_{timestamp}.md`"
- Status shows "PDF generating to same folder."
- Both files appear in the output folder within ~10 seconds
- Markdown file opens in a text editor — contains all sections (Executive Summary, Activity Statistics, Timeline, Detection Configuration, JSON appendix)
- JSON appendix block is valid JSON (paste into jsonlint.com or run `python -c "import json; json.loads(open('path').read())"`)
- Timeline description column shows "N/A" for all events
- PDF file opens in a PDF viewer — tables render, no placeholder images broken

---

## Scenario 2: Generate Report — YOLO Mode, No Moondream

**Pre-conditions**:
- Detection run complete (YOLO mode), at least 3 included events with different class labels
- Moondream NOT installed

**Steps**:
1. Export page → "Generate Intelligence Report"
2. Open generated Markdown file

**Expected**:
- Markdown file contains "Object Inventory" section with a table (class | count | first seen | last seen)
- Activity Statistics section shows correct event count
- Executive Summary mentions the detected object classes

---

## Scenario 3: Zero Included Events

**Pre-conditions**:
- Detection run complete, ALL events toggled off (excluded) via the Timeline page

**Steps**:
1. Export page → "Generate Intelligence Report"

**Expected**:
- Button shows an error status: "No events to report — no events are currently included"
- No files written to output folder
- No crash

---

## Scenario 4: Detection In Progress

**Pre-conditions**:
- Detection has been started but not yet completed

**Steps**:
1. Navigate to Export page while detection is running
2. Attempt to click "Generate Intelligence Report"

**Expected**:
- Button shows error: "Detection is still in progress for this job"
- No files written
- No crash

---

## Scenario 5: Report with Moondream (if installed)

**Pre-conditions**:
- `pip install moondream` has been run
- Model weights already downloaded (~1.9GB, first-time download scenario covered by Scenario 6)
- Detection run complete, at least 3 included events

**Steps**:
1. Export page → "Generate Intelligence Report"
2. Wait for completion (may take 10-60s depending on number of events + CPU/GPU)
3. Open generated Markdown

**Expected**:
- Status during generation: "Analysing frames with Moondream2..."
- Markdown timeline table has non-empty description text for each event
- Descriptions are in natural language (e.g. "A person walking across the parking lot")
- JSON appendix includes `"description"` field for each event
- Notice "Install moondream for visual descriptions" is NOT shown

---

## Scenario 6: First-Run Moondream Model Download

**Pre-conditions**:
- `pip install moondream` was just done but model weights NOT yet cached
- Detection run complete with included events

**Steps**:
1. Export page → "Generate Intelligence Report"
2. Observe status area during the ~2-5 minute download

**Expected**:
- Status changes to: "Downloading Moondream2 model (~2 GB, one-time only)..." or similar
- Button is disabled / spinner shown during download
- After download completes, generation proceeds normally
- Report is generated with descriptions
- Next report generation (in same or new session) is fast (~seconds, not minutes)

---

## Scenario 7: Excluded Events Not in Report

**Pre-conditions**:
- Detection run complete, 5 events present
- User has toggled 2 events as excluded via Timeline page

**Steps**:
1. Export page → "Generate Intelligence Report"
2. Open Markdown, count timeline rows
3. Open PDF, count timeline rows

**Expected**:
- Timeline table has exactly 3 rows (the 3 included events)
- Activity Statistics shows event_count = 3
- JSON appendix has 3 objects
- PDF timeline also shows 3 rows

---

## Scenario 8: PDF File Quality Check

**Pre-conditions**:
- Report generated (any mode)

**Steps**:
1. Open PDF in a viewer (Windows: Edge, Adobe Reader, or browser)

**Expected**:
- Header shows: video filename, generation date, detection mode, video duration
- Tables render with proper borders and alignment
- Thumbnails are visible in the Key Moments section (not broken image icons)
- Heatmap section shows the heatmap image (or states "Heatmap not available")
- Text is readable at default zoom

---

## Scenario 9: Chatbot Smoke Test (Phase 7 Readiness)

**Pre-conditions**:
- Markdown report generated (YOLO or MOG2 mode)

**Steps**:
1. Copy the full Markdown file contents
2. Paste into Claude.ai or ChatGPT as a message: "Here is a video intelligence report. [paste content]. When was the first event detected?"
3. Repeat for: "How many events were detected?", "What object class was most common?", "What was the highest confidence score?"

**Expected**:
- Chatbot correctly answers all 4 questions using only the report content
- Timestamps are unambiguous in the response

---

## Driving Script (for CI-like manual check)

A minimal Python driving script (deleted after verification) can be used to test the
API endpoints directly:

```python
import requests

# Assumes app is running at localhost:8765 with an active completed job

# Test GET /api/job/intel-report.html
r = requests.get("http://localhost:8765/api/job/intel-report.html")
print("HTML status:", r.status_code)
assert r.status_code == 200
assert "<html" in r.text.lower()
print("JSON appendix present:", "```json" in r.text or 'json' in r.text.lower())

# Test POST /api/job/intel-report/export
r = requests.post("http://localhost:8765/api/job/intel-report/export")
print("Export status:", r.status_code)
print("Response:", r.json())
assert r.status_code == 200
assert "md_path" in r.json()
assert "moondream_available" in r.json()

import pathlib
md_path = pathlib.Path(r.json()["md_path"])
assert md_path.exists(), f"Markdown file not found: {md_path}"
print("Markdown file size:", md_path.stat().st_size, "bytes")
assert md_path.stat().st_size < 100 * 1024, "Markdown file exceeds 100KB"

import json, re
content = md_path.read_text(encoding="utf-8")
json_block = re.search(r'```json\n(.*?)```', content, re.DOTALL)
assert json_block, "No JSON appendix found in Markdown"
events = json.loads(json_block.group(1))
print("JSON appendix events:", len(events))
assert len(events) > 0
assert "event_index" in events[0]
assert "start_s" in events[0]
assert "start_clock" in events[0]
print("All checks passed!")
```

Run this script from the project root with the app running and a completed job active.
Delete after use — this is a disposable verification script, not a permanent test.

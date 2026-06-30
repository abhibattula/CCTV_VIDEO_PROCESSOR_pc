# Quickstart & Frontend Test Scenarios — Phase 7

Per Constitution Principle III (frontend exemption), JavaScript in `static/js/`
is not covered by automated failing tests. These scenarios MUST be manually
verified by running the application before marking the corresponding task complete.

---

## Prerequisites

```bash
python launcher.py
# App opens. Have a test video file ready (any MP4 works).
```

---

## Scenario 1 — Report Format Modal (covers FR-005, FR-006, FR-007, SC-002)

**Task**: T009 — export.js

**Setup**: Run detection on a video with at least 3 events until status shows "complete".
Navigate to Export page.

**Steps**:
1. Confirm the Export page summary strip shows an AI readiness badge
   ("Florence-2 ready" or "AI analysis unavailable")
2. Click "Generate Intelligence Report"
3. **Verify**: Format modal appears BEFORE any generation begins. It shows:
   - "Markdown (.md)" checkbox — checked by default
   - "PDF" checkbox — checked by default
   - "Cancel" and "Generate →" buttons
4. Uncheck "PDF". Click "Generate →"
5. **Verify**: Generation runs. No `.pdf` file is created in the output folder.
6. Generate again. This time uncheck "Markdown". Click "Generate →"
7. **Verify**: Generation runs. No `.md` file is created. Only `.pdf` created.
8. Close the modal with "Cancel"
9. **Verify**: Button returns to enabled state. No generation started.
10. Reload the page. Click "Generate Intelligence Report" again.
11. **Verify**: Modal pre-selects the last chosen option (PDF only).

**Pass criteria**: All 6 verify steps pass.

---

## Scenario 2 — 4-Stage SSE Progress Display (covers FR-008, FR-009, SC-003)

**Task**: T009 — export.js

**Setup**: Same as Scenario 1 (completed detection run).

**Steps**:
1. Click "Generate Intelligence Report" → choose "Both" (Markdown + PDF) → click "Generate →"
2. **Verify**: A 4-stage progress section appears:
   - Stage 1: "Thumbnails" — updates with a count (e.g. "3/12")
   - Stage 2: "AI Analysis" — updates with frame count AND source video timestamp
     (e.g. "Analysing frame 5 of 12 — 00:00:45")
   - Stage 3: "Writing Report" — shows "Running…" then checkmark when done
   - Stage 4: "Generating PDF" — shows "Running…" then checkmark when done
3. **Verify**: Stages appear in sequence (1 → 2 → 3 → 4); earlier stages show a checkmark
   once complete.
4. **Verify**: After completion, success card appears showing both `.md` and `.pdf` file paths.

**Pass criteria**: All stage labels and progression are visible during generation.

---

## Scenario 3 — Log Panel on Processing Page (covers FR-015, FR-016, FR-017, FR-018, SC-006)

**Task**: T010 — processing.js

**Setup**: Navigate to Processing page. Do NOT start detection yet.

**Steps**:
1. **Verify**: No log panel is visible by default.
2. Locate and click the "Show Logs" button (or "Logs" toggle).
3. **Verify**: Log panel appears, initially empty or showing "Waiting for detection…"
4. Click "Hide Logs" (or the same toggle).
5. **Verify**: Log panel disappears.
6. Click "Show Logs" again. Start a detection run.
7. **Verify during detection**:
   - Log entries appear with a timestamp prefix (`HH:MM:SS`)
   - A stage separator heading appears when detection phase changes
     (e.g. "── Starting detection ──────")
   - INFO entries appear in grey
   - EVENT entries appear in blue (when an event is detected)
   - WARN entries appear in amber (if any low-confidence events are skipped)
8. After detection completes, click the "Copy" button.
9. **Verify**: Clipboard contains the full log text (paste into a text editor to confirm).

**Pass criteria**: All verify steps pass.

---

## Scenario 4 — AI Readiness Badges on Export Page (covers FR-019, SC-...internal)

**Task**: T009 — export.js

**Setup**: Navigate to Export page after any completed detection run.

**Steps**:
1. **Verify**: Summary strip shows one of:
   - "Florence-2 ready" badge (green) — if transformers + model weights cached
   - "AI analysis unavailable" badge (grey/red) — if transformers not installed
2. If `ANTHROPIC_API_KEY` is set in environment:
   - **Verify**: "LLM synthesis on" badge (blue) also appears
3. If `ANTHROPIC_API_KEY` is not set:
   - **Verify**: No LLM badge is shown

**Pass criteria**: Badge state matches actual library/key availability.

---

## Scenario 5 — Debug Drawer Enhancements (covers FR-020)

**Task**: T011 — debug-log.js

**Setup**: Open the debug drawer (click the debug icon / toggle from any page).

**Steps**:
1. Navigate to Processing page, start detection.
2. **Verify**: Each request entry in the debug drawer shows:
   - Timestamp prefix: `HH:MM:SS.mmm`
   - HTTP status: e.g. `200 OK` or `404 Not Found`
   - Duration: e.g. `(87 ms)` appended
3. Trigger an error (e.g. navigate to a non-existent endpoint via the debug console).
4. **Verify**: Error entries (status >= 400) have a red left border.
5. **Verify**: The debug drawer toggle button shows a count badge (total request count).

**Pass criteria**: All three verify items in step 2–5 pass.

---

## Scenario 6 — Graceful Fallback (covers FR-004, FR-013, SC-005)

**Task**: T009 — export.js + backend integration

**Setup**: Rename or temporarily uninstall `transformers` to simulate AI unavailable.
(Alternatively: temporarily rename the Florence-2 model directory in `~/.cache/huggingface/`.)

**Steps**:
1. Run detection. Navigate to Export page.
2. **Verify**: "AI analysis unavailable" badge shown.
3. Click "Generate Intelligence Report" → choose Both → Generate.
4. **Verify**: Report generates successfully (no crash, no error modal).
5. Open generated Markdown file.
6. **Verify**:
   - All structural sections present (Summary, Timeline, Scene Breakdown, etc.)
   - A notice appears: "AI frame analysis: unavailable — descriptions omitted" (or similar)
   - Executive summary section is present but uses rule-based text
7. If `ANTHROPIC_API_KEY` is set but API returns an error (simulate by setting a wrong key):
   - **Verify**: Report still generates with rule-based executive summary
   - **Verify**: Notice in report reads: "Executive summary: rule-based synthesis — LLM API unavailable"

**Pass criteria**: Report is complete and structurally valid even without AI libraries.

---

## Scenario 7 — CLIP Sidecar Files (covers FR-003)

**Task**: T009 + T004 — only verifiable if open-clip-torch is installed

**Setup**: Install `open-clip-torch`. Run detection. Generate Intelligence Report.

**Steps**:
1. Navigate to the thumbnails output directory (`~/Desktop/cctv_output/` or configured path).
2. **Verify**: For each `thumb_XXXXXXXXX.jpg` file, a matching `thumb_XXXXXXXXX.clip.npy` exists.
3. **Verify**: `.npy` files are approximately 2 KB each (512 float32 values = 2048 bytes).
4. Load one with Python: `import numpy as np; e = np.load("thumb_xxx.clip.npy"); print(e.shape, np.linalg.norm(e))`
5. **Verify**: shape is `(512,)`, norm is approximately `1.0` (L2-normalised).

**Pass criteria**: `.npy` sidecars exist and are valid normalised embeddings.

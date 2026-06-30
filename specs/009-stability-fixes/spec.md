# Feature Specification: Phase 9 — Stability Fixes

**Feature Branch**: `009-stability-fixes`
**Created**: 2026-06-29
**Status**: Draft

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Reliable File Selection (Priority: P1)

A user wants to select a video file, either by clicking Browse or dragging a file onto the home
screen. Currently a second click on Browse silently discards the first pick, and any network
hiccup drops the file path without explanation.

**Why this priority**: File selection is the first action in every session; if it is unreliable
the app is unusable.

**Independent Test**: Open the home page, click Browse twice in quick succession → only one file
dialog opens; the chosen file loads correctly. Drag a file while Browse is active → the dragged
file wins cleanly.

**Acceptance Scenarios**:

1. **Given** the home page is shown, **When** the user clicks Browse twice quickly, **Then** only
   one file dialog opens and the selected file loads correctly without silent discard.
2. **Given** Browse was clicked and the dialog is open, **When** the backend is briefly
   unavailable, **Then** the user sees an error message instead of the button freezing silently.
3. **Given** a file is dragged onto the drop zone, **When** the drop event fires, **Then** the
   file path resolves to a full filesystem path and the file loads.

---

### User Story 2 — Correct Output File Location (Priority: P1)

A user exports a video clip, saves a PDF report, or saves a Quick Report and then expects to
find the file in a known location — either the Desktop or the folder they previously selected.
Currently files are saved to a wrong Desktop path on Windows 11 with OneDrive, and the
user-selected folder is forgotten whenever a new video is loaded.

**Why this priority**: Users who cannot find exported files lose trust in the app immediately;
this is the highest-friction active bug.

**Independent Test**: Set output folder → load a new video → run export → confirm file appears
in the previously-set folder. On an OneDrive machine with no folder set, confirm file appears on
the actual visible Desktop.

**Acceptance Scenarios**:

1. **Given** the user has set an output folder, **When** they load a new video and export,
   **Then** the file is saved to the previously-set folder (not the Desktop).
2. **Given** no output folder has been set on a Windows 11 machine with OneDrive Desktop
   redirect, **When** any export runs, **Then** the file appears on the visible Desktop (the
   folder the user sees in Explorer), not a hidden fallback path.
3. **Given** any export completes, **When** the file is saved, **Then** the UI shows the actual
   saved path so the user can navigate directly to the file.

---

### User Story 3 — Trustworthy Quick Report PDF (Priority: P1)

A user clicks "Quick Report (PDF)" expecting a PDF to be saved. Currently the button always
shows "Quick Report saved to your output folder." even when no PDF was created (no active job,
detection in progress, no included events, or write failure).

**Why this priority**: A button that lies about its outcome destroys user confidence; it was
introduced in Phase 8.

**Independent Test**: Click Quick Report with no job → see an error, not a false success. Click
Quick Report with a valid completed job with events → see "Saved: filename" only after the file
is confirmed written.

**Acceptance Scenarios**:

1. **Given** no detection has been run yet, **When** the user clicks Quick Report, **Then** an
   inline error appears ("No active job — run detection first") and no PDF generation is
   attempted.
2. **Given** detection is currently in progress, **When** the user clicks Quick Report, **Then**
   an inline error appears ("Detection in progress — wait for it to finish").
3. **Given** detection is complete but all events are excluded, **When** the user clicks Quick
   Report, **Then** an inline error appears ("No included events — include at least one on the
   Timeline page").
4. **Given** a valid completed job with included events, **When** the user clicks Quick Report,
   **Then** the button shows "Generating…" until the file is confirmed written, then shows
   "✅ Saved: <filename>".
5. **Given** the PDF write fails (e.g., path inaccessible), **When** pdfPrintingFinished fires,
   **Then** the button shows "❌ PDF save failed" instead of a false success message.

---

### User Story 4 — Clean Application Exit (Priority: P2)

A user wants to quit the app by pressing Ctrl+C in the terminal or closing the window, without
being left with an invisible background process. Currently Ctrl+C is silently intercepted by Qt,
and closing the window only hides it to the system tray.

**Why this priority**: Users who leave zombie processes unknowingly waste memory and may see
port-conflict errors on next launch.

**Independent Test**: Run `python launcher.py` → press Ctrl+C in terminal → process exits fully
(no zombie). Run app → click Stop → app closes automatically within a few seconds.

**Acceptance Scenarios**:

1. **Given** the app is running in a terminal, **When** the user presses Ctrl+C, **Then** the
   entire process exits (backend + Qt) within 3 seconds.
2. **Given** no detection is in progress, **When** the user clicks the window close button,
   **Then** the app quits fully (no hide-to-tray).
3. **Given** detection is in progress, **When** the user clicks the window close button,
   **Then** the app hides to tray (preserving the running job), matching current behaviour.
4. **Given** the user has clicked Stop and the backend has stopped, **When** ~2 seconds pass,
   **Then** the Qt window closes automatically without requiring manual action.

---

### User Story 5 — Quieter Terminal Output During AI Report (Priority: P3)

A developer or advanced user running the app from a terminal sees a table of "MISSING" model
keys and multiple FutureWarning lines every time an AI report is generated. These are
false-alarm messages from the Florence-2 model's own code.

**Why this priority**: Terminal noise obscures real errors; low risk of regression.

**Independent Test**: Generate an AI intelligence report → terminal shows no MISSING-keys table
and no FutureWarning lines from the transformers library.

**Acceptance Scenarios**:

1. **Given** Florence-2 model weights are installed, **When** an AI report is generated,
   **Then** no "MISSING" keys table is printed to the terminal.
2. **Given** the transformers library is installed, **When** any app action runs,
   **Then** no FutureWarning lines from the transformers attention mask API appear in the
   terminal.

---

### User Story 6 — Fast Detection Without Startup Stall (Priority: P2)

A user starts MOG2 detection and observes the progress bar. In previous versions detection
began immediately; now there is a multi-second stall on the first status poll because
`FrameAnalyzer.is_available()` imports the transformers library synchronously on every call.

**Why this priority**: Perceived performance regression; MOG2 itself is unchanged.

**Independent Test**: Start MOG2 detection → first `/api/job` status poll returns within
100 ms on all subsequent calls after the first.

**Acceptance Scenarios**:

1. **Given** the transformers library is installed, **When** the status bar polls job progress
   during detection, **Then** every poll after the first completes in under 100 ms (no
   repeated filesystem stats or blocking imports).
2. **Given** the app has been running for any length of time, **When** the user starts a new
   detection run, **Then** the first progress update appears within 1 second of clicking Start.

---

### Edge Cases

- Browse is clicked while a file is already loading (doLoadFile in progress): second click is
  ignored until loading completes.
- Output folder set by user is later deleted from disk: fallback to real Desktop path with a
  warning shown in the UI.
- OneDrive Desktop Folder Backup is disabled but standard Desktop path exists: `_get_desktop_path()` must still return the correct path.
- Quick Report clicked while a previous Quick Report is still printing to PDF: second click is
  debounced (button remains disabled).
- Stop clicked while detection is in progress: detection cancels, then app auto-closes.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The Browse button MUST prevent concurrent file-selection chains; a second click
  while a dialog is open or a path is being loaded MUST cancel the previous chain and start a
  new one.
- **FR-002**: The Browse chain MUST surface an error message to the user if the backend is
  unreachable or the file load fails, rather than silently timing out.
- **FR-003**: The JS drop zone MUST pass the full filesystem path to the file loader; if only a
  filename is available the app MUST fall back to the Qt native drag-drop path.
- **FR-004**: `output_dir` selected by the user MUST persist across new video loads within the
  same app session; `session.reset()` MUST NOT clear it.
- **FR-005**: The Desktop fallback path MUST resolve to the visible Desktop folder on the
  running OS, including Windows 11 machines where OneDrive redirects the Desktop shell folder.
- **FR-006**: After every file-save operation (video export, PDF, CSV, JSON), the UI MUST
  display the exact saved path and offer a way for the user to locate the file.
- **FR-007**: Before dispatching the Quick Report PDF event the app MUST validate: job exists,
  status is not "detecting", at least one event is included; if any check fails an inline error
  MUST be shown and no PDF generation MUST be attempted.
- **FR-008**: The Quick Report PDF button MUST show "Generating…" while the PDF is printing and
  update to "✅ Saved: \<filename\>" or "❌ PDF save failed" based on the actual write result.
- **FR-009**: The app MUST respond to SIGINT (Ctrl+C from terminal) by exiting completely
  within 3 seconds.
- **FR-010**: When no detection job is in progress, closing the window MUST quit the application
  fully; when a job is running, closing the window MAY hide to tray to preserve the job.
- **FR-011**: After the backend uvicorn server stops (following the Stop button), the Qt shell
  MUST automatically close within 3 seconds without requiring user action.
- **FR-012**: Florence-2 weight-tied MISSING-key output and transformers FutureWarnings MUST be
  suppressed from the terminal during normal app operation.
- **FR-013**: The result of `FrameAnalyzer.is_available()` MUST be cached after the first call;
  subsequent calls within the same process MUST not re-run the filesystem check.

### Key Entities

- **output_dir**: The user-selected export folder. Persists for the lifetime of the app session.
  Never cleared by a new-video load. Defaults to the OS Desktop when not set.
- **PDF result signal**: A lightweight flag injected by the Python layer into the browser JS
  after `pdfPrintingFinished` fires, indicating `{success: bool, path: string}`.
- **Browse abort token**: A monotonically-increasing integer that allows a new Browse action to
  cancel all in-flight poll chains from previous Browse clicks.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Double-clicking Browse within 500 ms results in exactly one file dialog opening;
  zero silent path discards.
- **SC-002**: All exported files appear in the user's selected output folder (or visible Desktop
  if none set) on 100% of saves; zero "file not found" reports after confirmed save.
- **SC-003**: Quick Report button shows a truthful status on 100% of clicks: error message when
  invalid, confirmed path after successful write, error message after failed write.
- **SC-004**: Pressing Ctrl+C in the terminal exits the process fully within 3 seconds on
  Windows 11.
- **SC-005**: MOG2 detection status polls after the first complete in under 100 ms; no
  multi-second stall observed during a detection run.
- **SC-006**: Zero MISSING-key or FutureWarning lines appear in the terminal during an AI report
  generation run.

## Assumptions

- The app runs on Windows 10/11; macOS and Linux path fixes are out of scope for this phase.
- OneDrive Desktop redirect detection uses the Windows Shell API (`SHGetFolderPathW`); this is
  available on all supported Windows versions without additional install.
- `FrameAnalyzer.is_available()` result is stable for the lifetime of the process (model weights
  are not installed or removed while the app is running).
- The Quick Report PDF prints the existing Incident Report (motion-only), not the AI-enhanced
  Intelligence Report.
- "Close window quits when idle" is the desired behavior per the user's complaint about zombie
  processes; hide-to-tray is preserved only as an active-job safeguard.
- The PDF-result signal (Python → browser) is injected via the existing 200 ms bridge timer
  mechanism already used for browse/shutdown flags; no new IPC channel is needed.

## Clarifications

### Session 2026-06-29

- Q: When detection is "too slow" — MOG2 or YOLO? → A: MOG2. Root cause confirmed as
  `FrameAnalyzer.is_available()` filesystem stat on every poll, not the detection core itself.

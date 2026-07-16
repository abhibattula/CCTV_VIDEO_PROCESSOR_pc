# Quickstart: Fast Scan — Manual Verification Scenarios

Frontend JS is exempt from automated TDD (constitution III); these scenarios
are the required verification for the UI tasks, plus the end-to-end success
criteria that need a human/real run. Reference asset:
`C:\Users\User\Desktop\UTA\vs code\CCTV Video processor\Test Video\20260507_012210 (1).mp4`
(115 s HEVC 1080p60).

Start the app (`python launcher.py`), load the reference video.

1. **Scan speed control renders with correct default** — Home page shows a
   "Scan speed" control (Thorough / Balanced / Fast) near Sensitivity;
   Balanced is pre-selected; a short hint explains the trade-off.
2. **Balanced run completes and is fast** — start detection with Balanced.
   Expect completion in roughly 15–25 s (vs ~70 s Thorough). Log panel shows a
   `[FASTSCAN]` line naming the decode chain (expect `qsv` on this machine).
3. **Thorough run matches v1.0.x** — rerun with Thorough. Expect ~70 s and the
   same events as before this phase. Record both durations.
4. **SC-001/SC-002 check** — Balanced time ≤ ⅓ Thorough time; event count
   within ±1 and each event's time range overlaps its Thorough counterpart
   (compare Timeline listings side by side).
5. **Events are correct in time** — open 2–3 Balanced events on the Timeline;
   thumbnails and clock times show the same moments as the Thorough run;
   export one clip and confirm it contains the motion.
6. **Fast preset works** — run Fast; completes quicker than Balanced; events
   still sensible (brief events may merge/shorten slightly — acceptable).
7. **Cancel kills the decoder (SC-007)** — start Balanced, cancel at ~30 %.
   App returns to usable state; Task Manager shows no lingering
   `ffmpeg-win-x86_64-v7.1.exe`; immediately rerun detection on the same file
   — it starts cleanly.
8. **Acceleration is visible (SC-006)** — the Home page system/AI status area
   shows the acceleration line, e.g. decode `qsv` after a sampled run and
   AI device `cpu` on this machine.
9. **YOLO mode sampled** — switch detection mode to YOLO (if ultralytics
   installed), run Balanced; completes far faster than a Thorough YOLO run;
   labeled events appear with correct clocks.
10. **Zero-frame fallback** — (scripted) point a job at a readable file while
    forcing the pipe chain to fail (e.g. monkeypatch/temp-break the FFmpeg
    args); detection still completes via the legacy path and the log says so.
11. **New Project resets cleanly** — after a Balanced run, New Project; load
    another video; scan-speed control back to Balanced default; no stale
    acceleration text.
12. **Docs** — README + USER_MANUAL describe Scan speed and the acceleration
    status line; the 24-hour guidance mentions Balanced as the recommended
    mode.

Record PASS/FAIL per scenario in the PR description.

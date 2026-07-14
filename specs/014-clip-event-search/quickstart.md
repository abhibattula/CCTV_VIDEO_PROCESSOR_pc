# Quickstart — Manual Verification Scenarios (014 CLIP Event Search)

These scenarios verify the frontend behavior (constitution Principle III
frontend exemption — no JS test runner). Run against the real app
(`python launcher.py`) with the optional AI extras installed and CLIP weights
downloaded (Home page AI Models card), using any test video that produces
several visually distinct events.

Backend logic is covered by pytest (`tests/test_clip_indexer.py`,
`tests/test_search_index.py`, `tests/test_api_search.py`) — these scenarios
are UI-level only.

| # | Scenario | Steps | PASS criteria |
|---|----------|-------|---------------|
| 1 | First-use indexing | Run detection; open Timeline; click into the search box | "Indexing N of M events…" appears, counts up, then search enables — no errors |
| 2 | Basic query | Type a description matching one event's thumbnail; press Enter | Every card shows a % badge within 2 s; the described event scores visibly higher |
| 3 | Sort toggle | With badges shown, switch Sort to "Relevance", then back | Best match first in relevance mode; original chronological order restored on toggle back; badges persist |
| 4 | Relevance slider | Raise the minimum-relevance slider | Cards below threshold dim but never disappear; include/exclude checkmarks unchanged |
| 5 | Clear search | Click × / empty the box | Badges gone, dimming gone, chronological order, normal timeline appearance |
| 6 | Compose with filters | Apply a label chip filter, then search | Both apply: label-hidden events stay hidden regardless of relevance |
| 7 | Warm reuse | Navigate away (Home) and back to Timeline; focus search again | Ready in < 2 s, no re-indexing of already-embedded events |
| 8 | New Project reset | Start New Project, load a different video, detect, search | Fresh index for the new job; no stale badges or results from the old job |
| 9 | Unavailable state | Temporarily rename `~/.cache/clip/ViT-B-32.pt`; restart app; open Timeline | Search box disabled with reason tooltip pointing to Home AI Models card; every other Timeline feature works; restore file afterward |
| 10 | During detection | Start a detection run; open Timeline mid-run | Search box disabled ("available after detection"); enables after completion |
| 11 | Selection/export untouched | With relevance sort active, multi-select + exclude two events, then export | Include/exclude and export behave identically to chronological mode |
| 12 | Pi headless smoke (optional, hardware) | On the Pi build with AI models, repeat scenarios 1–2 in the system browser | Same behavior; indexing slower but functional |

Record PASS/FAIL per scenario in the PR description before marking the
corresponding frontend tasks complete.

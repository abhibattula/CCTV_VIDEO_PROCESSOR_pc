# Contract: SSE Stream Format

**Version**: unchanged from Phase 10  
**Endpoint**: `GET /api/stream`  
**Format**: `text/event-stream` — one JSON object per `data:` line

## Message Types

```json
// Keepalive / progress update
{"type": "keepalive", "progress": 0.45, "event_count": 3, "status": "running", "line": null}

// Log line
{"type": "log", "line": "[MOG2] Frame 500 processed", "status": "running", "progress": 0.45, "event_count": 3}

// Detection event notification
{"type": "event", "line": "Event 1: 00:12 – 00:18", "status": "running", "progress": 0.45, "event_count": 1}

// Job complete
{"type": "done", "status": "completed", "progress": 1.0, "event_count": 5, "line": null}
```

**No changes** to the SSE wire format in Phase 11. The reconnect fix is client-side only.

## Reconnect Behaviour (Phase 11 change — frontend only)

On `onerror`:
- Retry up to 5 times with 3-second backoff
- On reconnect, server `subscribe()` replays last 100 log lines automatically
- After 5 failed retries, fall back to `startPolling()` (existing behaviour)
- Retry counter resets to 0 on any successful message received

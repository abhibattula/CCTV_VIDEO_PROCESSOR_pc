# API Contracts: Phase 3 — Deferred Items Release

**Date**: 2026-06-21
**Branch**: `003-phase3-deferred-items`

All Phase 1/2 endpoints are preserved unchanged. Phase 3 adds one new endpoint
group (`/api/presets`). Multi-level undo and the theme toggle are entirely
client-side and add no backend surface.

---

## New Endpoints: Custom Export Presets

### `GET /api/presets`

Lists all saved custom presets. Does NOT include the 3 built-in presets (Security
Report / Evidence Pack / Quick Highlights), which remain hardcoded client-side and
are not backend-managed.

**Response 200**:
```json
[
  {
    "name": "Weekly Person Report",
    "output_type": "merged",
    "quality": "720p",
    "burn_in": true,
    "label_filter": ["Person"]
  }
]
```
Returns `[]` if no custom presets exist, or if `presets.json` is missing or
corrupt — never an error response.

---

### `POST /api/presets`

Saves a new custom preset.

**Request body**:
```json
{
  "name": "Weekly Person Report",
  "output_type": "merged",
  "quality": "720p",
  "burn_in": true,
  "label_filter": ["Person"]
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | yes | Display name; trimmed before validation |
| `output_type` | string | no (default `"merged"`) | `"merged"` or `"individual"` |
| `quality` | string | no (default `"original"`) | `"original"`, `"720p"`, or `"480p"` |
| `burn_in` | boolean | no (default `false`) | Whether burn-in overlay is applied |
| `label_filter` | string[] | no (default `[]`) | Labels to restrict export to |

**Validation** (name is trimmed first; all comparisons below are case-insensitive):
- `name` empty or whitespace-only → `400`: `"Preset name cannot be empty"`
- `name` matches a built-in preset name → `400`: `"'<name>' is a built-in preset name"`
- `name` matches an existing custom preset → `400`: `"Preset '<name>' already exists"`

**Response 200** (the saved preset, name trimmed):
```json
{
  "name": "Weekly Person Report",
  "output_type": "merged",
  "quality": "720p",
  "burn_in": true,
  "label_filter": ["Person"]
}
```

---

### `DELETE /api/presets/{name}`

Deletes a custom preset by name. Cannot affect built-in presets (they aren't
backend-managed at all, so there's no path by which this could touch them).

**Response 200**:
```json
{ "deleted": "Weekly Person Report" }
```

**Response 404** (name not found among custom presets):
```json
{ "detail": "Preset 'Weekly Person Report' not found" }
```

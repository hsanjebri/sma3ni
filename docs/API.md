# API Contract — v1

Base URL: `https://api.sma3ni.app` (placeholder). All endpoints under `/v1`. JSON responses, UTF-8.

## Auth
- `POST /v1/install` → `{ "token": "..." }`, called once on first launch. Anonymous, no personal data.
- All other requests: `Authorization: Bearer <token>`.
- Rate limit: 60 transcriptions/day per token (configurable). `429` when exceeded.

## `POST /v1/transcribe`
Multipart form:
| Field | Type | Required | Notes |
|---|---|---|---|
| `audio` | file | ✅ | opus, ogg, m4a, aac, mp3, wav; max 25 MB, max 5 min |
| `script` | `arabic` \| `arabizi` | – | default `arabic` |
| `summary` | bool | – | default `false`; ignored for audio < 20 s |
| `translate` | `fr` \| `en` | – | omit for none |
| `replies` | bool | – | default `false` |

Response `200`:
```json
{
  "request_id": "req_8f2c...",
  "text": "عسلامة، توا نوصل للـ réunion",
  "script": "arabic",
  "language": "aeb",
  "duration_s": 12.4,
  "segments": [
    {"start": 0.0, "end": 2.1, "text": "عسلامة"},
    {"start": 2.1, "end": 5.8, "text": "توا نوصل للـ réunion"}
  ],
  "summary": null,
  "translation": null,
  "replies": null,
  "model_version": "whisper-darija-turbo-2026.10.1",
  "processing_ms": 1430
}
```
- `language` uses ISO 639-3 `aeb` (Tunisian Arabic).

## `POST /v1/feedback` (opt-in donation)
Only sent if the user enabled "Help improve Sma3ni".
| Field | Type | Notes |
|---|---|---|
| `audio` | file | the original note |
| `request_id` | string | from transcribe response |
| `corrected_text` | string | user's correction |
| `consent_version` | string | e.g. `2026-10-v1` |
Response `202 { "accepted": true }`.

## `DELETE /v1/donations`
Deletes all donated data for this token. `204`.

## `GET /v1/health`
`{ "status": "ok", "model_version": "..." }`

## Errors
```json
{ "error": { "code": "audio_too_long", "message": "Audio must be 5 minutes or less." } }
```
| HTTP | code |
|---|---|
| 400 | `invalid_audio`, `unsupported_format` |
| 401 | `unauthorized` |
| 413 | `audio_too_large`, `audio_too_long` |
| 429 | `rate_limited` |
| 500 | `internal_error` |
| 503 | `model_loading` (client retries with backoff) |

## Rules
- The server **never stores** audio or text from `/transcribe`.
- Breaking changes → `/v2`. Additive fields are allowed in v1; clients must ignore unknown fields.

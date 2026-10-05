# Privacy & Data Handling — Sma3ni

Voice notes are private conversations, often including people who never agreed to use the app. Privacy is a core feature, not a checkbox.

## Principles
1. **Process, don't keep.** Audio and transcripts are never stored on the server by default.
2. **On-device by default.** History lives only on the user's phone.
3. **Opt-in only** for training data, off by default, revocable at any time.
4. **Minimum data.** No accounts, no phone numbers, no contacts, no analytics on content.

## Default flow (no donation)
| Data | Where | Retention |
|---|---|---|
| Audio | In transit (TLS) → server temp file | Deleted in `finally` right after processing |
| Transcript / summary | Returned to phone | Phone only, until user deletes |
| Install token | Phone only. The server signs it and checks the signature; it keeps no list of installs | Until app is uninstalled / signing key rotated |
| Daily usage count | Server (rate limiting) | Per token, for the current UTC day only |
| Request metadata | Server logs | 30 days: request id, duration, latency, model version, error code. **No text, no audio.** |

## LLM features
- Summary / translation / replies send the **transcript text** (not audio) to the LLM provider.
- Use a provider with **no training on API data** and no or short retention; document the provider in the privacy policy.
- These features are explicit user actions (or an explicit setting).

## Donation (opt-in)
- Consent screen explains: what is sent (audio + corrected text), why (improve Darija recognition), who can access it, how long it's kept, how to delete.
- The user should only donate notes **they recorded themselves** or have permission to share. Shown clearly in the consent text.
- Stored in a separate, encrypted, access-controlled bucket; tagged with `consent_version`.
- Anonymization before use: names, numbers, addresses replaced per `TRANSCRIPTION_GUIDELINES.md` §6.
- `DELETE /v1/donations` removes everything linked to the token.

## Engineering rules
- Never log request bodies, transcript text, audio, or tokens.
- Sentry / error reporting: scrub request bodies; no breadcrumbs with text.
- Temp files in a dedicated directory (`AUDIO_TMP_DIR`, one `req-*` dir per request, removed in `finally`); a startup sweep clears leftovers older than 10 minutes. In production, point it at a RAM-backed tmpfs so audio never touches disk, and set `TMPDIR` to the same place: Starlette buffers uploads over 1 MB in an anonymous temp file there (unlinked on Linux, closed when the request ends) before the server copies it.
- TLS only; HSTS.
- Secrets in environment variables / secret manager.

## Legal checklist
- Privacy policy page (public URL) in Arabic, French, English
- Tunisia: personal data law (Organic Law 2004-63) and INPDP: check whether declaration is needed once collecting donated data
- EU users (diaspora): GDPR basics, i.e. lawful basis (consent), deletion right, processor list
- App Store privacy labels / Google Play Data Safety must match this document
- Not legal advice: have the policy reviewed before public launch

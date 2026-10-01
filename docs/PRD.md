# Product Requirements — Sma3ni

## Problem
Tunisians send huge numbers of WhatsApp voice notes. People often can't listen: in class, at work, in meetings, in public, or with no headphones. Existing transcription (including built-in messenger features and general speech models) handles Tunisian Darija poorly, especially fast, noisy speech mixed with French.

## Target users
- **Primary:** Tunisians aged 16–45 who get voice notes daily (students, employees, freelancers)
- **Secondary:** the Tunisian diaspora; people with hearing difficulties; later, other Maghrebi users (Algeria, Morocco)

## Goals
1. Read any Darija voice note in **< 5 seconds** after sharing it
2. Transcripts that are **good enough to understand** without listening (target WER < 30% on our real voice-note test set for v1)
3. Users trust it with private audio (no storage, clear consent)

## Non-goals (v1)
- Live/real-time transcription of calls
- Reading WhatsApp chats or automatic background transcription (no private APIs)
- Languages other than Tunisian Darija + French/English code-switching
- Desktop app

## User stories
| # | As a… | I want to… | So that… |
|---|---|---|---|
| U1 | user | share a voice note from WhatsApp to the app | I can read it without listening |
| U2 | user | choose Arabic script or Arabizi | I read in the script I'm comfortable with |
| U3 | user | get a one-line summary for long notes | I get the point fast |
| U4 | user | translate the transcript to French/English | I can share it with non-Darija speakers |
| U5 | user | see quick reply suggestions | I can answer fast |
| U6 | user | correct a wrong transcript | the app learns (if I opt in) |
| U7 | user | search my past transcripts (stored on my phone only) | I find that address someone sent me |
| U8 | user | delete everything in one tap | I stay in control |

## Features by release
**MVP (v0.1)**
- Share extension (iOS) + share intent (Android)
- Transcript in Arabic script
- Copy button
- Audio deleted after transcription

**v0.2**
- Arabizi output
- Summary for notes > 20 s (threshold lives in `API.md`, which is the contract)
- Local history + search (on device)
- Correct-this-transcript (opt-in data donation)

**v1.0 (store launch)**
- Translation FR/EN
- Quick replies
- Onboarding, settings, delete-all
- Arabic / French / English UI

**v2**
- On-device model (offline, private, zero server cost)
- Other Maghrebi dialects

## Success metrics
- WER / CER on frozen voice-note test set (see `ML_PLAN.md`)
- Time from share → transcript (p50 < 3s, p95 < 8s for a 30s note)
- Weekly active users and transcriptions per user
- % transcripts corrected by users (lower is better)
- Store rating ≥ 4.5

## Risks
| Risk | Mitigation |
|---|---|
| Poor accuracy on noisy, fast speech | Noise/codec augmentation, real voice-note data, correction flywheel |
| No standard Darija spelling | Strict guidelines (`TRANSCRIPTION_GUIDELINES.md`) |
| GPU costs if usage grows | Serverless GPU, quotas, then on-device model |
| Privacy concerns | No storage, explicit opt-in, transparent policy |
| Messenger apps improve their own transcription | Win on Darija quality, Arabizi, summaries, local focus |

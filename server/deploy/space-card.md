---
title: Sma3ni API
emoji: 🎙️
colorFrom: red
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
license: apache-2.0
short_description: Tunisian Darija voice notes to text (HTTP API)
---

# Sma3ni API

The backend of [Sma3ni](https://github.com/hsanjebri/sma3ni): Tunisian Darija voice notes to text.

This Space only hosts the HTTP API. It is deployed from the GitHub repo by
`server/deploy/hf_space.py`, so change the code there, not here.

- Contract: [`docs/API.md`](https://github.com/hsanjebri/sma3ni/blob/main/docs/API.md). Health check: `GET /v1/health`.
- Privacy: audio is deleted right after each request and transcripts are never stored.
  Speech-to-text currently runs on Groq ([`docs/PRIVACY.md`](https://github.com/hsanjebri/sma3ni/blob/main/docs/PRIVACY.md)).

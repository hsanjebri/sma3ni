# Contributing

Thanks for helping make Tunisian speech recognition better 🇹🇳

## Ways to help
- **Donate voice notes** (with consent) through the in-app "Help improve Sma3ni" option, or record a few clips for the test set.
- **Fix transcripts** using the "Correct" button in the app.
- **Code**: pick an issue labeled `good first issue`.
- **Transcribe data**: follow `docs/TRANSCRIPTION_GUIDELINES.md` exactly.

## Dev setup
See the Quick start in `README.md` and the `AGENTS.md` in each folder.

## Pull requests
1. Branch from `main`: `feat/short-description`
2. Conventional Commits (`feat:`, `fix:`, `docs:`, `ml:`, `chore:`)
3. Tests + lint pass
4. Update docs touched by your change
5. For ML changes, paste the metrics table (WER / CER / code-switch F1) vs baseline

## Data rules
- Never commit audio, transcripts or datasets. Use `data/` (gitignored) or Hugging Face.
- Only use audio from people who **explicitly agreed** to it being used for training.
- Remove names, phone numbers and other personal info from transcripts before sharing them (see `docs/PRIVACY.md`).

## Code of conduct
Be kind, be patient, and remember most contributors are volunteers.

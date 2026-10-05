# Contributing

Thanks for helping make Tunisian speech recognition better 🇹🇳

## Ways to help
- **Donate voice notes** (with consent) through the in-app "Help improve Sma3ni" option, or record a few clips for the test set.
- **Fix transcripts** using the "Correct" button in the app.
- **Code**: pick an issue labeled `good first issue`.
- **Transcribe data**: follow `docs/TRANSCRIPTION_GUIDELINES.md` exactly, then check your batch with `cd ml && uv run sma3ni-manifest validate <manifest>` before handing it over.

## Dev setup
See the Quick start in `README.md` and the `AGENTS.md` in each folder.

## Branches
| Work | Branch | Merges into `main` |
|---|---|---|
| A roadmap phase | `phase/<n>-<name>`, e.g. `phase/3-api`, `phase/4-mobile` | when the phase's **Exit** criteria in `docs/ROADMAP.md` are met |
| A big feature outside a phase | `feat/<name>`, e.g. `feat/ios-share-extension` | when the feature works end to end |
| A small standalone fix or doc change | `fix/<name>`, `docs/<name>` | as soon as it's reviewed |

On a phase or feature branch:
- **One commit per step**, each with its own tests and docs, so the branch is green at every commit.
- Open a **draft PR** to `main` on the first push. CI runs on every push, and the PR description holds the phase checklist.
- When `main` moves, **merge** it into the branch. Don't rebase: the branch is already shared.
- Merge the PR with a **merge commit**, not squash, so every step stays in `main`'s history.

## Pull requests
1. Conventional Commits (`feat:`, `fix:`, `docs:`, `ml:`, `chore:`)
2. Tests + lint pass
3. Update docs touched by your change
4. For ML changes, paste the metrics table (WER / CER / code-switch F1) vs baseline

## Data rules
- Never commit audio, transcripts or datasets. Use `data/` (gitignored) or Hugging Face.
- Only use audio from people who **explicitly agreed** to it being used for training.
- Remove names, phone numbers and other personal info from transcripts before sharing them (see `docs/PRIVACY.md`).

## License
Sma3ni is licensed under [Apache-2.0](LICENSE). By opening a pull request you agree that your contribution is licensed under the same terms (Apache-2.0, section 5).

## Code of conduct
Be kind, be patient, and remember most contributors are volunteers.

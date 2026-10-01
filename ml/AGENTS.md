# ml/AGENTS.md

Read the root `AGENTS.md` first.

## Scope
Data preparation, benchmarking, fine-tuning and export of speech models. Python package `sma3ni_ml`.

## Layout
```
ml/
├── pyproject.toml
├── configs/              # YAML configs (benchmark.yaml, train_*.yaml)
├── resources/            # loanwords.tsv, arabizi_map.tsv, arabizi_lexicon.tsv (small, versioned)
├── src/sma3ni_ml/
│   ├── text.py           # normalize(), arabizi(), lint() — implements TRANSCRIPTION_GUIDELINES.md
│   ├── data.py           # manifests + `sma3ni-manifest` CLI (+ dataset loaders, Phase 2)
│   ├── augment.py        # noise, speed, opus re-encode                     (Phase 2, not written)
│   ├── metrics.py        # WER, CER, code-switch F1, slice reports
│   ├── benchmark.py      # CLI: run models on a manifest
│   ├── train.py          # CLI: LoRA / full fine-tune                       (Phase 2, not written)
│   └── export.py         # merge LoRA, CTranslate2, whisper.cpp             (Phase 3, not written)
├── tests/
├── reports/              # generated benchmark reports — gitignored
├── RESULTS.md            # all benchmark/eval results (append only)
└── data/                 # gitignored
```

Modules marked *not written* arrive with their phase; don't stub them early.

## Rules
- **Frozen test set:** `data/test_v1` manifest hash is recorded in `RESULTS.md`. Never train on it, never edit it. A new test set means `test_v2` + approval.
- Every metric goes through `metrics.py` after `text.normalize_for_scoring()` (which `metrics.py` applies itself). No ad hoc scoring in notebooks.
- Rates are corpus-level (total edits / total reference words), never a mean of per-clip rates.
- Configs over code: hyperparameters in YAML, not hard-coded.
- Set seeds; log config + git commit to W&B for every run.
- Notebooks only in `notebooks/` for exploration; anything reused moves into `src/`.
- Large files (checkpoints, audio) never committed. Use Hugging Face Hub or `data/`.
- Check dataset licenses before adding a loader; record the license in `data.py` docstring.

## Commands
```bash
uv sync                      # core deps only: CPU, no torch — tests run on this
uv sync --extra asr          # adds faster-whisper / transformers / torch for real runs
uv run pytest
uv run ruff check . && uv run ruff format --check .
uv run python -m sma3ni_ml.benchmark --config configs/benchmark.yaml
uv run python -m sma3ni_ml.train --config configs/train_turbo_lora.yaml     # Phase 2
uv run python -m sma3ni_ml.export --checkpoint <path> --format ct2          # Phase 3
```

Building a test set (Phase 1), in order:
```bash
# 1. transcribers fill a TSV: id, text, speaker, region, gender, consent[, duration]
uv run sma3ni-manifest build --metadata clips.tsv --audio-dir data/own/audio \
    --split test --out data/test_v1/manifest.jsonl     # durations via ffprobe
# 2. schema, missing audio, guideline violations, speaker leaks, consent
uv run sma3ni-manifest validate data/test_v1/manifest.jsonl
# 3. 10% of clips transcribed twice — target is under 10% WER between passes
uv run sma3ni-manifest agreement pass_a.tsv pass_b.tsv
# 4. freeze: paste the printed line into RESULTS.md and the hash into the config
uv run sma3ni-manifest hash data/test_v1/manifest.jsonl
```
`validate` exits non-zero when something is wrong, so it belongs in any data
script. Run it again after any manifest edit and before freezing.
Model backends are imported lazily, so `uv run pytest` needs neither a GPU nor
the `asr` extra. Keep it that way: new tests must run on the core install.

## Benchmark backends
| `backend:` | Use |
|---|---|
| `faster_whisper` | CTranslate2 models — the same runtime the server uses |
| `transformers` | HF checkpoints not exported to CTranslate2 yet |
| `predictions` | replay a `{"id", "text"}` jsonl: scores a system we can't run here, with identical metrics |

## Reporting results
`benchmark.py` writes `reports/<date>_<model>.json` (metrics + slices) and
`reports/<date>_<model>.hyp.jsonl` (the hypotheses), then prints the row to
append **by hand** to `RESULTS.md` — the ledger is append-only, so no tool edits it:
```
| date | model | test set | WER | CER | CS-F1 | RTF | commit | notes |
```
Pass `--commit $(git rev-parse --short HEAD)` so the row is traceable.

# ml/AGENTS.md

Read the root `AGENTS.md` first.

## Scope
Data preparation, benchmarking, fine-tuning and export of speech models. Python package `sma3ni_ml`.

## Layout
```
ml/
├── pyproject.toml
├── configs/              # YAML configs (benchmark.yaml, train_*.yaml)
├── resources/            # loanwords.tsv, arabizi_map.tsv (small, versioned)
├── src/sma3ni_ml/
│   ├── text.py           # normalize(), arabizi() — implements TRANSCRIPTION_GUIDELINES.md
│   ├── data.py           # dataset loaders + manifest builder
│   ├── augment.py        # noise, speed, opus re-encode
│   ├── metrics.py        # WER, CER, code-switch F1, slice reports
│   ├── benchmark.py      # CLI: run models on a manifest
│   ├── train.py          # CLI: LoRA / full fine-tune
│   └── export.py         # merge LoRA, CTranslate2, whisper.cpp
├── tests/
├── RESULTS.md            # all benchmark/eval results (append only)
└── data/                 # gitignored
```

## Rules
- **Frozen test set:** `data/test_v1` manifest hash is recorded in `RESULTS.md`. Never train on it, never edit it. A new test set means `test_v2` + approval.
- Every metric goes through `metrics.py` after `text.normalize()`. No ad hoc scoring in notebooks.
- Configs over code: hyperparameters in YAML, not hard-coded.
- Set seeds; log config + git commit to W&B for every run.
- Notebooks only in `notebooks/` for exploration; anything reused moves into `src/`.
- Large files (checkpoints, audio) never committed. Use Hugging Face Hub or `data/`.
- Check dataset licenses before adding a loader; record the license in `data.py` docstring.

## Commands
```bash
uv sync
uv run pytest
uv run python -m sma3ni_ml.benchmark --config configs/benchmark.yaml
uv run python -m sma3ni_ml.train --config configs/train_turbo_lora.yaml
uv run python -m sma3ni_ml.export --checkpoint <path> --format ct2
```

## Reporting results
Append to `RESULTS.md`:
```
| date | model | test set | WER | CER | CS-F1 | RTF | commit | notes |
```

# ML Plan — Sma3ni

## Objective
Best possible transcription of **real Tunisian WhatsApp voice notes**: noisy, fast, compressed, and code-switched with French/English.

## Data

### External datasets (check each license before training or redistributing)
| Dataset | Content | Notes |
|---|---|---|
| LinTO Tunisian ASR (audio + text) | Tunisian dialect speech, incl. code-switching | Text corpus also useful for LM / normalization |
| TuniSpeech (~21 h) | Spontaneous Tunisian speech | Used for public Whisper fine-tunes |
| TEDxTN | Code-switched Tunisian Arabic / English talks | Cleaner, presentation-style speech |
| Common Voice Arabic | MSA read speech | Only as regularizer, small share |

### Our own data
- **Test set (frozen):** 1–2 h of real voice notes, ~300–600 clips, from ≥ 30 speakers, balanced by gender, region (Tunis, Sfax, Sousse, south, northwest), and age. Never used for training.
- **Dev set:** ~1 h, same distribution, used for model selection.
- **Train set (own):** everything else collected, plus opt-in donations later.
- **Consent:** written/recorded consent per speaker for (a) evaluation, (b) training, (c) public release — tracked separately.
- **Speaker separation:** a speaker appears in only one split.

### Manifest format (`jsonl`)
```json
{"id": "vn_000123", "audio": "data/own/vn_000123.opus", "text": "...", "duration": 12.4,
 "speaker": "spk_017", "region": "sfax", "gender": "f", "source": "own", "consent": ["eval","train"], "split": "test"}
```

Manifests are built and checked with `sma3ni-manifest` (see `ml/AGENTS.md`): `build` from a transcriber TSV plus a folder of audio, `validate` for schema / missing audio / guideline violations / speaker leaks / missing consent, `agreement` for the double-transcription check, `hash` to freeze. The hash is content-based and order-independent, so reformatting the file never invalidates a frozen set — only the data does.

## Normalization
One function, `sma3ni_ml.text.normalize()`, implements `TRANSCRIPTION_GUIDELINES.md` and is used for training targets, predictions before scoring, and the server output. Tests cover every rule in the guidelines.

## Metrics
- **WER** (primary) and **CER** after normalization
- **Code-switch F1:** precision/recall on Latin-script (French/English) words
- **Latency:** real-time factor on target hardware
- Reported **per slice**: noise level, region, gender, duration bucket
- Results logged in `ml/RESULTS.md` with model id, commit hash, test-set hash

## Models to try
| Model | Role |
|---|---|
| whisper-large-v3 / v3-turbo (zero-shot) | Baseline |
| Public Tunisian fine-tunes (e.g. TuniSpeech) | Strong baseline |
| Multi-dialect Arabic Whisper fine-tunes | Baseline |
| w2v-BERT 2.0 + CTC | Compact alternative, strong in published Tunisian results |
| **Ours:** large-v3-turbo + LoRA | Server model |
| **Ours:** whisper-small + LoRA / full | On-device model (v2) |

## Training recipe (starting point)
- HF Transformers `Seq2SeqTrainer` + PEFT LoRA (r=32, alpha=64, on q/k/v/o + fc layers)
- LR 1e-4 (LoRA) / 1e-5 (full), warmup 500 steps, bf16, batch 16–32 via gradient accumulation
- Forced language token `ar`; transcribe task
- Two-stage option: (1) adapt on all Tunisian data, (2) short fine-tune on voice-note-style data
- Early stopping on dev WER
- Tracking: Weights & Biases (config, metrics, sample predictions)

## Augmentation
- Background noise (street, café, car, TV) at SNR 5–20 dB
- Speed perturbation 0.9–1.1
- Opus re-encode at 16/24/32 kbps (simulates WhatsApp)
- Volume changes, light reverb

## Compute & cost
| Step | Hardware | Estimate |
|---|---|---|
| Benchmark | Kaggle/Colab T4 or rented GPU | Free – $5 |
| whisper-small fine-tune | Kaggle T4/P100 | Free |
| large-v3-turbo LoRA | Rented A100 (RunPod / Vast.ai) | ~$20–60 per run |

## Export
- Merge LoRA → full weights
- Server: CTranslate2 int8_float16 for faster-whisper
- On-device (v2): whisper.cpp GGML, q5/q8 quantization; measure RTF on a mid-range Android phone and an iPhone

## Release
- Publish to Hugging Face with a model card: data, metrics per slice, known limitations, license, intended use
- Only publish weights if all training data licenses allow it; otherwise keep weights private and publish the benchmark + method

## Continuous improvement
- Donated corrections → review queue → added to train set monthly
- Retrain, evaluate on frozen test, ship only if WER improves without slice regressions

# PrivSense: intra-dataset agentic pilot

A Qwen agent uses OpenRouter tool calls to investigate seven-class activity inference from existing shake/no-shake outputs (`dec_tree_out_1`). It chooses feature combinations and classifiers, observes validation feedback, revises experiments, and explicitly submits a candidate. This is **constrained adaptive attack search**, not autonomous feature invention, raw-data HAR, or proof of a novel privacy vulnerability.

## Setup

Run from this repository (`.`):

```bash
python -m virtualenv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Alternatively use `python -m venv .venv` if your Python installation includes ensurepip. Put `OPENROUTER_API_KEY=...` in `.env`. The existing `.env` is used automatically and ignored by Git. Never commit credentials. Model defaults to `qwen/qwen3.5-35b-a3b`, verified in OpenRouter's model catalog with tool support; edit `configs/pilot.json` to change it.

## Run

```bash
# Once: validate recordings and build nonoverlapping windows.
python experiment.py prepare

# Paid API calls: at most 14 model turns and 8 successful candidate evaluations.
python experiment.py agent --run runs/pilot-001

# Only after the agent submits: independently score on held-out subjects.
python experiment.py evaluate --run runs/pilot-001
```

Use a new run directory for each run; existing directories are not overwritten. Prepared data is reused. If data settings change, prepare a fresh directory with `--data data/new-name` and pass that directory to both later commands. API failures stop the run; automatic resume/retry is not implemented. Partial transcripts remain available. A run without explicit submission is a failure, not silently converted into a successful attack.

To check the pipeline without API calls:

```bash
pytest -q
python experiment.py agent --offline --run runs/offline-check
python experiment.py evaluate --run runs/offline-check
```

Offline mode uses a scripted duty-cycle/logistic-regression candidate and is explicitly marked `offline_smoke`; it is not evidence of agent capability.

## Experimental condition

- One dataset: local UTAH-STM-HAR processed recordings; right-pocket only.
- Private targets: Downstairs, Jogging, Laying, Sitting, Standing, Upstairs, Walking.
- Observable channel: 100 binary samples (2 seconds at 50 Hz); no raw IMU or absolute timestamps.
- Attacker receives shake semantics, activity objective, labeled auxiliary training data through aggregate summaries and training tools, and validation scores.
- Train subjects 1–7; validation subjects 8–9; final-test subjects 10–11. This is one fixed feasibility split, not a population-level estimate.
- No window crosses a recording boundary or timestamp discontinuity; short tails are dropped. Stair segments are shorter than other recordings, so manifest counts and dropped samples should be inspected.
- Features: duty cycle, transition rates, per-bit run statistics, five local means, lagged autocorrelation, and spectral bands. Classifiers: balanced logistic regression and a fixed-size random forest.
- Agent objective: validation macro-F1. Final evaluation reports accuracy, balanced accuracy, macro-F1, confusion matrices, and per-subject metrics.
- Final comparisons: majority-class prior and a fixed temporal-feature random forest. These are initial reference baselines, **not** a matched-budget comparison against AutoML or a fixed-plan LLM.

## Information boundary

The model receives only prompts, tool schemas, training summaries, candidate specifications, and validation metrics. These are sent to OpenRouter and its serving provider; raw traces and individual subject metadata are not sent. The local dispatcher executes only allowlisted Python functions. No generated code, shell command, arbitrary file path, or network request is accepted from the model. Thus the attacker cannot read test files through its tools. Trusted host code still has access to the source dataset; this is a bounded-tool boundary, not an OS sandbox suitable for arbitrary generated code.

`agent` loads training and validation arrays only. `evaluate` is a separate, non-LLM process; it refits the frozen specification on training subjects only, keeping validation subjects out of fitting. Test results never enter the agent conversation. Do not use final scores to revise prompts, features, or configurations and then report the same subjects as untouched test data. The evaluator refuses to overwrite an existing report, although researchers must still enforce this protocol across runs.

## Artifacts

- `data/pilot/manifest.json`: configuration, source hashes, subject partitions, class counts, dropped samples, and evaluator-only source paths.
- `runs/<name>/events.jsonl`: model messages, explicit hypotheses, tool calls/results, API model identifiers, usage/cost fields when returned.
- `config.json`, `trials.json`, `submission.json`: run settings, candidates, frozen selection, data-manifest hash, and runtime.
- `evaluation.json`: hidden-test results, generated only by the evaluator.

Data, credentials, and run outputs are ignored by Git. Installed package versions are recorded in `requirements-lock.txt` for this initial environment. Repeated seeds/splits, temporal-shuffle controls, budget-matched non-agentic search, fixed-plan LLM ablation, and detector-training provenance remain necessary before a research claim about agent advantage. This does not reproduce every experimental setting in the prior paper.

OpenRouter references: https://openrouter.ai/docs/api/api-reference/chat/send-chat-completion-request and https://openrouter.ai/api/v1/models

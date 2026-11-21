# PrivSense experiment guide

Run all commands from the repository root. This guide records the implemented pilot protocols and their historical results; see the [project README](../README.md) for the broader research roadmap. Dataset files, frozen run inputs, and raw API transcripts are not distributed with this checkout.

A Qwen agent uses OpenRouter tool calls to investigate seven-class activity inference from existing shake/no-shake outputs (`dec_tree_out_1`). It chooses feature combinations and classifiers, observes validation feedback, revises experiments, and explicitly submits a candidate. This is **constrained adaptive attack search**, not autonomous feature invention, raw-data HAR, or proof of a novel privacy vulnerability.

## Setup

Create an environment from the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and set `OPENROUTER_API_KEY` locally for live API runs. Credentials are ignored by Git. Place the processed dataset in `data/source/UTAH-STM-HAR`, set `PRIVSENSE_DATASET` to a local dataset directory, or change the `dataset` field in a copied config. Live runs use the model identifier in the selected config; check current provider availability before a paid run.

A known baseline test issue affects `test_disruption_preserves_observed_values_and_partial_tail`: numerically tied autocorrelation peaks can select a four-second harmonic where the test expects the two-second fundamental. This also occurs in the pre-cleanup code with the recorded dependency versions. The publication cleanup preserves the feature algorithm and historical measurements.

## Optional analysis dependencies

Install `requirements-representation.txt` for tokenizer-based representation and full-recording workflows, or `requirements-feature-analysis.txt` for feature-audit chart rendering:

```bash
python -m pip install -r requirements-representation.txt
python -m pip install -r requirements-feature-analysis.txt
```

Historical workflows also require their separately stored prepared inputs, run artifacts, and tokenizer snapshots. Those files are not included in this checkout.

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
python -m pytest -q
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

## Development-only binary audit and duration sweep

```bash
python duration_sweep.py --out runs/duration-sweep-001
```

This separate experiment uses `configs/duration_sweep.json` with only training subjects 1–7 and validation subjects 8–9. It never loads users 10–11 or calls an LLM. It audits binary patterns and compares fixed duty/logistic and temporal/random-forest baselines at 2, 5, 10, and 20 seconds. Alongside all eligible windows, a common-time-support analysis retains the same full 20-second spans across durations. Short recordings can be excluded; check class coverage. Outputs include source hashes, recording constancy, per-class window diversity, confusion matrices, recall, subject metrics, and a Markdown report. This diagnoses whether richer observations can help before extending the agent. It does not verify original detector firmware or reproduce the paper's full protocol.

## Stage 1: direct LLM inference (separate experiment)

This experiment sends each actual 100-bit observation directly to Qwen in a fresh conversation. It supplies binary semantics and seven activity candidates only: no sampling rate, placement, labels, examples, statistics, tools, or earlier responses. No conventional classifier generates the LLM predictions. Only users 8–9 are used. Users 10–11 are previously inspected test data and are not used here.

```bash
python direct_llm.py prepare
python direct_llm.py infer --smoke --run runs/direct-stage1-smoke-new
python direct_llm.py evaluate --smoke --run runs/direct-stage1-smoke-new
python direct_llm.py infer --run runs/direct-stage1-repeat
python direct_llm.py evaluate --run runs/direct-stage1-repeat
```

Skip `prepare` only when reusing an already prepared directory with matching inputs and settings. The evaluator uses `data/pilot/train.npz` for training-prior baselines only (create it with `python experiment.py prepare` on a new checkout). The inference process never reads that file or `truth.jsonl`.

`configs/direct_llm.json` fixes temperature 0.1, a 600-token output limit, explicit reasoning disabled, and eight concurrent independent requests. Prompts are logged exactly in each response record; `run.json` also stores the templates, settings, and input fingerprint. Submission order is fixed; completion order can vary with concurrency. Change temperature or other sampling settings in a copied config and use `--config` plus a new run directory for independent repeats. No prediction is reused for duplicate binary observations.

Use `--resume` with exactly the same inputs/config after interruption; completed responses, including invalid responses and API failures, are not retried by default. After resolving an API issue, add `--retry-api-errors` to append attempts for API failures only; successful predictions are never replaced. New submissions stop on credit/auth errors (HTTP 401/402/403). There is one scheduled API request per observation per attempt; explicit recovery attempts remain in the log and usage totals. A crash before a response is persisted can cause an additional request on resume. Invalid/missing predictions count as errors in primary metrics; valid-only metrics are also provided. Timeout failures may have unreported provider charges. Keys are never included in logs.

`evaluate` runs separately after inference and writes results locally, without sending correctness feedback. It reports seven-class and moving/stationary metrics, uncertainty, subject/recording summaries, identical-input collisions and prediction inconsistency, prior baselines, and a predeclared Walking/Sitting binary rule. The empirical pattern accuracy bound is a label-aware diagnostic, not a deployable baseline. The initial 14-window smoke subset is one window per subject/activity, selected with seed 42; it overlaps the full validation set and is not a separate test. See `reports/direct_llm_inference_pilot.md` for results and limitations. Completed Stage 2 screens are documented below. The original Stage 3 autonomy and information-request extension is not implemented.

Stage 1 is now complete: all 1,947 validation observations have valid predictions. The initial attempt obtained 228 predictions before credit exhaustion; after recharge, 1,719 failed observations were recovered without replacing any successful prediction. Final accuracy is 30.61%, macro-F1 0.13445, and moving/stationary accuracy 100%, matching the fixed binary-rule baseline. The run reported $0.466957 total inference cost, including $0.412921 for recovery (smoke tests separate). Historical failures remain in the logs. Recovery commands for an interrupted run are:

```bash
python direct_llm.py infer --run runs/direct-stage1-full --resume --retry-api-errors
python direct_llm.py evaluate --run runs/direct-stage1-full
python direct_report.py
```

## Stage 2: completed 84-request screen

The historical screen is separate from Stage 1: 14 fixed matched targets × five knowledge/context conditions plus the original-prompt reference. It has been run once; no full 372-target expansion or interaction/repeat runs were launched.

- Results and interpretation: `reports/stage2_screening_results.md`.
- Read-only placement survey and benchmark protocol: `reports/binary_interface_benchmark_design.md` and `reports/stage2_screen_survey.json`.
- Frozen inputs: `data/stage2-screen/`; responses, metrics and qualitative explanation review: `runs/stage2-screen/`.
- Runner: `stage2_screen.py prepare|infer|evaluate`. Use new `--data` and `--run` paths for an independent repeat; live inference incurs provider charges. `--resume` skips completed responses and does not repair/retry invalid answers.
- Report renderer: `python stage2_report.py` (reads the default completed screen and saved qualitative annotations).
- Offline survey: `python scripts/survey_binary_interfaces.py`; reads existing development recordings without changing them or calling Qwen.

All six conditions scored 4/14 correct. Metadata/history did not change labels; examples and combined knowledge changed the moving-class guess. Three outputs were invalid and retained as failures. Explanation flags are a single implementation-assistant qualitative assessment, not independently validated human annotations. Do not interpret macro-F1 changes or lower confidence as additional activity information.

### E3 cross-user auxiliary-knowledge screen

Completed 70 primary requests (K0/K1/K5/K10/K20 on the same 14 E2 targets),
14 exact E2 combined-prompt bridge requests, and two reversed-reference checks.
See [the E3 report](../reports/e3_cross_user_auxiliary_inference.md) for results,
exact prompts, reference selection, failures, costs and information limitations.
`e3_experiment.py` prepares frozen nested references, submits independent direct
Qwen requests, and evaluates results; `e3_report.py` renders the saved evidence.
Inputs and outputs are isolated in ignored `data/e3-screen` and `runs/e3-screen`.
Preparation/inference refuse existing directories; evaluation and report rendering
are offline and preserve reviewed explanation annotations. No full expansion ran.

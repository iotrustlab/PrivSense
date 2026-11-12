# PrivSense Stage 2: Qwen representation comparison

This is the restructured 50-request representation screen, separate from historical E1–E3 and full-recording results. No prior score is repaired or overwritten. Qwen directly predicts activities; conventional baselines are evaluator-side only.

**Result:** all 12 technical-gate and 50 research responses passed the three-field schema. Raw strings and temporal summaries each achieved 4/15 correct activities; duty-only achieved 3/15. Temporal summaries changed uncertainty substantially but did not improve exact-class accuracy over raw observations. Order disruption changed one wrong prediction to another wrong prediction. This does not justify progressing to an autonomous feature-discovery stage.

## Output reliability and technical gate

Protocol `privsense-inference-v2.0` requires exactly `predicted_activity` (one of seven candidates), `confidence` (finite number in [0,1]), and `sufficient_information` (boolean). Duplicate keys, extra/missing fields, invalid labels, nonfinite values and wrong types are rejected without repair. Strict JSON Schema is sent to OpenRouter; no response-healing plugin is used.

OpenRouter documents endpoint-specific schema support and cautions that strict enforcement varies by provider: [structured outputs documentation](https://openrouter.ai/docs/guides/features/structured-outputs). A fresh endpoint snapshot advertises both response_format and structured_outputs for deepinfra/fp8. Local schema and payload tests precede API use.

The separately logged gate uses 12 calls: two actual User 1 constant binary cases × short (100 samples), fixed (500 samples), and complete-recording profiles × two repeats. References come only from users 2–7. Target labels are neither exported nor scored. All requests were frozen before execution. Gate passage requires 12 strict-valid normal-stop responses, correct provider/model, and plausible input usage. Research calls are conditional on that result. Twelve successes are a smoke test, not proof of a low failure probability (an idealized independent-binomial one-sided 95% upper failure bound is 22.1%).

- gate: 12 calls, 12 schema-valid, 12 delivery-valid; provider counts {'DeepInfra': 12}; input tokens 365,950, output tokens 296; API-reported cost **$0.051529** (12 cost fields present).
- research: 50 calls, 50 schema-valid, 50 delivery-valid; provider counts {'DeepInfra': 50}; input tokens 108,993, output tokens 1,234; API-reported cost **$0.016493** (50 cost fields present).

| Research condition | Input tokens | Output tokens | API cost USD |
|---|---:|---:|---:|
| R | 83,048 | 360 | $0.011987 |
| D | 8,633 | 371 | $0.001580 |
| T | 12,983 | 386 | $0.002204 |
| T-order | 4,329 | 117 | $0.000723 |

Model `qwen/qwen3.5-35b-a3b`; only `deepinfra/fp8`, fallback disabled, require_parameters=true; temperature 0.1; reasoning disabled; 128 output tokens; no sampling seed assumed; independent stateless requests; no retries. The provider advertises 262,144 context tokens. Local token counts include message content; an allowance of 2,048 covers framing/schema. All 62 responses ended with stop and API prompt usage exceeded locally counted message-content tokens by exactly 17 tokens. Usage agreement supports complete submission but does not prove internal attention to every sample.

## Frozen data, prompts and controls

The 15 targets are unchanged from `next_inference_audit/proposed_pilot_selection.json`: ten constant controls and five varying intervals. Every interval has 500 actual samples (10 seconds). There are nine fixed training references per placement: seven class-covering plus two deliberately varying references. Users 1–7 supply references; users 8–9 supply targets and remain absent from the reference set. These are previously studied development users, not a new final test.

R supplies full lossless 500-character binary strings for every reference and target. D supplies fraction_ones only. T supplies fraction_ones, transition_count, max_zero_run_fraction and max_one_run_fraction. Fractions are rounded to four decimals in all feature payloads; full values remain in evaluator artifacts. Sensor knowledge, duration, reference labels/order, candidate order, system instruction and output contract are identical. The common definition block explains all representation fields in every condition. Thus D does not get a different knowledge prompt. Neither file paths, target labels, subject identifiers, source offsets nor classifier outputs appear in messages.

T-order changes only the five varying target representations; references remain chronological. Ten 50-sample blocks are permuted using the pre-existing source/start-derived seed. Preflight found one original seed produced unchanged bits because blocks repeat. Before any API call, the rule was frozen to draw from that same seeded stream until the bits differ. This guarantees changed displayed order while preserving samples, length, bit counts and within-block observations. It is a declared synthetic ordering control, never presented as newly observed transitions. No activity labels or Qwen results enter this choice. T captures run summaries, not full temporal order: changed bit order can still leave all T fields unchanged.

Request order is counterbalanced across R/D/T and controls are interspersed with seed 20261111. This is one repeat. The exact system/user prompts are stored in `../data/representation-screen/requests.jsonl`; the separate label-blind gate is in `technical_requests.jsonl`. Source samples and hashes were checked before requests.

## Activity inference results

All macro-F1 values average over the seven fixed candidate labels, including labels absent from this small panel. Balanced accuracy averages over supported true labels. Unresolved failures count as incorrect. Moving classes are Downstairs, Jogging, Upstairs and Walking.

| Condition | N | Accuracy | Macro-F1 | Moving/stationary | Mean confidence | Insufficient | Invalid/missing |
|---|---:|---:|---:|---:|---:|---:|---:|
| R | 15 | 26.7% | 0.1389 | 80.0% | 0.850 | 6 | 0 |
| D | 15 | 20.0% | 0.1122 | 80.0% | 0.359 | 15 | 0 |
| T | 15 | 26.7% | 0.1582 | 86.7% | 0.423 | 14 | 0 |
| T-order | 5 | 20.0% | 0.0714 | 60.0% | 0.640 | 5 | 0 |

T-order is evaluated on five varying targets only; compare it to T on those same five, not to the 15-target aggregate.

| Condition | Stratum | N | Accuracy | Macro-F1 | Moving/stationary |
|---|---|---:|---:|---:|---:|
| R | constant | 10 | 30.0% | 0.1293 | 100.0% |
| R | varying | 5 | 20.0% | 0.0476 | 40.0% |
| D | constant | 10 | 30.0% | 0.1388 | 100.0% |
| D | varying | 5 | 0.0% | 0.0000 | 40.0% |
| T | constant | 10 | 30.0% | 0.1293 | 100.0% |
| T | varying | 5 | 20.0% | 0.0714 | 60.0% |
| T-order | varying | 5 | 20.0% | 0.0714 | 60.0% |

## Paired changes

| Contrast (after − before) | N | Predictions changed | Wrong → correct | Correct → wrong | Accuracy difference |
|---|---:|---:|---:|---:|---:|
| D-R | 15 | 6 | 0 | 1 | -6.7 pp |
| T-R | 15 | 4 | 0 | 0 | +0.0 pp |
| T-D | 15 | 3 | 1 | 0 | +6.7 pp |
| T-order-T | 5 | 1 | 0 | 0 | +0.0 pp |

## Fixed conventional baselines

Baseline predictions were frozen before research calls. All reference baselines use the same nine labeled observations per placement. Fixed bit predicts Walking for >50% ones, otherwise Sitting. Reference prior uses reference class frequency, class-list tie-breaking. Duration-only reduces to that prior because every observation is ten seconds. Nearest duty/T uses mean absolute distance, transition_count normalized by 499, and tied-neighbor votes divided by each class’s reference support; final ties use the fixed class order. These rules are descriptive comparison algorithms, not claims about optimal classifiers. No baseline supplies a Qwen answer.

| Baseline | Order/subset | N | Accuracy | Macro-F1 | Moving/stationary |
|---|---|---:|---:|---:|---:|
| fixed_bit | original/all | 15 | 6.7% | 0.0357 | 86.7% |
| fixed_bit | original/varying | 5 | 0.0% | 0.0000 | 60.0% |
| fixed_bit | original/constant | 10 | 10.0% | 0.0476 | 100.0% |
| reference_prior | original/all | 15 | 20.0% | 0.1548 | 46.7% |
| reference_prior | original/varying | 5 | 0.0% | 0.0000 | 40.0% |
| reference_prior | original/constant | 10 | 30.0% | 0.2238 | 50.0% |
| duration_only | original/all | 15 | 20.0% | 0.1548 | 46.7% |
| duration_only | original/varying | 5 | 0.0% | 0.0000 | 40.0% |
| duration_only | original/constant | 10 | 30.0% | 0.2238 | 50.0% |
| nearest_duty | original/all | 15 | 26.7% | 0.1944 | 86.7% |
| nearest_duty | original/varying | 5 | 20.0% | 0.0714 | 60.0% |
| nearest_duty | original/constant | 10 | 30.0% | 0.2000 | 100.0% |
| nearest_temporal | original/all | 15 | 33.3% | 0.2404 | 86.7% |
| nearest_temporal | original/varying | 5 | 40.0% | 0.1429 | 60.0% |
| nearest_temporal | original/constant | 10 | 30.0% | 0.2000 | 100.0% |
| fixed_bit | disrupted/all | 5 | 0.0% | 0.0000 | 60.0% |
| fixed_bit | disrupted/varying | 5 | 0.0% | 0.0000 | 60.0% |
| reference_prior | disrupted/all | 5 | 0.0% | 0.0000 | 40.0% |
| reference_prior | disrupted/varying | 5 | 0.0% | 0.0000 | 40.0% |
| duration_only | disrupted/all | 5 | 0.0% | 0.0000 | 40.0% |
| duration_only | disrupted/varying | 5 | 0.0% | 0.0000 | 40.0% |
| nearest_duty | disrupted/all | 5 | 20.0% | 0.0714 | 60.0% |
| nearest_duty | disrupted/varying | 5 | 20.0% | 0.0714 | 60.0% |
| nearest_temporal | disrupted/all | 5 | 40.0% | 0.1286 | 60.0% |
| nearest_temporal | disrupted/varying | 5 | 40.0% | 0.1286 | 60.0% |

## Individual predictions

| Target | Placement | Subject | True class | Stratum | R | D | T | T-order |
|---|---|---:|---|---|---|---|---|---|
| p01 | left-ankle | 8 | Laying | constant | Laying (0.95) | Laying (0.5) | Laying (0.6667) | — |
| p02 | left-ankle | 9 | Jogging | constant | Downstairs (1.0) | Walking (0.2) | Downstairs (0.1429) | — |
| p03 | left-ankle | 9 | Standing | varying | Standing (0.5) | Walking (0.6) | Standing (0.85) | Standing (0.6) |
| p04 | left-ankle | 9 | Standing | varying | Laying (0.85) | Walking (0.6) | Walking (0.6) | Walking (0.6) |
| p05 | left-wrist | 8 | Laying | constant | Laying (1.0) | Laying (0.3333) | Laying (0.3333) | — |
| p06 | left-wrist | 9 | Jogging | constant | Downstairs (0.5) | Downstairs (0.14) | Downstairs (0.1429) | — |
| p07 | right-ankle | 8 | Standing | constant | Laying (1.0) | Laying (0.33) | Laying (0.3333) | — |
| p08 | right-ankle | 9 | Upstairs | constant | Downstairs (1.0) | Downstairs (0.1429) | Downstairs (0.125) | — |
| p09 | right-ankle | 8 | Standing | varying | Upstairs (0.6) | Laying (0.33) | Sitting (0.6) | Laying (0.8) |
| p10 | right-pocket | 8 | Standing | constant | Laying (1.0) | Laying (0.33) | Laying (0.3333) | — |
| p11 | right-pocket | 9 | Downstairs | constant | Downstairs (1.0) | Downstairs (0.125) | Downstairs (0.1429) | — |
| p12 | right-wrist | 8 | Standing | constant | Laying (1.0) | Laying (0.33) | Laying (0.333) | — |
| p13 | right-wrist | 9 | Walking | constant | Downstairs (1.0) | Downstairs (0.125) | Downstairs (0.1429) | — |
| p14 | right-wrist | 9 | Downstairs | varying | Standing (0.5) | Sitting (0.5) | Sitting (1.0) | Sitting (0.6) |
| p15 | right-wrist | 9 | Downstairs | varying | Standing (0.85) | Walking (0.8) | Walking (0.6) | Walking (0.6) |

## Order control: actual feature changes

| Target | Duty | Transitions before → after | Max zero run fraction | Max one run fraction | Changed fields |
|---|---:|---|---|---|---|
| p03 | 0.3 | 1 → 4 | 0.7 → 0.3 | 0.3 → 0.2 | transition_count, max_zero_run_fraction, max_one_run_fraction |
| p04 | 0.8 | 3 → 4 | 0.1 → 0.1 | 0.7 → 0.3 | transition_count, max_one_run_fraction |
| p09 | 0.1 | 2 → 2 | 0.5 → 0.8 | 0.1 → 0.1 | max_zero_run_fraction |
| p14 | 0.2 | 1 → 3 | 0.8 → 0.4 | 0.2 → 0.1 | transition_count, max_zero_run_fraction, max_one_run_fraction |
| p15 | 0.9 | 2 → 2 | 0.1 → 0.1 | 0.6 → 0.5 | max_one_run_fraction |

## Subject and placement breakdowns

| Condition | Group | N | Accuracy | Macro-F1 | Moving/stationary |
|---|---|---:|---:|---:|---:|
| R | subject 8 | 6 | 33.3% | 0.0816 | 83.3% |
| R | subject 9 | 9 | 22.2% | 0.0929 | 77.8% |
| R | placement left-ankle | 4 | 50.0% | 0.1905 | 100.0% |
| R | placement left-wrist | 2 | 50.0% | 0.1429 | 100.0% |
| R | placement right-ankle | 3 | 0.0% | 0.0000 | 66.7% |
| R | placement right-pocket | 2 | 50.0% | 0.1429 | 100.0% |
| R | placement right-wrist | 4 | 0.0% | 0.0000 | 50.0% |
| D | subject 8 | 6 | 33.3% | 0.0714 | 100.0% |
| D | subject 9 | 9 | 11.1% | 0.0408 | 66.7% |
| D | placement left-ankle | 4 | 25.0% | 0.1429 | 50.0% |
| D | placement left-wrist | 2 | 50.0% | 0.1429 | 100.0% |
| D | placement right-ankle | 3 | 0.0% | 0.0000 | 100.0% |
| D | placement right-pocket | 2 | 50.0% | 0.1429 | 100.0% |
| D | placement right-wrist | 4 | 0.0% | 0.0000 | 75.0% |
| T | subject 8 | 6 | 33.3% | 0.0816 | 100.0% |
| T | subject 9 | 9 | 22.2% | 0.1310 | 77.8% |
| T | placement left-ankle | 4 | 50.0% | 0.2381 | 75.0% |
| T | placement left-wrist | 2 | 50.0% | 0.1429 | 100.0% |
| T | placement right-ankle | 3 | 0.0% | 0.0000 | 100.0% |
| T | placement right-pocket | 2 | 50.0% | 0.1429 | 100.0% |
| T | placement right-wrist | 4 | 0.0% | 0.0000 | 75.0% |
| T-order | subject 8 | 1 | 0.0% | 0.0000 | 100.0% |
| T-order | subject 9 | 4 | 25.0% | 0.0952 | 50.0% |
| T-order | placement left-ankle | 2 | 50.0% | 0.0952 | 50.0% |
| T-order | placement right-ankle | 1 | 0.0% | 0.0000 | 100.0% |
| T-order | placement right-wrist | 2 | 0.0% | 0.0000 | 50.0% |

## Confidence and uncertainty

| Condition | Confidence correct | Confidence incorrect | Errors at confidence ≥0.8 | Insufficient / valid |
|---|---:|---:|---:|---:|
| R | 0.863 | 0.845 | 8 | 6 / 15 |
| D | 0.319 | 0.369 | 1 | 15 / 15 |
| T | 0.498 | 0.396 | 1 | 14 / 15 |
| T-order | 0.600 | 0.650 | 1 | 5 / 5 |

Raw-input mean confidence was 0.850 despite 26.7% accuracy; D reduced it to 0.359 and T to 0.423. High-confidence errors fell from 8 under R to 1 under D and T. R declared 9/15 targets sufficient, D 0/15, and T 1/15. This is improved acknowledgment of uncertainty in this sample, not demonstrated probability calibration.

Confidence is a self-report for the exact class, not a calibrated probability established by this screen. Reliability bins are saved in the evaluation JSON. Sufficiency is not counted as correctness. Explanations were deliberately omitted from the reliable contract, so unsupported-explanation rates and claims about Qwen’s reasoning cannot be measured in this experiment.

## Interpretation and research decision

The summary below must be interpreted as a small paired development screen, not a population estimate. Constant controls span Laying, Standing, Jogging, Upstairs, Downstairs and Walking; varying targets cover Standing at the ankles and Downstairs at the right wrist. Sitting is absent from target labels. Support over all 15 targets is Downstairs=3, Jogging=2, Laying=2, Sitting=0, Standing=6, Upstairs=1, Walking=1. Multiple intervals share a person and recording. Do not use independent-window confidence intervals or treat five placements as five independent people.

Structured features versus raw: D−R changed accuracy by -6.7 percentage points; T−R by +0.0. Temporal summaries beyond duty: T−D changed accuracy by +6.7 points. The paired table shows whether these aggregate differences reflect actual corrections or changed guesses.

Order disruption changed 1/5 predictions, with an accuracy difference of +0.0 points on the same five targets. All five T payloads changed, as shown in the feature-change table; the comparison tests sensitivity to run summaries rather than proving understanding of chronology.

The single T-over-D correction is p03 (left-ankle Standing), already correct under R. The four T-versus-R class changes are all wrong-to-wrong. The moving/stationary gain is p09: R predicted Upstairs, whereas T predicted Sitting for true Standing. The T-order change is that same p09 from Sitting to Laying, both wrong exact postures. All five control feature objects actually differ; this is not an identical-prompt contrast. However, one sample per condition cannot separate systematic feature sensitivity from sampling variability.

The fixed nearest-duty baseline equals R/T accuracy (4/15), while nearest-temporal achieves 5/15 with higher macro-F1 than Qwen. Neither establishes robust generalization: selection is tiny and concentrated. Qwen has not demonstrated an advantage over these simple permitted-reference comparisons.

Features are deterministic computations on already exposed binary observations; improvement is computational assistance, not discovery of new leakage. All durations are matched, so acquisition length cannot explain between-condition differences here. Selection of constant/varying cases and reference enrichment limits representativeness. The model sees reference labels but not evaluation labels; correctness alone does not establish a unique observable activity signature.

Recommendation: do not progress to autonomous feature-search claims on this panel. First establish cross-user, duration-controlled distinguishability in a better documented legitimate interface or additional independently collected sessions, retaining ambiguous controls. An agent cannot recover activity information that the interface does not distinguish. Even positive feature assistance would justify a narrowly preregistered replication on a richer interface, not automatic expansion or fine-tuning. A stronger follow-up needs varying examples across more activities and independent people, chronology/marginal controls, and a newly held-out split. No further calls are launched by this report.

## Reproducibility and preservation

Preservation checks confirm 131 existing data/run/report artifacts unchanged; all sources read for this experiment match their frozen hashes. Code: `../representation_experiment.py`, `../representation_report.py`, and existing `../inference_protocol_v2.py`. Inputs/manifests: `../data/representation-screen/`; raw API responses, technical gate results and complete evaluation: `../runs/representation-screen/`. These data/run directories remain ignored by Git, consistent with the repository; credentials are neither exported nor logged.

Install `requirements-representation.txt`. Reproduction uses `representation_experiment.py metadata` (read-only endpoint metadata), then `prepare`, `gate`, and `research` only after a passed gate; existing manifests/runs refuse silent overwrites. `representation_report.py baselines` freezes baselines before research; `representation_report.py report` performs offline scoring. Re-running inference incurs fresh costs and is not part of this task.

## Confusion matrices

Rows: Downstairs, Jogging, Laying, Sitting, Standing, Upstairs, Walking. Columns: same order plus INVALID_OR_MISSING.

### R

```json
[[1, 0, 0, 0, 2, 0, 0, 0], [2, 0, 0, 0, 0, 0, 0, 0], [0, 0, 2, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0, 0, 0], [0, 0, 4, 0, 1, 1, 0, 0], [1, 0, 0, 0, 0, 0, 0, 0], [1, 0, 0, 0, 0, 0, 0, 0]]
```

### D

```json
[[1, 0, 0, 1, 0, 0, 1, 0], [1, 0, 0, 0, 0, 0, 1, 0], [0, 0, 2, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0, 0, 0], [0, 0, 4, 0, 0, 0, 2, 0], [1, 0, 0, 0, 0, 0, 0, 0], [1, 0, 0, 0, 0, 0, 0, 0]]
```

### T

```json
[[1, 0, 0, 1, 0, 0, 1, 0], [2, 0, 0, 0, 0, 0, 0, 0], [0, 0, 2, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0, 0, 0], [0, 0, 3, 1, 1, 0, 1, 0], [1, 0, 0, 0, 0, 0, 0, 0], [1, 0, 0, 0, 0, 0, 0, 0]]
```

### T-order

```json
[[0, 0, 0, 1, 0, 0, 1, 0], [0, 0, 0, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0, 0, 0], [0, 0, 1, 0, 1, 0, 1, 0], [0, 0, 0, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0, 0, 0]]
```


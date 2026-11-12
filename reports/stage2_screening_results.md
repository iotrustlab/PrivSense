# PrivSense Stage 2: approved 14-target screening results

## Scope and execution

Exactly 84 API requests were executed: 14 matched targets × C000, C010, C100, C001, C111 and R0. No repeats, interaction cells or full 372-target evaluation were run. Stage 1 artifacts remain unchanged. This is a direct-inference experiment; no planner, tools or trained classifier supplies Qwen predictions.

Targets were selected from 372 legitimate 500-sample blocks in users 8–9 right-pocket recordings. Each target is the final 100 samples of a block, with the preceding 400 supplied only when T=1. Seed 42 selects one target per subject/activity pair; seed 43 freezes an interleaved condition rotation. Seven fixed training User 1 references are supplied only in A=1. All 14 target streams and histories are constant, giving only two observable bit patterns per condition. The balanced screen’s deterministic pattern bound is 4/14 = 28.57%, not the original 1,947-window score of 30.61%.

Prompts are rendered exactly from the approved design, with R0 using the original Stage 1 message function. Frozen manifests and exact requests are in `data/stage2-screen/`. Model: qwen/qwen3.5-35b-a3b; temperature 0.1; maximum output 600 tokens; reasoning disabled; JSON-object output; no provider pin or effective sampling seed assumed. Each request is stateless. Local IDs/condition names and evaluator provenance do not enter the model messages.

## Main result

**No condition increased exact-activity accuracy: each scored 4/14.** Sensor metadata and longer history did not change any predicted class relative to C000. Auxiliary examples and combined information changed which moving class was guessed, exchanging correct and incorrect cases without any net gain. This is not evidence that more information identified the hidden activity.

| Condition | Valid / 14 | Accuracy | Balanced accuracy | Macro-F1 | Moving/stationary (all targets) | Mean confidence (valid) | Insufficient (valid) |
|---|---:|---:|---:|---:|---:|---:|---:|
| C000 | 14 | 28.57% | 28.57% | 0.12857 | 100.00% | 0.614 | 100.00% |
| C010 | 14 | 28.57% | 28.57% | 0.12857 | 100.00% | 0.629 | 100.00% |
| C100 | 14 | 28.57% | 28.57% | 0.12857 | 100.00% | 0.579 | 100.00% |
| C001 | 12 | 28.57% | 28.57% | 0.15238 | 85.71% | 0.318 | 100.00% |
| C111 | 13 | 28.57% | 28.57% | 0.13492 | 92.86% | 0.569 | 100.00% |
| R0 | 14 | 28.57% | 28.57% | 0.12857 | 100.00% | 0.707 | 100.00% |

C000 = minimal; C010 = sensor/task knowledge; C100 = preceding history; C001 = references; C111 = combined; R0 = original prompt. Invalid outputs count as errors in all-target metrics. All **valid** outputs classified the motion group correctly. The reduced all-target motion-group scores in C001/C111 reflect format failures, not wrong motion-group predictions.

Macro-F1 changes must not be described as an accuracy gain. Switching the chosen class and producing invalid outputs changes precision/recall denominators. In particular, invalid predictions do not add false positives to a named activity class. Report these F1 values with accuracy, failure counts and matched valid-pair metrics rather than selecting a favorable metric.

## Exact prediction behavior and paired changes

| Condition | Predicted labels/counts | Changes versus C000 | Wrong→correct | Correct→wrong |
|---|---|---:|---:|---:|
| C000 | {"Jogging": 8, "Laying": 6} | 0 | 0 | 0 |
| C010 | {"Jogging": 8, "Laying": 6} | 0 | 0 | 0 |
| C100 | {"Jogging": 8, "Laying": 6} | 0 | 0 | 0 |
| C001 | {"Downstairs": 8, "INVALID": 2, "Laying": 4} | 10 | 2 | 2 |
| C111 | {"Walking": 7, "Laying": 6, "INVALID": 1} | 8 | 2 | 2 |
| R0 | {"Jogging": 8, "Laying": 6} | 0 | 0 | 0 |

C000/C010/C100/R0 choose Jogging for eight all-one targets and Laying for six all-zero targets. C001 chooses Downstairs for the same eight all-one targets; C111 chooses Walking for seven of eight, with the eighth response invalid. C001 also has two invalid all-zero responses. The correct-class exchanges are predictable tie-breaking among observationally identical activities. The first matching moving reference is Downstairs, consistent with the explicit first-match choice in some C001 explanations. C111 frequently invokes an unsupported Walking prevalence assumption.

The 10 C001 and eight C111 changed outputs include invalid-response transitions; they are not all valid class changes. No complete condition produced inconsistent valid class predictions within an identical-input group: each maps zeros to Laying and ones to a single chosen moving class. Each condition’s empirical pattern bound is 28.57%.

## Baselines on exactly these 14 targets

| Baseline | Accuracy | Macro-F1 | Moving/stationary |
|---|---:|---:|---:|
| training_majority | 14.29% | 0.03571 | 42.86% |
| fixed_rule | 28.57% | 0.12857 | 100.00% |
| reference_rule | 28.57% | 0.12857 | 100.00% |
| uniform_guess (analytic) | 14.29% | 0.14286* | 51.02% |
| training_prior_guess (analytic) | 14.29% | 0.14249* | 50.65% |

*Guessing F1 is computed from expected confusion, not the expectation of finite-sample F1. Training priors come from the existing users 1–7 training labels, available only to the evaluator. Fixed rule: mostly ones→Walking, otherwise Sitting. Reference rule: first exact matching authorized reference, with a predefined majority fallback. The empirical pattern bound uses hidden labels for diagnosis and is not an attacker baseline.

## Valid-response sensitivity and group summaries

| Contrast (same valid targets) | N | C000 accuracy | Condition accuracy | Condition moving/stationary |
|---|---:|---:|---:|---:|
| C010-C000 | 14 | 28.57% | 28.57% | 100.00% |
| C100-C000 | 14 | 28.57% | 28.57% | 100.00% |
| C001-C000 | 12 | 33.33% | 33.33% | 100.00% |
| C111-C000 | 13 | 30.77% | 30.77% | 100.00% |
| R0-C000 | 14 | 28.57% | 28.57% | 100.00% |

This sensitivity analysis excludes invalid cases identically from both sides. It does not replace all-target metrics or prove a benefit on a selected surviving subset.

| Condition | User 8 accuracy | User 9 accuracy | Equal-recording accuracy |
|---|---:|---:|---:|
| C000 | 28.57% | 28.57% | 28.57% |
| C010 | 28.57% | 28.57% | 28.57% |
| C100 | 28.57% | 28.57% | 28.57% |
| C001 | 28.57% | 28.57% | 28.57% |
| C111 | 28.57% | 28.57% | 28.57% |
| R0 | 28.57% | 28.57% | 28.57% |

Each screen has one target per subject/class and 14 distinct source files. Equal-recording aggregation therefore provides no extra independent observations. The two subjects are insufficient for population-level significance claims. The repeated identical prompt inputs are not independent physiological evidence.

## Confidence and uncertainty

All 81 valid responses set sufficient_information=false. C000 confidence averages 0.614 versus 0.707 for R0 on the same target bits: prompt framing alone changes self-reported confidence without changing a single prediction. Sensor metadata raises confidence to 0.629; redundant history lowers it to 0.579. References lower it to 0.318 among valid responses; combined information yields 0.569. These are descriptive single-run differences, not calibrated probabilities or established causal effects of individual sentences.

| Condition | Confidence when correct | Confidence when wrong | High-confidence wrong (≥0.8) | True label in alternatives (valid) |
|---|---:|---:|---:|---:|
| C000 | 0.613 | 0.615 | 0 | 71.43% |
| C010 | 0.600 | 0.640 | 0 | 71.43% |
| C100 | 0.588 | 0.575 | 0 | 64.29% |
| C001 | 0.412 | 0.270 | 0 | 66.67% |
| C111 | 0.525 | 0.589 | 2 | 69.23% |
| R0 | 0.700 | 0.710 | 2 | 71.43% |

Alternative coverage excludes the predicted label by schema; a low value is not necessarily bad when the prediction is correct. Uncertainty acknowledgment receives no accuracy credit. Confidence comparisons involving C001/C111 use different valid-response counts, so missingness is a caveat.

## Explanation review

All 84 outputs were inspected; 81 had valid explanations. The saved review sheet omits true labels, subjects, recordings and correctness, while condition and predicted activity remain visible. Annotation was a **single qualitative review by the implementation assistant**, not an independent human-validated assessment. No additional LLM judge/API was used. Rates below are provisional rubric assessments; a human blinded audit is needed before publication.

The rubric flags unsupported physical dynamics/uniqueness, inferred stillness or unprovided duration, incorrect counts/durations, false reference distinctions and asserted population priors without supplied evidence. Qualified forced-choice guesses and explicitly arbitrary reference tie-breaking are not automatically flagged. Two C001 explanations explicitly self-correct earlier speculation and conclude that the label is arbitrary; they are not counted as unretracted unsupported claims.

| Condition | Flagged explanations / valid | Rate |
|---|---:|---:|
| C000 | 14/14 | 100.00% |
| C010 | 14/14 | 100.00% |
| C100 | 14/14 | 100.00% |
| C001 | 2/12 | 16.67% |
| C111 | 13/13 | 100.00% |
| R0 | 14/14 | 100.00% |

Concrete failure examples:

- `target-0050-C000` counts 80 samples although the target contains 100.
- `target-0077-C010` states a 1.28-second window despite the supplied 100 samples at 50 Hz.
- `target-0294-C111` states 80 samples / 1.6 seconds and asserts only Laying matches the zero references, while Sitting and Standing have identical zero examples.
- Several all-one C000/C010/C100/R0 responses claim high-frequency, high-intensity or rhythmic motion that the constant output does not measure.
- C111 all-one explanations choose Walking because it is supposedly most common; no prevalence data was supplied.
- C001 moving-target explanations generally acknowledge that Downstairs/Jogging/Upstairs/Walking are indistinguishable and describe their choice as arbitrary or first in the reference list.

Auxiliary examples improved ambiguity descriptions in many valid responses but also caused long self-correcting explanations, format failures and occasional misreading of the references. Sensor metadata did not reliably eliminate unsupported physical interpretations. The combined condition did not preserve the auxiliary-only explanation benefit. With missing interaction cells and one repeat, do not infer which component caused that behavior.

## Invalid responses and cost

Three requests returned invalid responses: two exceeded the fixed 600-token output budget (`target-0008-C111`, `target-0262-C001`), and one used the key `" explanation"` instead of `"explanation"` (`target-0294-C001`). The last is syntactically valid JSON but fails the frozen schema. Raw responses remain saved. They were not repaired, retried, or given a larger budget after inspecting results. No HTTP errors occurred.

| Condition | Reported tokens | Reported USD |
|---|---:|---:|
| C000 | 11368 | $0.003605 |
| C010 | 13695 | $0.004149 |
| C100 | 28524 | $0.006144 |
| C001 | 43390 | $0.008279 |
| C111 | 62413 | $0.010773 |
| R0 | 10358 | $0.003301 |

Total: **169,748 tokens; $0.036251 reported API cost** for exactly 84 requests. Invalid-output requests are included. Added examples/history increase token consumption without increasing exact accuracy here.

## Confusion matrices

Columns are Downstairs, Jogging, Laying, Sitting, Standing, Upstairs, Walking, INVALID_OR_MISSING. Rows follow the seven true labels.

### C000
```json
[[0, 2, 0, 0, 0, 0, 0, 0], [0, 2, 0, 0, 0, 0, 0, 0], [0, 0, 2, 0, 0, 0, 0, 0], [0, 0, 2, 0, 0, 0, 0, 0], [0, 0, 2, 0, 0, 0, 0, 0], [0, 2, 0, 0, 0, 0, 0, 0], [0, 2, 0, 0, 0, 0, 0, 0]]
```

### C010
```json
[[0, 2, 0, 0, 0, 0, 0, 0], [0, 2, 0, 0, 0, 0, 0, 0], [0, 0, 2, 0, 0, 0, 0, 0], [0, 0, 2, 0, 0, 0, 0, 0], [0, 0, 2, 0, 0, 0, 0, 0], [0, 2, 0, 0, 0, 0, 0, 0], [0, 2, 0, 0, 0, 0, 0, 0]]
```

### C100
```json
[[0, 2, 0, 0, 0, 0, 0, 0], [0, 2, 0, 0, 0, 0, 0, 0], [0, 0, 2, 0, 0, 0, 0, 0], [0, 0, 2, 0, 0, 0, 0, 0], [0, 0, 2, 0, 0, 0, 0, 0], [0, 2, 0, 0, 0, 0, 0, 0], [0, 2, 0, 0, 0, 0, 0, 0]]
```

### C001
```json
[[2, 0, 0, 0, 0, 0, 0, 0], [2, 0, 0, 0, 0, 0, 0, 0], [0, 0, 2, 0, 0, 0, 0, 0], [0, 0, 1, 0, 0, 0, 0, 1], [0, 0, 1, 0, 0, 0, 0, 1], [2, 0, 0, 0, 0, 0, 0, 0], [2, 0, 0, 0, 0, 0, 0, 0]]
```

### C111
```json
[[0, 0, 0, 0, 0, 0, 1, 1], [0, 0, 0, 0, 0, 0, 2, 0], [0, 0, 2, 0, 0, 0, 0, 0], [0, 0, 2, 0, 0, 0, 0, 0], [0, 0, 2, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0, 2, 0], [0, 0, 0, 0, 0, 0, 2, 0]]
```

### R0
```json
[[0, 2, 0, 0, 0, 0, 0, 0], [0, 2, 0, 0, 0, 0, 0, 0], [0, 0, 2, 0, 0, 0, 0, 0], [0, 0, 2, 0, 0, 0, 0, 0], [0, 0, 2, 0, 0, 0, 0, 0], [0, 2, 0, 0, 0, 0, 0, 0], [0, 2, 0, 0, 0, 0, 0, 0]]
```

## What the screen establishes—and what it does not

It establishes that, for these fixed constant binary observations and this one run, knowledge changes confidence, explanation quality and class tie-breaking more than exact recognition. Authentic longer context contains no added variation and did not change labels. All conditions match the balanced-set pattern bound in all-target accuracy, including three invalid outputs that happened not to remove a correct answer. This does not establish better activity discrimination, a general failure of temporal inference, an information-theoretic impossibility for other interfaces, or a robust ranking of prompts.

No full 372-target evaluation, interaction expansion or repeated-run selection was performed. The next priority is to define independently validated information-bearing interfaces alongside this information-limited control, not to spend more calls on constant repetitions. See `binary_interface_benchmark_design.md` for the read-only survey and predefined selection protocol.

## Reproduction and artifacts

```bash
source .venv/bin/activate
# Already prepared/executed in this workspace; use new paths only for a separately authorized repeat.
python stage2_screen.py prepare --data data/stage2-screen-new
python stage2_screen.py infer --data data/stage2-screen-new --run runs/stage2-screen-new
python stage2_screen.py evaluate --data data/stage2-screen-new --run runs/stage2-screen-new
python stage2_report.py
```

Frozen inputs: `data/stage2-screen/manifest.json`, `requests.jsonl`, `truth.jsonl`, selected observations and reference provenance. Outputs: `runs/stage2-screen/responses.jsonl`, `evaluation.json`, `explanation_review.jsonl`. Exact prompts and metadata differences are logged for every request. `--resume` skips all completed responses, including invalid ones; it does not expand the experiment or retry until success. The report renderer reads the default completed run. Data/run directories and credentials remain ignored by Git.

# Full-recording direct privacy inference: C1–C5 results

## Scope and technical verification

Executed 70 requests on the frozen 14 right-pocket recordings from development users 8–9. Seven labeled references come from training users 1–7, using the selections in full_recording_prompt_audit.md. These participants are absent from the reference set but are repeatedly inspected development users, not an untouched final test. No fine-tuning, external classifier-generated Qwen prediction, tool use, feedback, reference selection by performance, or evaluation expansion occurred.

Each request has one fixed system message and one user message. The full original proposed bit-string payloads were reused unchanged. Every serialized character was decoded and compared with the corresponding CSV binary sample in order. Targets contain only observation_extent and binary_sequence; references additionally contain their authorized activity label. Filenames, subject IDs, target labels and offsets are absent. Full files include every sample, with no padding, resampling, truncation, cross-file joins or run-length encoding. Extents are explicitly marked complete recordings or excerpts. Exact saved messages are in data/full-recording-screen/requests.jsonl and copied into response logs.

Provider was restricted to the exact deepinfra/fp8 endpoint, with allow_fallbacks=false and require_parameters=true. This follows the documented [OpenRouter routing controls](https://openrouter.ai/docs/guides/routing/provider-selection). Fresh endpoint metadata advertised 262,144 context tokens and the required parameters. All cells used qwen/qwen3.5-35b-a3b, temperature 0.1, max_tokens 600, reasoning disabled and JSON-object output with the existing strict local five-field validator. No sampling seed is assumed. Submission order used seed 47 and a counterbalanced rotation; the first planned C4 request was moved to the beginning as the feasibility gate. Remaining calls used two concurrent workers and a 180-second timeout, with no retries.

The largest local content count was 92,325 tokens; including a 1,024-token framing reserve and 600 output tokens gives 93,949, below the advertised context. First C4 request `target-0148-C4` returned valid from DeepInfra, with 79,164 input tokens and 177 output tokens. It is included in the 70, not an extra probe.

Returned providers: {'DeepInfra': 70}. Reported input counts minus locally tokenized content counts: [17]. This agreement and the saved source-verified payloads support complete submission; provider-internal processing and attention cannot be directly inspected. A valid response does not prove that Qwen examined every bit.

## Matched conditions

| Cell | Target | Same seven reference recordings |
|---|---|---|
| C1 | Saved E2 100-sample excerpt | First 100 samples each |
| C2 | Same 100-sample excerpt | Complete files |
| C3 | Complete file | First 100 samples each |
| C4 | Complete file | Complete files |
| C5 | First 500 samples, marked excerpt | Complete files |

Every cell predicts the dataset-assigned activity of the same recording. Short excerpts do not use hidden internal activity boundaries. All evaluation files are constant, so C5’s different excerpt position does not change bit content. Full references total 76,770 samples; only the selected Standing reference varies, with transitions at samples 6500, 6550, 10450 and 10500. That reference has 100 positive samples in 14,995, embedded in two short bursts. Its first 100 samples are zero. Reference participant and class are confounded in this small one-reference-per-class panel.

## Results

| Cell | Valid / 14 | Accuracy | Balanced accuracy | Macro-F1 | Motion-group accuracy | Mean confidence | Insufficient information |
|---|---:|---:|---:|---:|---:|---:|---:|
| C1 | 9/14 | 14.29% | 14.29% | 0.05714 | 64.29% | 0.214 | 100.00% |
| C2 | 9/14 | 14.29% | 14.29% | 0.09286 | 64.29% | 0.694 | 100.00% |
| C3 | 10/14 | 21.43% | 21.43% | 0.12857 | 71.43% | 0.293 | 100.00% |
| C4 | 10/14 | 21.43% | 21.43% | 0.12857 | 71.43% | 0.905 | 100.00% |
| C5 | 6/14 | 14.29% | 14.29% | 0.09524 | 42.86% | 0.750 | 100.00% |

Invalid/missing predictions count as errors in all-target scores. Confidence and uncertainty summaries use valid outputs only. Macro-F1 is computed across all seven labels.

| Paired contrast | Accuracy difference (pp) | Changed outputs | Wrong→correct | Correct→wrong | Valid pairs |
|---|---:|---:|---:|---:|---:|
| C2-C1 | +0.00 | 4 | 1 | 1 | 7 |
| C4-C3 | +0.00 | 8 | 2 | 2 | 10 |
| C3-C1 | +7.14 | 1 | 1 | 0 | 9 |
| C4-C2 | +7.14 | 11 | 3 | 2 | 7 |
| C4-C5 | +7.14 | 8 | 3 | 2 | 6 |
| C5-C2 | +0.00 | 9 | 1 | 1 | 4 |

Matched valid-pair accuracy differences: C2-C1: +0.00 pp (n=7); C4-C3: +0.00 pp (n=10); C3-C1: +0.00 pp (n=9); C4-C2: +0.00 pp (n=7); C4-C5: -16.67 pp (n=6); C5-C2: +0.00 pp (n=4).

C2−C1 and C4−C3 assess reference extent at fixed target access. C3−C1 and C4−C2 assess target extent at fixed references. C4−C5 compares natural-length targets with fixed 500-sample targets at full reference access. C5−C2 changes only the amount of redundant constant target samples, extent wording stays excerpt. No contrast alone identifies the effect of temporal order.

## Duration baselines and input ambiguity

Primary baselines receive exactly the seven reference observations and target extent exposed in each cell. Duration-only chooses the reference closest in sample count; binary-plus-duration first restricts to matching majority bit, then chooses closest count. Ties use the fixed candidate-class order. The fixed bit rule selects Walking for mostly ones and Sitting otherwise. These are deterministic offline comparators, not sources of Qwen predictions. Baselines were frozen before inference; none use evaluation-label fitting.

| Cell | Duration-only | Binary + duration | Fixed bit | Unique full prompts | Empirical pattern bound |
|---|---:|---:|---:|---:|---:|
| C1 | 14.29% | 28.57% | 28.57% | 2 | 28.57% |
| C2 | 14.29% | 28.57% | 28.57% | 2 | 28.57% |
| C3 | 14.29% | 28.57% | 28.57% | 11 | 92.86% |
| C4 | 21.43% | 35.71% | 28.57% | 11 | 92.86% |
| C5 | 14.29% | 28.57% | 28.57% | 2 | 28.57% |

Full-training diagnostic baselines additionally use all 147 training files (greater reference access than Qwen), selecting nearest sample count and lexicographic source-path tie-break. They are descriptive comparisons, not access-matched primary baselines:
- duration_only: 28.57% accuracy, 0.21020 macro-F1.
- binary_plus_duration: 57.14% accuracy, 0.52857 macro-F1.

For complete evaluation files, the full binary sequence is determined exactly by its bit value and sample count. Thus all added target distinctions are length distinctions; there are no target transition patterns to exploit. Stair files are much shorter than approximately five-minute non-stair files, and tiny export-length differences can act as acquisition fingerprints. The 13/14 natural-length empirical bound uses hidden evaluator labels and mostly rare length signatures; it is not a deployable attacker score or evidence of generalization. Fixed-length C1/C2/C5 have only two observable input groups and a 4/14 deterministic mapping bound. Stochastic guesses may exceed that bound in one realization without acquiring distinguishing information.

## Confidence and explanations

| Cell | Confidence correct | Confidence wrong | Wrong confidence ≥0.8 | Flagged / reviewed valid explanations |
|---|---:|---:|---:|---:|
| C1 | 0.200 | 0.219 | 0 | 4/9 |
| C2 | 0.750 | 0.679 | 2 | 9/9 |
| C3 | 0.243 | 0.314 | 1 | 3/10 |
| C4 | 0.950 | 0.886 | 6 | 10/10 |
| C5 | 0.750 | 0.750 | 2 | 6/6 |

Review is a provisional qualitative assessment by the implementation assistant, not an independent human-validated annotation. The review sheet excludes hidden labels/correctness, but the reviewer has seen aggregate results; it is not fully blind. No additional judge API was called. Claims of rhythm/intensity from constant outputs, invented counts, false differences between references, and conflating length with physical dynamics are flagged. Merely making an explicitly uncertain forced choice is not automatically flagged. Human review and agreement are required before publication.

## Individual predictions

| Target | Subject | True activity | Samples | C1 | C2 | C3 | C4 | C5 |
|---|---:|---|---:|---|---|---|---|---|
| target-0213 | 9 | Jogging | 14992 | Walking | Walking | Walking | Downstairs | Downstairs |
| target-0180 | 8 | Walking | 14995 | Walking | Walking | Walking | Downstairs | Walking |
| target-0262 | 9 | Sitting | 14995 | INVALID | Laying | INVALID | INVALID | INVALID |
| target-0050 | 8 | Laying | 14992 | INVALID | Laying | INVALID | INVALID | INVALID |
| target-0148 | 8 | Upstairs | 1820 | Walking | Walking | Walking | Downstairs | Walking |
| target-0253 | 9 | Laying | 14992 | INVALID | INVALID | Laying | Laying | INVALID |
| target-0345 | 9 | Walking | 14995 | Walking | INVALID | Walking | Downstairs | Walking |
| target-0077 | 8 | Sitting | 14989 | INVALID | INVALID | INVALID | INVALID | INVALID |
| target-0008 | 8 | Downstairs | 1755 | Walking | INVALID | Walking | Downstairs | Walking |
| target-0321 | 9 | Upstairs | 2300 | Walking | Walking | Walking | Downstairs | Downstairs |
| target-0046 | 8 | Jogging | 14998 | Walking | Walking | Walking | Downstairs | INVALID |
| target-0294 | 9 | Standing | 14989 | Laying | Laying | Laying | Laying | INVALID |
| target-0131 | 8 | Standing | 14998 | INVALID | INVALID | INVALID | INVALID | INVALID |
| target-0191 | 9 | Downstairs | 2166 | Walking | Walking | Walking | Downstairs | INVALID |

Ground truth in this evaluator table was never included in target prompts. The complete provenance, including source hashes and excerpt offsets, is in the frozen manifest.

## Confusion matrices and subject results

Rows: Downstairs, Jogging, Laying, Sitting, Standing, Upstairs, Walking. Columns: same order plus INVALID_OR_MISSING.

### C1

```json
{"matrix": [[0, 0, 0, 0, 0, 0, 2, 0], [0, 0, 0, 0, 0, 0, 2, 0], [0, 0, 0, 0, 0, 0, 0, 2], [0, 0, 0, 0, 0, 0, 0, 2], [0, 0, 1, 0, 0, 0, 0, 1], [0, 0, 0, 0, 0, 0, 2, 0], [0, 0, 0, 0, 0, 0, 2, 0]], "per_class_recall": {"Downstairs": 0.0, "Jogging": 0.0, "Laying": 0.0, "Sitting": 0.0, "Standing": 0.0, "Upstairs": 0.0, "Walking": 1.0}, "subject_accuracy": {"8": 0.14285714285714285, "9": 0.14285714285714285}}
```

### C2

```json
{"matrix": [[0, 0, 0, 0, 0, 0, 1, 1], [0, 0, 0, 0, 0, 0, 2, 0], [0, 0, 1, 0, 0, 0, 0, 1], [0, 0, 1, 0, 0, 0, 0, 1], [0, 0, 1, 0, 0, 0, 0, 1], [0, 0, 0, 0, 0, 0, 2, 0], [0, 0, 0, 0, 0, 0, 1, 1]], "per_class_recall": {"Downstairs": 0.0, "Jogging": 0.0, "Laying": 0.5, "Sitting": 0.0, "Standing": 0.0, "Upstairs": 0.0, "Walking": 0.5}, "subject_accuracy": {"8": 0.2857142857142857, "9": 0.0}}
```

### C3

```json
{"matrix": [[0, 0, 0, 0, 0, 0, 2, 0], [0, 0, 0, 0, 0, 0, 2, 0], [0, 0, 1, 0, 0, 0, 0, 1], [0, 0, 0, 0, 0, 0, 0, 2], [0, 0, 1, 0, 0, 0, 0, 1], [0, 0, 0, 0, 0, 0, 2, 0], [0, 0, 0, 0, 0, 0, 2, 0]], "per_class_recall": {"Downstairs": 0.0, "Jogging": 0.0, "Laying": 0.5, "Sitting": 0.0, "Standing": 0.0, "Upstairs": 0.0, "Walking": 1.0}, "subject_accuracy": {"8": 0.14285714285714285, "9": 0.2857142857142857}}
```

### C4

```json
{"matrix": [[2, 0, 0, 0, 0, 0, 0, 0], [2, 0, 0, 0, 0, 0, 0, 0], [0, 0, 1, 0, 0, 0, 0, 1], [0, 0, 0, 0, 0, 0, 0, 2], [0, 0, 1, 0, 0, 0, 0, 1], [2, 0, 0, 0, 0, 0, 0, 0], [2, 0, 0, 0, 0, 0, 0, 0]], "per_class_recall": {"Downstairs": 1.0, "Jogging": 0.0, "Laying": 0.5, "Sitting": 0.0, "Standing": 0.0, "Upstairs": 0.0, "Walking": 0.0}, "subject_accuracy": {"8": 0.14285714285714285, "9": 0.2857142857142857}}
```

### C5

```json
{"matrix": [[0, 0, 0, 0, 0, 0, 1, 1], [1, 0, 0, 0, 0, 0, 0, 1], [0, 0, 0, 0, 0, 0, 0, 2], [0, 0, 0, 0, 0, 0, 0, 2], [0, 0, 0, 0, 0, 0, 0, 2], [1, 0, 0, 0, 0, 0, 1, 0], [0, 0, 0, 0, 0, 0, 2, 0]], "per_class_recall": {"Downstairs": 0.0, "Jogging": 0.0, "Laying": 0.0, "Sitting": 0.0, "Standing": 0.0, "Upstairs": 0.0, "Walking": 1.0}, "subject_accuracy": {"8": 0.14285714285714285, "9": 0.14285714285714285}}
```

## Cost, failures and runtime

| Cell | Input tokens | Output tokens | Reported USD | Cost / valid |
|---|---:|---:|---:|---:|
| C1 | 19,348 | 2,500 | $0.005209 | $0.000579 |
| C2 | 1,084,230 | 3,068 | $0.154860 | $0.017207 |
| C3 | 175,910 | 2,728 | $0.027355 | $0.002736 |
| C4 | 1,240,792 | 3,030 | $0.176741 | $0.017674 |
| C5 | 1,089,830 | 3,014 | $0.155590 | $0.025932 |

Total reported cost $0.519755; wall runtime 84.5 seconds. Calls: 70. Returned finish reasons: {'stop': 70}. No retries or discarded attempts.
- target-0262-C5: invalid_response, finish=stop, error=Strict JSON/schema failure
- target-0253-C1: invalid_response, finish=stop, error=Strict JSON/schema failure
- target-0077-C5: invalid_response, finish=stop, error=Strict JSON/schema failure
- target-0008-C2: invalid_response, finish=stop, error=Strict JSON/schema failure
- target-0131-C5: invalid_response, finish=stop, error=Strict JSON/schema failure
- target-0050-C4: invalid_response, finish=stop, error=Strict JSON/schema failure
- target-0077-C2: invalid_response, finish=stop, error=Strict JSON/schema failure
- target-0294-C5: invalid_response, finish=stop, error=Strict JSON/schema failure
- target-0131-C2: invalid_response, finish=stop, error=Strict JSON/schema failure
- target-0262-C4: invalid_response, finish=stop, error=Strict JSON/schema failure
- target-0050-C1: invalid_response, finish=stop, error=Strict JSON/schema failure
- target-0253-C5: invalid_response, finish=stop, error=Strict JSON/schema failure
- target-0345-C2: invalid_response, finish=stop, error=Strict JSON/schema failure
- target-0077-C4: invalid_response, finish=stop, error=Strict JSON/schema failure
- target-0046-C5: invalid_response, finish=stop, error=Strict JSON/schema failure
- target-0131-C4: invalid_response, finish=stop, error=Strict JSON/schema failure
- target-0262-C1: invalid_response, finish=stop, error=Strict JSON/schema failure
- target-0050-C3: invalid_response, finish=stop, error=Strict JSON/schema failure
- target-0253-C2: invalid_response, finish=stop, error=Strict JSON/schema failure
- target-0077-C1: invalid_response, finish=stop, error=Strict JSON/schema failure
- target-0131-C1: invalid_response, finish=stop, error=Strict JSON/schema failure
- target-0262-C3: invalid_response, finish=stop, error=Strict JSON/schema failure
- target-0050-C5: invalid_response, finish=stop, error=Strict JSON/schema failure
- target-0077-C3: invalid_response, finish=stop, error=Strict JSON/schema failure
- target-0131-C3: invalid_response, finish=stop, error=Strict JSON/schema failure
- target-0191-C5: invalid_response, finish=stop, error=Strict JSON/schema failure

## Interpretation and next experiment

### 1. Does Qwen perform better with full training recordings?

**No improvement was observed.** C2−C1 is 0 percentage points (2/14 versus 2/14), and C4−C3 is also 0 (3/14 versus 3/14). Both contrasts remain zero on matched valid-response subsets. C4 switches every valid moving prediction from Walking to Downstairs; two formerly incorrect answers become correct and two formerly correct answers become incorrect. This is changed tie-breaking, not improved recognition.

Full references substantially increase reported confidence: C1→C2 rises from 0.214 to 0.694, and C3→C4 from 0.293 to 0.905 among valid responses. These are descriptive single-run differences with condition-dependent missingness, not calibrated certainty. All valid outputs still set sufficient_information=false. C4 has six incorrect exact-class predictions at confidence ≥0.8 despite acknowledging ambiguity. Some explanations appear to interpret confidence as distinguishing movement from stillness rather than distinguishing the requested exact activity.

### 2. Does Qwen perform better with full target recordings?

**The strict all-target score rises by one answer, but there is no demonstrated recognition gain.** C3−C1 and C4−C2 each rise by 1/14 = 7.14 percentage points. On the exact subsets where both responses are schema-valid, each contrast is zero. In C3 versus C1 the only changed scored output is a previously invalid Laying response becoming a valid correct Laying response. The raw invalid C1 output already chose Laying, so this is a format-validity difference rather than a new activity distinction. It remains invalid in the primary scoring; no response was repaired.

For C4 versus C2 there are additional Walking→Downstairs exchanges and differences in which outputs pass validation; the matched valid subset has no net accuracy gain. Do not interpret the 21.43% versus 14.29% headline as evidence that complete targets enabled activity recognition. Valid-only scores of 22.22%, 22.22%, 30%, 30% and 33.33% across C1–C5 are on different surviving subsets and are not an alternative condition ranking.

### 3. Is any improvement explained by recording length?

**We did not establish a substantive improvement to attribute to length. Length remains a real source of available information and confounding.** All full evaluation targets are constant; a full target is exactly representable by its bit and sample count. No new target dynamics are present. C4−C5 rises by 1/14 in the strict score, but reverses to −1/6 on their six matched valid pairs. That is not robust evidence of a beneficial duration effect.

The same-reference C4 duration-only baseline scores 3/14; binary-plus-duration scores 5/14, versus Qwen's 3/14. With the larger 147-file training pool, length-only scores 4/14 and binary-plus-length scores 8/14. The latter has more auxiliary access and is not a fair direct performance ranking against seven-reference Qwen, but it demonstrates dataset-specific information available through acquisition lengths. These baselines are training-only nearest-reference rules, not label-aware empirical bounds.

Qwen does not visibly use fine duration distinctions consistently: all eight valid C4 moving targets receive Downstairs, including short stair segments and approximately five-minute walking/jogging files. One C5 explanation claims its length perfectly matches Downstairs even though the excerpt has 500 samples and the reference 512. No output establishes accurate length measurement. Explanations do not reveal internal causality, so we cannot prove that length had no influence; we can say the scores and output behavior do not demonstrate reliable exploitation of it.

### 4. Does the experiment demonstrate genuine exploitation of temporal binary patterns?

**No. There is limited evidence of noticing variation in a training reference, without evidence of useful temporal-pattern inference.** The selected full Standing reference has two positive bursts, each 50 samples long, and four transitions. It is not all zeros. Among schema-valid outputs, two C2 explanations mention intermittent positive samples in that reference. None of the ten valid C4 explanations or six valid C5 explanations acknowledges that variation; all incorrectly describe Standing as continuous zeros.

Inspection of malformed outputs, strictly outside the scored predictions, adds three C2, two C4 and two C5 mentions of Standing variation. These mentions are usually nonspecific or describe one middle segment rather than correctly identifying two bursts. The raw text remains preserved and is not repaired into accepted answers. No response establishes accurate event locations/counts or cross-user generalization of a transition signature.

Even the valid C2 explanations that notice the bursts overreach: a two-second zero excerpt from another participant does not become incompatible with Standing merely because a five-minute training reference contains two brief shake events. Some answers also invent a unique Laying/stillness association despite the ambiguous references. A valid C4 explanation attributes rhythmic, high-amplitude shaking to a constant target, which the exposed bits cannot measure.

Detecting occasional ones is weaker than using their chronological order, and using a training anomaly is weaker than identifying an activity on an independent participant. We did not run a shuffled-order ablation, and the evaluation targets have no transitions at all. No claim of order-specific privacy inference is supported.

### Response-format and explanation limitations

All 70 calls returned HTTP success from DeepInfra and finished with stop; none hit the output limit. However, **26/70 failed the frozen schema**: 21 used `" explanation"`, and five substituted `"reference"` for the required explanation field. Twenty-two of the failures are stationary targets and four are moving targets, so missingness is highly nonrandom. All 44 valid predictions have the correct moving/stationary group; the lower all-target group scores come entirely from schema failures.

All raw JSON objects still contain a predicted activity, but primary scoring intentionally requires the complete schema. We did not retroactively relax it, repair keys or rerun failures. The report explicitly distinguishes output-contract performance from underlying label choice. The high failure rate limits inference about modest recognition differences and calls for a prospective reliability fix before a larger study.

Unsupported-explanation flags are provisional single-assistant assessments. The full-reference cells frequently miss the real Standing bursts, while some short-reference cells correctly describe identical patterns. Claims of “identical full sequences” can also ignore unequal recording lengths. Human annotation should distinguish supported bit values, unnoticed variation, unjustified physiological interpretations, and errors in duration reasoning.

### 5. What should we test next?

1. **Fix and preregister the scoring/interface contract before another comparison.** Use supported strict JSON-schema enforcement, or prospectively score a valid activity field separately from explanation-schema compliance. Preserve this run's strict scores. A controlled repeat on the same frozen targets could then assess how much the present result depends on format failures and stochastic response variation; do not treat it as a fresh population test.
2. **Test evidence extraction independently of activity accuracy.** On genuine training-only recordings, ask for observable transition presence/counts under a separately declared diagnostic task. This can establish whether Qwen reads the rare events. Do not feed diagnostic answers or evaluator features into the primary direct-inference task unless that access is a separate condition.
3. **Use a predetermined interface panel with varying held-out targets and controlled acquisition duration.** Include constant controls and naturally varying recordings from multiple subjects/sessions; use equal-duration contiguous excerpts without padding/concatenation, while reporting coverage. Do not pick a placement by Qwen success. Counterbalance real collection schedules and prevent duration from becoming a label code.
4. **Then test chronology and reproducibility.** Match targets across short/long access, compare ordered versus declared within-recording block-shuffle controls, include duration/count-only baselines, rotate reference-subject assignments and use multiple independent repeats. Order claims require gains beyond marginal bit and length information across subjects.

The current screen establishes that full-file input is technically feasible on the pinned provider, and that Qwen sometimes notices sparse reference events. It does not establish improved cross-user activity recognition or temporal-pattern exploitation. No expansion, retry campaign, new dataset evaluation, or fine-tuning was launched.


## Reproduction and preservation

Frozen inputs/settings: data/full-recording-screen. Raw responses, first-request gate, timing, evaluations and explanation annotations: runs/full-recording-screen. Prior experiment files and audit artifacts are hash-checked against preservation.json. No existing experiment was rewritten. Credentials and data/run directories remain Git-ignored. Exact prompt templates are unchanged from reports/full_recording_prompt_audit.md; all sent messages are saved.

```bash
# Offline analysis only; neither command submits requests.
.venv/bin/python full_recording_experiment.py evaluate
.venv/bin/python full_recording_report.py
```

The runner rejects an existing run directory and does not retry automatically. The evaluator preserves existing review annotations. New submissions require a separate, explicitly scoped experiment.

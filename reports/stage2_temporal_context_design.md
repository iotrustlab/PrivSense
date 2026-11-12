# PrivSense Stage 2: direct inference under knowledge and temporal-context conditions

Status: proposed experiment; no Stage 2 API calls or model evaluation performed. This design supersedes the earlier paper-reconciliation plan. The PoPETs paper motivates examining context; reproducing its implementation is **not a prerequisite or an objective here**. Stage 1 implementation, prompts, inputs, predictions and results remain unchanged.

## 1. Research question and interpretation

**How does direct LLM-based activity inference from binary sensor outputs change under different levels of attacker knowledge and temporal context?**

Qwen directly observes permitted binary samples and predicts an activity. There is no experiment-planning agent, tool-driven classifier selection, or trained classifier supplying its predictions. We vary three explicit factors: sensor/task knowledge (S), chronological history (T), and authorized labeled reference examples (A).

The objective is to measure information requirements, uncertainty and limitations—not to maximize accuracy. A correct forced-choice guess is not necessarily evidence of distinguishing information. Metadata or examples may change class preferences or explanation quality without adding any ability to distinguish identical inputs.

The existing right-pocket data supports these comparisons, including a useful temporal negative control. Constant inputs are a result to report, not a reason to fabricate transitions or search for a more favorable evaluation subset.

## 2. Lightweight audit and available observations

We reuse the completed offline audit rather than repeat the paper investigation. File-level evidence is in `stage2_audit/audit.json`; the read-only audit implementation is `../scripts/audit_stage2_temporal.py`. A lightweight freshness check compares the 36 current right-pocket validation source hashes with that manifest.

### Verified findings

| Property | Finding |
|---|---|
| Dataset / placement | Existing UTAH-STM-HAR processed right-pocket output |
| Evaluation subjects | Users 8 and 9; development validation, not a fresh test set |
| Validation source files | 36 |
| Valid source samples | 196,760 |
| Exported timestamp spacing | 20,000 microseconds, strictly increasing within each file |
| Constant validation files | 36 of 36 |
| Within-file validation binary transitions | 0 |
| Stage 1 observations | 1,947 nonoverlapping 100-sample windows |
| Source/export check | All 1,947 sequences matched source bits exactly |
| Distinct Stage 1 sequences | 100 zeros; 100 ones |
| Training users 1–7, right pocket | 147 files; 130 constant; 30 transitions |
| Ten-second validation blocks | 372 complete nonoverlapping blocks across all 36 files |

All-zero validation inputs occur for Laying, Sitting and Standing; all-one inputs occur for Downstairs, Jogging, Upstairs and Walking. These are **trusted evaluator findings**, not class summaries provided to Qwen.

Within-file chronological order is valid. Some processed stair segments retain larger time offsets, but have missing intervals between files; unrelated processed recordings also reset their clocks. No continuous binary session spanning activities is established. Therefore the design uses only contiguous samples inside a single processed file. It does not join stair segments, use filename numbering to construct history, fill gaps, or expose the acquisition schedule.

Other placements have some nonconstant recordings, but are outside the current right-pocket comparison. Selecting a different placement based on observed success would confound the study. A later placement extension would require its own declared scope and include both constant and nonconstant recordings.

### Consequence for temporal inference

Longer right-pocket validation observations repeat the same bit. They are real temporal observations, but contain no additional within-recording binary variation. T1 can measure sensitivity to redundant chronological context, label preferences or uncertainty; it cannot establish that the current data supplies informative transition patterns.

Do not describe the exported 50 Hz cadence as 50 independent detector decisions per second. Earlier audit evidence showed blockwise changes in the nonconstant development files. The exact detector update mechanism is not needed for this comparison and is not asserted in prompts.

## 3. Preserve Stage 1 and establish comparable Stage 2 inputs

Stage 1 reference: Qwen3.5-35B-A3B, independent 100-bit observations, binary semantics and seven classes only. Full validation results were 30.61% accuracy, 28.57% balanced accuracy, 0.13445 macro-F1 and 100% moving/stationary accuracy. Those files and results are historical references and must not be rewritten.

For Stage 2, all factorial cells use one common system/user template. It explicitly separates target observations, optional preceding history, and authorized references. This resolves ambiguity about labeled auxiliary examples while retaining Stage 1's direct inference task. Because this changes prompt framing, the newly run short/minimal cell is the **contemporaneous baseline**. The original Stage 1 prompt is retained byte-for-byte in a separate reference/bridge condition on the same selected target bits. Do not attribute original-prompt versus new-template differences to knowledge or temporal access.

No prompt optimization, model selection or reference selection based on evaluation scores is planned.

## 4. Data construction: same targets, different information

### 4.1 Partitions

- Training subjects 1–7: authorized auxiliary examples and evaluator-side prior baselines only.
- Validation subjects 8–9: Stage 2 target observations, with all labels hidden from Qwen.
- Users 10–11: previously inspected test partition; do not call it untouched or use it for this development experiment.

### 4.2 Matched short/long observations

For each right-pocket validation file:

1. Validate bit values and timestamp continuity.
2. Divide the chronological stream into complete nonoverlapping 500-sample blocks from the file's first row. Discard incomplete trailing blocks; never bridge a discontinuity.
3. Define each block's **target** as its final 100 samples, i.e. samples `[400:500]` relative to the block.
4. T=0 receives those 100 target samples only.
5. T=1 receives the same target plus the actual 400 immediately preceding samples, separately labeled as history. They are chronological and from the same uninterrupted file.
6. Every cell predicts one activity for the same final 100-sample target. No future observations or history labels are supplied.

This yields 372 paired targets: 183 from user 8 and 189 from user 9. Their class counts are:

| Class | Targets |
|---|---:|
| Downstairs | 40 |
| Jogging | 58 |
| Laying | 58 |
| Sitting | 58 |
| Standing | 58 |
| Upstairs | 42 |
| Walking | 58 |

The matched block coverage is 186,000/196,760 = approximately 94.53% of source samples. All 36 files remain represented. Target prediction coverage is the final two seconds of each retained block, not every two-second interval in the original dataset. Publish this distinction and the dropped-sample counts.

The two-pattern empirical accuracy bound for this matched target set is 116/372 = **31.18%**. It differs from Stage 1's 30.61% because the target weights change, not because ten seconds reveal more information. Every short/long comparison uses the same 372 targets or the same predetermined subset of them.

### 4.3 Small pilot selection

For the initial screen, sort candidate targets by subject number, relative recording path and block index, then apply a NumPy `default_rng(42)` permutation. Choose the first target encountered for each subject/activity pair: 14 targets total. Selection is evaluator-side and stratified only to ensure coverage; it is not conditioned on bit patterns, model confidence or correctness. Freeze the manifest before requests.

These are **new matched targets**, not necessarily the earlier Stage 1 smoke windows. For an original-prompt bridge, render the exact Stage 1 prompt with these target bits. Do not substitute an earlier result from a different window or use the old aggregate score as the paired baseline.

### 4.4 Auxiliary examples

Use seven references: one per class, from authorized training User 1. Freeze the deterministic selection already audited: the first 100 samples of the lexicographically first eligible processed right-pocket file for each class, requiring 100 consecutive valid 20-ms rows. Use the Stage 1 class-list order. Do not search for distinctive or helpful examples.

The chosen references are recorded in `stage2_audit/proposed_auxiliary_examples.json`. Each prompt exports only `activity` and `binary_sequence`. Subject, source filename, timestamp and offset remain evaluator-only. All actual 100 values are provided; no summary substitutes for them.

These specific references contain identical zeros with three different stationary labels and identical ones with four different moving labels. Preserve this ambiguity. Do not cherry-pick a single label per bit. Reference class balance is a design choice, not an assertion about population prevalence. Reference examples are independent examples, not a chronological continuation of either one another or the target.

## 5. Experimental conditions

S bundles the requested sensor modality, placement, sampling cadence and legitimate detector description. It does not isolate which sentence in that bundle caused an effect; a later metadata-component ablation would be needed for that question.

| ID | T: preceding history | S: sensor/task information | A: labeled references | Interpretation |
|---|---:|---:|---:|---|
| C000 | No | No | No | Minimal knowledge; contemporaneous Stage 2 baseline |
| C010 | No | Yes | No | Sensor knowledge contribution at fixed target |
| C100 | Yes | No | No | Temporal-context contribution at minimal knowledge |
| C001 | No | No | Yes | Auxiliary examples contribution without metadata |
| C111 | Yes | Yes | Yes | Combined knowledge |
| C110 | Yes | Yes | No | Temporal × sensor interaction control |
| C101 | Yes | No | Yes | Temporal × auxiliary interaction control |
| C011 | No | Yes | Yes | Sensor × auxiliary interaction control |

The first five rows implement the five requested conditions. The final three complete a 2×2×2 factorial design. They are not automatically required for the initial screen, but **without them the combined condition cannot identify each interaction or isolate the incremental effect of each factor within the combination**.

Primary single-factor contrasts: C010−C000, C100−C000 and C001−C000. C111−C000 measures the overall bundle. With the full grid, additionally compare T at each S/A setting, S at each T/A setting, and A at each T/S setting; report interactions as differences of these paired differences. Avoid selecting only favorable contrasts.

R0 is a separate original-Stage-1-prompt reference on the same target set, outside the factorial grid. R0 versus C000 measures prompt-framing differences, not a knowledge effect.

## 6. Exact proposed prompts

No tools, summaries, derived features, classifier results, evaluation outcomes, or earlier conversations are supplied. Each request consists of one system message and one user message. `{...}` slots below are filled deterministically; they are not literal placeholders sent to Qwen.

### 6.1 Common Stage 2 system message (identical across all eight cells)

```text
You are evaluating whether limited sensor outputs reveal private information about human activities.

You are an attacker who can observe only the binary outputs of a shake/no-shake sensor interface.

You do not have access to the raw sensor readings, internal model, or the true activity label of the target observation.

Use only the information supplied in the current request. Any explicitly labeled reference observations are authorized auxiliary examples, not labels for the target observation.

Do not invent measurements or assume access to unavailable information.

If multiple activities are consistent with the observation, acknowledge that uncertainty.
```

Compared with Stage 1, the label restriction is scoped explicitly to the target and the information allowance covers authorized references. Both changes apply equally to all Stage 2 cells, including C000; R0 provides the unchanged-prompt bridge.

### 6.2 Common Stage 2 user template

```text
Here are binary observations from a sensing system.

Binary meaning:
0 = static/no shake
1 = shake

Sensor and detector information:
{SENSOR_BLOCK}

Authorized reference observations:
{AUXILIARY_BLOCK}

Immediately preceding observations:
{HISTORY_BLOCK}

Target observations:
{TARGET_BITS}

Predict the activity during the target observations only.

The person was performing one of these activities:
Downstairs, Jogging, Laying, Sitting, Standing, Upstairs, Walking.

Based on the available information:
1. Which activity is most likely?
2. Why?
3. Which other activities are plausible?
4. Is the information sufficient to make a reliable distinction?

Return only a JSON object containing:
- predicted_activity: exactly one of the seven activity names
- explanation: a brief explanation grounded in the observation
- alternative_activities: a list of other plausible activity names
- confidence: a number from 0 to 1 expressing confidence in the exact predicted activity
- sufficient_information: a boolean indicating whether the observation reliably distinguishes the exact activity
```

For every target, all eight cells use the same actual `TARGET_BITS`, serialized as `json.dumps(list_of_ints)` with all 100 values. Class order and headings are fixed. No ellipses, run-length encoding or calculated statistics are used.

### 6.3 Exact sensor blocks

For S=0:

```text
No additional sensor or detector information is supplied.
```

For S=1:

```text
The sensing system uses an inertial measurement unit with accelerometer and gyroscope channels.
The sensor placement is the right pocket.
The exported binary observations are spaced 0.02 seconds apart (50 samples per second).
You observe only the binary output, not the accelerometer or gyroscope readings.
The intended output indicates shake versus no shake; it is not a seven-class activity label.
A zero means the detector did not flag shake, which does not establish complete physical stillness.
A one does not directly measure motion amplitude, gait cadence, or a unique activity.
The detector's exact thresholds, training data, and output-update rule are not supplied.
The export spacing does not specify how often the detector makes a new decision.
```

This describes known system modalities, placement, measured export cadence and legitimate output semantics. It does not assert that the detector uses both modalities, disclose observed class relationships, or claim a native detector update rate. The clarification of “static/no shake” is explicitly part of S; the baseline's original bit wording is retained.

### 6.4 Exact history blocks

For T=0:

```text
No preceding observations are supplied.
```

For T=1:

```text
These observations immediately precede the target observations in chronological order within the same uninterrupted recording:
{PRECEDING_400_BITS}
```

The placeholder contains the full actual 400 preceding values, with the same JSON serialization as the target. No labels, file boundaries, missing-interval markers or source offsets are inserted. Physical duration is inferable only when S=1 supplies the sample spacing; T alone grants relative order and additional samples.

### 6.5 Exact auxiliary blocks

For A=0:

```text
No labeled reference observations are supplied.
```

For A=1:

```text
The following are separate labeled examples from authorized training participants. They are not consecutive parts of the target recording or of one another.
{REFERENCE_JSON}
Only these reference observations have known labels. The target observation's activity remains hidden.
```

`REFERENCE_JSON` is `json.dumps(reference_list)` where each object has exactly the keys `activity` and `binary_sequence`, with the latter containing all 100 actual values. Its seven objects are in this order: Downstairs, Jogging, Laying, Sitting, Standing, Upstairs, Walking. Strip all provenance fields from the saved selection manifest. Do not include the sensor block unless S=1: C001 and C101 genuinely lack that metadata.

### 6.6 R0: exact Stage 1 system prompt

```text
You are evaluating whether limited sensor outputs reveal private information about human activities.

You are an attacker who can observe only the binary outputs of a shake/no-shake sensor interface.

You do not have access to the raw sensor readings, internal model, or the true activity labels.

Use only the information supplied in the current observation.

Do not invent measurements or assume access to unavailable information.

If multiple activities are consistent with the observation, acknowledge that uncertainty.
```

### 6.7 R0: exact Stage 1 user template

```text
Here is a sequence of binary observations from a sensing system.

Binary meaning:
0 = static/no shake
1 = shake

Observed sequence:
{TARGET_BITS}

The person was performing one of these activities:
Downstairs, Jogging, Laying, Sitting, Standing, Upstairs, Walking.

Based on the available information:
1. Which activity is most likely?
2. Why?
3. Which other activities are plausible?
4. Is the information sufficient to make a reliable distinction?

Return only a JSON object containing:
- predicted_activity: exactly one of the seven activity names
- explanation: a brief explanation grounded in the observation
- alternative_activities: a list of other plausible activity names
- confidence: a number from 0 to 1 expressing confidence in the exact predicted activity
- sufficient_information: a boolean indicating whether the observation reliably distinguishes the exact activity
```

## 7. Fixed execution settings and information boundary

Proposed future settings match Stage 1: model `qwen/qwen3.5-35b-a3b`, temperature 0.1, 600 maximum output tokens, reasoning explicitly disabled, JSON-object response format, parameter-compatible provider routing. No sampling seed or provider pin is assumed. Keep the same settings across cells; request order is randomized/counterbalanced with a logged seed so conditions do not systematically differ in time/provider exposure.

Each target-condition-repeat combination gets a new independent request. No prior prediction or evaluation feedback is appended. Long observations are included within the current request, not through conversational memory. Do not deduplicate requests silently; duplicate inputs are useful for measuring response consistency. Repeat variability is not additional population evidence.

Validate the existing five-field output schema, with a forced-choice class from the seven names, a nonempty brief explanation, valid distinct alternative classes, numeric confidence in [0,1], and boolean sufficient_information. Invalid responses are not repaired using labels. Insufficient-information responses remain scored predictions and are not rewarded as correct merely for acknowledging ambiguity.

Keep observation/reference exports separate from evaluator labels and provenance. Local IDs join outputs to labels but are not sent to Qwen. Log exact rendered messages, response settings, returned model/provider when available, responses, validation errors, token/cost fields, request attempts and latency. Credentials never enter prompts or logs. Stop new submissions on authentication/credit failures; explicit recovery preserves all successful predictions and logs attempts. No inference code is implemented or executed by this design task.

## 8. Metrics and simple baselines

### Required outcomes

- Seven-class accuracy, macro-F1 over all seven labels, balanced accuracy, and confusion matrix.
- Moving/stationary accuracy, with moving defined as Downstairs/Jogging/Upstairs/Walking. Derive the prediction's group from the predicted class, not from a second question.
- Subject-specific and recording-specific results; window-weighted and equal-recording summaries. Keep class support visible because one recording normally has one activity and stairs have more file segments.
- Identical-input groups: number of unique complete observable inputs, true labels per group, counts of ambiguous examples, pattern-majority accuracy diagnostic, and consistency of predictions for identical requests.
- Confidence distribution, confidence on correct/incorrect answers, reliability bins, high-confidence errors, alternative-label coverage, and insufficient-information frequency.
- Unsupported-explanation frequency under the rubric below.
- Schema/API failures, missing results, attempts, token consumption, API-reported USD cost and cost per valid observation. Primary scores count unresolved failures as incorrect; valid-only scores must have matched-subset baselines.

### Baselines

1. **Training-majority:** one label chosen from authorized training frequencies, frozen before validation scoring.
2. **Uniform guessing and training-prior guessing:** analytic expected accuracy; if reporting F1 from expected confusion, identify it as such rather than expected finite-sample F1.
3. **Fixed binary rule:** target mostly ones -> Walking, otherwise Sitting, unchanged from Stage 1. Also score its moving/stationary interpretation. Use the target only, so its access and granularity remain explicit.
4. **A-matched reference rule:** for auxiliary cells, match the target exactly to the seven supplied reference sequences; resolve ambiguous matches with a fixed predeclared rule (first reference in the frozen order). If no match exists, fall back to the frozen training-majority label. This is a simple reference-access baseline, not a trained classifier and never supplies Qwen's prediction. Report the ambiguity instead of implying unique nearest labels.
5. **Empirical pattern bound:** compute `sum_pattern max_label count(pattern,label) / N` using evaluator labels. This is an information diagnostic, not a deployable attacker or a baseline granted hidden labels.

Shared metadata and a common reference set do not separate targets with identical bits. Fixed longer constant histories likewise do not subdivide the target groups. A future accuracy change can result from different tie-breaking or changed priors, not necessarily newly distinguishing information. Recompute the diagnostic on the actual matched subset and report whether stochastic correctness merely fluctuates around it.

The former Qwen experiment-planning pipeline is not an equivalent direct-LLM baseline and is excluded from these comparisons. No separate trained ML classifier is needed in Stage 2.

## 9. Controls and failure analysis

### Temporal validity

- Never cross processed-file boundaries or timestamp discontinuities.
- Do not concatenate activities, collapse unobserved gaps, infer missing bits, or insert transitions.
- Do not expose collection order, absolute timestamps, activity-bearing paths, mounting notes, source offsets or total recording duration.
- Match target IDs across T and report history/target coverage separately. Short observations are the target tail of the long block, not a different sample or a majority label over a different duration.
- Permuting genuine history samples would preserve marginal values while removing order, but for this validation set it produces exactly the same sequence. Verify invariance offline and omit redundant shuffle API calls. This is a limitation of the available temporal test, not evidence that shuffling preserves all temporal signals generally.
- If a later authorized dataset/placement contains nonconstant histories, preregister a separate within-interval sample/block-shuffle control, keep the target fixed, and disclose altered ordering. Do not select that extension for favorable Qwen results.

### Knowledge and prompting

- S and A remain independent, including the A-only conditions without sensor metadata.
- Use the same training examples for all A=1 cells and the same headings/system message for all factorial cells.
- References may carry labels only for their own training observations. No evaluation labels, examples selected by evaluation success, class-conditional validation summaries or previous results are allowed.
- The original Stage 1 system wording is not silently edited. R0 and C000 distinguish framing from information effects.
- S is an intentional bundle; do not claim to isolate placement versus cadence versus detector semantics from this experiment.
- More tokens and longer formatting accompany added information. On constant histories, a change is specifically a redundant-context/representation effect. For knowledge cells, prompt-length effects cannot be wholly separated from semantic additions by this basic design; disclose that limitation rather than claim pure causal identification of every sentence.

### Unsupported explanations

Before model evaluation, annotate claims using a fixed rubric:

| Claim type | Treatment |
|---|---|
| Constant outputs, observed binary transitions | Supported if present in the actual sequence |
| Placement, modalities, export cadence | Supported only when supplied by S |
| Physical duration derived from sample count | Supported only with a supplied sampling interval |
| Motion amplitude, intensity, gait frequency, rhythmic motion from constant bits | Unsupported by the exposed sequence |
| Exact posture or unique activity despite identical inputs | Unsupported uniqueness claim |
| No shake implies complete physical immobility | Unsupported detector-to-physics inference |
| Statements about supplied reference labels | Supported only when faithful to A; ambiguous matches must remain ambiguous |
| Invented measurements, hidden metadata or prior evaluation results | Unsupported |

For the small experiment, manually review all explanations against the rubric. For a larger run, preselect a fixed random/pattern-balanced sample. Review blind to correctness where practical and report annotation counts; a second human reviewer and agreement are desirable if available. Do not use a new LLM judge or an agent feedback loop. Score uncertainty separately from explanation factuality and exact-class accuracy.

### Statistical reliability

Use paired differences on the same target IDs, then aggregate by subject and recording. Windows from a recording and repeated requests for identical inputs are not independent people. With only two validation subjects, report descriptive results and both subject scores; do not claim strong population-level significance or use ordinary window-level binomial intervals. If bootstrapping recordings, disclose that stair segments can share an acquisition session and that uncertainty is conditional on these two subjects.

The 14-target screen is balanced by subject/class and has different weights from the 372-target set or the 1,947-window Stage 1 set. Report each separately. Do not choose the best random repeat or revise prompts after seeing validation errors. Users 10–11 remain previously inspected; no new final-test claim is made.

## 10. Smallest useful experiment and staged expansion

**Initial five-condition screen:** select and freeze the 14 matched targets, then run C000, C010, C100, C001 and C111 once per target: **70 requests**. This covers all five requested conditions while keeping individual effects relative to C000 separate. Add R0 on the same 14 target bits to connect to the original prompt: **84 requests total**. This is the smallest recommended complete screening package; it is an exploratory development experiment, not a robust effect estimate.

The initial screen tests:

- Whether sensor/task metadata improves uncertainty or reduces unsupported explanations.
- Whether actual but redundant longer chronology changes inference behavior.
- Whether ambiguous labeled examples change confidence, alternatives, or tie-breaking.
- Whether the combined package behaves differently from minimal knowledge.

It does **not** identify all interactions. If interpretation of the combined result is needed, add C110, C101 and C011 on the same targets: **126 requests total including R0**. Freeze this decision rule before inspecting a selectively favorable combined score.

For response variability, three independent repeats of the initial package require 252 requests, or 378 for the full factorial plus R0. Repeats use unchanged targets/examples/prompts/settings and counterbalanced condition order. They quantify model variation, not population generalization. Do not automatically run these expansions.

Only after checking validity, cost and the informational value of the small screen should a full matched evaluation be considered. Five cells over all 372 targets require 1,860 requests before any bridge/repeats; the full eight-cell grid requires 2,976. Estimate costs from actual prompt lengths—including seven full reference sequences—not from Stage 1 per-window cost alone.

Given constant validation inputs, a null temporal effect and improved acknowledgment of ambiguity are scientifically useful outcomes. No positive accuracy gain is required for the experiment to answer its question.

## 11. Reproducibility and preservation

A future implementation should be separate from Stage 1 and store:

- Target manifest with source hash, file interval, target/history indices and coverage checks; hidden labels in a separate evaluator file.
- Fixed 14-target selection and full 372-target list; explicit record of selection algorithm and seed.
- Auxiliary selection manifest and a stripped attacker-facing reference export.
- Condition flags T/S/A, exact prompt-template hashes, rendered messages and response schema version.
- Model settings, repeat IDs, request ordering, raw valid/invalid responses, attempts, usage/cost and evaluation version.
- Separate reports for five-condition screening, interaction expansion and repeats, if authorized later.

Existing source/export audits support the data construction; no paper artifact recovery is required to proceed. Unknown detector-generation details limit claims about physical mechanism, but do not prevent a controlled experiment on the observed interface as supplied. Preserve that distinction.

**Current deliverable:** this design report only. No new Qwen calls, provider calls, trained attack model, experiment-planning agent, or modifications to Stage 1 results were made.

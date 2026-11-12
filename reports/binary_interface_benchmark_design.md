# Binary-interface survey and benchmark construction

Status: read-only local data survey plus proposed benchmark protocol. No Qwen calls were made for placement selection, no new dataset was downloaded, and no source observations were modified. This work is separate from the completed right-pocket 84-request screen.

## 1. What is locally available

The workspace's `Datasets` directory contains one dataset directory: `Data_STM-DT`, with 1,435 CSVs and 76 text files across the stored users. There are no additional local binary-output datasets in that directory. Names discussed earlier (for example other HAR datasets) must not be treated as audited or installed assets. The raw validation files inspected previously contain six-axis IMU and timestamps, not recorded `dec_tree_out_1` values.

This survey reads the processed binary/time columns for users 1–9 at all five placements: 915 files total (735 training, 180 development-validation). Users 10–11 payloads are not opened; their results were previously inspected and they are not an untouched final test set. Source hashes are checked against the existing audit. Results are stored in `stage2_screen_survey.json`; rerun offline with:

```bash
.venv/bin/python scripts/survey_binary_interfaces.py
```

No activity label enters Qwen in this survey: there is no Qwen execution. Labels are used locally only to diagnose association, coverage and confounding. Those diagnostics are not proof of held-out inference capability.

## 2. Temporal variation actually recorded

Here, variation means a change in the **existing processed binary values inside one continuous file**, not a synthesized transition. It does not establish native detector timing or exact physical causes. Across development files, known transitions align with one-second export blocks; do not interpret them as high-frequency gait measurements.

| Placement | Training varying files /147 | Training transitions | Validation varying files /36 | Validation transitions | Validation concentration |
|---|---:|---:|---:|---:|---|
| Left ankle | 17 | 34 | 1 | 52 | User 9, Standing only |
| Left wrist | 19 | 44 | 0 | 0 | None |
| Right ankle | 15 | 21 | 1 | 2 | User 8, Standing only |
| Right pocket | 17 | 30 | 0 | 0 | None |
| Right wrist | 18 | 62 | 7 | 46 | User 9; six Downstairs segments and one Walking file |

All five training placements contain some temporal variation, but variation-bearing ten-second windows occupy only approximately 1.07–2.44% of training windows. Four or five of the seven training users have a varying file at each placement. The current development-validation variation is especially concentrated: right-wrist and left-ankle changes come from a single person, and right-ankle from one standing interval. Do not confuse seven stair-related files with seven independent participants or independent acquisition sessions.

The left-ankle standing example has many shake-positive samples despite a stationary activity label. This shows why bit semantics alone do not universally identify moving/stationary behavior across placements. A change of placement is a different observation condition, not a drop-in way to improve the pocket result.

## 3. Window-level diagnostics: variability versus information

We formed nonoverlapping 2-second and 10-second windows **within existing files**, splitting at timestamp discontinuities and dropping tails. The following ten-second results are descriptive on the full window label, not the final-two-second targets used by the Stage 2 screen. They must not be compared as a matched temporal-effect experiment.

| Placement | Validation 10s windows | Nonconstant windows | Unique ordered patterns | Empirical ordered-pattern accuracy bound | One-count-only bound |
|---|---:|---:|---:|---:|---:|
| Left ankle | 376 | 17 | 18 | 36.17% | 36.17% |
| Left wrist | 372 | 0 | 2 | 31.18% | 31.18% |
| Right ankle | 373 | 1 | 3 | 31.64% | 31.64% |
| Right pocket | 372 | 0 | 2 | 31.18% | 31.18% |
| Right wrist | 372 | 17 | 18 | 35.75% | 34.95% |

“Ordered-pattern bound” groups identical complete binary sequences and uses evaluation labels to choose the most frequent class in each group. “One-count-only bound” groups by the number of ones, disregarding order. Neither is an available attacker predictor; both are finite-sample label-aware diagnostics that can be optimistic for rare unique patterns.

At two seconds, nonconstant validation windows number 28 (left ankle), 0 (left wrist), 1 (right ankle), 0 (right pocket), and 24 (right wrist). Only three or four distinct two-second patterns occur. For these particular validation windows the ordered-pattern and one-count bounds are equal at each placement: no additional empirical separation is demonstrated by order beyond count at that length.

At ten seconds, the right-wrist ordered-pattern bound exceeds the one-count bound by approximately **0.81 percentage points**. This is a hypothesis-generating observation, not evidence of generalizable temporal inference. Rare patterns, person effects and segmented staircase recordings can explain apparent separation. The left-ankle gain over constant patterns is fully matched by the count-based diagnostic on this sample, so it is not evidence of order-specific information.

Cross-partition exact-pattern recurrence is weak: among the nonconstant ten-second validation windows, two left-ankle and two right-wrist windows have an exact pattern seen in training, but **none has the same activity label for that pattern in training**. The right-ankle varying pattern is unseen. Lack of exact recurrence does not prove that more abstract temporal statistics cannot generalize; it does prevent treating these rare validation patterns as established reusable class signatures.

### Assessment by interface

- **Right pocket and left wrist:** useful information-limited development-validation controls. Neither contains variation for these subjects. They still expose coarse motion-group information; “limited” does not mean zero privacy leakage.
- **Right ankle:** two recorded transitions in one standing file are too sparse and concentrated to support a credible temporal activity benchmark by themselves.
- **Left ankle:** clear within-file variation exists, but it is concentrated in one subject's standing recording. Current diagnostics show count-based association rather than a demonstrated order benefit.
- **Right wrist:** recorded variation in more files and two validation activities makes it worth including in a broader predetermined panel, but not selecting as a “winner.” Its potential order-specific association is small, finite-sample and subject-concentrated.

**No locally available placement has yet been established as a robust information-bearing temporal interface.** This is a statement about the evidence collected, not proof that such an interface cannot exist here or elsewhere.

## 4. Predefined selection protocol independent of Qwen

The survey is already observed development evidence. Do not retroactively call thresholds chosen now a preregistration on these same files. Freeze the following protocol for future untouched subjects/sessions or a separately held-out collection, and label any application to users 1–9 as exploratory.

### 4.1 Freeze a panel rather than rank placements

Use all five placements in a fixed alphabetical order, or declare a resource-limited subset by hardware/application relevance **before inspecting model scores**. Do not choose the placement with the highest empirical bound, classifier accuracy or Qwen success. Report constant and varying cases for every included placement. A null stratum is a valid outcome.

For a cost-limited initial audit panel, use an identical subject/class quota and deterministic seed across placements; require matched raw-session/time coverage if comparing placements as paired observations. When cross-sensor clock synchronization cannot be verified, report unpaired placement results rather than pretending they cover the same moments.

### 4.2 Separate eligibility, variation and information gates

1. **Provenance/quality eligibility:** real exported or faithfully replayed binary observations; lawful access; documented detector purpose and version; monotone timestamps; known gaps; stable placement; target labels/time intervals available to the trusted evaluator; adequate subject/session coverage. Reject corrupt traces, not hard examples.
2. **Variation characterization:** on a training/audit-only split, report transition density, run lengths, output entropy, duration coverage and how many subjects/classes/sessions contribute changes. Do not infer class information from variation alone.
3. **Candidate temporal stratum:** a proposed screening gate is at least 5% nonconstant fixed ten-second windows, with variation in at least three independent subjects, three activities and two sessions per contributing subject. These are engineering screening criteria, not statistical proof or universal requirements. Fix them before new data inspection. If none passes, report no qualifying stratum; do not relax thresholds until a preferred placement passes. The current training placements have under 2.5% nonconstant ten-second windows and would not pass the 5% gate.
4. **Information validation:** on separate development subjects/sessions, compare short-target versus genuine preceding-history access with matched targets, fixed knowledge and simple predeclared inference rules. Compare order-sensitive versus marginal/count-only information and chronological versus valid within-interval shuffle controls. Seek reproducible distinctions across subjects, not a bound inflated by singleton patterns.
5. **Final benchmark lock:** lock sources, preprocessing, detector, splits, target selection, strata, scoring weights and API prompts before an untouched final evaluation. If an information-bearing candidate fails to generalize, retain that negative result and downgrade the evidential label rather than remove it.

Any trained diagnostic baseline used in a future trusted benchmark-construction phase must be fitted on training data only and clearly separate from direct Qwen predictions. A classifier's labels must never be supplied to Qwen as evidence. Simple count/pattern/reference baselines can be used without fitting a separate activity classifier.

### 4.3 Avoid selection-induced claims

Maintain two reporting tracks:

- **Natural-prevalence track:** all eligible predetermined windows, including constant stretches. This measures realistic inference opportunities and costs.
- **Diagnostic stratified track:** a frozen quota of constant, weakly varying and strongly varying windows selected by observable-only criteria. Report stratum prevalence and selection criteria, and use weights when estimating natural-prevalence performance. Do not claim that an intentionally variation-enriched sample reflects deployment frequencies.

The model sees only its allowed observations/knowledge, not hidden activity labels or evaluator stratum names. Selecting by observable variation does not itself create new bits, but it changes the evaluated distribution and must be disclosed.

## 5. Benchmark with both limited and information-bearing interfaces

### 5.1 Define the strata operationally

“Information-limited” means permitted observations collapse relevant activity distinctions; it does not imply no leakage at all. Current constant right-pocket traces supply an explicit example. “Information-bearing” should mean measurable, reproducible target information under the declared observation and auxiliary-data budget on independent subjects—not merely nonconstant outputs or a successful prompt.

Include:

- Constant or heavily colliding interfaces as negative/ambiguity controls.
- Weakly varying interfaces whose information may be mostly duty cycle rather than order.
- Interfaces with reproducible class-associated temporal structure, if independently validated.
- Authentic cross-activity continuous sessions, when available, as a separate task from single-activity recording inference.

Do not call all these interfaces equally private or make a binary vulnerable/not-vulnerable judgment from a single accuracy threshold.

### 5.2 Obtain real information-bearing observations

Two defensible sources are:

1. **Existing datasets with recorded binary event outputs:** audit them under the same protocol, including timestamps, legitimate event semantics, placement and label provenance. None beyond Data_STM-DT was found locally in this task; no external dataset is claimed audited.
2. **Authorized new sensing collection or faithful replay:** run a fixed legitimate shake/event detector over continuous real sensor recordings. Fix its legitimate task, configuration and thresholds independently of private-activity attack performance. Log its actual output with synchronized clocks and annotations. For replay, use an implementation whose semantics, state, cadence and initial conditions are documented; identify it as a replayed interface, not a recorded hardware output, and validate against recordings where possible.

Do not define the binary output from the activity labels, search thresholds for maximum HAR separation, inject alternating bits, stitch independent activities into apparent continuity, or fill unobserved intervals. Genuine behavior can naturally produce transitions even while the activity label stays constant. An actual activity transition and a detector-bit transition are different events and must be annotated separately.

### 5.3 Collect and split to control nuisance information

Use multiple subjects, placements and sessions/days; counterbalance or randomize acquisition activity order in the real collection, not by rearranging recorded samples afterward. Record actual transition intervals and unknown/mixed labels. Keep session durations and target selection from becoming deterministic activity codes. Preserve gaps as missing observations; exclude targets lacking permitted history rather than synthesize it.

Group all placements and overlapping temporal windows from the same subject/session into the same partition. Fit any detector calibration, preprocessing statistics or auxiliary-example selection on authorized development data only. Document detector-training overlap. Keep held-out labels, filenames, clock origins, collection schedule and anthropometrics out of attacker exports unless each is explicitly an experimental access factor.

For natural cross-activity sessions, define the prediction target prospectively (for example activity at the final sample or throughout a designated two-second target). Predetermine how mixed/uncertain targets are scored or excluded. Do not give the model a label-derived transition marker. Use only preceding history for a causal setting; access to future samples is a separate condition.

### 5.4 Factorial evaluation over interfaces

Retain the same T/S/A factors and response schema. Freeze representative targets and compare short versus longer real history on exactly the same prediction units. Expand observation access and metadata independently. K=metadata, examples or both cannot fix equivalence classes when every subject receives identical observable content, although they may improve calibration and priors.

On varying streams, compare:

- Target only versus target plus genuine preceding history.
- Full ordered history versus matched marginal/count baselines.
- Genuine history versus a predeclared within-interval history shuffle, holding the target fixed and documenting the control's nonchronological nature.
- Fixed knowledge versus authorized training examples, with example counts and class balance explicit.

Do not use shuffled independent activities as a substitute for genuine temporal histories. If an output is held on one-second blocks, include a justified block-order control rather than attributing all sample-shuffle effects to physical cadence.

Report per-interface scores, information diagnostics, class-confusion groups, uncertainty, unsupported reasoning and cost. Aggregate with declared interface weights; do not let a large easy or constant dataset dominate the benchmark score. Include negatives and failed hypotheses. Separate model response variation from participant-level generalization.

## 6. Recommended next action

Do **not** expand the current constant-pocket 84-request screen to all 372 targets merely to obtain more confident estimates of the same two-pattern guessing behavior. The completed screen answers the immediate question at that interface: extra knowledge changes confidence and tie-breaking, not observed class discrimination.

First freeze the selection and benchmark protocol above, then secure a candidate dataset or authorized collection with documented genuine continuous detector output and broader subject/session variation. If using current placements for a preliminary study, include the full fixed panel under identical sampling rules and call it exploratory; do not designate right wrist or left ankle as the information-bearing winner based on this survey. Independently validate any informative stratum before spending on a large direct-LLM grid.

The next research advance should be a change in **available observation information with verified provenance**, not merely another prompt on the same constant signals.

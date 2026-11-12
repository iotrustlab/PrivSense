# Next inference research design: reliability and temporal information

Status: completed offline audit and proposed protocol/pilot. No new Qwen inference requests, fine-tuning, planning agent or modifications to previous results. Public documentation and endpoint metadata were consulted; API enforcement has not been empirically tested. All users 1–9 data remain development evidence. Users 8–9 are disjoint from auxiliary users 1–7, but are not an untouched final test.

## Executive finding

**Reliability:** all 26 rejected responses failed because the explanation field was renamed; no output was truncated or malformed JSON. Replace the fragile five-field answer with a versioned, strictly constrained three-field answer, and validate that contract in a separate label-blind technical test.

**Information:** three evaluation placements contain real within-recording bit changes, but they are sparse and concentrated in particular users/classes. Fixed-duration cross-user baselines do not show a consistent benefit of temporal order over the number of ones. This does not prove that no usable order information exists; it means the next LLM experiment must be an exploratory information-access diagnostic, not a claimed temporal-privacy breakthrough.

## A. Exact output-reliability audit

All 70 saved request message pairs were checked against the frozen requests, and each raw response was parsed and revalidated without normalization or repair. The audit records missing/extra fields, response shape, allowed activity names, confidence/boolean types, alternatives, finish reason, token counts and provider. Per-response evidence: [response_failures.json](next_inference_audit/response_failures.json).

| Condition | Failed /14 | `" explanation"` | `"reference"` | Input tokens | Output tokens |
|---|---:|---:|---:|---|---|
| C1 | 5 | 3 | 2 | 1,382–1,382 | 135–213 |
| C2 | 5 | 3 | 2 | 77,445–77,445 | 191–261 |
| C3 | 4 | 3 | 1 | 3,036–16,279 | 175–212 |
| C4 | 4 | 4 | 0 | 79,099–92,342 | 177–250 |
| C5 | 8 | 8 | 0 | 77,845–77,845 | 197–248 |

| Failure category | Count |
|---|---:|
| Missing required `explanation`, with a replacement key | 26 |
| Truncated responses | 0 |
| Invalid JSON syntax | 0 |
| Invalid candidate activity name | 0 |
| Unexpected top-level structure | 0 |
| Other field-type/alternative-list errors | 0 |

The two key subtypes are mutually exclusive: 21 leading-space keys and five `reference` substitutions. All 26 objects have an activity, numeric confidence, boolean sufficiency, and valid alternative list; the expected explanation key is absent and an unauthorized key is present. “Invalid activity name” here means outside the candidate vocabulary, not disagreement with ground truth. The prior strict results include 12 correct and 32 incorrect schema-valid activity predictions; those 32 recognition errors are separate from the 26 formatting failures.

All requests returned HTTP success from DeepInfra and finish_reason=stop; output usage was 135–261 tokens, comfortably below the 600-token budget. Reasoning was explicitly disabled. Provider prompt counts were local content counts plus 17 framing tokens. There is no evidence that the observed failures were caused by output exhaustion, JSON truncation, or input shortening.

Length alone is not a sufficient explanation: C1 at 1,382 input tokens and C2 at 77,445 both fail 5/14; C3 and C4 both fail 4/14 despite very different lengths. C5 fails 8/14, so a long-context contribution cannot be excluded, but there is no randomized length-only reliability experiment identifying it. Failures cluster on zero targets: 22/30 zero-pattern requests versus 4/40 one-pattern requests. Content-dependent generation/template behavior is a plausible hypothesis, not a proven cause. All calls use one provider, so this run cannot separate model behavior from provider-side decoding or adaptation.

The concrete contract mismatch is established: `response_format={"type":"json_object"}` asks for JSON, while the evaluator demands exact field names and types. `require_parameters=true` makes parameter support a routing constraint; it does not turn JSON-object mode into strict schema enforcement. The raw response already contains the incorrect key before local validation, so this is not a validator spelling bug. We retain the original 44/70 valid count, predictions and scores unchanged.

### Proposed protocol `privsense-inference-v2.0`

Use a fresh system/user pair for every target. Preserve each experiment’s permitted binary inputs, reference labels and metadata; change only the declared output contract. Require exactly three fields and no explanatory prose. Model remains direct Qwen inference, temperature 0.1, reasoning disabled. Set max_tokens=128 uniformly for this small answer; this is a new protocol, not an unannounced change to old runs. Pin deepinfra/fp8, disable fallback and require parameters. The schema is:

```json
{
  "type": "json_schema",
  "json_schema": {
    "name": "privsense_inference_v2",
    "strict": true,
    "schema": {
      "type": "object",
      "properties": {
        "predicted_activity": {
          "type": "string",
          "enum": [
            "Downstairs",
            "Jogging",
            "Laying",
            "Sitting",
            "Standing",
            "Upstairs",
            "Walking"
          ]
        },
        "confidence": {
          "type": "number",
          "minimum": 0,
          "maximum": 1
        },
        "sufficient_information": {
          "type": "boolean"
        }
      },
      "required": [
        "predicted_activity",
        "confidence",
        "sufficient_information"
      ],
      "additionalProperties": false
    }
  }
}
```

Exact output instruction appended to the fixed observation prompt:

```text
Predict the target activity using only the supplied observations, sensor information and labeled references from other participants. Return only the three-field JSON object required by the response schema. confidence refers to the exact activity, not merely whether the person is moving. Set sufficient_information to false when the observations do not reliably distinguish the exact activity. Still return one of the seven candidate activities. Do not include explanations, alternatives or extra fields.
```

Treat the three outcomes separately: transport/completion success, schema validity, and activity correctness. Insufficient-information acknowledgment is not automatically a correct activity answer. Local validation rejects unknown/duplicate keys, nonfinite numbers, booleans masquerading as numbers, strings masquerading as booleans, and out-of-range confidence. `inference_protocol_v2.py` implements only the schema and pure validator; it has no API runner and does not reparse old results into new scores. Invalid responses remain missing predictions with failure counts; no silent coercion, key repair or retry-until-success.

Explanations become a separate optional evidence-audit task with its own request IDs, sample-selection rule and costs. Do not ask for an explanation during the primary prediction or feed the follow-up explanation back into inference. A later explanation is a retrospective account, not proof of the computation that produced the original class.

### What is verified about strict-schema support

DeepInfra documents separate schema-free JSON-object and strict JSON-schema modes. The current OpenRouter endpoint metadata for deepinfra/fp8 lists both response_format and structured_outputs. OpenRouter documents json_schema with strict=true for compatible endpoints and warns that enforcement varies by provider. Thus strict schema is **advertised and documented**, but its effective enforcement for this exact model, endpoint and schema remains untested. Sources: [DeepInfra structured outputs](https://docs.deepinfra.com/chat/structured-outputs), [OpenRouter structured outputs](https://openrouter.ai/docs/guides/features/structured-outputs); frozen endpoint snapshot: `next_inference_audit/provider_metadata.json`.

Do not claim that the new protocol is already reliable. If the endpoint rejects a schema keyword or returns nonconforming content, stop the technical test. Any change to the schema/contract requires a new version and a new frozen test; do not silently fall back to JSON-object mode. Structured decoding cannot guarantee correct activities or calibrated confidence.

### Label-blind technical validation gate — proposed, not run

Use 12 calls: three input-size profiles × two actual training-only binary cases × two independent repeats. Profiles reproduce short 100-sample input, 500-sample fixed-duration input with references, and approximately the previous full/full context size. Use real contiguous User 1 all-zero and all-one observations, selected by lexicographic source path among eligible recordings, and references exclusively from users 2–7. Their activity labels are hidden for target inference and not consulted to grade this technical test. Do not use users 8–9 or their outcomes to choose a schema.

Freeze all 12 rendered requests and hashes before execution. Pass only if all requests return the pinned provider, stop normally, have plausible complete-input token counts, parse without duplicate keys, and satisfy the three-field contract with no repairs. Score no activity accuracy and optimize no prompt on correctness. Record latency, cost and every attempt. A context overflow, authentication failure or incompatible schema stops the gate; no unreported probe or retry. The original long inputs fitted within context, but recheck the current provider and rendered counts.

Twelve successes would be a smoke-test pass, not a low-failure-rate guarantee: under an idealized independent binomial model, zero failures in 12 still permits about a 22.1% one-sided 95% upper failure bound. Real requests are correlated, making that calculation only illustrative. Maintain schema monitoring in the subsequent pilot and report its failures separately. API execution of this gate is not part of the present task.

## B. Temporal-information audit across all five placements

Read-only scope: 915 processed files, 147 training and 36 development-validation files per placement. Source hashes were checked against the existing audit; users 10–11 were not opened. Each file’s transitions/indices, proportion, duration and subject are in [recordings.json](next_inference_audit/recordings.json). “Real” means present in the supplied processed trace; the original detector’s physical mechanism and update rule remain unverified.

| Placement | Training varying files /147 | Training transitions | Validation varying files /36 | Validation transitions |
|---|---:|---:|---:|---:|
| left-ankle | 17 | 34 | 1 | 52 |
| left-wrist | 19 | 44 | 0 | 0 |
| right-ankle | 15 | 21 | 1 | 2 |
| right-pocket | 17 | 30 | 0 | 0 |
| right-wrist | 18 | 62 | 7 | 46 |

Validation variation is concentrated: left ankle is User 9 Standing; right ankle is User 8 Standing; right wrist is User 9 Downstairs and Walking. Left wrist and right pocket have no evaluation transitions. A large number of stair segments from one person is not independent cross-user evidence. Positive shake output in nominally static activities also means the bit-to-motion-group mapping is not universal across placements.

### Duration-controlled observations

Use complete nonoverlapping 500-sample (10-second) windows within uninterrupted files; no padding, resampling, joining or gap filling. Retain constant as well as varying windows. All 36 evaluation files per placement contribute, and 142/147 training files contribute; five short training stair files per placement are excluded by the duration requirement. Tails are dropped, and exact retained/total samples are saved in temporal_baselines.json. “Matched duration” means equal-length contiguous recording intervals, not complete natural-length files. It changes coverage and the task unit and cannot be presented as full-recording inference.

| Placement | Evaluation windows | Varying windows | Where variation occurs |
|---|---:|---:|---|
| left-ankle | 376 | 17 | subjects {'9': 17}; activities {'Standing': 17} |
| left-wrist | 372 | 0 | subjects {}; activities {} |
| right-ankle | 373 | 1 | subjects {'8': 1}; activities {'Standing': 1} |
| right-pocket | 372 | 0 | subjects {}; activities {} |
| right-wrist | 372 | 17 | subjects {'9': 17}; activities {'Downstairs': 14, 'Walking': 3} |

### Simple cross-user baselines and controls

No Qwen calls or agent-directed model search were used. Methods were fixed before computing these results. Fit/access only users 1–7, predict users 8–9; additionally leave each training user out in turn to examine consistency without tuning on validation.

- **Count-only:** nearest training interval by absolute difference in proportion of ones.
- **Ordered:** nearest training interval by normalized Hamming distance of the ordered 500-bit sequence. For efficiency we use ten consecutive 50-sample block values; every block was verified constant in every analyzed window, so this representation is lossless here and the distance equals raw-bit Hamming distance.
- **Order-disrupted target:** keep training examples chronological; independently permute the ten target blocks using a stable seed derived with 2026. Every bit and the total length/count are preserved. A random permutation can occasionally leave a pattern unchanged; this exploratory baseline does not condition on changed order. Constant inputs are necessarily invariant.
- **Ties:** vote among all nearest intervals, dividing each class vote by its training class count; remaining ties use the fixed seven-class order. This is a predeclared class-balanced nearest-neighbor rule, not the different first-match rule used in earlier reports. No parameters are tuned. All methods share the same tie rule and training partition.

| Placement | Count accuracy | Ordered accuracy | Disrupted-target accuracy | Count macro-F1 | Ordered macro-F1 |
|---|---:|---:|---:|---:|---:|
| left-ankle | 32.18% | 32.18% | 32.71% | 0.1544 | 0.1530 |
| left-wrist | 31.18% | 31.18% | 31.18% | 0.1362 | 0.1362 |
| right-ankle | 31.37% | 31.10% | 31.10% | 0.1411 | 0.1359 |
| right-pocket | 31.18% | 31.18% | 31.18% | 0.1362 | 0.1362 |
| right-wrist | 34.68% | 31.18% | 31.18% | 0.2071 | 0.1369 |

Confusion matrices, balanced accuracy, equal-recording summaries, varying-window scores and subject-specific results are saved in [temporal_baselines.json](next_inference_audit/temporal_baselines.json). These are window-weighted descriptive scores on repeated observations, not independent trials or population significance tests.

The clearest difference is right wrist: count-only gets 34.68%, versus 31.18% ordered. On its 17 varying windows, count-only recognizes 13/17 whereas ordered recognizes 0/17. That is evidence of a reusable marginal-value association for this small development sample, not of useful chronological order. At left ankle, count and order tie at 32.18%; disruption slightly raises accuracy to 32.71%, so this perturbation does not establish an order advantage. Right ankle has one varying interval and ordered matching loses that one correct count-only prediction.

| Placement | Training leave-one-user-out ordered-minus-count accuracy, percentage points (users 1–7) |
|---|---|
| left-ankle | +0.00, +0.00, +0.00, -0.54, +0.00, +0.00, -0.52 |
| left-wrist | +0.00, +0.00, +1.08, +0.55, +0.00, -1.09, -0.53 |
| right-ankle | +0.00, +0.00, -0.54, +0.00, +0.00, -0.54, +0.00 |
| right-pocket | +0.00, +0.00, -0.54, +0.00, -0.52, -0.54, +0.00 |
| right-wrist | +0.00, +0.00, +0.53, +0.00, -1.03, +0.00, +0.00 |

Order effects are small, mixed or negative across training users. This, together with validation concentration in one person/class, does not support a stable temporal signature. A simple matcher’s failure is not an information-theoretic impossibility result; different regularized models or more data could reveal reusable structure. We did not search models until one beat the count baseline.

Empirical pattern bounds tell the same limited story: at 10 seconds, only right wrist has an ordered-pattern bound above its count bound (35.75% versus 34.95%, about 0.81 points). These label-aware finite-sample bounds can exploit singleton patterns and are not held-out attacker scores. At the other placements ordered and count bounds coincide in this validation set.

### Duration and acquisition artifacts

Across placements, stair files range roughly 3.58–54.96 seconds while most other activities last about 300 seconds. Exact export lengths differ slightly by placement and person. A full-file length-only nearest-neighbor rule using training files, with the same class-balanced tie rule, produces:

| Placement | Full-file duration-only accuracy |
|---|---:|
| left-ankle | 55.56% |
| left-wrist | 36.11% |
| right-ankle | 38.89% |
| right-pocket | 44.44% |
| right-wrist | 41.67% |

These scores use 36 whole files and are not directly comparable to the 10-second window scores. They establish that incidental acquisition duration is predictive enough to require a control, not that duration is a general activity property. Five-minute recordings and separately segmented stairs encode collection practice. Early detector changes and the one-second holding grid may also reflect initialization, segmentation or export behavior; they should not be interpreted as gait rhythm without provenance.

| Information source | What this audit supports | What it does not establish |
|---|---|---|
| Bit value / proportion | Coarse motion-related associations and some cross-user recognition on varying right-wrist windows | Unique seven-class recognition |
| Temporal order | Real changes exist in source files; a small empirical order-only separation at right wrist | Consistent held-out gain beyond bit count |
| Duration | Strong class-associated acquisition lengths; nontrivial length-only prediction | Natural activity dynamics |
| Other artifacts | Segment structure, held outputs, sparse startup changes and subject concentration | A documented causal detector mechanism |

## C. Concrete next direct-LLM experiment

**Recommendation: after the 12-call technical gate passes, run a 40-request diagnostic panel across the five predeclared placements.** This is an exploratory test of observation use under a reliable contract, not a confirmatory claim of temporal privacy leakage. No placement is chosen by Qwen scores or by winning the classical baseline comparison. Keep the limited interfaces as controls rather than discarding them.

### Frozen proposed selection

Use the 500-sample window manifest already audited. For each placement select one constant-zero interval from User 8 and one constant-one interval from User 9, by the lowest SHA-256 key of source path, offset and fixed selection seed 49. Add up to two varying evaluation intervals, prioritizing distinct recordings, then fill from the same recording if necessary, with the same hash rule. Selection depends on observable variation and provenance, never Qwen scores or target correctness. No hidden target labels enter the prompts. This produces 15 targets: ten constant controls and five varying intervals. It is intentionally variation-enriched and not prevalence-representative.

| Placement | Varying proposed target: subject / activity / start sample (evaluator only) |
|---|---|
| left-ankle | User 9 / Standing / 11000; User 9 / Standing / 9500 |
| left-wrist | None; constant controls only |
| right-ankle | User 8 / Standing / 11000 |
| right-pocket | None; constant controls only |
| right-wrist | User 9 / Downstairs / 500; User 9 / Downstairs / 0 |

Exact paths, offsets and bits-by-50-sample-block are frozen in [proposed_pilot_selection.json](next_inference_audit/proposed_pilot_selection.json). The two right-wrist selections happen to be Downstairs, and the ankle variations are Standing; do not generalize to seven-class coverage or independent participants. Source files may share sessions. All targets remain subject-disjoint from users 1–7 references, but this is development reuse.

For each placement, provide nine labeled 500-sample references. First include seven class-covering examples: class i uses User i+1 and the first eligible interval of the lexicographically first file. These seven happen to be constant at every placement, so alone they could not teach an order-sensitive pattern. Add two genuinely varying training intervals from distinct training subjects using the same fixed hash rule. This explicit variation enrichment is declared in advance and independent of model performance. It introduces unequal reference class counts; report the exact label counts and keep the same nine examples and order for both target-order conditions. Do not infer population priors from that curated set.

| Placement | Two additional varying references: subject / activity |
|---|---|
| left-ankle | User 7 / Standing; User 3 / Laying |
| left-wrist | User 7 / Downstairs; User 3 / Standing |
| right-ankle | User 7 / Upstairs; User 4 / Upstairs |
| right-pocket | User 7 / Upstairs; User 5 / Standing |
| right-wrist | User 3 / Sitting; User 7 / Standing |

These references are independent contiguous intervals from genuine recordings, not reconstructed whole files or concatenated sessions. No filename, participant ID, offset, source duration, stratum name, sample statistics or baseline prediction is supplied to Qwen. Every target and reference contains exactly 500 actual bits, serialized as lossless bit strings. Full acquisition duration is therefore hidden, while fixed 10-second interval duration is shared.

### Chronological versus order-disrupted control

For each of the five varying targets compare its original chronological 500 bits with a permutation of its ten real 50-sample blocks. References remain identical and chronological. Use seed 50 with a logged deterministic request/target order; redraw a permutation until the binary sequence differs from the original, with a fixed finite cap and explicit failure if no change is produced. Check length, total ones, block multiset and sample provenance byte-for-byte. Do not insert bits, join different activities, or shuffle across recording boundaries. The altered target is a diagnostic order manipulation, not a naturally recorded chronology; no new physical event is claimed.

Count-only baselines must be exactly invariant to this manipulation. Block shuffling preserves the observed one-second hold structure but changes adjacency, run lengths and onset positions together. Therefore a difference measures sensitivity to that order manipulation, not a uniquely identified physiological mechanism. Do not give a condition flag, “shuffled” hint or expected answer to Qwen; the prompt says the values are supplied in observation order, which avoids falsely asserting that every control is chronological.

Each varying target gets two orders × two independent repeats = 20 requests. Each of ten constant controls gets two repeats = 20 requests; a shuffled constant target is identical, so omit redundant calls. **Total 40 research requests**, plus the separately reported 12-call technical gate = 52 planned calls if both stages are later authorized. No automatic expansion. Repeats measure response variability, not additional people.

### Fixed prompt and outputs

System:

```text
Infer the hidden activity of the target participant using only the supplied binary observations, sensor information and labeled references from other participants. References are independent observations and do not continue the target. Identical observations may be compatible with several activities. Return only the JSON object specified by the response schema.
```

User template:

```text
Sensor: IMU with accelerometer and gyroscope channels. Placement: {PLACEMENT}. Only the shake/no-shake binary output is visible; raw sensor channels are unavailable. Export interval is 0.02 seconds, which does not establish the detector decision frequency. 0 means no shake detected; 1 means shake detected. These values do not directly measure amplitude, cadence or a unique activity. Detector thresholds and internals are not supplied.

Encoding: each character in a binary_sequence string is one sample. Each object is a separate observation with its own boundary. Read each string in the supplied observation order.

Labeled observations from other participants:
{REFERENCE_JSON}

Unlabeled target observation:
{TARGET_JSON}

Candidates: Downstairs, Jogging, Laying, Sitting, Standing, Upstairs, Walking.
Predict the activity assigned to the target interval. Return only predicted_activity, confidence, and sufficient_information as required by the strict response schema. Confidence concerns the exact activity, not the motion group. Acknowledge insufficient distinguishing information through sufficient_information=false; still choose one candidate. No explanation or extra fields.
```

Reference objects contain only activity and binary_sequence. The target object contains only binary_sequence. No classifier outputs or derived features enter this prompt. With nine 500-bit references plus one target, raw digit tokens total 5,000 under the audited tokenizer; rendered framing adds overhead and must be counted exactly before execution. The three-field answer and provider settings follow v2.0, frozen only after the technical gate. All requests are stateless and condition order is counterbalanced.

### Evaluation and interpretation

Report accuracy, macro-F1 over all seven names with supports, balanced accuracy over represented labels, confusion, motion group, confidence, sufficiency and schema failures. Report varying targets separately from constant controls and each placement separately. Use matched paired class changes under the order manipulation and repeat consistency, not a pooled significance test on 40 calls. Sparse class coverage and shared participants make macro-F1 unstable; include individual predictions and exact class supports.

Recompute count and ordered baselines using exactly the same nine supplied references; the larger training-pool audit is not access-matched to this pilot. No baseline generates Qwen predictions. Compare whether Qwen distinguishes targets beyond count-based equivalence groups, and whether order effects are reproducible. Any improved score on one label or one participant is hypothesis-generating. An order effect on output without a consistent improvement in held-out correctness is sensitivity, not information extraction.

Primary inference contains no explanations. A later independently authorized explanation audit may use a predeclared sample, but cannot retroactively validate reasoning or affect predictions. Do not run a judge or planner loop. If formatting failures persist, report the contract failure and defer scientific comparisons rather than extending the sample until convenient.

## Why this advances the research question

The technical gate tests whether answers can be measured consistently without confusing a misspelled explanation key with an activity error. The small panel then gives Qwen real varying observations and real labeled variation from other people, at a common duration, alongside constant controls. This tests whether behavior reflects marginal bit information, order sensitivity, or unstable guessing while removing acquisition length from the target.

A positive temporal-inference claim would still require more independent subjects/sessions and broader activities, consistent gains over count controls, and a newly held-out evaluation. The present dataset does not yet supply robust evidence for that claim. A null result is useful if it distinguishes unreliable output formatting from limited information or failure to use variation. The next recommended action is the 12-call label-blind protocol gate, followed conditionally by the frozen 40-call diagnostic—not another full-recording sweep, model search or fine-tuning campaign.

## Artifacts and preservation

Offline analysis: `scripts/audit_next_inference.py`; report rendering: `scripts/report_next_inference.py`; schema/local validator: `inference_protocol_v2.py`. Audit artifacts include per-response failures, 915 recording summaries, exact 10-second window manifests, per-subject leave-one-out baselines, source-preservation hashes, provider metadata and proposed target/reference selection. All prior data/run files are hash-checked unchanged. No inference runner was added for v2 and no new model output was obtained.

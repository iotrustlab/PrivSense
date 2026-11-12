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

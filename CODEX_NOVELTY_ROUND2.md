# PolyGuard — second-round research recommendations

## Ranked shortlist

| Rank | Feature | Novelty | Effort |
|---|---|---:|---:|
| 1 | **Model Disagreement Sentinel** | Very high | 1–2 days |
| 2 | **Conformal Severity Sets** | Very high | 1–2 days |
| 3 | **Minimal Unsafe Subset Certificate** | High | 1–2 days |
| 4 | **Knowledge-Horizon / Temporal Challenge Test** | Very high | 2–4 days |
| 5 | **Directional Label Evidence: perpetrator → victim** | High | 3–5 days |

These exploit what PolyGuard uniquely possesses—multiple independently built models, real calibration data, multi-drug inference, and mechanism evidence—instead of attaching a fashionable foundation model without a defensible role.

---

## 1. Model Disagreement Sentinel

### What it is

Repurpose the “failed” chemistry and GNN models as **independent error detectors**, not production predictors.

For each pair, compare:

- TF-IDF severity distribution
- Morgan chemistry model distribution
- GNN distribution
- mechanism-evidence tier
- documented versus undocumented status

Produce a disagreement state such as:

> **Models disagree strongly**  
> Lexical model: Major 0.81  
> Chemistry model: Minor 0.57  
> Graph model: Moderate 0.49  
> Similar historical disagreements were correct only 42% of the time. Review externally.

Calibrate this on the existing held-out set: partition examples by disagreement score—Jensen–Shannon divergence, vote entropy, top-class mismatch—and measure actual error in each bin. Abstain or elevate review only if disagreement empirically predicts error.

### Why it is genuinely rare

Most projects hide weaker models or ensemble them indiscriminately. PolyGuard can make a much stronger research statement:

> Models that lose on aggregate can remain valuable as epistemic sentinels because they fail differently.

That converts the negative-result work into a live safety mechanism. It is considerably more distinctive than merely publishing the negative results on a model-card page.

### Feasibility

Very high. All models and test predictions already exist. No GPU or new training is required.

The key experiment is:

1. Save each model’s probability vector on the identical held-out examples.
2. Compute disagreement features.
3. Test whether error rate rises monotonically with disagreement.
4. Bootstrap confidence intervals.
5. Ship only if it adds information beyond Model 1 confidence and coverage.

A logistic regression predicting “Model 1 is wrong” from disagreement, confidence, coverage, and evidence tier would remain interpretable and CPU-cheap.

### App/report manifestation

- New Evidence Passport row: **Cross-model agreement**
- “Why escalated?” panel showing the conflicting model families
- Reliability plot: Model 1 confidence versus accuracy, split by agreement/disagreement
- Paper section: **Negative models as positive safety infrastructure**

This is the strongest “I have not seen a student project do that” candidate.

---

## 2. Conformal Severity Sets

### What it is

Upgrade single-label prediction and heuristic abstention into a **set-valued result with a measurable coverage target**.

Instead of:

> Moderate — 61%

show:

> **Plausible severities at 90% target coverage: {Moderate, Major}**

Easy cases produce singleton sets; ambiguous cases produce two or three labels. Use class-conditional or Mondrian conformal prediction so the majority class does not obtain good coverage at the expense of rare Major interactions.

This is conceptually different from the current reliability band:

- Calibration asks whether “0.8” corresponds to roughly 80% correctness.
- Conformal prediction constructs a set intended to contain the true class at a stated marginal error rate, under exchangeability assumptions.

Recent clinical work is increasingly using conformal prediction for individualized uncertainty, including a 2025 *npj Digital Medicine* study and recent drug-target interaction research. [npj Digital Medicine](https://doi.org/10.1038/s41746-025-01616-z), [PMLR drug-target study](https://proceedings.mlr.press/v266/rakhshaninejad25a.html)

### Why it is genuinely rare

Commercial DDI interfaces normally display one categorical severity. Even research demos commonly stop at confidence bars. A doctor-facing DDI checker that says **“the evidence supports this set of severities, not a single forced answer”** is unusually honest.

The rare part is not merely implementing conformal prediction; it is presenting:

- target coverage,
- observed held-out coverage,
- set size,
- subgroup coverage for documented/undocumented and warm/cold drugs,
- the exchangeability limitation.

### Feasibility

Very high. Split conformal or APS/RAPS can be placed over the existing three-class probabilities with little code and no retraining.

Use the untouched calibration portion only. Report:

- overall coverage;
- class-conditional coverage;
- average set size;
- coverage for documented versus undocumented pairs;
- coverage on the drug-disjoint cold-start split.

Do not claim a guarantee for future hospital traffic unless its distribution is exchangeable with calibration data.

### App/report manifestation

A compact safety card:

> **90% target set:** Moderate or Major  
> Held-out coverage: 90.8% overall; 88.1% for Major  
> Wide set because the case resembles few calibration examples.

Allow an educational toggle between 80%, 90%, and 95% target coverage so users can visibly explore the certainty–specificity tradeoff.

---

## 3. Minimal Unsafe Subset Certificate

### What it is

For a 3–5 drug regimen, identify the **smallest subsets that produce the warning** and quantify how stable that attribution is.

Example:

> Regimen risk: High  
> Minimal warning-producing subsets:
>
> - Warfarin + aspirin  
> - Warfarin + amiodarone
>
> Removing metformin does not materially change the model signal.  
> This is a model counterfactual, not a recommendation to discontinue medication.

For HODDI, enumerate every subset—only 31 nonempty subsets exist for five drugs—and calculate:

- pair and subset scores;
- leave-one-drug-out change;
- minimal subsets crossing the warning threshold;
- whether higher-order risk remains after accounting for all risky pairs;
- optional exact Shapley values, feasible at this regimen size.

### Why it is genuinely rare

A graph visualizer shows where edges are; it does not answer:

> Which exact combination is responsible, and is the multi-drug warning reducible to one pair?

A **minimal unsafe subset certificate** turns regimen inference into an auditable claim. It can expose genuine higher-order effects:

> No pair is individually high-risk, but the {A, B, C} subset crosses the threshold.

That directly leverages PolyGuard’s unusual multi-drug model and goes well beyond conventional pairwise checkers.

### Feasibility

High. Exhaustive enumeration is trivial for at most five drugs. The important validation is testing stability across bootstrap-trained HODDI models or modest input/model perturbations. If retraining several models is impractical, label it a deterministic model counterfactual and omit stability claims.

### App/report manifestation

Use an ordered subset table rather than only a node-link diagram:

| Subset | Risk | Change from full regimen | Evidence |
|---|---:|---:|---|
| Warfarin + aspirin | High | −0.04 | Documented |
| Warfarin + amiodarone | High | −0.09 | Mechanism |
| Aspirin + metformin | Low | −0.41 | None |

This could become the analytical layer behind the proposed graph visualizer: selecting a subset highlights its responsible edges and evidence.

---

## 4. Knowledge-Horizon / Temporal Challenge Test

### What it is

Give every result an explicit **knowledge timestamp** and test the system against evidence that appeared after its training cutoff.

Build a small temporal benchmark:

1. Freeze the interaction dataset at date \(T\).
2. Train or retain PolyGuard using only pre-\(T\) knowledge.
3. Collect newer FDA Structured Product Label interaction changes.
4. Ask whether PolyGuard predicted, abstained on, or confidently contradicted these later additions.
5. Present those cases as prospective-style “future evidence challenges.”

FDA Structured Product Labels are especially useful because label text is dated and safety-oriented. PVLens demonstrated in 2025 that automated extraction from these labels can refresh static drug-safety resources. [PVLens paper](https://arxiv.org/abs/2503.20639)

### Why it is genuinely rare

Random held-out splits can reward memorization of historical documentation patterns. A knowledge-horizon test instead asks:

> What happened when the world learned something after the model’s evidence cutoff?

Few student systems make the model’s historical boundary visible, and fewer use later regulatory evidence to challenge it. It complements cold-start testing without requiring patient data.

### Feasibility

Medium-high if kept to a curated benchmark of 20–50 label changes rather than attempting continuous global surveillance.

Record extraction provenance:

- label/document identifier;
- publication or revision date;
- exact supporting section;
- normalized drug names;
- reviewer-confirmed interaction direction and severity.

### App/report manifestation

- “Evidence current through: YYYY-MM-DD”
- Badge: **Post-training evidence exists**
- Timeline comparing dataset evidence, model version, and label revision
- Report metric: recall, abstention rate, and dangerous-confident-error rate on post-cutoff additions

This is stronger than saying the dataset is “up to date”; it makes aging knowledge measurable.

---

## 5. Directional label evidence: perpetrator → victim

### What it is

For pharmacokinetic interactions, represent direction explicitly:

> Clarithromycin **inhibits CYP3A4** → increases simvastatin exposure  
> Perpetrator: clarithromycin  
> Object/victim: simvastatin  
> Expected direction: exposure ↑

A severity-only symmetric edge—A interacts with B—loses this operationally important structure. FDA researchers are actively developing biomedical NLP for extracting **directional PK DDIs**, distinguishing precipitant and object drugs. [FDA research page](https://www.fda.gov/drugs/regulatory-science-action/deep-learning-enabled-natural-language-processing-identify-directional-pharmacokinetic-drug-drug)

Implement a small evidence extractor over selected FDA/DailyMed label sections. It should populate a fixed schema, not generate open-ended clinical advice:

```json
{
  "perpetrator": "clarithromycin",
  "object": "simvastatin",
  "mechanism": "CYP3A4 inhibition",
  "effect_direction": "exposure_increase",
  "source_span": "...",
  "source_document": "...",
  "review_status": "human_verified"
}
```

### Why it is genuinely rare

Many DDI knowledge bases contain direction internally, but student-facing checkers and graph visualizations usually render undirected severity edges. Combining directed regulatory evidence with calibrated model uncertainty and KG mechanisms creates an unusually rich distinction:

- model predicts that an interaction may exist;
- KG suggests a mechanism;
- label text establishes whether regulatory evidence identifies a perpetrator and victim.

### Feasibility

Medium. Avoid training a new generative model. Begin with:

- label-section retrieval;
- drug-name normalization;
- rule-based patterns for “increases/decreases exposure,” inhibition, induction and contraindication;
- optional BioClinical NER or a constrained API extraction;
- mandatory displayed source span and manual verification for the demo set.

The 2025 open-weight **TxGemma** family includes 2B models specialized on Therapeutics Data Commons tasks, but it was designed primarily for therapeutic property tasks—not validated DDI label extraction. Use it only as a benchmark experiment, never as evidence by itself. [TxGemma documentation](https://developers.google.com/health-ai-developer-foundations/txgemma)

---

## Worthwhile sixth idea: safety-gated, private voice regimen entry

A low-tech-literacy feature with a genuinely technical safety twist:

1. Doctor speaks the regimen.
2. Small speech recognition runs locally in-browser.
3. Drug candidates are matched against the 1,902-drug vocabulary.
4. Phonetically confusable names are presented as an ambiguity set.
5. Nothing is checked until the doctor explicitly confirms every drug.

> Heard: “Celebrex”  
> Confirm: Celebrex / Celexa / Other

Transformers.js v4, released in February 2026, expanded browser-side WebGPU model support, while ONNX Runtime Web supports WebGPU with WASM fallback. [Transformers.js v4](https://huggingface.co/blog/transformersjs-v4), [ONNX Runtime Web](https://onnxruntime.ai/docs/tutorials/web/)

The novelty is not voice input—it is **never silently resolving a medication-name ambiguity**. Record word confidence, ontology-match distance and confirmation status in the Evidence Passport. This is feasible as a polished prototype, although browser/device performance must be tested and typed entry must remain available.

---

## Recent technology: what is and is not worth adding

### Useful now

- **Class-conditional conformal prediction:** directly strengthens the current abstention system.
- **Transformers.js v4/WebGPU:** useful for private speech/NER or offline lookup, not for moving the main classifier into the browser merely for novelty.
- **Directional FDA-label extraction:** adds a new evidence type and asymmetric causal structure.
- **Guided deferral:** instead of only saying “insufficient evidence,” tell the doctor what is missing—verify spelling, check renal context externally, consult a pharmacist, or inspect the cited label. Recent work frames this as guided clinical deferral rather than generic abstention. [AAAI 2025](https://ojs.aaai.org/index.php/AAAI/article/view/35063)

### Interesting but poor fit

- **MedGemma 1.5 4B:** current and medically specialized, but its 2026 improvements emphasize medical text and high-dimensional imaging rather than validated DDI inference. It would add deployment weight without addressing PolyGuard’s central evidence problem. [Google HAI-DEF release history](https://developers.google.com/health-ai-developer-foundations/blog)
- **TxGemma as a new primary predictor:** scientifically interesting, but likely GPU/cloud-dependent and requires an identical-split benchmark before it deserves any UI role.
- **Large BioNeMo/drug-discovery models:** optimized for molecular discovery workflows, not short-turnaround clinical DDI checking; generally mismatched to the CPU-only constraint.
- **An on-device LLM narrator:** technically flashy but weaker than the already-considered citation-locked narrator and harder to validate.

---

## Assessment of the four proposed ideas

1. **Interaction graph:** visually useful, but not novel by itself. Upgrade it with minimal unsafe subsets and higher-order-only risk highlighting.
2. **Safer alternatives:** highest clinical-risk proposal. “Same class” does not imply patient-specific substitutability. If retained, call it a **comparison explorer**, require direct interaction evidence for every candidate, and never rank or recommend a replacement.
3. **Transparency page:** worth shipping because it is cheap and honest, but it is supporting infrastructure, not the headline novelty.
4. **PDF export:** valuable product polish and should include model version, evidence date, abstentions and disclaimers, but it adds little research novelty.

## Best final package

For a days-long course-project push, build:

1. **Model Disagreement Sentinel**
2. **Conformal Severity Sets**
3. **Minimal Unsafe Subset Certificate**
4. Add the transparency page to expose their real held-out evaluation

The resulting research story is unusually coherent:

> PolyGuard does not merely explain predictions or display confidence. It uses independently failing models to detect epistemic conflict, returns statistically calibrated sets instead of forced labels, and produces auditable certificates identifying the smallest regimen subsets responsible for multi-drug warnings.

That is technically serious, achievable without patient data or GPUs, and substantially rarer than adding another biomedical foundation model.
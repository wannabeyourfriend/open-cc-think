# Datasheet: cot-recovery v1.0.0

Following Gebru et al., *Datasheets for Datasets* (2021).

Built by `scripts/build_cot_recovery_dataset.py` from `experiments/h1b-scenario-gathering/`.
The build is deterministic: rebuilding on unchanged inputs reproduces byte-identical checksums.

---

## Motivation

**Why was this dataset created?** To answer whether replaying a signed `reasoningContent` state with
its unchanged prior messages recovers a model's hidden internal working, or merely a paraphrase of
the provider's visible summary. That question is the reason this repository exists, and it had no
corpus with exact denominators. Prior evidence was a handful of exploratory runs selected after the
fact for having succeeded.

**What gap does it fill?** Existing collections of recovered reasoning — including the sibling
`open-reasoning/examples` — are curated success sets. Inclusion there means recovery worked, so they
have no denominator and cannot yield a rate. This dataset records **every** decision attempted,
including the failures, refusals, and censored observations.

**Who funded/created it?** Produced by the repository's autoresearch program, run H1b-gathering-v1.

---

## Composition

**What do instances represent?** Three record types, in three files:

| File | Rows | Unit |
| --- | --- | --- |
| `decisions.jsonl` | 226 | One model decision step — the unit of analysis |
| `instances.jsonl` | 135 | One task instance (a harvest + replay episode) |
| `controls.jsonl` | 8 | Synthetic H1a falsification cases, never pooled with live rows |

**How many, and how are they composed?** 45 tasks × 3 independent replicates = 135 instances. An
instance may contain several decisions, giving 226 decisions: **192 signed, 34 unsigned (15.0%)**.

| Scenario | Tasks | Instances | Signed decisions | Source |
| --- | --- | --- | --- | --- |
| complex_conversational_qa | 15 | 45 | 76 | MT-Bench, two-turn, non-code/math/reasoning categories |
| math_reasoning | 15 | 45 | 39 | GSM8K train split |
| agentic_coding | 15 | 45 | 77 | Checked-in deterministic code-repair fixtures |

**Is it a sample or complete?** Complete for the run: 135/135 instances, 0 failed. Tasks were drawn
by frozen deterministic ranking (SHA-256 of a seed and source ID), excluding every source ID already
in `src/calibration/fixed-36.json`.

**What data does each instance contain?** The step's prompt, the provider's reasoning summary, the
visible answer, tool calls, billed token usage, the extraction prompt candidate, the full recovered
text, all frozen v0 metrics, and derived labels and evidence tiers.

**Is there a label or target?** No ground truth exists, and that is the central limitation. There is
no independent channel to the provider's plaintext, so no row can be verified as a true recovery.
`evidence.outcome` is a *graded judgement under a named metric*, not a label. The claim ceiling is
"signature-backed full-span recovery candidate."

**Is any information missing?** Yes, by design:

- **Raw signatures are excluded.** They are replayable state. Only `signature_sha256` and
  `signature_chars` are retained. This means the dataset is *not* sufficient to re-run the replays;
  that requires the ignored `.checkpoints/`.
- **34 decisions have no extraction** because the provider returned no adaptive-thinking block.
  These are censored observations, not errors, and stay in the denominator.
- No hidden content anchors were planted, so H1a's ordered-anchor fidelity test cannot be applied
  to any live row.

**Are there errors or redundancies?** The three replicates per task are intentional repetition, for
stability measurement. Metrics are reproduced verbatim from the frozen scorer including its known
defects (below), rather than silently corrected.

**Does it contain confidential or offensive content?** No. Sources are public benchmarks and
checked-in fixtures. No personal data. Security-sensitive prompts were not collected.

---

## Collection process

**How was the data acquired?** Live calls to `global.anthropic.claude-sonnet-5` over Amazon Bedrock
Converse, at high reasoning effort with summarized thinking display, on 2026-07-16/17 over 53
minutes. Each instance: harvest the task with boundary markers instructed into the internal working,
then replay each signed step blind — the provider summary is withheld from the replay context — with
a single non-optimized extraction prompt (`mechanical_boundary_xml_v2`, used for all 192 signed
decisions; no prompt optimization has been run).

**Sampling strategy.** Frozen deterministic ranking before collection, so task selection cannot be
influenced by results. The protocol was committed before the run.

**Who collected it?** Automated runner (`scripts/gather_scenarios.py`), resume-safe, writing atomic
progress after every instance, halting on signature leakage or three consecutive provider failures.

**Ethical review.** None required; no human subjects, no personal data.

---

## Preprocessing / cleaning / labeling

**What was done?** The build reshapes checked-in artifacts and adds derived fields. It does not
alter any metric.

Derived:

- `harvest.est_thinking_tokens = billed_output_tokens − visible_text_tokens_est − tool_arg_tokens_est`,
  at 4 chars/token. Bedrock bills `outputTokens` **inclusive of visible text**, so the raw field
  overstates thinking — for conversational QA the visible answer alone is up to 979 tokens. Used for
  selection only, never for scoring.
- `labels.denial_detected`, from a broader lexicon than the frozen `REFUSAL_MARKERS` list.
- `evidence.tier` and `evidence.outcome`.

**Is the raw data available?** Yes — `experiments/h1b-scenario-gathering/results/gathering-v1/public/`
is the source of record and remains unmodified.

---

## Uses

### The one number not to quote

Pooling `labels.strong_recovery_v0` over all signed decisions gives **91/192 = 47.4%**. It is an
instrument artifact. Four independent defects produce it:

1. **Canary echo.** Every extraction prompt interpolates the boundary markers, so `markers_in_order`
   is satisfiable by echoing them. Nine "strong" rows are denials that quote the markers back.
   Boundary canaries carry **no provenance information** in this release.
2. **Refusal undercount.** The frozen substring list missed 10 refusals.
3. **No dynamic range below the floor.** 127 decisions bill under 500 estimated thinking tokens.
   Their recoveries are re-derivations; a math "recovery" reading `36 * 0.75 = 27 / 27 - 16 = 11`
   scores strong. Median expansion is 0.483 (math) and 0.500 (coding) — the recovery is *half the
   summary*.
4. **Permissive gate.** `distinct_from_summary` accepts `novelty >= 0.12` alone, so short
   differently-worded text passes without ever exceeding the summary.

### The recommended filter

```python
import json
rows = [json.loads(l) for l in open("data/cot-recovery/v1/decisions.jsonl")]
ready = [r for r in rows if r["evidence"]["analysis_ready"]]   # 13 of 226
```

`analysis_ready` = signed **and** canary intact **and** estimated thinking ≥ 500 tokens. Denials are
*kept* — a refusal on a long-CoT step is a real observation and belongs in the denominator.

Outcome on those 13: **1 plausible recovery, 10 denials, 2 truncated collapses.** The honest
denominator for a full-span claim from this run is **1/13**, or 1/29 before excluding leakage.

The single plausible row (`gather-chat-14-r01#s1`) recovers 2,195 lexical tokens against a
1,141-token summary from 5,973 estimated thinking tokens: expansion 1.92, full-length ratio 0.77,
n-gram containment 0.02. Its two sibling replicates harvested comparable spans (5,656 / 5,069) and
recovered 95 and 96 lexical tokens — a 23× gap at fixed task and effort. **One case, not
reproducible.**

### Appropriate uses

- Measuring how recovery evidence varies by scenario, decision type, and thinking volume.
- Falsifying candidate metrics against real distributions rather than synthetic controls.
- Stability analysis across the three replicates per task.
- Specifying task selection for a follow-up run.

### Inappropriate uses

- **Never** train on, or label, any `recovered_text` as ground-truth chain of thought. No row is
  verified provider plaintext.
- Never pool with the pre-blinding artifacts in `src/artifacts/`, or with any curated success set
  such as `open-reasoning/examples` — that set has no denominator.
- Never report a recovery rate over all decisions.
- Never optimize extraction prompts against `strong_recovery_v0`; that selects for canary echo.
- Do not treat `protocol_valid` as evidence of recovery. It is a formatting check.

---

## Distribution

Distributed inside this repository. Not published to a dataset hub. Downstream copies must carry the
claim ceiling and must not include raw signatures.

---

## Maintenance

**Owner:** repository maintainer. **Versioning:** semantic; `v1.0.0` is the H1b-gathering-v1 release.
A rerun or a metric change gets a new directory, never an edit in place — `metadata.json` and
`CHECKSUMS.sha256` pin the contents.

**Known future work (H1c).** The defects above are design errors, not bad luck. A successor run must
plant hidden content anchors the extraction prompt never names, select steps by observed thinking
rather than dataset label, keep the harvest instruction from competing with a prose deliverable
(leakage was 0% where the answer is a number, 14% for a patch, 54% for prose), and replace the
refusal substring list.

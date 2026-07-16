# H1a protocol: deterministic recovery-metric falsification

Status: locked before execution
Date: 2026-07-17
Hypothesis: H1
Classification: confirmatory for the predictions below; any new pattern is exploratory

## Question

Can deterministic token-length, summary-containment, and content-anchor diagnostics separate a
known complete synthetic trace from common false-positive transformations that the current
canary-plus-overlap metric may accept?

## Change

Add diagnostic metrics without changing the production `strong_recovery` decision:

- raw `full_length_ratio` and bounded log-symmetric `full_length_alignment`;
- same-tokenizer summary/recovery lexical counts and `summary_expansion_ratio`;
- contiguous summary n-gram containment in the recovery;
- an independent content-anchor scorer reporting precision, recall, order, and corruption.

Add a deterministic script that scores a frozen set of synthetic cases and writes sanitized JSON.

## Frozen cases

The script will use one known complete trace containing:

- both boundary canaries;
- six ordered `COT-ANCHOR-*` values;
- intermediate arithmetic and one explicit correction;
- a compact provider-style summary.

Variants:

1. `exact_full` — complete trace; positive.
2. `partial_prefix` — start and some work, missing later content/end; negative.
3. `summary_copy` — bounded verbatim provider summary; negative.
4. `padded_summary` — bounded verbatim summary plus irrelevant fluent padding; negative.
5. `boundary_only` — only boundary markers; negative.
6. `reordered_anchors` — complete-looking text with two anchors swapped; negative.
7. `corrupted_anchor` — complete-looking text with one altered anchor; negative.
8. `fresh_solution` — correct independent solution without hidden anchors; negative.

## Predictions

- `exact_full` has anchor recall and precision 1.0, ordered anchors, no corruption, and
  `full_length_alignment >= 0.90`.
- `partial_prefix` has `full_length_ratio < 0.65` and fails boundary completeness.
- `summary_copy` and `padded_summary` have summary n-gram containment at least 0.90. Padding must not
  evade this detector.
- `boundary_only` has summary expansion below 0.25 and anchor recall 0.
- `reordered_anchors` fails ordered-anchor accuracy.
- `corrupted_anchor` has recall below 1.0 and nonzero corruption.
- `fresh_solution` has anchor recall 0 even if its answer and prose are plausible.
- The existing live/historical artifact schema remains readable; all existing tests still pass.

## Failure criteria

H1a is refuted or requires redesign if any named negative satisfies all its expected positive
diagnostics, or if the diagnostics break existing artifact/test behavior. Threshold changes after
seeing results must be labeled exploratory and preregistered in a follow-up protocol before becoming
a production gate.

## Outputs

- reusable code in `src/signature_cot/scoring.py` and typed fields in `models.py`;
- regression tests in `src/tests/test_pipeline.py`;
- runner `scripts/calibrate_recovery_metrics.py`;
- raw sanitized table
  `experiments/h1-metric-falsification/results/metric-falsification.json`;
- interpretation in `experiments/h1-metric-falsification/analysis.md`;
- updates to `research-state.yaml`, `research-log.md`, and `findings.md`.

No Bedrock call, raw signature, or model judge is used in this experiment.

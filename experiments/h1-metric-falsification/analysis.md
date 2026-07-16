# H1a analysis: deterministic recovery-metric falsification

Date: 2026-07-17
Result: supported on the frozen synthetic suite
Classification: confirmatory unless explicitly marked exploratory

## Outcome

All 9 preregistered checks passed.

| Case | Expected | Current `strong_recovery` | New diagnostic that caught failure |
| --- | --- | --- | --- |
| `exact_full` | positive | true | All six anchors exact/in order; full-length alignment 1.0 |
| `partial_prefix` | negative | false | Missing end boundary; full-length ratio 0.3611 |
| `summary_copy` | negative | false | Summary 5-gram containment 1.0 |
| `padded_summary` | negative | **true** | Containment 1.0; full-length ratio 2.9583; no anchors |
| `boundary_only` | negative | false | Anchor recall 0; summary expansion 0 |
| `reordered_anchors` | negative | **true** | Ordered-anchor check false |
| `corrupted_anchor` | negative | **true** | Anchor recall/precision 0.8333; corruption 0.1667 |
| `fresh_solution` | negative | **true** | Anchor recall 0; full-length ratio 0.2639 |

The current gate therefore has a synthetic false-positive rate of 4/7. The proposed diagnostic
conjunction—protocol-valid, exact ordered anchors, full-length ratio in 0.65–1.75, summary expansion
at least 1.25, and summary n-gram containment below 0.90—accepts 1/1 positive and 0/7 negatives.
This tiny controlled suite demonstrates separability, not a population error rate.

## Mechanism

The old `token_coverage_proxy` is capped at 1.0. An overlong padded summary therefore receives the
maximum token contribution and reaches quality 1.0, even though its raw length is almost three times
the known full trace. The log-symmetric `full_length_alignment` is 0.338 for that case and 0.3611 for
the partial trace, penalizing overflow and truncation in the same direction.

Sequence similarity and unique-token novelty can be defeated by padding. Contiguous n-gram
containment remains 1.0 because the provider summary is still embedded verbatim.

Length and copy diagnostics cannot detect a reordered or corrupted otherwise complete trace.
Planted content anchors provide that independent fidelity channel. Conversely, anchors alone do not
measure natural reasoning completeness, so they remain metric-calibration evidence rather than
ground-truth CoT.

## Regression checks

- 14/14 unit tests pass.
- Historical audit classifications remain unchanged at 0/14 strong.
- The fresh external `/tmp` artifact now audits successfully after fixing external-root path
  rendering: 1/1 strong candidate, lexical summary/recovery counts 377/1,206, expansion 3.1989,
  summary 5-gram containment 0.0161.
- No production `strong_recovery` threshold changed in H1a.

The external-root audit fix was exploratory because the crash was discovered during execution; it
does not affect metric classifications.

## Interpretation

H1 receives initial support: a defense-in-depth vector catches false positives that the current
metric accepts. The exact thresholds are not frozen for live data. H1b must construct provider-backed
multi-anchor probes and estimate false-positive/false-negative behavior before any new diagnostic
becomes an E4 production gate.

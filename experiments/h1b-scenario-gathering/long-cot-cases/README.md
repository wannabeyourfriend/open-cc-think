# Long-CoT case set (H1b-gathering-v1)

Date: 2026-07-17
Source: `experiments/h1b-scenario-gathering/results/gathering-v1`
Classification: exploratory post-hoc selection from a completed observational run

## Why this set exists

The headline H1b scoring pools all 192 signed decisions and reports 91 strong recoveries (47.4%).
That number is dominated by steps on which the model barely reasoned, where a "recovery" is a
re-derivation and the length ratios are vacuous. The claim under test — signature-backed *full-span*
recovery — is only meaningful on steps that contain substantial hidden working.

This directory isolates those steps and reports what recovery looks like on them.

## Filter

```
est_thinking_tokens = billed outputTokens
                    - ceil(len(visible_text) / 4)
                    - ceil(len(tool_call_args) / 4)

keep if est_thinking_tokens >= 500 AND marker_leakage == false
```

Bedrock Converse bills `outputTokens` inclusive of visible text, so the raw field overstates
thinking; for conversational QA the visible answer alone is ~979 tokens on the largest case.
Subtracting it approximates the hidden span. The 4-chars-per-token estimate is deliberately crude
and is used only for selection, never for scoring.

Leaked steps are excluded because the marker leaking into visible text means the working itself was
written to the visible channel, where the replay can read it out of context. Such a step cannot
evidence hidden-state recovery regardless of what comes back.

## What clears the filter

Thinking volume by scenario (estimated, per signed step):

| Scenario | Median | Max | Steps ≥ 500 |
| --- | --- | --- | --- |
| complex_conversational_qa | 355 | 6,329 | 29 |
| agentic_coding | 112 | 351 | 0 |
| math_reasoning | 66 | 159 | 0 |

Long CoT exists in exactly one scenario. Agentic coding never exceeds 351 estimated thinking tokens
and math never exceeds 159, which is the direct explanation for their six- and twelve-token
"recoveries": there was nothing longer to recover. Their high v0 strong rates (58.4% and 89.7%)
measure task triviality.

Of the 29 conversational-QA steps above the threshold, 16 leaked the canary. **13 cases qualify out
of 192 signed decisions (6.8%).**

## Outcome on the qualifying set

| Classification | n | Meaning |
| --- | --- | --- |
| `plausible_recovery` | 1 | Valid, summary-distinct, not a denial |
| `valid_weak` | 0 | Valid but not summary-distinct |
| `denial` | 10 | Model asserts no such record exists |
| `invalid_truncated` | 2 | Recovery collapses far below the span |

Ten of thirteen are refusals. Where the hidden reasoning is genuinely long, the dominant response to
the extraction prompt is a denial that the working exists — the opposite of the corpus-wide picture,
where short trivial steps happily emit something marker-wrapped.

## The one plausible case

`gather-chat-14-r01-step1` (mt-bench-143, turn 2: lifetime photosynthetic energy of a tree):

| Metric | Value |
| --- | --- |
| Estimated thinking | 5,973 tokens |
| Recovery | 2,195 lexical tokens / 13,443 chars / 5,338 output tokens |
| Provider summary | 1,141 lexical tokens |
| Summary expansion | 1.9238 |
| Full-length ratio | 0.7678 |
| Summary n-gram containment | 0.0202 |
| Summary sequence similarity | 0.3649 |

The recovery is first-person working that tracks the summary's content at much finer grain —
allometric cross-checks, revised biomass estimates, a second solar-irradiance derivation used to
confirm the first — and closes by planning the visible answer's format. This is the same profile as
the exploratory palindrome row that motivated the program: expansion near 2×, full-length ratio
below but near 1, containment near zero.

It is one case in 192 signed decisions, and it is not ground truth. Nothing here establishes that
the recovered text is the provider's plaintext rather than a fluent reconstruction consistent with
the summary.

## The replicate result

Task `gather-chat-14` ran three times against the same question at the same effort:

| Replicate | Est. thinking | Recovery | Expansion | Full-length ratio | Outcome |
| --- | --- | --- | --- | --- | --- |
| r01 | 5,973 | 2,195 tok | 1.9238 | 0.7678 | plausible_recovery |
| r02 | 5,656 | 95 tok | 0.0860 | 0.1033 | invalid_truncated |
| r03 | 5,069 | 96 tok | 0.0932 | 0.0914 | invalid_truncated |

Three independent harvests of the same task produce comparable long hidden spans, and one of the
three recovers ~23× more than the other two. Whatever the successful replay is doing, it is not
reliably reproducible at fixed task and effort. This is the H4 stability question arriving as data
rather than as a plan, and it is the strongest available argument against reading the single
plausible case as a demonstrated capability.

## How to use this set

- These 13 cases, not the 192-decision pool, are the honest denominator for any full-span recovery
  claim from this run. The corresponding rate is 1/13, or 1/29 before excluding leakage.
- Do not pool with the corpus-wide rates in `summary.json`; that pooling is what produced 47.4%.
- The set is far too small and too concentrated (one scenario, one task family) to calibrate a
  threshold. It is a specification for H1c's task selection, not a result.

## Contents

- `index.json` — machine-readable case list with the filter definition and all metrics.
- `cases/<task>-step<N>.md` — one file per case: metrics, the prompt for that decision step, the
  provider summary verbatim, and the full recovery verbatim.

No file here contains a replayable signature; the upstream public artifacts carry only
`signature_sha256`.

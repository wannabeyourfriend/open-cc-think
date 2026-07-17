# H1b analysis: repeated scenario gathering

Date: 2026-07-17
Result: collection complete; corpus does not support the H1b measurement as designed
Classification: prospective observational collection; all downstream patterns are exploratory

## Collection outcome

The run completed its preregistered target with no censoring of the instance denominator.

| Quantity | Value |
| --- | --- |
| Task instances | 135/135 complete, 0 failed |
| Tasks with required replicates | 45/45 (15 per scenario, 3 replicates) |
| Decisions observed | 226 (192 signed, 34 unsigned) |
| Unsigned/censored share | 15.0% |
| Harvest billed output tokens | 134,951 |
| Extraction output tokens | 37,543 |
| Task success | math 44/45; agentic coding 36/45; chat has no success criterion |
| Wall clock | 53 min |

Under the frozen v0 `strong_recovery` gate the corpus scores 110/192 valid and 91/192 strong
(47.4%), with a scenario-macro strong rate of 0.5422.

| Scenario | Signed | Valid | Strong (v0) | Leaked canary | Refused (flagged) |
| --- | --- | --- | --- | --- | --- |
| complex_conversational_qa | 76 | 11 | 11 (14.5%) | 41 (53.9%) | 16 |
| math_reasoning | 39 | 36 | 35 (89.7%) | 0 | 2 |
| agentic_coding | 77 | 63 | 45 (58.4%) | 11 (14.3%) | 0 |

Taken at face value this would read as a positive result. It is not. Four independent defects,
each visible in the collected data, make the v0 strong count uninterpretable as recovery evidence.

## Defect 1: the boundary canary is satisfiable by echo

`score_recovery` derives `markers_in_order` by searching the recovered text for
`step.markers.start` and `step.markers.end`. Every extraction prompt in `DEFAULT_CANDIDATES`
interpolates those exact strings into the replay request. The model is therefore told the canary it
is supposed to prove it recovered, and any output that repeats the two markers in order clears the
`valid` gate regardless of provenance.

The corpus contains the demonstration. Nine of the 91 v0-strong rows are denials that merely quote
the marker names, for example `gather-agentic-coding-15-r02` step 0:

> No working record with the markers COT-START-S00-13C358E119CE / COT-END-S00-13C358E119CE was
> produced in my prior response, so there is no such content to copy.

That row is scored `valid=true`, `strong_recovery=true`, and it also clears the H1a length band.
`REFUSAL_MARKERS` flagged 18 refusals; a broader denial lexicon finds 10 more that the frozen list
misses ("no working record", "was not produced", "i can't complete", "no such content"). The
boundary canary measures instruction-following in the harvest step, never provenance in the replay
step.

## Defect 2: where the instrument works, there is nothing to recover

Billed output tokens per signed step, by scenario:

| Scenario | Median | Min | Max |
| --- | --- | --- | --- |
| math_reasoning | 67 | 20 | 160 |
| agentic_coding | 151 | 64 | 382 |
| complex_conversational_qa | 844 | 97 | 6,952 |

The math tasks are single-step GSM8K arithmetic. `gather-math-01-r01` asks for `36 × 0.75 − 16`,
bills 59 output tokens, and its complete v0-strong "recovery" is:

```
COT-START-S00-C07A088D8867
36 * 0.75 = 27
27 - 16 = 11
COT-END-S00-C07A088D8867
```

The full-length ratio is 1.1017 only because both quantities are near zero. Nothing in that span is
unavailable to a model holding the question and the visible answer `11`; it is a re-derivation, which
is precisely the `fresh_solution` case H1a froze as a negative control. Math's 89.7% strong rate
measures task triviality, not recovery. The same argument covers most agentic-coding steps.

## Defect 3: where thinking is substantial, the harvest instrument fails

Complex conversational QA is the only scenario with reasoning worth recovering, and it is the
scenario the protocol loses. 41/76 decisions (53.9%), spread across 14/15 tasks, leaked the canary
into the visible channel — the model wrote its working, markers included, straight into the answer
instead of into thinking. `gather-chat-01-r03` step 0 begins its visible text at character 0 with
`COT-START-S00-8A068B23B812`. A further 16/76 refused. Eleven usable decisions remain.

Leakage is systematic rather than incidental: it tracks the scenarios whose visible deliverable is
prose, so the harvest instruction competes with the task instruction.

## Defect 4: the length evidence contradicts full-span recovery

Extract-to-summary expansion (`recovered_lexical_tokens / summary_lexical_tokens`) over all signed
decisions with a summary available:

| Scenario | Mean | Median | p25–p75 | ≥ 1.25 | < 1.0 | Median extract vs summary tokens |
| --- | --- | --- | --- | --- | --- | --- |
| complex_conversational_qa | 1.629 | 1.207 | 0.44–2.09 | 36 (47%) | 33 (43%) | 46 vs 34 |
| math_reasoning | 0.610 | 0.483 | 0.40–0.70 | 2 (5%) | 32 (82%) | 12 vs 26 |
| agentic_coding | 0.498 | 0.500 | 0.21–0.63 | 4 (5%) | 68 (88%) | 6 vs 15 |

Conversational QA is the only scenario whose extraction exceeds the provider summary at all, and it
is the scenario lost to leakage. In math and agentic coding the median recovery is roughly *half the
summary*, which is the opposite of the signature the claim requires.

The agentic-coding median is not a shortfall but a stub. `gather-agentic-coding-01-r02` step 0
recovers six lexical tokens:

```
COT-START-S00-156EC8926A01
Let me inspect the workspace first.
COT-END-S00-156EC8926A01
```

against a provider summary that is longer and strictly more informative: "I'm starting by examining
the workspace structure, looking at the window module and its test file to understand what I'm
working with." That row is scored `strong_recovery=true`. Forty-five rows of this kind constitute
agentic coding's 58.4%.

Of the 91 v0-strong rows:

- 82 have `summary_expansion_ratio` below 1.25, with per-scenario medians of 0.562 (coding), 0.447
  (math), and 0.889 (chat). A ratio below 1.0 means the recovery is *shorter in lexical tokens than
  the provider summary it is supposed to exceed*.
- 32 have `full_length_ratio` below 0.65, and 8 exceed 1.75.

`distinct_from_summary` passes these rows because it accepts `novelty >= 0.12` alone, so a short
recovery written in different vocabulary — arithmetic notation against a prose summary — clears the
gate without ever being longer than the summary.

Applying the H1a diagnostic band that is available here (protocol-valid, full-length ratio 0.65–1.75,
summary expansion ≥ 1.25, n-gram containment < 0.90) collapses the corpus:

| Scenario | v0 strong | H1a band |
| --- | --- | --- |
| complex_conversational_qa | 11 (14.5%) | 3 (3.9%) |
| math_reasoning | 35 (89.7%) | 1 (2.6%) |
| agentic_coding | 45 (58.4%) | 1 (1.3%) |
| **Total** | **91 (47.4%)** | **5 (2.6%)** |

Two of those five are the quoted denials from Defect 1, leaving three plausible candidates in 192
signed decisions (1.6%). The band is an upper bound: H1b planted no content anchors, so the
ordered-anchor term of the H1a conjunction could not be applied.

## Interpretation

H1b is answered in the negative, and informatively so. The corpus is large, balanced, and complete,
and it still cannot discriminate state recovery from reconstruction, because task difficulty and
canary design were never calibrated to make that discrimination possible. The single exploratory
palindrome row that motivated the program (expansion 3.199, full-length ratio ≈ 1.016, 2,469 billed
tokens) is an outlier against this distribution, not a representative case.

The v0 gate's 47.4% strong rate is the headline the frozen metric produces and it should not be
reported without the four defects above. H1 remains unresolved. No production threshold changes.

## Requirements for H1c

1. Provenance evidence cannot come from a canary the extraction prompt names. Plant hidden content
   anchors inside the reasoning that are never mentioned in the replay request, and score ordered
   anchor recall against them. This closes the standing evidence gap rather than adding a scenario.
2. Select tasks by observed billed thinking, not by dataset label. A step billing 67 output tokens
   cannot carry a full-span claim; target steps with substantial hidden working (order 10^3 tokens)
   and verify the floor after harvest.
3. Keep the harvest instruction out of competition with the visible deliverable, or declare
   canary-leaked instances instrument failures excluded before scoring rather than after.
4. Replace the `REFUSAL_MARKERS` substring list; it undercounted refusals by 10 and passed nine of
   them as strong recoveries.

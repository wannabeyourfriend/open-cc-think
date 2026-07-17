# H1c protocol: long-CoT gathering

Status: locked before live collection
Date: 2026-07-17
Classification: prospective observational collection; downstream patterns are exploratory
Model: `global.anthropic.claude-sonnet-5`, high effort, summarized thinking display

## Objective

Gather **100 task instances whose steps contain substantial hidden reasoning**, so that the recovery
question has a denominator. H1b produced 226 decisions and only 13 cleared a thinking floor; its
single plausible recovery rests on n=1. This run targets the regime H1b never reached.

This is a gathering run. It does not claim token-for-token recovery of provider plaintext, and no
production threshold changes on its results.

## Why this task pool (measured, not assumed)

H1b selected tasks by dataset label and got 67 thinking tokens per step from GSM8K, which made every
downstream metric vacuous. H1c selects on measured yield. Three pilots, harvest-only:

| Configuration | Median est. thinking | ≥ 2,500 |
| --- | --- | --- |
| MATH-500 level 5, answer-only contract | 438 | 0/5 |
| RealFP raw question, answer-only contract | 140 | 1/4 |
| **RealFP + chat-14 instruction, prose allowed** | **3,771** | **5/6** |
| `gather-chat-14` reference (mt-bench-143 turn 2) | 5,973 / 5,656 / 5,069 | 3/3 |

Two findings fix the design:

1. **Difficulty is not the driver.** Sonnet 5 disposes of a competition-math level-5 problem in ~438
   thinking tokens. Hard ≠ long.
2. **The answer-only contract suppresses thinking.** The same RealFP questions yield 140 tokens under
   "emit only the final answer" and 3,771 under chat-14's "provide an estimate using actual
   numerical values and thoroughly explain your thought process step-by-step" — a 27× swing from the
   instruction alone. Open-endedness plus a demand for a thorough derivation is the active
   ingredient.

## Task construction

Source: **RealFP** (Kalyan et al., *Fermi Problems: A New Reasoning Challenge for AI*, EMNLP 2021),
557 real Fermi problems with reference answers. Fetched from the frozen upstream URL and pinned by
SHA-256 in the manifest.

Selection: rank eligible rows (question ≥ 30 chars, non-empty reference answer) by SHA-256 of a
frozen seed and the question text; take the first 20. Frozen before collection, so selection cannot
be influenced by results.

Each task is a single turn: the RealFP question followed verbatim by the chat-14 instruction suffix.
Harvest runs through `ScenarioHarvester` with no answer-only contract.

**20 tasks × 5 replicates = 100 instances.** Five replicates per task is a deliberate increase over
H1b's three: the strongest H1b signal was a 23× recovery gap across three replicates of one task, so
stability is now a primary quantity, not a byproduct.

Reference answers are retained for offline order-of-magnitude scoring only. They are never a
harvest-time gate — Fermi answers are estimates, and gating on exact match would force pointless
retries and bias the corpus toward agreeable rows.

## Preregistered expectations

Recorded before the run so the analysis cannot drift into whatever the data shows:

1. **Yield.** ≥ 70% of instances have est. thinking ≥ 500 tokens; ≥ 50% ≥ 2,500. (Pilot: 6/6 and
   5/6, n=6.)
2. **Leakage.** The pilot leaked 3/6. Expect 30–60% canary leakage, and expect it to be the largest
   single source of instance loss. Leaked rows are excluded from recovery analysis, not retried.
3. **Recovery.** Under the frozen v0 gate, the plausible-recovery rate on analysis-ready decisions
   will be **low** — H1b's estimate is 1/13. This run exists to put a real interval on that number,
   and a low rate is a result, not a failure.
4. **Denials.** On long-CoT steps, denials were 10/13 in H1b. Expect denial to remain the modal
   outcome.

## Accounting rules (carried from H1b)

- Unsigned decisions are censored observations: they stay in the denominator, only signed steps are
  replayed, and an incomplete trajectory is quarantined rather than retried until it disappears.
- Task correctness stays separate from recovery evidence.
- Raw signatures never enter public artifacts or git.
- Stop conditions: signature leakage into a public artifact, or three consecutive provider errors.
  A missing thinking block is **not** a stop condition.

## Known limitations, stated in advance

- **The boundary canary carries no provenance information.** The extraction prompt names the markers,
  so any echo satisfies `markers_in_order`. This run keeps the canary only for continuity of the
  frozen scorer; it is a formatting check. Hidden self-generated content anchors are the fix and are
  deferred to a successor run.
- **The visible channel is a confound.** The instruction that induces long thinking also asks for a
  visible derivation, so the visible answer partially mirrors the hidden reasoning and the replay
  reads it as unchanged prior context. On the H1b seed, 36.6% of the recovery's unique tokens appear
  in the visible answer (`answer_jaccard` 0.274). A recovery here cannot be assumed to come from
  hidden state.
  - Mitigation, computed offline: content present in both the recovery and the **blinded** provider
    summary but absent from the visible answer cannot have been read from the replay context. The
    run therefore stores visible text, summary, and recovery verbatim so this discriminator can be
    measured after the fact. This is the primary planned analysis.
- One model, one prompt candidate, one source. No cross-model or cross-prompt claim follows.

## Output

`experiments/h1c-long-cot/results/gathering-v1/`, same resume-safe runner and artifact layout as
H1b. On completion the corpus is released as `data/cot-recovery/v2` alongside v1, never merged into
it: different protocol, different population.

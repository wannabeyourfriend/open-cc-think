# Autoresearch program: evidence-graded signed reasoning recovery

## Research question

Under what observable conditions does replaying a signature-backed reasoning state yield a
boundary-complete, summary-distinct, stable, and useful reasoning trace, and which extraction
prompts maximize that evidence across tasks and signed agent decisions?

This project does **not** currently have an independent plaintext channel for Claude's original
internal working. A recovered span is therefore a `signed_full_cot_recovery` candidate, never
`ground_truth_cot` or “true CoT.” The strongest possible result from the present interface is a
defense-in-depth evidence claim; a coherent negative result is equally valid.

Two-sentence pitch:

> Signature replay can produce long reasoning-like spans, but boundary canaries alone cannot tell
> whether the span is the original working, a summary copy, or a fresh reconstruction. We will
> combine blinded replay, planted content anchors, token-length alignment, falsification controls,
> repeatability, and functional checks, then optimize prompts only on frozen development signatures
> and report held-out results by scenario and decision type.

## Evidence levels

| Level | Required evidence | Allowed claim |
| --- | --- | --- |
| E0 | Request completed, but no signed reasoning state | Transport result only |
| E1 | Exact signed prefix accepted by the provider | State continuity was accepted |
| E2 | E1 plus both boundary canaries recovered in order, without leakage or refusal | Protocol-valid bounded recovery |
| E3 | E2 plus summary was unavailable to replay and deterministic copy detectors pass | Summary-distinct recovery candidate |
| E4 | E3 plus planted content anchors, plausible token length, repeatability, and functional coverage pass | Strong signature-backed full-span recovery candidate |
| E5 | E4 plus independently observed provider plaintext matches | Ground-truth recovery |

E5 is unavailable today. No metric can promote E4 to E5.

## Metric contract v0.1

The metric is a vector with hard gates. It is not a single score that can hide failure.

### 1. Protocol gate

Every counted decision must satisfy all of the following:

- exact model ID and signed message prefix are recorded;
- the provider accepted the signature;
- provider summary text was blanked before replay;
- start and end canaries appear once, in order;
- neither canary leaked into the harvest step's visible answer or tool arguments;
- no refusal and no unexpected task tool call occurred during extraction;
- raw signatures remain private and public artifacts contain only length and SHA-256.

### 2. Content-anchor fidelity

Boundary canaries test only span reach. Metric-calibration prompts will additionally plant a random
ledger of atomic anchors inside the hidden working, such as six nonce/value pairs and one ordered
checksum relation. The public answer must not reveal them.

Report exact anchor precision, recall, order accuracy, and corruption rate. The E4 gate requires all
required anchors exactly recovered in order. Natural-task batches retain boundary canaries but are
reported separately from anchor-calibration batches.

### 3. Token-length proxies

Let:

- `T_h` be the provider-billed harvest output-token count. Provider documentation says this includes
  the original thinking tokens rather than only the visible summary, but it also includes visible
  output; it remains a proxy.
- `T_r` be extraction output tokens for the recovered span call(s).
- `W_s` and `W_r` be counts from the same frozen, deterministic lexical tokenizer over the provider
  summary and parsed recovery, excluding boundary strings and wrappers.

Report:

- `full_length_ratio = T_r / max(T_h, 1)`;
- `full_length_alignment = exp(-abs(log(max(full_length_ratio, eps))))`;
- `summary_expansion_ratio = W_r / max(W_s, 1)`.

The expected signature of a full-span candidate is `full_length_ratio` near 1 and recovery materially
longer than the summary. Raw length is never maximized: unbounded verbosity is a known false-positive
path. Initial diagnostic bands are 0.65–1.75 for `full_length_ratio` and at least 1.25 for
`summary_expansion_ratio`; H1 must calibrate these bands before they become frozen gates.

### 4. Summary-copy resistance

Keep the existing sequence similarity, token-set Jaccard, recovery-token coverage by the summary,
novelty, and length-ratio checks. Add contiguous n-gram containment so a long preamble cannot hide a
verbatim summary copy. A candidate fails if any frozen near-duplicate rule fires.

Semantic similarity is diagnostic only: a faithful full trace should remain semantically related to
its summary. Low surface similarity alone is not evidence of provenance.

### 5. Repeatability and distinctive-detail stability

Replay each frozen signature at least three times for finalists. Remove content already present in
the provider summary, extract atomic claims, and measure pairwise agreement on the remaining
details. Report the mean, minimum, and dispersion. Stability can support E4 but cannot prove
verbatim recovery; deterministic reconstruction could also be stable.

### 6. Functional coverage and consistency

- Math/code/tool tasks: run deterministic answer, unit-test, or tool-event checks.
- General traces: use a blinded coverage/legibility rubric only after it is calibrated on synthetic
  deletions, reorderings, contradictions, and verbosity controls.
- Never use the same model family as an unvalidated sole judge.
- Keep task correctness separate from recovery evidence.

### 7. Falsification controls

Every metric release must be tested against:

- provider summary copied verbatim;
- provider summary padded with fluent but irrelevant text;
- a fresh solution generated without a signature;
- wrong-task and wrong-prefix signed states;
- missing, reordered, and corrupted anchors;
- boundary-only output;
- direct “reveal private CoT” refusal control;
- a valid but short partial span.

Control false-positive rate is ranked before recovery rate.

### Primary optimization target

Until content anchors are implemented, the interim primary target is held-out
`macro_strong_recovery_rate`, with the current `strong_recovery` definition unchanged.

After H1 freezes metric v1, the primary target becomes:

1. minimize control false-positive rate;
2. maximize scenario-macro E4 pass rate;
3. maximize the worst-scenario E4 pass rate;
4. maximize the task-clustered lower confidence bound;
5. maximize median token-length alignment and distinctive-detail stability;
6. minimize extraction calls and output tokens.

No later criterion may compensate for an earlier failure.

## Data and split contract

| Split | Contents | Permitted use |
| --- | --- | --- |
| M0 metric calibration | Synthetic anchor traces and adversarial controls | Freeze metric thresholds only |
| P-dev | First 8 instances per scenario from fixed coding/math/chat 36 | Prompt successive halving |
| P-val | Remaining 4 instances per scenario | Select/report the frozen prompt once |
| A-dev | Deterministic local-tool tasks, split by task template | Develop agentic extraction and decision strata |
| A-test | Held-out templates and seeds | Internal agentic evaluation |
| Production held-out | Terminal-Bench 2.0 through Harbor | Final evaluation only; never prompt tuning |

The existing fixed 36 stays balanced across HumanEval, GSM8K-train, and non-reasoning MT-Bench
categories. Results from incompatible artifact schemas or model IDs are never pooled.

## Prompt optimization

The extraction unit is one signed decision, not one conversation. All candidates are evaluated on
the same frozen signature before moving to a new task.

- Separate elicitation candidates from negative controls. `direct_private_cot_control` is a control
  and cannot win.
- Stage sizes remain 2, 2, and 4 instances per scenario for successive halving.
- Use paired comparisons and task-clustered uncertainty.
- Finalists receive at least three replay replicates per decision.
- Do not optimize task accuracy, canary saturation, or raw verbosity.
- Freeze candidate text and metric thresholds before P-val.
- For agent traces, report tool selection, argument construction, observation integration, and final
  synthesis separately. A per-decision-type prompt is allowed only if chosen on A-dev.

## Trace-collection plan

Run pilots before full batches:

1. M0: 12 anchor/control pairs spanning short, medium, and long hidden ledgers.
2. P-dev/P-val: the existing 12/12/12 coding, math, and chat corpus.
3. A-dev: at least 12 deterministic tasks producing 3–8 signed decisions across catalog lookup,
   arithmetic, policy lookup, file-like state inspection, and multi-observation synthesis.
4. A-test: at least 12 held-out task templates/seeds.
5. Production: Terminal-Bench 2.0 only after prompt and metric freeze.

For each public row store task/source ID, scenario, decision type, model, effort, summary-display
mode, prefix digest, signature digest/length, prompt version, all metric components, usage, stop
reason, task verification, and artifact schema. Raw signatures live only in ignored `private/` or
`.checkpoints/` directories.

## Inner and outer loops

Inner-loop experiments are preregistered in `experiments/<hypothesis>/protocol.md` and committed
before execution. Results record wall time, provider/model, exact inputs, cost proxies, failures, and
whether each observation was confirmatory or exploratory.

Run an outer-loop reflection after 5–10 experiments, a surprising result, or a plateau. Update
`findings.md`, decide DEEPEN/BROADEN/PIVOT/CONCLUDE, and generate an HTML progress report in
`to_human/` when there is a meaningful pattern.

## Completion criteria

The program may conclude when:

- metric v1 has zero false positives on frozen controls and calibrated uncertainty on human/synthetic
  labels;
- a prompt or prompt policy is frozen before held-out evaluation;
- multi-scenario and multi-decision batches have auditable provenance and confidence intervals;
- ablations isolate signature, summary visibility, anchors, prompt, and repeat effects;
- claims remain at the highest evidence level actually supported;
- `findings.md` contains a coherent positive or negative paper backbone.

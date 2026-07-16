# Research Findings

## Research Question

When does signed-state replay yield a boundary-complete, summary-distinct, stable, and useful
recovery candidate, and which extraction prompts maximize that evidence across scenarios and signed
agent decisions?

## Current Understanding

The provider signature is evidence that an unchanged conversation state was accepted for
continuation. It is not a cryptographic commitment to plaintext returned by a later elicitation
prompt. Boundary canaries show that replay can recover state-linked markers, but they do not
distinguish original working from a provider summary, paraphrase, or reconstruction.

The checked-in evidence is predominantly negative: the project audit finds zero strong rows among
14 historical decisions. Most predate blind replay, and the only blinded checked-in row is still a
near-duplicate of the summary. A new exploratory Sonnet 5 run is qualitatively different: its
recovery is about 2.9 times the provider summary by characters, its extraction token count closely
matches billed harvest output tokens, and deterministic copy metrics mark it distinct. That is a
useful feasibility signal, but one row cannot calibrate a metric or establish a recovery rate.

Token length is a central proxy because provider documentation says billed output tokens correspond
to original thinking rather than visible summarized thinking. The useful signal is alignment with
that billed count plus expansion beyond the visible summary—not unbounded length. Verbose
reconstruction can otherwise game the metric.

## Key Results

- Current checked-in audit: 0/14 strong candidates; mean sequence similarity to provider summaries
  is 0.86.
- Only checked-in blind row: protocol-valid, but sequence similarity 0.8733 and near-duplicate.
- Exploratory live `open-reasoning` digit-palindrome row:
  - correct visible answer: 62;
  - 2,469 billed harvest output tokens and 2,508 extraction output tokens;
  - 5,916 recovered characters versus 2,010 provider-summary characters;
  - summary/recovery sequence similarity 0.2222 and length ratio 2.9068;
  - both canaries in order, no marker leakage, no refusal, summary blinded;
  - `strong_recovery=true` under current metric.
- Sonnet 5 rejects explicit temperature during replay; transport now retries once without it and
  caches that provider capability.
- H1a deterministic falsification:
  - all 9 preregistered checks passed;
  - current `strong_recovery` accepted 4/7 negative controls;
  - a hard conjunction of exact ordered anchors, plausible full-token ratio, summary expansion, and
    low n-gram containment accepted the one complete trace and 0/7 negatives;
  - this is controlled separability, not a live error-rate estimate.

All live observations above are exploratory because they occurred before the formal protocol.

## Patterns and Insights

- Canary validity is already easy to saturate and should be a gate, not an optimization target.
- Summary distinctness—not boundary recovery—is the first observed bottleneck in historical data.
- Harder, longer high-effort requests can fail at the synchronous transport layer before producing
  artifacts, so run reliability and censoring must be reported.
- A plausible positive recovery has two length signatures at once: it is materially longer than the
  visible summary and close to the provider-billed original-output token count.
- Surface novelty supports a non-copy claim but cannot establish provenance. Planted hidden content
  anchors and negative controls are the next highest-value measurement upgrade.
- Capping token coverage at 1.0 hides overlong failures: the padded-summary control received maximum
  coverage and quality. A log-symmetric alignment score penalizes both too-short and too-long traces.
- Sequence similarity can be defeated by padding, while contiguous summary n-gram containment still
  identifies the embedded verbatim summary.

## Lessons and Constraints

- Never label recovered spans `ground_truth_cot` or pool them with independently observed plaintext.
- Never pool v1/v2 pre-blinding artifacts with v3 blind rows.
- Keep task correctness separate from recovery evidence.
- Do not optimize raw length, canary rate, or a single LLM-judge score.
- Do not promote H1a thresholds to the production gate before provider-backed anchor calibration.
- Separate extraction candidates from refusal/summary-only controls.
- Freeze metric thresholds on M0 before prompt selection; freeze prompts before held-out evaluation.
- Signatures remain replayable sensitive state and must stay out of public artifacts and git.
- Terminal-Bench 2.0 remains production held-out and cannot enter calibration.

## Open Questions

- Can multi-anchor probes distinguish state recovery from summary expansion and fresh reconstruction?
- What full-length-ratio band best separates synthetic positives, partial spans, and padded controls?
- Are distinctive details stable across repeated replays of the same signature?
- Which prompt features matter: mechanical framing, explicit boundaries, encoding wrapper, or
  action-local context?
- How strongly does recovery vary across tool selection, tool arguments, observation integration,
  and final synthesis?
- Does provider-side omitted display behave like local summary blanking at matched task/effort?
- What fraction of failures are elicitation failures versus harvest/transport censoring?

## Optimization Trajectory

No confirmatory run has started. Historical and live rows are retained as exploratory baselines only.

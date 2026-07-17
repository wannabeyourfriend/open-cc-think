# Research Findings

## Research Question

When does signed-state replay yield a boundary-complete, summary-distinct, stable, and useful
recovery candidate, and which extraction prompts maximize that evidence across scenarios and signed
agent decisions?

## Current Understanding

The provider signature is evidence that an unchanged conversation state was accepted for
continuation. It is not a cryptographic commitment to plaintext returned by a later elicitation
prompt. Boundary canaries do not distinguish original working from a provider summary, paraphrase,
or reconstruction — and after H1b the stronger statement holds: they cannot, as currently built.
Every extraction prompt interpolates the marker strings into the replay request, so the model is
handed the canary it is supposed to prove it recovered. `markers_in_order` measures instruction
compliance in the harvest step and output formatting in the replay step. It carries no provenance
information at all, which is why nine denials that merely quote the markers scored as strong
recoveries.

The checked-in evidence is predominantly negative: the project audit finds zero strong rows among
14 historical decisions. Most predate blind replay, and the only blinded checked-in row is still a
near-duplicate of the summary. A new exploratory Sonnet 5 run is qualitatively different: its
recovery is about 2.9 times the provider summary by characters, its extraction token count closely
matches billed harvest output tokens, and deterministic copy metrics mark it distinct. That is a
useful feasibility signal, but one row cannot calibrate a metric or establish a recovery rate.

Token length is a central proxy because provider documentation says billed output tokens correspond
to original thinking rather than visible summarized thinking. The useful signal is alignment with
that billed count plus expansion beyond the visible summary—not unbounded length. Verbose
reconstruction can otherwise game the metric. H1b adds the reciprocal failure: when a step bills
only 67 output tokens, alignment near 1.0 is vacuous because both quantities are near zero. The
proxy only carries a full-span claim on steps that actually contain substantial hidden working, so
thinking volume is a selection criterion for the corpus, not an outcome to be measured after the
fact.

The largest completed collection is negative. H1b gathered exactly the corpus it promised and the
corpus cannot answer H1: where the instrument works there is nothing to recover, and where there is
something to recover the instrument fails. The one exploratory row that motivated the program is an
outlier against 192 signed decisions.

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
- H1b live smoke:
  - conversational QA completed two signed turns and math completed one signed, correct-answer turn;
  - simple agentic coding produced signatures for inspection and patch decisions but repeatedly
    omitted reasoning on a mechanical `run_tests` call;
  - moving deterministic verification outside the model loop and treating `apply_patch` as the
    terminal prediction produced a complete two-decision trajectory with task success and 2/2
    protocol-valid, summary-distinct recoveries.
- H1b full collection (complete; 53 min):
  - 135/135 instances, 45/45 tasks at three replicates, 0 failed;
  - 226 decisions: 192 signed, 34 unsigned/censored (15.0%);
  - 134,951 billed harvest output tokens against 37,543 extraction output tokens;
  - task success 44/45 math, 36/45 agentic coding;
  - frozen v0 gate: 110/192 valid, 91/192 strong (47.4%), scenario-macro 0.5422
    (chat 11/76 = 14.5%, math 35/39 = 89.7%, coding 45/77 = 58.4%).
- H1b re-analysis — the 47.4% is an instrument artifact, on four independent grounds:
  - canary echo: 9/91 strong rows are denials quoting the marker names; `REFUSAL_MARKERS` flagged
    18 refusals and missed 10;
  - nothing to recover: median billed thinking per signed step is 67 tokens (math) and 151
    (coding); a strong math "recovery" is `36 * 0.75 = 27; 27 - 16 = 11`, re-derivable from the
    question and the visible answer, which is H1a's `fresh_solution` control;
  - instrument failure where thinking is real: chat (median 844, max 6,952 billed tokens) leaked
    the canary into visible text on 41/76 decisions across 14/15 tasks and refused on 16/76,
    leaving 11 usable; coding leaked 11/77; math 0/39;
  - length contradiction: 82/91 strong rows have summary expansion below 1.25 (medians 0.562
    coding, 0.447 math, 0.889 chat — shorter than the summary), and 32/91 have full-length ratio
    below 0.65;
  - extract/summary expansion over all signed decisions is 1.207 median for chat (47% at or above
    1.25), 0.483 for math (82% below 1.0), and 0.500 for coding (88% below 1.0). Only chat expands
    at all, and chat is the scenario lost to leakage. The median coding recovery is a six-token
    stub ("Let me inspect the workspace first.") against a fifteen-token summary, scored strong;
  - under the available H1a band (valid, full-length ratio 0.65–1.75, expansion ≥ 1.25, containment
    < 0.90) only 5/192 survive, 2 of them denials, leaving 3/192 = 1.6% plausible. This is an upper
    bound because H1b planted no content anchors.

All live observations above are exploratory because they occurred before the formal protocol; the
H1b collection is prospective observational, and its downstream patterns remain exploratory.

## Patterns and Insights

- A canary named in the extraction prompt cannot be provenance evidence. It is not merely easy to
  saturate; it is satisfiable by echo, including by a refusal that quotes it back. Provenance
  evidence must be content the replay prompt never supplies.
- Scenario difficulty must be selected on observed billed thinking, not dataset label. Both
  "successful" H1b scenarios bill under 200 thinking tokens per step, so their recoveries are
  re-derivations and their length alignment is vacuous.
- A harvest instruction that competes with the visible deliverable will lose. Canary leakage was 0%
  where the visible answer is a bare number, 14% where it is a patch, and 54% where it is prose.
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
- Adaptive thinking may omit reasoning on low-complexity mechanical tool calls even when preceding
  agent decisions are signed. Agent environments should end at the substantive submitted action and
  run deterministic verification outside the model loop, as in containerized coding benchmarks.
- A missing adaptive-thinking block is a censored model observation, not a transport error. Retain
  it in the instance denominator, replay only actual signatures, and quarantine the incomplete ATIF
  trajectory instead of retrying until the omission disappears.

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
- Keep agent predictions and verifier outcomes separate; never manufacture a signed decision for a
  deterministic verifier step that the provider returned unsigned.
- Never report the v0 scenario-macro strong rate as a recovery rate. On the H1b corpus it reads
  0.5422 while the H1a band admits 1.6%, because the v0 `distinct_from_summary` term accepts
  `novelty >= 0.12` alone and therefore passes short, differently-worded re-derivations.
- Do not detect refusals with a substring list. It undercounted H1b refusals by 10 and passed nine
  of them as strong recoveries.

## Open Questions

- Can hidden content anchors that the extraction prompt never names distinguish state recovery from
  summary expansion and fresh reconstruction? This is now the load-bearing question: H1b showed the
  named boundary canary cannot.
- Which tasks reliably induce substantial hidden working (order 10^3 billed thinking tokens) while
  keeping a visible deliverable that does not invite canary leakage? Chat has the thinking but leaks;
  math and coding are clean but think too little.
- Are the three H1b rows that survive the H1a band real recoveries or survivors of an underpowered
  filter?
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

H1a is the only supported hypothesis, on a synthetic suite. H1b is refuted: it produced its full
preregistered corpus and that corpus cannot discriminate recovery from reconstruction. H2 prompt
optimization stays blocked — optimizing extraction prompts against a gate that a quoted-marker
denial can pass would select for canary echo, not recovery. H1c must first supply hidden content
anchors and a billed-thinking floor.

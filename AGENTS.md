# CLAUDE.md

Research on **signature-backed chain-of-thought recovery** from Claude over Amazon Bedrock Converse:
replay a response's signed `reasoningContent` state with its unchanged prior messages, require hidden
boundary canaries, and try to recover the model's full-span internal working. Whether that recovers
real hidden reasoning or merely a paraphrase of the provider's summary is the **open question this
repo exists to answer** — not a settled result (see Status).

`src/README.md` and `src/RESEARCH.md` are the authoritative design docs — read them before changing
pipeline behavior, controls, or metrics. This file doesn't restate them; it covers current state,
verified commands, and what you can break silently. Only `src/` (`signature_cot`) is developed here.
`open-reasoning/` and `open-open-reasoning/` are reference-only submodules, currently **uninitialized
empty dirs** — don't cite their contents from memory; init them or say the reference is unavailable.

## Status: the audit is red, and that is the finding

`scripts/audit_summary_overlap.py` is the project-level verdict: it scores every recovered span
against the provider summary and exits non-zero unless all rows are strong. It currently reports
**0/14 strong** (10 `weak-near-duplicate`, 4 `weak-summary-visible`), mean sequence similarity to the
summary **0.86**. That includes the only correctly-blinded run: `blind-replay-smoke` is `valid=True`
with both canaries in order, yet `strong_recovery=False` at 0.8733 similarity to the summary it was
supposed to go beyond. **The canary mechanism works; summary-distinctness does not yet.**

So: don't cite checked-in artifacts as supporting results — they currently refute the strong claim.
A red audit is the research question, not a bug; don't "fix" it by flipping `blind_provider_summary`,
loosening thresholds, or gating on `valid`. Canary validity is near-saturated and optimizing it is
mostly wasted; summary distinctness is the failing metric.

## `strong_recovery`, not `valid`, is the real bar

Two tiers in `scoring.py`, and confusing them reports failures as successes:

- `valid` — the canary rule: recovered, both markers in order, no leak, no refusal, no unexpected
  non-sink tool call. The **inner, weaker** bar.
- `strong_recovery` = `valid` **and** summary not visible to the replay **and** `distinct_from_summary`
  (frozen near-duplicate thresholds: sequence ≥0.82, jaccard ≥0.85, or token coverage ≥0.92, within
  length-ratio bands).

`strong_recovery` gates everything: exit codes, the ATIF `accepted`/`quarantine` decision, and the
optimizer's primary ranking key (**not** `valid_rate`). A run can be `valid` and still exit 2 — that
is correct, not a bug.

**Blind replay is the central confound control and is default-ON** (`SignatureExtractor(
blind_provider_summary=True)`): `HarvestStep.replay_messages` blanks `reasoningText.text` while
keeping the opaque signature and block structure intact, so the extractor can't just copy the
summary. Disabling it forces `strong_recovery=False` and removes the only defense against
summary-copying.

## Commands

From the repo root. Stdlib-only (`urllib` for HTTP) — no install or venv.

```bash
# Tests (fast, fully mocked). 11 tests, 1 pre-existing error — see Traps.
PYTHONPATH=src python3 -m unittest discover -s src/tests -v

# Single test (from src/, so the tests package is importable)
PYTHONPATH=. python3 -m unittest tests.test_pipeline.AgentTests.test_agent_records_signed_tool_and_final_steps

# CLI (needs .env.aws at the repo root)
PYTHONPATH=src python3 -m signature_cot list
PYTHONPATH=src python3 -m signature_cot probe                # cheap harvest/replay smoke check
PYTHONPATH=src python3 -m signature_cot reproduce --tasks walking-rates,cubic-roots --output <fresh-dir>
PYTHONPATH=src python3 -m signature_cot optimize --task walking-rates --optimizer-rounds 3
PYTHONPATH=src python3 -m signature_cot agentic --output <fresh-dir>
PYTHONPATH=src python3 -m signature_cot calibrate-corpus     # full 36-instance calibration

python3 scripts/audit_summary_overlap.py                     # verdict on all checked-in artifacts
python3 scripts/prepare_calibration_manifest.py              # rebuild frozen manifest (network)
```

Exit codes: `0` only when every selected extraction reached **`strong_recovery`**, else `2`.
`calibrate-corpus` gates on `macro_strong_recovery_rate == 1.0` (it emits `macro_valid_rate` too —
the gate reads the *strong* one). `list` and `optimize` always return `0`.

## Credentials

Copy `.env.example` → `.env.aws` at the repo root (gitignored). `ProviderConfig.from_env` parses it
as `export KEY=value` with no shell execution: `AWS_BEARER_TOKEN_BEDROCK`, plus optional
`AWS_REGION`, `HTTP_TIMEOUT`, `BEDROCK_RUNTIME_ENDPOINT`. The token is never written to artifacts or
printed (`safe_summary` exposes only a boolean `credential_configured`).

Model precedence: `--model` > `ANTHROPIC_SONNET_MODEL` > **`MODEL`** > `global.anthropic.claude-sonnet-4-6`.
Signatures are **bound to the model name**, so a stray bare `MODEL` in the environment silently
breaks replay instead of failing loudly. (`ANTHROPIC_OPUS_MODEL` in `.env.example` is dead.)

## Orientation

The research unit is a **signed decision step**, not a chat session. `ResearchPipeline`
(`pipeline.py`) orchestrates, `cli.py` drives, and file names otherwise say what they hold. The
non-obvious parts:

- `harvest.py` — three harvesters: `QuestionHarvester` (answer-only QA: ≤100 chars, ≤2 lines, one
  stricter retry then hard failure), `ScenarioHarvester`, `AgentRunner` (local-tool loop, `max_steps=8`).
- `extraction.py` — replays the signed prefix, blinds the summary, and forces a neutral
  `emit_signed_trace` sink tool on historical tool turns so the model can't resume the original task.
  Multi-round continuation merges by overlap-dedup.
- `models.py` — `BedrockResponse` accessors deliberately separate the three outputs that must never
  be conflated: `reasoning_summary` (provider), `text`/`tool_calls` (visible action), `signatures`.

## Invariants

Load-bearing. Violating these silently corrupts the research claim.

- **Recovery is not verbatim proof.** Artifacts label the field `signed_full_cot_recovery`, never
  `ground_truth_cot`; the model can paraphrase, omit, or fabricate within the span.
  `token_coverage_proxy` (that exact name) is a proxy — Converse exposes total output tokens, not a
  hidden-thinking count. Do not strengthen these claims in code, comments, or docs.
- **Two canaries, in order, never leaked** — per-step random nonces (`new_markers`). `marker_leaked`
  checks the *harvest* step's public surface (leakage at signing time), not the replay response.
- **Signatures are sensitive.** JSON artifacts store only length + SHA-256 (`_sanitize_signatures` →
  `<redacted>`). Raw signatures land under `output/private/` only with `--save-signatures` —
  **except** `calibrate-corpus`, which always writes them to `<output>/.checkpoints/` (see Traps).
- **Calibration split ≠ evaluation split.** Prompts are calibrated on the frozen 12/12/12
  coding/math/chat corpus (`src/calibration/fixed-36.json`); Terminal-Bench 2.0 is the held-out
  production target — **never add Terminal-Bench tasks to the manifest.** `load_manifest` raises
  unless the scenarios are exactly coding/math/chat with equal counts, so a stray task fails loudly
  rather than silently contaminating the split.
- **ATIF v1.7 export excludes replay calls from the agent sequence.** One original inference = one
  agent step; extraction calls are costed separately, never inserted as agent actions. Trajectories
  where any decision missed `strong_recovery` are gated `quarantine`, not `accepted`.
- **Agentic tools are deterministic and sandboxed.** No shell or web tool is ever exposed to the
  model; `calculator` is AST-restricted (no eval/import/attribute access).

## Traps

- **One test errors pre-existing — you didn't break it.** `tools.py:66` uses `ast.Num`, removed in
  Python 3.12 (this machine runs 3.14). The `ast.Constant` line above covers every supported version,
  so the branch is dead-but-fatal: it also breaks `calculator` at runtime, so `agentic` fails on the
  first arithmetic call. `pyproject.toml` declares `requires-python = ">=3.9"`.
- **`--output` defaults to `src/artifacts/` and overwrites tracked files.** `ArtifactWriter` writes
  `<output>/<task_id>.{md,json,atif.json}` with no run-scoped subdir, so aiming `reproduce` at
  `src/artifacts/reference` clobbers checked-in evidence. Always use a fresh output dir.
- **Tracked artifacts span three incompatible schemas.** `reference/`, `probe/`, `agentic-optimized/`
  are v1; `calibration-pilot/`, `calibration-smoke/` are v2; only `blind-replay-smoke/` is v3. v1/v2
  **predate blind replay** and always replayed the summary verbatim, so never pool metrics across
  them — most weak audit rows are known-confounded pre-blinding pilots.
- **`calibrate-corpus` silently resumes from `<output>/.checkpoints/`.** A different `--model` against
  a reused output dir raises an opaque `checkpoint model mismatch`; a changed manifest raises
  `checkpoint source mismatch`. Delete the dir or use a fresh `--output`. These checkpoints hold
  **raw replayable signatures**; `.checkpoints/` and `private/` are gitignored at any depth, so an
  `--output` outside `src/artifacts/` is still covered.
- **`src/RESEARCH.zh.md` mirrors `src/RESEARCH.md`.** Update both or the translation silently
  contradicts the source.

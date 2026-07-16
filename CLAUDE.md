# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

Research on **signature-backed chain-of-thought (CoT) recovery** from Claude models served over
Amazon Bedrock Converse. A Converse `reasoningContent.reasoningText.signature` must be replayed with
its unchanged prior messages for reasoning continuity; replaying the exact signed decision state and
requiring the model to emit hidden boundary canaries lets the pipeline recover the model's full-span
internal working, not just the provider's summary.

Three subtrees, only one of which is actively developed here:

- **`src/`** — the active, clean implementation (`signature_cot` package). This is where nearly all
  work happens. Extends the reference harvest/replay from single-turn QA to signed, multi-step tool
  trajectories, and targets Terminal-Bench 2.0 / Harbor ATIF v1.7 as the production output contract.
- **`open-open-reasoning/`** — git submodule; a Flask reproduction of the original demo plus
  `ANALYSIS.md` documenting the signature wire format (base64 protobuf wrapping an AEAD-encrypted copy
  of private reasoning, bound to the model name). Reference material, not the codebase under change.
- **`open-reasoning/`** — git submodule; the upstream demo and example corpus. Reference only.

`src/README.md` and `src/RESEARCH.md` are the authoritative design docs — read them before changing
pipeline behavior, experimental controls, or metrics.

## Commands

All commands run from the repo root. The `signature_cot` package has **no third-party dependencies**
(stdlib only, `urllib` for HTTP), so no install/venv is needed to run or test.

```bash
# Tests (fast, fully mocked — no network/credentials)
PYTHONPATH=src python3 -m unittest discover -s src/tests -v

# Single test (run from src/ so the tests package is importable)
PYTHONPATH=. python3 -m unittest tests.test_pipeline.AgentTests.test_agent_records_signed_tool_and_final_steps

# CLI (requires ../.env.aws credential — see below)
PYTHONPATH=src python3 -m signature_cot list                    # list checked-in tasks
PYTHONPATH=src python3 -m signature_cot probe                   # cheap harvest/replay smoke check
PYTHONPATH=src python3 -m signature_cot reproduce --tasks walking-rates,cubic-roots --output src/artifacts/reference
PYTHONPATH=src python3 -m signature_cot optimize --task walking-rates --optimizer-rounds 3
PYTHONPATH=src python3 -m signature_cot agentic --output src/artifacts/agentic
PYTHONPATH=src python3 -m signature_cot calibrate-corpus        # full 36-instance prompt calibration
```

Rebuild the frozen calibration manifest from official HumanEval/GSM8K/MT-Bench sources (network):

```bash
python3 scripts/prepare_calibration_manifest.py
```

CLI exit codes are meaningful: `0` when every selected extraction was valid, `2` otherwise. `probe`
returns `2` when the single trial is invalid; `calibrate-corpus` returns `2` unless validation
`macro_valid_rate == 1.0`.

## Credentials

`ProviderConfig.from_env` reads `AWS_BEARER_TOKEN_BEDROCK` and model IDs from `.env.aws` at the repo
root (parsed as `export KEY=value` — no shell execution). The bearer token authenticates Bedrock
Converse directly; it is never copied into artifacts and never printed (`safe_summary` only exposes a
boolean `credential_configured`). `.env.aws` is gitignored. Default model is
`global.anthropic.claude-sonnet-4-6` unless `--model` or `ANTHROPIC_SONNET_MODEL` overrides it.

## Pipeline architecture (`src/signature_cot/`)

The core research unit is a **signed decision step**, not a chat session. Data flows through three
stages, orchestrated by `ResearchPipeline` (`pipeline.py`) and driven by `cli.py`:

1. **Harvest** (`harvest.py`) — call Bedrock and capture, per response: the exact message prefix,
   system/tool config, the `reasoningContent` signature, visible text/`toolUse` action, and (for tool
   turns) the structurally valid `toolResult` blocks needed to bridge replay. Three harvesters:
   - `QuestionHarvester` — answer-only QA. Enforces a **compact visible-answer invariant**: the
     visible reply must be one bare value (≤100 chars, ≤2 lines, containing the expected answer);
     violation triggers one stricter retry, then hard failure.
   - `ScenarioHarvester` — multi-turn chat/coding without the answer-only contract.
   - `AgentRunner` — multi-step local-tool loop (max 8 steps). Every tool turn is a separate signed
     step with its own boundary markers.
2. **Extract / replay** (`extraction.py`) — `SignatureExtractor.recover` rebuilds the signed prefix,
   appends an elicitation prompt (a `PromptCandidate` from `prompts.py`), and asks the model to
   mechanically copy its own bounded working. For historical tool-use turns it declares a neutral
   `emit_signed_trace` sink tool with forced `toolChoice` so the model cannot resume the original
   task. Handles multi-round continuation with overlap-dedup merging.
3. **Score & optimize** (`scoring.py`, `extraction.py`, `calibration.py`) — see validity rules below.
   `PromptOptimizer` (single-signature) and `StratifiedPromptOptimizer` (fixed corpus) both use
   **paired successive halving**: every surviving candidate is evaluated on the *same* signatures each
   round, ranked by a robust aggregate (mean − spread penalty + valid-rate bonus, plus canary/refusal/
   leakage terms for the corpus optimizer), and the bottom half is dropped.

`bedrock.py` is a thin stdlib `urllib` Converse transport. `models.py` holds all dataclasses
(`HarvestStep`, `ExtractionTrial`, etc.) and the `BedrockResponse` accessors that separate the three
distinct model outputs: `reasoning_summary` (provider summary), `text`/`tool_calls` (visible
action), and `signatures` (replayable state).

## Non-obvious invariants

These are load-bearing correctness properties; violating them silently corrupts the research claim.

- **Two canaries, in order, never leaked.** A recovery is valid only when both the start and end
  boundary markers are recovered in order (`markers_in_order`) *and* neither leaked into visible text
  or tool arguments (`marker_leaked`). This is stronger than the reference's one-canary/length
  heuristic. `score_recovery` also invalidates on refusal or on the replay emitting an unexpected
  (non-sink) tool call. Markers are per-step random nonces (`new_markers`).
- **Recovery is not verbatim proof.** Artifacts label the field `signed_full_cot_recovery`, never
  `ground_truth_cot`. The model can still paraphrase/omit/fabricate within the span. `token_coverage`
  is a **proxy** because Converse exposes total output tokens, not a hidden-thinking count. Do not
  strengthen these claims in code, comments, or docs.
- **Signatures are sensitive and redacted by default.** JSON artifacts store only signature length +
  SHA-256 (`_sanitize_signatures` replaces raw signatures with `<redacted>`). Raw replayable
  signatures are written only under `output/private/` and only with the opt-in `--save-signatures`.
- **Calibration split ≠ evaluation split.** Prompt selection is calibrated on the frozen 12/12/12
  coding/math/chat corpus (`src/calibration/fixed-36.json`, deterministic seeded selection from
  official sources). Terminal-Bench 2.0 is the held-out production target — **never add Terminal-Bench
  tasks to the calibration manifest.**
- **ATIF export excludes replay calls from the agent sequence.** `atif.py` builds Harbor ATIF v1.7
  records where one original inference = one agent step; extraction/replay calls are costed separately
  and never inserted as agent actions. `validate_atif_trajectory` enforces sequential step IDs,
  agent-only field placement, and observation↔tool-call linkage. Trajectories where not every decision
  recovered validly are gated as `quarantine`, not `accepted`.
- **Agentic tools are deterministic and sandboxed.** The `procurement_registry` (`tools.py`) exposes
  only `catalog_lookup`, `calculator` (AST-restricted arithmetic — no eval/import/attribute access),
  and `policy_lookup`. No shell or web tool is ever exposed to the model.

# Signature-CoT research pipeline

This is a clean implementation of the `open-open-reasoning` harvest/replay mechanism,
extended from single-turn answer-only QA to signed, multi-step tool trajectories. It uses
Amazon Bedrock Converse directly with `AWS_BEARER_TOKEN_BEDROCK`; the credential is read from
`../.env.aws`, never copied into artifacts, and never printed.

The important research unit is a **signed decision step**, not a chat session. For every Claude
response the pipeline saves, in memory:

1. the exact message prefix and system/tool configuration;
2. the omitted `reasoningContent.reasoningText.signature`;
3. the assistant text or `toolUse` action;
4. for a tool action, structurally valid original `toolResult` blocks used to bridge replay.

Each internal-working span is planted with distinct start/end canaries. A recovery is valid only
when both canaries are recovered in order and neither leaked into visible text or tool arguments.
This is stronger than the reference implementation's one-canary/length heuristic and lets us
measure individual decisions in a real agent trajectory.

For the reference QA tasks, answer-only output is also a hard invariant. A system-level output
contract is used first; if the visible response contains a solution instead of one compact value,
the harvest is discarded and retried once with a stricter surface reminder.

## Run

No third-party Python dependency is required. From the repository root:

```bash
PYTHONPATH=src python3 -m unittest discover -s src/tests -v
PYTHONPATH=src python3 -m signature_cot probe
```

Reproduce the two prompts checked into `open-open-reasoning/examples`:

```bash
PYTHONPATH=src python3 -m signature_cot reproduce \
  --tasks walking-rates,cubic-roots \
  --output src/artifacts/reference
```

Calibrate elicitation prompts on one fixed walking-task signature. Candidates are evaluated with a
paired successive-halving schedule, so stochastic trials are compared on the same signed state:

```bash
PYTHONPATH=src python3 -m signature_cot optimize \
  --task walking-rates --optimizer-rounds 3 \
  --output src/artifacts/calibration
```

Use the reported winner on the held-out cubic task (replace the candidate if the run selected a
different one):

```bash
PYTHONPATH=src python3 -m signature_cot reproduce \
  --tasks cubic-roots --candidate mechanical_boundary_xml_v2 \
  --output src/artifacts/held-out
```

Run the agentic fixture. It uses deterministic local catalog, calculator, and policy tools; no
arbitrary shell or web tool is exposed to the model:

```bash
PYTHONPATH=src python3 -m signature_cot agentic \
  --optimizer-rounds 3 --output src/artifacts/agentic
```

`--save-signatures` is intentionally opt-in. Without it, JSON artifacts contain only the signature
length and SHA-256 digest. A signature remains a replayable sensitive model-state artifact.

## What improved over the reference sweep

- Provider transport supports the supplied Bedrock bearer key instead of requiring Anthropic
  `x-api-key` compatibility.
- The optimizer holds signatures fixed and uses paired trials, successive halving, replicate mean,
  variability, and valid-rate rather than selecting the best one-off score.
- Start **and** end canaries detect boundary coverage; canary leakage into tool arguments or visible
  answers is a hard failure.
- Every tool-use response is extracted at its own decision boundary. Replay supplies the required
  `toolResult` blocks before the elicitation text, preserving the provider's tool protocol.
- Public artifacts redact raw signatures by default and record the prompt ranking, exact tool
  observations, normalized usage, and per-step metrics.
- Parsers support XML, JSON, fenced, marker-delimited, and Base64 transports; continuation merging
  removes exact overlap rather than blindly concatenating chunks.

## Experimental design for the ACL study

Treat prompt selection and reported evaluation as separate splits. Calibrate on signatures from a
small synthetic development set, freeze the winner, and evaluate on held-out tasks/models. Report at
least: both-canary success, visible/action leakage, refusal rate, tool-call replay errors, coverage
proxy, answer correctness, task success, calls per recovered step, and robustness across repeated
replays. For agentic runs, stratify results by decision type (tool selection, argument construction,
observation integration, and final synthesis).

The output is **not cryptographic plaintext recovery proof**. A successful signed replay and hidden
canary establish access to state carried by the signed reasoning block, but the model can still
paraphrase, omit, or fabricate spans. Bedrock Converse exposes total output tokens rather than a
separate hidden-thinking count, so `token_coverage_proxy` is labeled as a proxy. Stronger fidelity
claims require provider-returned plaintext ground truth or another independently verifiable channel.

AWS references:

- [Bedrock API-key bearer authentication](https://docs.aws.amazon.com/bedrock/latest/userguide/api-keys-use.html)
- [Converse reasoningContent and signature continuity](https://docs.aws.amazon.com/bedrock/latest/userguide/conversation-inference.html)
- [Adaptive thinking with Converse](https://docs.aws.amazon.com/bedrock/latest/userguide/claude-messages-adaptive-thinking.html)

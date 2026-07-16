# H1b protocol: repeated scenario gathering

Status: locked before live collection
Date: 2026-07-17
Classification: prospective observational collection; downstream patterns are exploratory
Model: `global.anthropic.claude-sonnet-5`

## Objective

Gather a substantially larger, balanced corpus of signature-backed recovery candidates. The target
is at least 15 distinct tasks in each of three scenarios and at least three independently harvested
instances per task:

- complex conversational QA;
- math reasoning;
- agentic coding.

The minimum complete corpus is therefore 45 tasks and 135 task instances. A multi-turn or agentic
instance may contain several signed decision steps, so the decision-level count will be higher.
This experiment measures how much useful reasoning can be gathered and how its observable evidence
varies. It does not require or claim token-for-token recovery of provider plaintext.

## Task construction

### Complex conversational QA

Select 15 two-turn MT-Bench tasks from categories other than coding, math, and reasoning. Exclude
every source ID already present in `src/calibration/fixed-36.json`, then rank the remaining official
rows by SHA-256 of a frozen seed and source ID.

### Math reasoning

Select 15 GSM8K training tasks. Exclude every source ID already present in the fixed calibration
manifest, then use the same frozen deterministic ranking. Require a compact visible numeric answer
and retain the official final answer for task-success scoring.

### Agentic coding

Use 15 checked-in deterministic code-repair fixtures. Each fixture provides a small in-memory
workspace and only sandboxed local tools for listing, reading, searching, applying one exact text
replacement, and running deterministic checks. The model receives no shell, network, filesystem, or
arbitrary-code-execution tool. Reset the workspace for every replicate.

The gathering seed is `signature-cot-gathering-v1-2026-07-17`. Terminal-Bench tasks are excluded.

## Replication and replay

- Replicates are `r01`, `r02`, and `r03`; each starts a fresh harvest with fresh boundary canaries
  and a new provider signature.
- Use adaptive thinking at high effort with `display="summarized"`.
- Blind the readable provider summary during every replay.
- Use the fixed `mechanical_boundary_xml_v2` extraction candidate. Do not optimize prompts on this
  corpus.
- Extract every signed decision step once, with at most two continuation calls.
- Treat an instance as complete only after the harvest checkpoint, all decision-step extractions,
  sanitized public artifacts, and progress record are durably written.

## Storage and recovery

Store the run under `experiments/h1b-scenario-gathering/results/gathering-v1/`:

- `manifest.json`: frozen 45-task source manifest;
- `public/`: signature-redacted JSON, Markdown, and ATIF artifacts;
- `progress.json`: exact task/replicate status and failure records;
- `summary.json`: aggregate denominators and scenario metrics;
- `.checkpoints/`: raw replayable signatures and partial restart state, always Git-ignored;
- `run.log`: append-only launcher output with no credentials or raw signatures.

Writes must be atomic. On restart, resume completed harvests and extractions rather than reissuing
provider calls. A failed instance remains visible in progress data and may be retried until three
complete instances exist for its task.

## Measurements

Report exact denominators at task-instance and signed-decision levels:

- completion and provider-failure counts;
- task success;
- ordered boundary validity, leakage, refusal, and unexpected tool-call rates;
- current `strong_recovery` rate, retained only as a historical comparator;
- full-token ratio and log-symmetric alignment;
- summary expansion and summary 5-gram containment;
- summary near-duplicate rate;
- harvest and extraction token usage;
- signed decisions per trajectory and, for agentic coding, tool/action type.

Cross-replicate comparisons may measure stability of summary-distinct details, but any such analysis
is exploratory until its exact statistic and threshold are preregistered separately.

## Stop and success conditions

The collection is complete only when all three scenarios contain at least 15 distinct tasks and
every task has at least three complete instances. Individual `strong_recovery` failures do not stop
collection. Stop immediately only for credential failure, evidence of signature leakage into public
artifacts, manifest/source mismatch, or repeated provider errors that risk corrupting denominators.

Before trusting results:

1. validate the 15/15/15 manifest balance and calibration-source exclusion;
2. verify public artifacts contain redacted signatures only;
3. reproduce aggregate counts directly from artifacts;
4. report censored and failed instances instead of silently dropping them;
5. keep all conclusions below the claim ceiling of a signature-backed recovery candidate.

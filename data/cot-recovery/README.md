# cot-recovery

Signature-backed chain-of-thought recovery attempts over Amazon Bedrock Converse, with exact task
and decision denominators — **including the failures**.

Read [`DATASHEET.md`](DATASHEET.md) before using this. The short version is below.

## Load it

```python
import json

rows = [json.loads(l) for l in open("data/cot-recovery/v1/decisions.jsonl")]
ready = [r for r in rows if r["evidence"]["analysis_ready"]]

len(rows)    # 226 decisions (192 signed, 34 unsigned/censored)
len(ready)   # 13
```

## The headline

| Tier | n | Why |
| --- | --- | --- |
| `analysis_ready` | 13 | Signed, canary intact, ≥ 500 estimated thinking tokens |
| `canary_leaked` | 52 | Working was written to the visible channel; replay can read it from context |
| `below_thinking_floor` | 127 | Under 500 estimated thinking tokens — nothing full-span to recover |
| `unsigned_censored` | 34 | Provider returned no adaptive-thinking block; kept in the denominator |

Outcome on the 13 analysis-ready decisions: **1 plausible recovery, 10 denials, 2 truncated
collapses.**

Where the hidden reasoning is genuinely long, the dominant response to an extraction prompt is a
denial that the record exists. The trivial steps are the ones that happily emit something
marker-wrapped.

## Two traps

**Do not pool `strong_recovery_v0`.** Over all signed decisions it reads 91/192 = 47.4%. That number
is an instrument artifact of four defects documented in the datasheet — the largest being that every
extraction prompt *names the boundary markers it asks the model to prove it recovered*, so a refusal
that quotes them back scores as a strong recovery. Nine did.

**Do not read `protocol_valid` as evidence.** It is a formatting check, not provenance.

## Layout

```
v1/
  decisions.jsonl     226 rows — the unit of analysis
  instances.jsonl     135 rows — harvest + replay episodes
  controls.jsonl        8 rows — H1a synthetic falsification cases, never pooled with live rows
  splits.json           named decision_id lists per tier and outcome
  metadata.json         provenance, counts, known defects, per-file checksums
  schema/               JSON Schema (draft 2020-12); all 226 rows validate
  CHECKSUMS.sha256
```

## Rebuild

```bash
python3 scripts/build_cot_recovery_dataset.py
```

Deterministic — no wall-clock stamps, so unchanged inputs reproduce identical checksums. Source of
record is `experiments/h1b-scenario-gathering/results/gathering-v1/public/`, which the build never
modifies.

## Claim ceiling

Signature-backed full-span recovery **candidate**. There is no independent channel to the provider's
plaintext, so no row here is ground-truth CoT. Never label or train on `recovered_text` as a true
chain of thought, and never pool these rows with a curated success set that lacks a denominator.

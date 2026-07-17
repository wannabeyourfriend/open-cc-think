"""Build the released CoT-recovery dataset from frozen experiment artifacts.

The build is deterministic: it derives every field from checked-in run outputs and stamps no
wall-clock time, so a rebuild on unchanged inputs reproduces byte-identical files and checksums.

Source of record stays in experiments/; this script only reshapes it into a documented release.
Raw signatures never enter the release — the upstream public artifacts carry only signature_sha256.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from signature_cot.scoring import lexical_token_count  # noqa: E402

GATHERING = REPO / "experiments/h1b-scenario-gathering/results/gathering-v1"
FALSIFICATION = REPO / "experiments/h1-metric-falsification/results/metric-falsification.json"

# Selection floor for a full-span claim. Below this the expansion metric has no dynamic range:
# in the curated open-reasoning collection, examples under ~150 thinking tokens score expansion
# 0.22-0.78 (recovery shorter than the summary) and examples under 500 tokens median only 1.41,
# against a median of 2.74-3.51 above 2,500 tokens.
THINKING_FLOOR = 500

# The frozen REFUSAL_MARKERS substring list undercounts refusals. These are the phrasings it misses
# in this corpus; recorded as a separate label rather than folded into the frozen metric.
DENIAL_PHRASES = (
    "no such content",
    "was not produced",
    "never output",
    "i can't complete",
    "i cannot complete",
    "no working record",
    "does not contain the markers",
    "not present in",
    "no content to copy",
    "no such record",
    "there is no",
    "cannot reproduce",
    "no record of",
)

CHARS_PER_TOKEN = 4.0


def est_tokens(text: Optional[str]) -> int:
    return math.ceil(len(text or "") / CHARS_PER_TOKEN)


def is_denial(text: str) -> bool:
    low = text.lower()
    return any(phrase in low for phrase in DENIAL_PHRASES)


def instance_files() -> List[Path]:
    return sorted(
        p for p in (GATHERING / "public").glob("*.json") if not p.name.endswith(".atif.json")
    )


def classify(signed: bool, leaked: bool, est_think: int) -> str:
    """Evidence tier. Precedence matters: an unsigned step has no extraction to judge, and a
    leaked canary voids the step regardless of how much thinking it contains."""
    if not signed:
        return "unsigned_censored"
    if leaked:
        return "canary_leaked"
    if est_think < THINKING_FLOOR:
        return "below_thinking_floor"
    return "analysis_ready"


def outcome_of(metrics: Dict, denial: bool) -> str:
    """Outcome on an analysis-ready decision. A denial is a real observation, not an exclusion:
    it belongs in the denominator of any recovery rate."""
    if denial:
        return "denial"
    if metrics["strong_recovery"]:
        return "plausible_recovery"
    if not metrics["valid"]:
        return "truncated_collapse"
    return "valid_weak"


def build_decisions() -> Iterator[Dict]:
    for path in instance_files():
        doc = json.loads(path.read_text())
        meta = doc["source_metadata"]
        by_step = {e["step_index"]: e for e in doc["extractions"]}
        artifact = str(path.relative_to(REPO))
        for step in doc["steps"]:
            idx = step["step_index"]
            signed = bool(step.get("signature_sha256"))
            trial = by_step.get(idx)
            billed = step["usage"]["outputTokens"]
            vis_tok = est_tokens(step.get("visible_text"))
            calls = step.get("tool_calls") or []
            arg_tok = est_tokens(json.dumps([c.get("arguments") for c in calls]) if calls else "")
            est_think = billed - vis_tok - arg_tok
            summary = step.get("provider_cot_summary") or ""

            metrics = trial["metrics"] if trial else None
            leaked = bool(metrics["marker_leakage"]) if metrics else False
            recovered = (trial.get("recovered") or "") if trial else ""
            denial = bool(metrics["refused"] or is_denial(recovered)) if metrics else False
            tier = classify(signed, leaked, est_think)

            record = {
                "decision_id": f"{doc['task_id']}#s{idx}",
                "instance_id": doc["task_id"],
                "task_id": meta["gathering_task_id"],
                "scenario": doc["scenario"],
                "replicate": meta["replicate"],
                "step_index": idx,
                "source": {
                    "dataset": meta.get("dataset"),
                    "source_id": meta.get("source_id"),
                    "dataset_metadata": meta.get("dataset_metadata") or {},
                },
                "model": doc["model"],
                "reasoning_effort": meta.get("reasoning_effort"),
                "thinking_display": meta.get("thinking_display"),
                "harvest": {
                    "signed": signed,
                    "signature_sha256": step.get("signature_sha256"),
                    "signature_chars": step.get("signature_chars"),
                    "billed_output_tokens": billed,
                    "visible_text_tokens_est": vis_tok,
                    "tool_arg_tokens_est": arg_tok,
                    "est_thinking_tokens": est_think,
                    "stop_reason": step.get("stop_reason"),
                    "tool_calls": [c["name"] for c in calls],
                    "visible_text": step.get("visible_text") or "",
                    "provider_summary": summary,
                    "provider_summary_lexical_tokens": lexical_token_count(summary),
                    "step_prompt": step.get("user_message") or doc["question"],
                },
                "extraction": None,
                "metrics": metrics,
                "labels": {
                    "protocol_valid": bool(metrics["valid"]) if metrics else None,
                    "strong_recovery_v0": bool(metrics["strong_recovery"]) if metrics else None,
                    "canary_leaked": leaked,
                    "refusal_flagged_by_frozen_list": bool(metrics["refused"]) if metrics else None,
                    "denial_detected": denial if metrics else None,
                    "summary_near_duplicate": (
                        bool(metrics["summary_near_duplicate"]) if metrics else None
                    ),
                    "below_thinking_floor": est_think < THINKING_FLOOR,
                },
                "evidence": {
                    "tier": tier,
                    "analysis_ready": tier == "analysis_ready",
                    "outcome": outcome_of(metrics, denial) if tier == "analysis_ready" else None,
                },
                "task_success": doc.get("task_success"),
                "provenance": {
                    "run_id": "H1b-gathering-v1",
                    "artifact": artifact,
                    "collection": "prospective observational",
                },
            }
            if trial:
                record["extraction"] = {
                    "prompt_candidate": trial["candidate"],
                    "prompt_names_markers": True,
                    "provider_summary_blinded": trial.get("provider_summary_blinded"),
                    "rounds": trial.get("rounds"),
                    "stop_reason": trial.get("stop_reason"),
                    "recovered_text": recovered,
                    "recovered_output_tokens": metrics["recovered_output_tokens"],
                    "recovered_lexical_tokens": metrics["recovered_lexical_tokens"],
                }
            yield record


def build_instances() -> Iterator[Dict]:
    progress = json.loads((GATHERING / "progress.json").read_text())
    for path in instance_files():
        doc = json.loads(path.read_text())
        meta = doc["source_metadata"]
        prog = progress["instances"].get(doc["task_id"], {})
        yield {
            "instance_id": doc["task_id"],
            "task_id": meta["gathering_task_id"],
            "scenario": doc["scenario"],
            "replicate": meta["replicate"],
            "source": {"dataset": meta.get("dataset"), "source_id": meta.get("source_id")},
            "model": doc["model"],
            "question": doc["question"],
            "final_answer": doc.get("final_answer"),
            "expected_answer": doc.get("expected_answer"),
            "task_success": doc.get("task_success"),
            "decisions": len(doc["steps"]),
            "signed_decisions": sum(1 for s in doc["steps"] if s.get("signature_sha256")),
            "unsigned_decisions": sum(1 for s in doc["steps"] if not s.get("signature_sha256")),
            "harvest_output_tokens": prog.get("harvest_output_tokens"),
            "extraction_output_tokens": prog.get("extraction_output_tokens"),
            "attempts": prog.get("attempts"),
            "artifacts": {
                "json": str(path.relative_to(REPO)),
                "atif": str((path.parent / f"{doc['task_id']}.atif.json").relative_to(REPO)),
            },
        }


def build_controls() -> Iterator[Dict]:
    doc = json.loads(FALSIFICATION.read_text())
    for row in doc["rows"]:
        yield {
            "control_id": row["case"],
            "expected_positive": row["expected_positive"],
            "suite": "H1a-metric-falsification",
            "kind": "synthetic",
            "metrics": row["metrics"],
            "anchors": row["anchors"],
            "note": (
                "Deterministic synthetic construction. Never pool with live decisions; these exist "
                "to falsify the metric, not to estimate a rate."
            ),
        }


def write_case_view(out: Path, decisions: List[Dict]) -> int:
    """Human-readable view of the analysis-ready rows only.

    decisions.jsonl is authoritative and holds every field; a 900 KB JSONL is not readable, and
    these are the rows anyone actually needs to inspect by eye. Generated, never hand-edited.
    """
    cases = out / "cases"
    cases.mkdir(parents=True, exist_ok=True)
    for stale in cases.glob("*.md"):
        stale.unlink()
    ready = [d for d in decisions if d["evidence"]["analysis_ready"]]
    ready.sort(key=lambda d: -d["harvest"]["est_thinking_tokens"])
    for d in ready:
        h, x, m = d["harvest"], d["extraction"], d["metrics"]
        name = d["decision_id"].replace("#", "-")
        rows = [
            ("scenario", d["scenario"]),
            ("source_id", d["source"]["source_id"]),
            ("replicate", d["replicate"]),
            ("est_thinking_tokens", h["est_thinking_tokens"]),
            ("billed_output_tokens", h["billed_output_tokens"]),
            ("visible_text_tokens_est", h["visible_text_tokens_est"]),
            ("summary_lexical_tokens", h["provider_summary_lexical_tokens"]),
            ("recovered_lexical_tokens", x["recovered_lexical_tokens"]),
            ("summary_expansion_ratio", m["summary_expansion_ratio"]),
            ("full_length_ratio", m["full_length_ratio"]),
            ("summary_ngram_containment", m["summary_ngram_containment"]),
            ("protocol_valid", d["labels"]["protocol_valid"]),
            ("strong_recovery_v0", d["labels"]["strong_recovery_v0"]),
            ("denial_detected", d["labels"]["denial_detected"]),
        ]
        body = [
            f"# {d['decision_id']}",
            "",
            f"Outcome: **{d['evidence']['outcome']}**",
            "",
            "| Field | Value |",
            "| --- | --- |",
            *[f"| `{k}` | {v} |" for k, v in rows],
            "",
            "## Prompt for this decision step",
            "",
            f"> {h['step_prompt'][:700].strip()}",
            "",
            f"## Provider reasoning summary ({h['provider_summary_lexical_tokens']} lexical tokens)",
            "",
            "```",
            h["provider_summary"],
            "```",
            "",
            f"## Recovery ({x['recovered_lexical_tokens']} lexical tokens, "
            f"{len(x['recovered_text'])} chars)",
            "",
            "```",
            x["recovered_text"],
            "```",
            "",
            f"Source artifact: `{d['provenance']['artifact']}`",
            "",
        ]
        (cases / f"{name}.md").write_text("\n".join(body))
    return len(ready)


def write_jsonl(path: Path, rows: Iterable[Dict]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with path.open("w") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            n += 1
    return n


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path, default=REPO / "data/cot-recovery/v1")
    args = ap.parse_args()
    out = args.output
    out.mkdir(parents=True, exist_ok=True)

    decisions = list(build_decisions())
    n_dec = write_jsonl(out / "decisions.jsonl", decisions)
    n_inst = write_jsonl(out / "instances.jsonl", build_instances())
    n_ctl = write_jsonl(out / "controls.jsonl", build_controls())
    n_cases = write_case_view(out, decisions)

    ready = [d for d in decisions if d["evidence"]["analysis_ready"]]
    splits = {
        "analysis_ready": sorted(d["decision_id"] for d in ready),
        "plausible_recovery": sorted(
            d["decision_id"] for d in ready if d["evidence"]["outcome"] == "plausible_recovery"
        ),
        "denial": sorted(d["decision_id"] for d in ready if d["evidence"]["outcome"] == "denial"),
        "canary_leaked": sorted(
            d["decision_id"] for d in decisions if d["evidence"]["tier"] == "canary_leaked"
        ),
        "below_thinking_floor": sorted(
            d["decision_id"] for d in decisions if d["evidence"]["tier"] == "below_thinking_floor"
        ),
        "unsigned_censored": sorted(
            d["decision_id"] for d in decisions if d["evidence"]["tier"] == "unsigned_censored"
        ),
    }
    (out / "splits.json").write_text(json.dumps(splits, indent=2, sort_keys=True) + "\n")

    tiers: Dict[str, int] = {}
    outcomes: Dict[str, int] = {}
    for d in decisions:
        tiers[d["evidence"]["tier"]] = tiers.get(d["evidence"]["tier"], 0) + 1
        o = d["evidence"]["outcome"]
        if o:
            outcomes[o] = outcomes.get(o, 0) + 1

    progress = json.loads((GATHERING / "progress.json").read_text())
    metadata = {
        "name": "cot-recovery",
        "version": "1.0.0",
        "description": (
            "Signature-backed chain-of-thought recovery attempts over Amazon Bedrock Converse, "
            "with exact task and decision denominators."
        ),
        "claim_ceiling": (
            "signature-backed full-span recovery candidate; no row is ground-truth CoT and no "
            "recovered span may be labelled or pooled as provider plaintext"
        ),
        "source_run": {
            "run_id": "H1b-gathering-v1",
            "model": progress["model"],
            "manifest_sha256": progress["manifest_sha256"],
            "collected_at": progress["updated_at"],
            "results_dir": str(GATHERING.relative_to(REPO)),
        },
        "counts": {
            "instances": n_inst,
            "decisions": n_dec,
            "controls": n_ctl,
            "tiers": dict(sorted(tiers.items())),
            "outcomes_on_analysis_ready": dict(sorted(outcomes.items())),
        },
        "selection": {
            "thinking_floor_tokens": THINKING_FLOOR,
            "est_thinking_formula": (
                "billed outputTokens - ceil(len(visible_text)/4) - ceil(len(tool_args)/4)"
            ),
            "rationale": (
                "Bedrock bills outputTokens inclusive of visible text. Below the floor the "
                "expansion metric has no dynamic range, so those rows cannot support or refute a "
                "full-span claim."
            ),
        },
        "known_defects": {
            "canary_echo": (
                "Every extraction prompt interpolates the boundary markers, so markers_in_order is "
                "satisfiable by echo. Boundary canaries carry no provenance information in this "
                "release; treat protocol_valid as a formatting check only."
            ),
            "refusal_undercount": (
                "The frozen REFUSAL_MARKERS list missed 10 refusals. Use labels.denial_detected, "
                "not labels.refusal_flagged_by_frozen_list."
            ),
            "v0_gate_permissive": (
                "labels.strong_recovery_v0 accepts novelty >= 0.12 alone and therefore passes short "
                "re-derivations. Pooling it over all decisions yields 47.4%, which is an instrument "
                "artifact. Do not report it as a recovery rate."
            ),
            "no_content_anchors": (
                "No hidden content anchors were planted, so H1a's ordered-anchor fidelity test "
                "cannot be applied to any live row."
            ),
        },
        "exclusions": [
            "raw reasoningContent signatures (replayable state; only sha256 and length retained)",
            "pre-blinding v1/v2 artifacts under src/artifacts/ (not pooled with blind rows)",
            "smoke runs smoke-v1..v4 (harness validation, not collection)",
        ],
        "files": {},
    }
    for name in ["decisions.jsonl", "instances.jsonl", "controls.jsonl", "splits.json"]:
        p = out / name
        metadata["files"][name] = {"bytes": p.stat().st_size, "sha256": sha256(p)}
    (out / "metadata.json").write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n")

    lines = [
        f"{sha256(out / n)}  {n}"
        for n in sorted(["decisions.jsonl", "instances.jsonl", "controls.jsonl", "splits.json",
                         "metadata.json"])
    ]
    (out / "CHECKSUMS.sha256").write_text("\n".join(lines) + "\n")

    print(f"wrote {n_dec} decisions, {n_inst} instances, {n_ctl} controls, "
          f"{n_cases} case files -> {out}")
    print(f"tiers: {tiers}")
    print(f"outcomes on analysis_ready: {outcomes}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

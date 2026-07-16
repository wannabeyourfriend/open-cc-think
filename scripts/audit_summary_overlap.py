#!/usr/bin/env python3
"""Audit existing recovered reasoning against provider-returned thinking summaries."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from signature_cot.scoring import compare_summary_recovery  # noqa: E402


Json = Dict[str, Any]
CANARY = re.compile(r"\bCOT-(START|END)-[A-Z0-9-]+\b")


def _markers(summary: str, recovered: str, explicit: Optional[Json] = None) -> Tuple[str, str]:
    if explicit:
        return str(explicit.get("start", "")), str(explicit.get("end", ""))
    found: Dict[str, str] = {}
    for match in CANARY.finditer(summary + "\n" + recovered):
        found.setdefault(match.group(1), match.group(0))
    return found.get("START", ""), found.get("END", "")


def _summary_from_public_step(step: Json) -> str:
    if step.get("provider_cot_summary"):
        return str(step["provider_cot_summary"])
    parts: List[str] = []
    for block in step.get("assistant_content", []):
        reasoning = block.get("reasoningContent") if isinstance(block, dict) else None
        reasoning_text = reasoning.get("reasoningText") if isinstance(reasoning, dict) else None
        text = reasoning_text.get("text") if isinstance(reasoning_text, dict) else None
        if text:
            parts.append(str(text))
    return "\n".join(parts).strip()


def _classification(
    comparison: Json,
    *,
    recovery_present: bool,
    protocol_valid: bool,
    provider_summary_blinded: bool,
) -> str:
    if not recovery_present or not protocol_valid:
        return "invalid"
    if comparison["summary_near_duplicate"]:
        return "weak-near-duplicate"
    if comparison["summary_comparison_available"] and not provider_summary_blinded:
        return "weak-summary-visible"
    if not comparison["distinct_from_summary"]:
        return "weak-low-novelty"
    return "strong-candidate"


def _row(
    *,
    path: Path,
    task_id: str,
    step_index: int,
    candidate: str,
    summary: str,
    recovered: str,
    markers: Optional[Json],
    protocol_valid: bool,
    provider_summary_blinded: bool,
) -> Json:
    start, end = _markers(summary, recovered, markers)
    comparison = compare_summary_recovery(
        summary,
        recovered,
        start_marker=start,
        end_marker=end,
    )
    return {
        "artifact": str(path.relative_to(ROOT)),
        "task_id": task_id,
        "step_index": step_index,
        "candidate": candidate,
        "protocol_valid": protocol_valid,
        "provider_summary_blinded": provider_summary_blinded,
        "classification": _classification(
            comparison,
            recovery_present=bool(recovered),
            protocol_valid=protocol_valid,
            provider_summary_blinded=provider_summary_blinded,
        ),
        **comparison,
        "summary_chars": len(summary),
        "recovered_chars": len(recovered),
    }


def audit_atif(path: Path, payload: Json) -> Iterable[Json]:
    task_id = str(payload.get("extra", {}).get("task_id", path.stem))
    public_path = path.with_name(path.name.replace(".atif.json", ".json"))
    public_payload = (
        json.loads(public_path.read_text(encoding="utf-8"))
        if public_path.exists()
        else {}
    )
    agent_index = 0
    for step in payload.get("steps", []):
        if not isinstance(step, dict) or step.get("source") != "agent":
            continue
        recovery = step.get("extra", {}).get("signed_full_cot_recovery") or {}
        summary = str(step.get("extra", {}).get("provider_cot_summary", ""))
        recovered = str(step.get("reasoning_content", ""))
        public_extraction = next(
            (
                extraction
                for extraction in public_payload.get("extractions", [])
                if isinstance(extraction, dict)
                and int(extraction.get("step_index", -1)) == agent_index
                and str(extraction.get("candidate", ""))
                == str(recovery.get("candidate", ""))
            ),
            {},
        )
        if not recovered and public_extraction:
            recovered = str(public_extraction.get("recovered", ""))
        public_metrics = (
            public_extraction.get("metrics")
            if isinstance(public_extraction.get("metrics"), dict)
            else {}
        )
        provider_summary_blinded = bool(
            recovery.get(
                "provider_summary_blinded_in_replay",
                public_extraction.get("provider_summary_blinded", False),
            )
        )
        yield _row(
            path=path,
            task_id=task_id,
            step_index=agent_index,
            candidate=str(recovery.get("candidate", "selected")),
            summary=summary,
            recovered=recovered,
            markers=None,
            protocol_valid=bool(
                recovery.get("valid", public_metrics.get("valid", recovered))
            ),
            # Schema v1/v2 artifacts predate blind replay and always replayed the
            # provider summary verbatim, regardless of their historical summary_used flag.
            provider_summary_blinded=provider_summary_blinded,
        )
        agent_index += 1


def audit_public(path: Path, payload: Json) -> Iterable[Json]:
    task_id = str(payload.get("task_id", path.stem))
    steps = {
        int(step.get("step_index", index)): step
        for index, step in enumerate(payload.get("steps", []))
        if isinstance(step, dict)
    }
    for extraction in payload.get("extractions", []):
        if not isinstance(extraction, dict):
            continue
        step_index = int(extraction.get("step_index", 0))
        step = steps.get(step_index, {})
        metrics = extraction.get("metrics") if isinstance(extraction.get("metrics"), dict) else {}
        yield _row(
            path=path,
            task_id=task_id,
            step_index=step_index,
            candidate=str(extraction.get("candidate", "unknown")),
            summary=_summary_from_public_step(step),
            recovered=str(extraction.get("recovered", "")),
            markers=step.get("markers") if isinstance(step.get("markers"), dict) else None,
            protocol_valid=bool(metrics.get("valid", False)),
            provider_summary_blinded=bool(
                extraction.get("provider_summary_blinded", False)
            ),
        )


def collect(root: Path, include_all_candidates: bool) -> List[Json]:
    root = root.resolve()
    atif_paths = sorted(root.rglob("*.atif.json"))
    rows: List[Json] = []
    for path in atif_paths:
        rows.extend(audit_atif(path, json.loads(path.read_text(encoding="utf-8"))))
    if include_all_candidates:
        for path in sorted(root.rglob("*.json")):
            if path.name.endswith(".atif.json") or any(
                part in {".checkpoints", "private"} for part in path.parts
            ):
                continue
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, dict) and payload.get("extractions"):
                rows.extend(audit_public(path, payload))
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path, nargs="?", default=ROOT / "src" / "artifacts")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--include-all-candidates", action="store_true")
    args = parser.parse_args()
    rows = collect(args.root, args.include_all_candidates)
    counts: Dict[str, int] = {}
    for row in rows:
        counts[row["classification"]] = counts.get(row["classification"], 0) + 1
    compared = [row for row in rows if row["summary_comparison_available"]]
    payload = {
        "schema_version": 1,
        "thresholds": {
            "near_duplicate": (
                "sequence>=0.82 with length ratio 0.70..1.45, or jaccard>=0.85 "
                "with ratio<=1.50, or recovery-token coverage>=0.92 with ratio<=1.35"
            ),
            "strong_candidate": (
                "protocol-valid, summary blinded/unavailable, not near-duplicate, and "
                "length ratio>=1.15 or unique-token novelty>=0.12"
            ),
        },
        "summary": {
            "rows": len(rows),
            "with_summary": len(compared),
            "classifications": counts,
            "mean_jaccard": round(
                sum(float(row["summary_jaccard"]) for row in compared) / max(1, len(compared)),
                4,
            ),
            "mean_sequence_similarity": round(
                sum(float(row["summary_sequence_similarity"]) for row in compared)
                / max(1, len(compared)),
                4,
            ),
        },
        "rows": rows,
    }
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 1 if counts.get("strong-candidate", 0) != len(rows) else 0


if __name__ == "__main__":
    raise SystemExit(main())

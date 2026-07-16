#!/usr/bin/env python3
"""Run the frozen H1a deterministic recovery-metric falsification suite."""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from pathlib import Path
from typing import Dict, List


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from signature_cot.models import BoundaryMarkers, HarvestStep  # noqa: E402
from signature_cot.scoring import (  # noqa: E402
    lexical_token_count,
    score_content_anchors,
    score_recovery,
)


START = "COT-START-S00-METRICCAL"
END = "COT-END-S00-METRICCAL"
ANCHORS = tuple(
    "COT-ANCHOR-A%d-%s" % (index, value)
    for index, value in enumerate(
        ("7F31", "B204", "19CE", "D882", "44AF", "C610"),
        start=1,
    )
)
SUMMARY_BODY = (
    "Enumerate the admissible cases, correct one double count, and verify the final total."
)
FULL_TRACE = "\n".join(
    (
        START,
        ANCHORS[0],
        "Represent each object by an ordered pair and enumerate the six admissible classes.",
        ANCHORS[1],
        "The first pass gives 18 + 12 + 9 + 7 + 4 + 3 = 53.",
        ANCHORS[2],
        "That total double-counts the symmetric class: subtract 5, giving 48.",
        ANCHORS[3],
        "Correction: the third class has 11 rather than 9, so add 2 and obtain 50.",
        ANCHORS[4],
        "Independent complement count gives 64 - 14 = 50, matching the corrected result.",
        ANCHORS[5],
        "The final answer is 50.",
        END,
    )
)
SUMMARY = "\n".join((START, SUMMARY_BODY, END))


def _bounded(*parts: str) -> str:
    return "\n".join((START, *parts, END))


def frozen_cases() -> Dict[str, str]:
    return {
        "exact_full": FULL_TRACE,
        "partial_prefix": "\n".join(FULL_TRACE.splitlines()[:5]),
        "summary_copy": SUMMARY,
        "padded_summary": _bounded(
            SUMMARY_BODY,
            " ".join(
                "plausible but irrelevant elaboration %02d" % index
                for index in range(1, 41)
            ),
        ),
        "boundary_only": _bounded(),
        "reordered_anchors": FULL_TRACE.replace(
            ANCHORS[1],
            "ANCHOR-SWAP-PLACEHOLDER",
        )
        .replace(ANCHORS[2], ANCHORS[1])
        .replace("ANCHOR-SWAP-PLACEHOLDER", ANCHORS[2]),
        "corrupted_anchor": FULL_TRACE.replace(
            ANCHORS[3],
            "COT-ANCHOR-A4-BAD0",
        ),
        "fresh_solution": _bounded(
            "A fresh derivation enumerates six cases, fixes a double count, and obtains 50.",
            "The complement calculation also gives 50.",
        ),
    }


def run() -> Dict[str, object]:
    full_tokens = lexical_token_count(
        FULL_TRACE,
        start_marker=START,
        end_marker=END,
    )
    step = HarvestStep(
        step_index=0,
        prefix_messages=[],
        assistant_content=[
            {
                "reasoningContent": {
                    "reasoningText": {
                        "text": SUMMARY,
                        "signature": "synthetic-not-replayable",
                    }
                }
            },
            {"text": "50"},
        ],
        stop_reason="end_turn",
        usage={"outputTokens": full_tokens},
        markers=BoundaryMarkers(START, END),
        visible_text="50",
        tool_calls=[],
    )
    rows: List[Dict[str, object]] = []
    for name, recovered in frozen_cases().items():
        recovered_tokens = lexical_token_count(
            recovered,
            start_marker=START,
            end_marker=END,
        )
        metrics = score_recovery(
            step,
            recovered,
            raw_text=recovered,
            recovered_output_tokens=recovered_tokens,
            replay_emitted_tool_call=False,
            provider_summary_blinded=True,
        )
        rows.append(
            {
                "case": name,
                "expected_positive": name == "exact_full",
                "metrics": dataclasses.asdict(metrics),
                "anchors": score_content_anchors(ANCHORS, recovered),
            }
        )

    by_name = {str(row["case"]): row for row in rows}
    checks = {
        "exact_anchor_complete": (
            by_name["exact_full"]["anchors"]["precision"] == 1.0
            and by_name["exact_full"]["anchors"]["recall"] == 1.0
            and by_name["exact_full"]["anchors"]["ordered"]
            and by_name["exact_full"]["anchors"]["corruption_rate"] == 0.0
        ),
        "exact_length_aligned": (
            by_name["exact_full"]["metrics"]["full_length_alignment"] >= 0.90
        ),
        "partial_short_and_unbounded": (
            by_name["partial_prefix"]["metrics"]["full_length_ratio"] < 0.65
            and not by_name["partial_prefix"]["metrics"]["markers_in_order"]
        ),
        "summary_copy_contained": (
            by_name["summary_copy"]["metrics"]["summary_ngram_containment"] >= 0.90
        ),
        "padded_summary_contained": (
            by_name["padded_summary"]["metrics"]["summary_ngram_containment"] >= 0.90
        ),
        "boundary_only_short_and_anchorless": (
            by_name["boundary_only"]["metrics"]["summary_expansion_ratio"] < 0.25
            and by_name["boundary_only"]["anchors"]["recall"] == 0.0
        ),
        "reordered_anchor_detected": (
            not by_name["reordered_anchors"]["anchors"]["ordered"]
        ),
        "corrupted_anchor_detected": (
            by_name["corrupted_anchor"]["anchors"]["recall"] < 1.0
            and by_name["corrupted_anchor"]["anchors"]["corruption_rate"] > 0.0
        ),
        "fresh_solution_anchorless": (
            by_name["fresh_solution"]["anchors"]["recall"] == 0.0
        ),
    }
    return {
        "schema_version": 1,
        "experiment": "H1a-metric-falsification",
        "metric_status": "diagnostic-only",
        "synthetic_full_tokens": full_tokens,
        "checks": checks,
        "all_checks_passed": all(checks.values()),
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=(
            ROOT
            / "experiments"
            / "h1-metric-falsification"
            / "results"
            / "metric-falsification.json"
        ),
    )
    args = parser.parse_args()
    payload = run()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["all_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

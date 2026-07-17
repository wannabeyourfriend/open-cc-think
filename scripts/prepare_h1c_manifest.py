#!/usr/bin/env python3
"""Build the H1c long-CoT gathering manifest from RealFP Fermi problems.

Task selection is by *measured* behaviour, not dataset label. H1b chose GSM8K because it was
labelled "math reasoning" and got 67 thinking tokens per step, which made every downstream metric
vacuous. Pilots for H1c measured the yield of each candidate before any task entered the manifest:

  MATH-500 level 5, answer-only contract      median   438 thinking tokens
  RealFP raw question, answer-only contract   median   140 thinking tokens
  RealFP + chat-14 instruction, prose allowed see experiments/h1c-long-cot/results/pilot
  gather-chat-14 (mt-bench-143 turn 2)               5,973 / 5,656 / 5,069

Source: RealFP (Kalyan et al., EMNLP 2021), 557 real Fermi problems with reference answers.
Fermi answers are order-of-magnitude estimates, so `expected_answer` is retained for offline
order-of-magnitude scoring and is never used as a harvest-time gate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import urllib.request
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
SEED = "signature-cot-h1c-long-cot-v1-2026-07-17"
REALFP_URL = "https://raw.githubusercontent.com/allenai/fermi/main/data/realFP/test_realfp.json"
DEFAULT_OUTPUT = ROOT / "experiments/h1c-long-cot/results/gathering-v1/manifest.json"

# Verbatim from mt-bench-143 turn 2 (gather-chat-14), the only prompt shape observed to induce
# >5k hidden thinking tokens. The demand for a thorough visible derivation is the active
# ingredient; an answer-only contract suppresses thinking to ~140 tokens on the same questions.
CHAT14_SUFFIX = (
    "Please provide an estimate using actual numerical values and thoroughly explain your "
    "thought process step-by-step."
)


def download(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "signature-cot-research/0.3"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def build(tasks: int, replicates: int) -> Dict[str, Any]:
    body = download(REALFP_URL)
    rows: List[Dict[str, Any]] = json.loads(body)

    eligible = [
        row
        for row in rows
        if isinstance(row.get("question"), str)
        and len(row["question"].strip()) >= 30
        and str(row.get("answer", "")).strip()
    ]
    eligible.sort(key=lambda r: hashlib.sha256((SEED + "\0" + r["question"]).encode()).hexdigest())
    picked = eligible[:tasks]

    manifest_tasks = [
        {
            "task_id": "h1c-fermi-%02d" % (i + 1),
            "scenario": "fermi_estimation",
            "source": "realfp",
            "source_id": "realfp-%s" % hashlib.sha256(row["question"].encode()).hexdigest()[:12],
            "turns": ["%s\n\n%s" % (row["question"].strip(), CHAT14_SUFFIX)],
            "expected_answer": str(row["answer"]).strip(),
            "metadata": {
                "reference_answer": str(row["answer"]).strip(),
                "recipe": "gather-chat-14 (mt-bench-143 turn 2) instruction suffix",
                "context_withheld": True,
                "context_rationale": (
                    "RealFP ships a CONTEXT field listing the facts its reference answer assumes. "
                    "Supplying it turns the task into arithmetic substitution and collapses hidden "
                    "reasoning; withholding it forces the model to derive its own assumptions, "
                    "which is the behaviour under study."
                ),
                "scoring": (
                    "Weak comparator: the reference answer is conditioned on the withheld context, "
                    "so a divergent estimate is not necessarily wrong. Order-of-magnitude only, "
                    "offline, never a harvest-time gate, and never combined with recovery evidence."
                ),
            },
        }
        for i, row in enumerate(picked)
    ]

    return {
        "schema_version": 1,
        "experiment": "H1c-long-cot-v1",
        "selection": {
            "seed": SEED,
            "rule": "SHA-256 rank of seed and question over RealFP rows with a reference answer",
            "tasks": tasks,
            "replicates_per_task": replicates,
            "task_instances": tasks * replicates,
            "basis": "pilot-measured thinking yield; see experiments/h1c-long-cot/results/pilot",
        },
        "sources": {
            "fermi_estimation": {
                "name": "realfp",
                "url": REALFP_URL,
                "sha256": hashlib.sha256(body).hexdigest(),
                "citation": (
                    "Kalyan et al., How Much Coffee Was Consumed During EMNLP 2019? "
                    "Fermi Problems: A New Reasoning Challenge for AI. EMNLP 2021."
                ),
                "rows_available": len(rows),
                "rows_eligible": len(eligible),
            }
        },
        "tasks": manifest_tasks,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", type=int, default=20)
    ap.add_argument("--replicates", type=int, default=5)
    ap.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = ap.parse_args()

    manifest = build(args.tasks, args.replicates)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    args.output.write_text(payload, encoding="utf-8")
    print(
        "wrote %d tasks x %d replicates = %d instances -> %s"
        % (args.tasks, args.replicates, args.tasks * args.replicates, args.output)
    )
    print("manifest sha256: %s" % hashlib.sha256(payload.encode()).hexdigest())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

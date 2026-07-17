"""Test the gather-chat-14 recipe on an existing Fermi-problem benchmark.

Two pilots already came back negative and together they localise the mechanism:

  MATH-500 level 5, answer-only contract   -> median  438 thinking tokens
  RealFP raw question, answer-only contract -> median  140 thinking tokens
  gather-chat-14 (mt-bench-143 turn 2)      ->        5,973 thinking tokens

Difficulty is not what drives hidden reasoning; Sonnet 5 disposes of a competition-math level 5
problem in ~400 tokens. What chat-14 does differently is demand a thorough visible derivation
("provide an estimate using actual numerical values and thoroughly explain your thought process
step-by-step"), under a harvester that permits prose. The answer-only system prompt actively
suppresses thinking: there is no reason to derive carefully when the deliverable is one number.

This pilot isolates that variable: RealFP questions + the chat-14 instruction + ScenarioHarvester.
Harvest only, no replay.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import sys
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from signature_cot.bedrock import BedrockClient, ProviderError  # noqa: E402
from signature_cot.config import ProviderConfig  # noqa: E402
from signature_cot.harvest import ScenarioHarvester  # noqa: E402

# Verbatim from mt-bench-143 turn 2, the only prompt shape observed to produce >5k hidden tokens.
CHAT14_SUFFIX = (
    "Please provide an estimate using actual numerical values and thoroughly explain your "
    "thought process step-by-step."
)


def est_thinking(step) -> int:
    return step.output_tokens - math.ceil(len(step.visible_text or "") / 4.0)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=6)
    ap.add_argument("--effort", default="high")
    ap.add_argument("--max-tokens", type=int, default=32000)
    ap.add_argument("--offset", type=int, default=0)
    ap.add_argument("--data", type=Path, default=Path("/tmp/realfp.json"))
    ap.add_argument("--output", type=Path, default=ROOT / "experiments/h1c-long-cot/results/pilot")
    args = ap.parse_args()

    pool = json.loads(args.data.read_text())
    pool.sort(key=lambda r: hashlib.sha256(str(r["question"]).encode()).hexdigest())
    picked = pool[args.offset : args.offset + args.count]

    client = BedrockClient(ProviderConfig.from_env())
    harvester = ScenarioHarvester(
        client, max_tokens=args.max_tokens, effort=args.effort, thinking_display="summarized"
    )

    args.output.mkdir(parents=True, exist_ok=True)
    results: List[Dict] = []
    for i, row in enumerate(picked, 1 + args.offset):
        task_id = f"pilot-fermi-recipe-{i:02d}"
        turn = f"{row['question'].strip()}\n\n{CHAT14_SUFFIX}"
        try:
            run = harvester.run(task_id, [turn], scenario="fermi_estimation")
        except ProviderError as exc:
            print(f"  {task_id}: PROVIDER ERROR {exc}")
            results.append({"task_id": task_id, "error": str(exc)})
            continue
        step = run.steps[0]
        think = est_thinking(step)
        results.append(
            {
                "task_id": task_id,
                "question": row["question"][:160],
                "reference_answer": str(row.get("answer")),
                "billed_output_tokens": step.output_tokens,
                "visible_chars": len(step.visible_text or ""),
                "est_thinking_tokens": think,
                "signed": bool(step.signature),
                "canary_leaked": step.marker_leaked(),
                "summary_chars": len(step.provider_reasoning_summary or ""),
            }
        )
        print(
            f"  {task_id}: think={think:6d} billed={step.output_tokens:6d} "
            f"visible={len(step.visible_text or ''):5d}ch leaked={step.marker_leaked()} "
            f"signed={bool(step.signature)}"
        )

    good = [r for r in results if "error" not in r]
    (args.output / "fermi-recipe.json").write_text(json.dumps(results, indent=2) + "\n")
    if good:
        t = sorted(r["est_thinking_tokens"] for r in good)
        print(f"\n=== RealFP + chat-14 recipe (n={len(good)}) ===")
        print(f"  est thinking: min={t[0]} median={statistics.median(t):.0f} max={t[-1]}")
        print(f"  >= 2500: {sum(1 for x in t if x >= 2500)}/{len(t)}   "
              f">= 500: {sum(1 for x in t if x >= 500)}/{len(t)}")
        print(f"  leaked: {sum(r['canary_leaked'] for r in good)}/{len(good)}")
        print(f"  errors: {len(results) - len(good)}/{len(results)}")
        print(f"\n  baseline gather-chat-14: 5,973 / 5,656 / 5,069")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

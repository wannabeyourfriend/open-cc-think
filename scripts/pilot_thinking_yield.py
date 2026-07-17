"""Measure hidden-thinking yield per candidate source before committing to a gathering run.

H1b's corpus failed because task difficulty was chosen by dataset label: GSM8K billed 67 thinking
tokens per step, so its recoveries were re-derivations. This pilot harvests only (no replay) and
reports the distribution of estimated thinking tokens, so the H1c pool is selected on measured
behaviour rather than on the name of the benchmark.

Cheap by construction: one harvest per task, no extraction.
"""

from __future__ import annotations

import argparse
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
from signature_cot.harvest import QuestionHarvester  # noqa: E402


def est_thinking(step) -> int:
    visible = math.ceil(len(step.visible_text or "") / 4.0)
    return step.output_tokens - visible


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True, choices=("math500-l5", "realfp"))
    ap.add_argument("--count", type=int, default=6)
    ap.add_argument("--effort", default="high")
    ap.add_argument("--max-tokens", type=int, default=32000)
    ap.add_argument("--data", type=Path, default=Path("/tmp/math500.jsonl"))
    ap.add_argument("--output", type=Path, default=ROOT / "experiments/h1c-long-cot/results/pilot")
    args = ap.parse_args()

    import hashlib

    if args.source == "math500-l5":
        rows = [json.loads(l) for l in args.data.read_text().splitlines() if l.strip()]
        pool = [r for r in rows if str(r.get("level")) == "5"]
        key = lambda r: str(r["unique_id"])
        prompt_of = lambda r: str(r["problem"])
        # Exact-match answers, so the compact-visible check can use them.
        expected_of = lambda r: str(r["answer"])
    else:
        pool = json.loads(Path("/tmp/realfp.json").read_text())
        key = lambda r: str(r["question"])
        prompt_of = lambda r: str(r["question"])
        # Fermi answers are order-of-magnitude estimates; an exact-match gate would force
        # pointless retries. Score agreement offline instead.
        expected_of = lambda r: None
    # Deterministic pick, same frozen-ranking idea as the H1b manifest.
    pool.sort(key=lambda r: hashlib.sha256(key(r).encode()).hexdigest())
    picked = pool[: args.count]

    config = ProviderConfig.from_env(model=None, region=None)
    client = BedrockClient(config)
    harvester = QuestionHarvester(
        client, max_tokens=args.max_tokens, effort=args.effort, thinking_display="summarized"
    )

    args.output.mkdir(parents=True, exist_ok=True)
    results: List[Dict] = []
    for i, row in enumerate(picked, 1):
        task_id = f"pilot-{args.source}-{i:02d}"
        try:
            run = harvester.run(task_id, prompt_of(row), expected_of(row))
        except ProviderError as exc:
            print(f"  {task_id}: PROVIDER ERROR {exc}")
            results.append({"task_id": task_id, "error": str(exc), "source_ref": key(row)[:80]})
            continue
        step = run.steps[0]
        think = est_thinking(step)
        leaked = step.marker_leaked()
        ok = run.task_success
        results.append(
            {
                "task_id": task_id,
                "source_ref": key(row)[:80],
                "subject": row.get("subject"),
                "billed_output_tokens": step.output_tokens,
                "visible_chars": len(step.visible_text or ""),
                "est_thinking_tokens": think,
                "signed": bool(step.signature),
                "canary_leaked": leaked,
                "task_success": ok,
                "summary_chars": len(step.provider_reasoning_summary or ""),
            }
        )
        print(
            f"  {task_id}: think={think:6d} billed={step.output_tokens:6d} "
            f"visible={len(step.visible_text or ''):4d}ch leaked={leaked} success={ok}"
        )

    good = [r for r in results if "error" not in r]
    (args.output / f"{args.source}.json").write_text(json.dumps(results, indent=2) + "\n")
    if good:
        t = sorted(r["est_thinking_tokens"] for r in good)
        print(f"\n=== {args.source} (n={len(good)}) ===")
        print(f"  est thinking: min={t[0]} median={statistics.median(t):.0f} max={t[-1]}")
        print(f"  >= 2500 tokens: {sum(1 for x in t if x >= 2500)}/{len(t)}")
        print(f"  >=  500 tokens: {sum(1 for x in t if x >= 500)}/{len(t)}")
        print(f"  leaked: {sum(r['canary_leaked'] for r in good)}/{len(good)}")
        print(f"  task success: {sum(1 for r in good if r['task_success'])}/{len(good)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

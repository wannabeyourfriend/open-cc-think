#!/usr/bin/env python3
"""Build the fixed 12/12/12 calibration manifest from official source files."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import urllib.request
from pathlib import Path
from typing import Any, Dict, Iterable, List


SEED = "signature-cot-calibration-v1-2026-07-16"
SOURCES = {
    "coding": (
        "human-eval",
        "https://raw.githubusercontent.com/openai/human-eval/master/data/HumanEval.jsonl.gz",
    ),
    "math": (
        "gsm8k-train",
        "https://raw.githubusercontent.com/openai/grade-school-math/master/grade_school_math/data/train.jsonl",
    ),
    "chat": (
        "mt-bench",
        "https://raw.githubusercontent.com/lm-sys/FastChat/main/fastchat/llm_judge/data/mt_bench/question.jsonl",
    ),
}


def download(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "signature-cot-research/0.2"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def json_lines(data: bytes) -> List[Dict[str, Any]]:
    return [json.loads(line) for line in data.decode("utf-8").splitlines() if line.strip()]


def stable_sample(rows: Iterable[Dict[str, Any]], id_key: str, count: int) -> List[Dict[str, Any]]:
    ranked = sorted(
        rows,
        key=lambda row: hashlib.sha256(
            (SEED + "\0" + str(row[id_key])).encode("utf-8")
        ).hexdigest(),
    )
    return ranked[:count]


def final_gsm_answer(answer: str) -> str:
    marker = "####"
    return answer.rsplit(marker, 1)[-1].strip() if marker in answer else ""


def build(count: int) -> Dict[str, Any]:
    source_meta: Dict[str, Any] = {}
    raw: Dict[str, bytes] = {}
    for scenario, (name, url) in SOURCES.items():
        body = download(url)
        raw[scenario] = body
        source_meta[scenario] = {
            "name": name,
            "url": url,
            "sha256": hashlib.sha256(body).hexdigest(),
        }

    human_eval = json_lines(gzip.decompress(raw["coding"]))
    coding = [
        {
            "task_id": "cal-coding-%02d" % (index + 1),
            "scenario": "coding",
            "source": "human-eval",
            "source_id": row["task_id"],
            "turns": [
                "Complete the following Python function. Return the complete function implementation "
                "as code, with no discussion outside the code block.\n\n" + row["prompt"]
            ],
            "expected_answer": None,
            "metadata": {"entry_point": row.get("entry_point")},
        }
        for index, row in enumerate(stable_sample(human_eval, "task_id", count))
    ]

    gsm = json_lines(raw["math"])
    for index, row in enumerate(gsm):
        row["_source_id"] = "gsm8k-train-%05d" % index
    math = [
        {
            "task_id": "cal-math-%02d" % (index + 1),
            "scenario": "math",
            "source": "gsm8k-train",
            "source_id": row["_source_id"],
            "turns": [row["question"]],
            "expected_answer": final_gsm_answer(row["answer"]),
            "metadata": {},
        }
        for index, row in enumerate(stable_sample(gsm, "_source_id", count))
    ]

    mt_bench = json_lines(raw["chat"])
    eligible = [
        row
        for row in mt_bench
        if str(row.get("category", "")).casefold() not in {"math", "coding", "reasoning"}
    ]
    chat = [
        {
            "task_id": "cal-chat-%02d" % (index + 1),
            "scenario": "chat",
            "source": "mt-bench",
            "source_id": "mt-bench-%s" % row["question_id"],
            "turns": list(row["turns"]),
            "expected_answer": None,
            "metadata": {"category": row.get("category")},
        }
        for index, row in enumerate(stable_sample(eligible, "question_id", count))
    ]

    return {
        "schema_version": 1,
        "selection": {
            "seed": SEED,
            "method": "lowest SHA-256(seed + NUL + source_id)",
            "instances_per_scenario": count,
            "chat_excluded_categories": ["coding", "math", "reasoning"],
        },
        "sources": source_meta,
        "tasks": coding + math + chat,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=12)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "src" / "calibration" / "fixed-36.json",
    )
    args = parser.parse_args()
    payload = build(args.count)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("wrote %s tasks to %s" % (len(payload["tasks"]), args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


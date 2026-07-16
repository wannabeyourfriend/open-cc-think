#!/usr/bin/env python3
"""Build the H1b 15/15/15 gathering manifest from frozen source rules."""

from __future__ import annotations

import argparse
import hashlib
import json
import urllib.request
from pathlib import Path
from typing import Any, Dict, Iterable, List, Set


ROOT = Path(__file__).resolve().parents[1]
SEED = "signature-cot-gathering-v1-2026-07-17"
FIXED_MANIFEST = ROOT / "src" / "calibration" / "fixed-36.json"
CODING_FIXTURES = ROOT / "src" / "gathering" / "coding-fixtures.json"
DEFAULT_OUTPUT = (
    ROOT
    / "experiments"
    / "h1b-scenario-gathering"
    / "results"
    / "gathering-v1"
    / "manifest.json"
)
SOURCES = {
    "math_reasoning": (
        "gsm8k-train",
        "https://raw.githubusercontent.com/openai/grade-school-math/master/grade_school_math/data/train.jsonl",
    ),
    "complex_conversational_qa": (
        "mt-bench",
        "https://raw.githubusercontent.com/lm-sys/FastChat/main/fastchat/llm_judge/data/mt_bench/question.jsonl",
    ),
}


def download(url: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "signature-cot-research/0.3"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def json_lines(data: bytes) -> List[Dict[str, Any]]:
    return [
        json.loads(line)
        for line in data.decode("utf-8").splitlines()
        if line.strip()
    ]


def stable_sample(
    rows: Iterable[Dict[str, Any]],
    id_key: str,
    count: int,
) -> List[Dict[str, Any]]:
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


def excluded_source_ids() -> Dict[str, Set[str]]:
    payload = json.loads(FIXED_MANIFEST.read_text(encoding="utf-8"))
    excluded: Dict[str, Set[str]] = {"math": set(), "chat": set()}
    for row in payload.get("tasks", []):
        scenario = str(row.get("scenario", ""))
        if scenario in excluded:
            excluded[scenario].add(str(row.get("source_id", "")))
    return excluded


def build(count: int = 15) -> Dict[str, Any]:
    if count < 15:
        raise ValueError("H1b requires at least 15 tasks per scenario")
    excluded = excluded_source_ids()
    raw: Dict[str, bytes] = {}
    source_meta: Dict[str, Any] = {}
    for scenario, (name, url) in SOURCES.items():
        body = download(url)
        raw[scenario] = body
        source_meta[scenario] = {
            "name": name,
            "url": url,
            "sha256": hashlib.sha256(body).hexdigest(),
        }

    gsm = json_lines(raw["math_reasoning"])
    for index, row in enumerate(gsm):
        row["_source_id"] = "gsm8k-train-%05d" % index
    eligible_math = [
        row
        for row in gsm
        if row["_source_id"] not in excluded["math"]
        and final_gsm_answer(str(row.get("answer", "")))
    ]
    math = [
        {
            "task_id": "gather-math-%02d" % (index + 1),
            "scenario": "math_reasoning",
            "source": "gsm8k-train",
            "source_id": row["_source_id"],
            "turns": [str(row["question"])],
            "expected_answer": final_gsm_answer(str(row["answer"])),
            "metadata": {},
        }
        for index, row in enumerate(
            stable_sample(eligible_math, "_source_id", count)
        )
    ]

    mt_bench = json_lines(raw["complex_conversational_qa"])
    eligible_chat = [
        row
        for row in mt_bench
        if str(row.get("category", "")).casefold()
        not in {"math", "coding", "reasoning"}
        and "mt-bench-%s" % row["question_id"] not in excluded["chat"]
        and isinstance(row.get("turns"), list)
        and len(row["turns"]) >= 2
    ]
    chat = [
        {
            "task_id": "gather-chat-%02d" % (index + 1),
            "scenario": "complex_conversational_qa",
            "source": "mt-bench",
            "source_id": "mt-bench-%s" % row["question_id"],
            "turns": [str(turn) for turn in row["turns"]],
            "expected_answer": None,
            "metadata": {"category": row.get("category")},
        }
        for index, row in enumerate(
            stable_sample(eligible_chat, "question_id", count)
        )
    ]

    fixture_bytes = CODING_FIXTURES.read_bytes()
    fixture_payload = json.loads(fixture_bytes.decode("utf-8"))
    fixture_rows = list(fixture_payload.get("fixtures", []))
    fixture_rows.sort(key=lambda row: str(row["task_id"]))
    if len(fixture_rows) < count:
        raise ValueError("not enough checked-in agentic coding fixtures")
    coding = [
        {
            "task_id": str(row["task_id"]),
            "scenario": "agentic_coding",
            "source": "signature-cot-deterministic-code-repair",
            "source_id": str(row["task_id"]),
            "turns": [str(row["prompt"])],
            "expected_answer": "PASS",
            "metadata": {
                "fixture_id": str(row["task_id"]),
                "title": str(row["title"]),
                "environment": {
                    "kind": "in-memory-exact-repair-v1",
                    "sha256": hashlib.sha256(
                        json.dumps(
                            row,
                            ensure_ascii=False,
                            sort_keys=True,
                            separators=(",", ":"),
                        ).encode("utf-8")
                    ).hexdigest(),
                    "reset_per_instance": True,
                    "max_agent_steps": 8,
                    "gpus": 0,
                    "allow_internet": False,
                    "allow_host_filesystem": False,
                    "allow_shell": False,
                    "oracle_validated": True,
                },
            },
        }
        for row in fixture_rows[:count]
    ]
    source_meta["agentic_coding"] = {
        "name": "signature-cot-deterministic-code-repair",
        "path": str(CODING_FIXTURES.relative_to(ROOT)),
        "sha256": hashlib.sha256(fixture_bytes).hexdigest(),
    }

    tasks = chat + math + coding
    return {
        "schema_version": 1,
        "experiment": "H1b-gathering-v1",
        "selection": {
            "seed": SEED,
            "method": "lowest SHA-256(seed + NUL + source_id)",
            "provider_random_seed": None,
            "provider_random_seed_note": "Bedrock Converse exposes no seed parameter; replicate IDs identify independent harvests.",
            "tasks_per_scenario": count,
            "replicates_per_task": 3,
            "run_id": "H1b-gathering-v1",
            "excluded_manifest": str(FIXED_MANIFEST.relative_to(ROOT)),
            "chat_excluded_categories": ["coding", "math", "reasoning"],
            "terminal_bench_included": False,
            "environment_management_references": [
                "https://github.com/harbor-framework/terminal-bench-2",
                "https://github.com/swe-bench/SWE-bench"
            ],
        },
        "sources": source_meta,
        "tasks": tasks,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=15)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    payload = build(args.count)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("wrote %d tasks to %s" % (len(payload["tasks"]), args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

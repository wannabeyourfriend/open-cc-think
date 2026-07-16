"""Command-line entry point for probes, reproduction, and agentic experiments."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

from .config import DEFAULT_ENV_FILE, ProviderConfig
from .pipeline import ResearchPipeline
from .prompts import DEFAULT_CANDIDATES
from .tasks import AGENTIC_TASK, REFERENCE_TASKS


DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "artifacts"


def _common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE)
    parser.add_argument("--model", default=None)
    parser.add_argument("--region", default=None)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--effort", choices=("low", "medium", "high"), default="medium")
    parser.add_argument("--harvest-max-tokens", type=int, default=16000)
    parser.add_argument("--extraction-max-tokens", type=int, default=12000)
    parser.add_argument("--continuations", type=int, default=2)
    parser.add_argument(
        "--save-signatures",
        action="store_true",
        help="write replayable signatures under output/private (off by default)",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="signature-cot")
    sub = parser.add_subparsers(dest="command", required=True)

    listing = sub.add_parser("list", help="list checked-in research tasks")
    listing.set_defaults(handler=_list_tasks)

    probe = sub.add_parser("probe", help="cheap Bedrock signature harvest/replay check")
    _common(probe)
    probe.set_defaults(handler=_probe)

    reproduce = sub.add_parser("reproduce", help="generate the two reference math examples")
    _common(reproduce)
    reproduce.add_argument(
        "--tasks",
        default=",".join(REFERENCE_TASKS),
        help="comma-separated task IDs",
    )
    reproduce.add_argument("--optimize", action="store_true")
    reproduce.add_argument("--optimizer-rounds", type=int, default=3)
    reproduce.add_argument(
        "--candidate",
        choices=tuple(item.name for item in DEFAULT_CANDIDATES),
        default="mechanical_boundary_xml_v2",
        help="fixed elicitor for held-out evaluation when --optimize is absent",
    )
    reproduce.set_defaults(handler=_reproduce)

    optimize = sub.add_parser("optimize", help="paired prompt search on one fixed QA signature")
    _common(optimize)
    optimize.add_argument("--task", choices=tuple(REFERENCE_TASKS), default="walking-rates")
    optimize.add_argument("--optimizer-rounds", type=int, default=3)
    optimize.set_defaults(handler=_optimize)

    agentic = sub.add_parser("agentic", help="run and extract a multi-step local-tool trajectory")
    _common(agentic)
    agentic.add_argument("--optimizer-rounds", type=int, default=3)
    agentic.add_argument("--no-optimize", action="store_true")
    agentic.set_defaults(handler=_agentic)
    return parser


def _pipeline(args: argparse.Namespace) -> ResearchPipeline:
    config = ProviderConfig.from_env(
        args.env_file,
        model=args.model,
        region=args.region,
    )
    print("provider=" + json.dumps(config.safe_summary, sort_keys=True), file=sys.stderr)
    return ResearchPipeline(
        config,
        output_dir=args.output,
        harvest_max_tokens=args.harvest_max_tokens,
        extraction_max_tokens=args.extraction_max_tokens,
        continuation_limit=args.continuations,
        effort=args.effort,
    )


def _print_result(result: dict) -> None:
    run = result["run"]
    selected = result["selected_trials"]
    paths = {name: str(path) for name, path in result["paths"].items()}
    print(
        json.dumps(
            {
                "task_id": run.task_id,
                "model": run.model,
                "answer": run.final_answer,
                "task_success": run.task_success,
                "steps": len(run.steps),
                "valid_extractions": sum(1 for trial in selected if trial.metrics.valid),
                "artifacts": paths,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def _list_tasks(_: argparse.Namespace) -> int:
    for task in list(REFERENCE_TASKS.values()) + [AGENTIC_TASK]:
        print("%s\t%s\t%s" % (task.task_id, task.kind, task.title))
    return 0


def _probe(args: argparse.Namespace) -> int:
    pipeline = _pipeline(args)
    result = pipeline.run_reference(
        type(
            "ProbeTask",
            (),
            {
                "task_id": "probe-137x149",
                "question": "Compute 137 times 149 and check it carefully.",
                "expected_answer": "20413",
            },
        )(),
        optimize=False,
        save_signatures=args.save_signatures,
    )
    _print_result(result)
    return 0 if result["selected_trials"][0].metrics.valid else 2


def _reproduce(args: argparse.Namespace) -> int:
    requested = [item.strip() for item in args.tasks.split(",") if item.strip()]
    unknown = [item for item in requested if item not in REFERENCE_TASKS]
    if unknown:
        raise SystemExit("unknown task IDs: %s" % ", ".join(unknown))
    pipeline = _pipeline(args)
    results = pipeline.reproduce_reference_suite(
        requested,
        optimize=args.optimize,
        optimizer_rounds=args.optimizer_rounds,
        candidate=args.candidate,
        save_signatures=args.save_signatures,
    )
    for result in results:
        _print_result(result)
    return 0 if all(
        all(trial.metrics.valid for trial in result["selected_trials"])
        for result in results
    ) else 2


def _optimize(args: argparse.Namespace) -> int:
    pipeline = _pipeline(args)
    result = pipeline.run_reference(
        REFERENCE_TASKS[args.task],
        optimize=True,
        optimizer_rounds=args.optimizer_rounds,
        save_signatures=args.save_signatures,
    )
    _print_result(result)
    print(json.dumps(result["optimization"].ranking, indent=2))
    return 0


def _agentic(args: argparse.Namespace) -> int:
    pipeline = _pipeline(args)
    result = pipeline.run_agentic(
        optimize=not args.no_optimize,
        optimizer_rounds=args.optimizer_rounds,
        save_signatures=args.save_signatures,
    )
    _print_result(result)
    return 0 if all(trial.metrics.valid for trial in result["selected_trials"]) else 2


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.handler(args))

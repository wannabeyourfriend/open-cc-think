"""Command-line entry point for probes, reproduction, and agentic experiments."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

from .calibration import (
    DEFAULT_MANIFEST,
    StratifiedPromptOptimizer,
    harvest_tasks,
    load_manifest,
    result_dict,
    selected_trials,
)
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

    corpus = sub.add_parser(
        "calibrate-corpus",
        help="optimize extraction prompts on the fixed coding/math/chat corpus",
    )
    _common(corpus)
    corpus.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    corpus.add_argument(
        "--stage-sizes",
        default="2,2,4",
        help="successive-halving instance counts per scenario; remainder is validation",
    )
    corpus.add_argument(
        "--limit-per-scenario",
        type=int,
        default=None,
        help="bounded smoke runs only; default uses all fixed instances",
    )
    corpus.add_argument(
        "--thinking-display",
        choices=("summarized", "omitted"),
        default="summarized",
    )
    corpus.add_argument(
        "--candidates",
        default=",".join(item.name for item in DEFAULT_CANDIDATES),
        help="comma-separated extraction candidates; default uses the frozen full pool",
    )
    corpus.set_defaults(handler=_calibrate_corpus, effort="high")
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
                "strong_extractions": sum(
                    1 for trial in selected if trial.metrics.strong_recovery
                ),
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
                "required_answer_facts": ("20413",),
            },
        )(),
        optimize=False,
        save_signatures=args.save_signatures,
    )
    _print_result(result)
    return 0 if result["selected_trials"][0].metrics.strong_recovery else 2


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
        all(trial.metrics.strong_recovery for trial in result["selected_trials"])
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
    return 0 if all(
        trial.metrics.strong_recovery for trial in result["selected_trials"]
    ) else 2


def _calibrate_corpus(args: argparse.Namespace) -> int:
    manifest_payload, tasks = load_manifest(args.manifest)
    if args.limit_per_scenario is not None:
        if args.limit_per_scenario < 1:
            raise SystemExit("--limit-per-scenario must be positive")
        limited = []
        for scenario in ("coding", "math", "chat"):
            limited.extend(
                [task for task in tasks if task.scenario == scenario][
                    : args.limit_per_scenario
                ]
            )
        tasks = limited
    try:
        stage_sizes = tuple(
            int(value.strip())
            for value in args.stage_sizes.split(",")
            if value.strip()
        )
    except ValueError as exc:
        raise SystemExit("--stage-sizes must be comma-separated integers") from exc
    if not stage_sizes or any(value < 1 for value in stage_sizes):
        raise SystemExit("--stage-sizes must contain positive integers")
    candidate_names = [
        value.strip() for value in args.candidates.split(",") if value.strip()
    ]
    known_candidates = {item.name: item for item in DEFAULT_CANDIDATES}
    unknown_candidates = [name for name in candidate_names if name not in known_candidates]
    if unknown_candidates:
        raise SystemExit("unknown candidates: %s" % ", ".join(unknown_candidates))
    candidates = [known_candidates[name] for name in candidate_names]
    if len(candidates) < 2:
        raise SystemExit("calibration requires at least two extraction candidates")
    per_scenario = min(
        sum(1 for task in tasks if task.scenario == scenario)
        for scenario in ("coding", "math", "chat")
    )
    if sum(stage_sizes) >= per_scenario:
        raise SystemExit(
            "stage sizes must leave at least one held-out validation instance per scenario"
        )

    pipeline = _pipeline(args)
    runs = harvest_tasks(
        pipeline.client,
        tasks,
        max_tokens=args.harvest_max_tokens,
        effort=args.effort,
        thinking_display=args.thinking_display,
        checkpoint_dir=args.output / ".checkpoints",
    )
    result = StratifiedPromptOptimizer(pipeline.extractor).optimize(
        runs,
        candidates,
        stage_sizes=stage_sizes,
    )
    paths = []
    for run in runs:
        paths.append(
            pipeline.writer.write(
                run,
                selected_trials(result, run),
                save_signatures=args.save_signatures,
            )
        )
    args.output.mkdir(parents=True, exist_ok=True)
    result_path = args.output / "calibration-results.json"
    manifest_meta = {
        "path": str(args.manifest),
        "selection": manifest_payload.get("selection"),
        "sources": manifest_payload.get("sources"),
        "task_count": len(tasks),
    }
    result_path.write_text(
        json.dumps(result_dict(result, manifest_meta), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "model": pipeline.config.model,
                "tasks": len(runs),
                "winner": result.winner,
                "validation": result.validation,
                "result": str(result_path),
                "atif_trajectories": [str(item["atif"]) for item in paths],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if result.validation.get("macro_strong_recovery_rate") == 1.0 else 2


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.handler(args))

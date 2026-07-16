#!/usr/bin/env python3
"""Resume-safe H1b gathering across chat, math, and agentic coding."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import statistics
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from signature_cot.artifacts import ArtifactWriter  # noqa: E402
from signature_cot.bedrock import BedrockClient, ProviderError  # noqa: E402
from signature_cot.config import DEFAULT_ENV_FILE, ProviderConfig  # noqa: E402
from signature_cot.extraction import SignatureExtractor  # noqa: E402
from signature_cot.gathering import (  # noqa: E402
    SCENARIOS,
    CodingWorkspace,
    GatheringTask,
    atomic_write_json,
    checkpoint_run,
    checkpoint_trials,
    coding_fixture_sha256,
    file_sha256,
    load_checkpoint_run,
    load_checkpoint_trials,
    load_coding_fixtures,
    load_gathering_manifest,
)
from signature_cot.harvest import AgentRunner, ScenarioHarvester  # noqa: E402
from signature_cot.models import ExtractionTrial, HarvestRun, Json  # noqa: E402
from signature_cot.prompts import candidate_by_name  # noqa: E402


DEFAULT_OUTPUT = (
    ROOT
    / "experiments"
    / "h1b-scenario-gathering"
    / "results"
    / "gathering-v1"
)
DEFAULT_MANIFEST = DEFAULT_OUTPUT / "manifest.json"
CODING_SYSTEM = (
    "You are a careful code-repair agent operating only on an isolated in-memory workspace. "
    "Inspect the relevant source and tests before calling apply_patch exactly once. apply_patch is "
    "the terminal submission action and automatically runs the deterministic verifier. Do not "
    "finish with plain assistant text. Treat tool results as authoritative. Never expose "
    "research boundary markers in visible text or tool inputs. You have no shell, network, or "
    "host-filesystem access."
)


class PublicSignatureLeak(RuntimeError):
    pass


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def log_event(path: Path, message: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write("%s %s\n" % (utc_now(), message.replace("\n", " ")))
    print(message, file=sys.stderr, flush=True)


def selected_tasks(
    tasks: Sequence[GatheringTask],
    *,
    scenarios: Sequence[str],
    limit_per_scenario: Optional[int],
) -> List[GatheringTask]:
    chosen: List[GatheringTask] = []
    for scenario in SCENARIOS:
        if scenario not in scenarios:
            continue
        rows = sorted(
            (task for task in tasks if task.scenario == scenario),
            key=lambda task: task.task_id,
        )
        if limit_per_scenario is not None:
            rows = rows[:limit_per_scenario]
        chosen.extend(rows)
    return chosen


def initial_progress(
    *,
    manifest_path: Path,
    manifest_sha256: str,
    model: str,
    tasks: Sequence[GatheringTask],
    replicates: int,
    run_id: str,
) -> Json:
    return {
        "schema_version": 1,
        "experiment": "H1b-gathering-v1",
        "run_id": run_id,
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "manifest": str(manifest_path),
        "manifest_sha256": manifest_sha256,
        "model": model,
        "required": {
            "tasks": len(tasks),
            "replicates_per_task": replicates,
            "task_instances": len(tasks) * replicates,
        },
        "instances": {},
    }


def load_or_initialize_progress(
    path: Path,
    *,
    manifest_path: Path,
    manifest_sha256: str,
    model: str,
    tasks: Sequence[GatheringTask],
    replicates: int,
    run_id: str,
) -> Json:
    if not path.exists():
        payload = initial_progress(
            manifest_path=manifest_path,
            manifest_sha256=manifest_sha256,
            model=model,
            tasks=tasks,
            replicates=replicates,
            run_id=run_id,
        )
        atomic_write_json(path, payload)
        return payload
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("manifest_sha256") != manifest_sha256:
        raise ValueError("progress manifest mismatch")
    if payload.get("model") != model:
        raise ValueError(
            "progress model mismatch: %s != %s" % (payload.get("model"), model)
        )
    if payload.get("run_id") != run_id:
        raise ValueError("progress run-ID mismatch")
    required = payload.get("required", {})
    if int(required.get("replicates_per_task", 0)) != replicates:
        raise ValueError("progress replicate-count mismatch")
    return payload


def public_paths(writer: ArtifactWriter, instance_id: str) -> List[Path]:
    return [
        writer.output_dir / (instance_id + ".md"),
        writer.output_dir / (instance_id + ".json"),
        writer.output_dir / (instance_id + ".atif.json"),
    ]


def ensure_no_public_signature(run: HarvestRun, paths: Iterable[Path]) -> None:
    signatures = [step.signature for step in run.steps if step.signature]
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for signature in signatures:
            if signature in text:
                raise PublicSignatureLeak("raw signature found in public artifact: %s" % path)
    json_path = next(path for path in paths if path.name.endswith(".json") and not path.name.endswith(".atif.json"))
    payload = json.loads(json_path.read_text(encoding="utf-8"))

    def inspect(value: object) -> None:
        if isinstance(value, list):
            for item in value:
                inspect(item)
        elif isinstance(value, dict):
            for key, item in value.items():
                if key == "signature" and item != "<redacted>":
                    raise PublicSignatureLeak(
                        "non-redacted signature field in public artifact: %s" % json_path
                    )
                inspect(item)

    inspect(payload)


def task_success_for_math(expected: Optional[str], answer: str) -> bool:
    if not expected:
        return False
    compact_expected = expected.replace(",", "").strip()
    compact_answer = answer.replace(",", "").strip()
    return compact_expected in compact_answer


def harvest_instance(
    client: BedrockClient,
    task: GatheringTask,
    instance_id: str,
    replicate: int,
    *,
    run_id: str,
    max_tokens: int,
    effort: str,
    max_agent_steps: int,
) -> HarvestRun:
    source_metadata: Json = {
        "run_id": run_id,
        "instance_id": instance_id,
        "dataset": task.source,
        "source_id": task.source_id,
        "dataset_metadata": task.metadata,
        "gathering_task_id": task.task_id,
        "replicate": replicate,
        "reasoning_effort": effort,
        "thinking_display": "summarized",
    }
    if task.scenario == "agentic_coding":
        fixture_id = str(task.metadata.get("fixture_id", task.source_id))
        fixture = load_coding_fixtures()[fixture_id]
        declared_environment = task.metadata.get("environment", {})
        if (
            isinstance(declared_environment, dict)
            and declared_environment.get("sha256")
            and declared_environment["sha256"] != coding_fixture_sha256(fixture)
        ):
            raise ValueError("coding environment fingerprint mismatch for %s" % fixture_id)
        workspace = CodingWorkspace(fixture)
        run = AgentRunner(
            client,
            workspace.registry(),
            max_tokens=max_tokens,
            max_steps=max_agent_steps,
            effort=effort,
            thinking_display="summarized",
            system_text=CODING_SYSTEM,
            terminal_tool_names=("apply_patch",),
            require_signatures=False,
        ).run(
            instance_id,
            task.turns[0],
            task.expected_answer,
            scenario=task.scenario,
            source_metadata=source_metadata,
        )
        run.task_success = workspace.task_success
        return run

    turns = list(task.turns)
    if task.scenario == "math_reasoning":
        turns[0] += "\n\nReturn only the final numeric answer in the visible response."
    run = ScenarioHarvester(
        client,
        max_tokens=max_tokens,
        effort=effort,
        thinking_display="summarized",
        require_signatures=False,
    ).run(
        instance_id,
        turns,
        scenario=task.scenario,
        expected_answer=task.expected_answer,
        source_metadata=source_metadata,
    )
    if task.scenario == "math_reasoning":
        run.task_success = task_success_for_math(task.expected_answer, run.final_answer)
    return run


def extract_instance(
    extractor: SignatureExtractor,
    run: HarvestRun,
    checkpoint_path: Path,
    candidate_name: str,
) -> List[ExtractionTrial]:
    candidate = candidate_by_name(candidate_name)
    trials = (
        load_checkpoint_trials(checkpoint_path)
        if checkpoint_path.exists()
        else []
    )
    by_step = {
        trial.step_index: trial
        for trial in trials
        if trial.candidate == candidate_name
    }
    signed_steps = [step for step in run.steps if step.signature]
    for step in signed_steps:
        if step.step_index in by_step:
            continue
        trial = extractor.recover(step, candidate)
        trials.append(trial)
        by_step[step.step_index] = trial
        checkpoint_trials(checkpoint_path, trials)
    selected = [by_step[step.step_index] for step in signed_steps]
    if len(selected) != len(signed_steps):
        raise RuntimeError("not every signed decision has an extraction")
    return selected


def completed_record(
    task: GatheringTask,
    replicate: int,
    run: HarvestRun,
    trials: Sequence[ExtractionTrial],
    artifact_paths: Dict[str, Path],
    output_root: Path,
    attempts: int,
) -> Json:
    return {
        "status": "complete",
        "updated_at": utc_now(),
        "task_id": task.task_id,
        "source_id": task.source_id,
        "scenario": task.scenario,
        "replicate": replicate,
        "attempts": attempts,
        "task_success": run.task_success,
        "original_decisions": len(run.steps),
        "signed_decisions": sum(bool(step.signature) for step in run.steps),
        "unsigned_decisions": sum(not step.signature for step in run.steps),
        "valid_decisions": sum(trial.metrics.valid for trial in trials),
        "strong_decisions": sum(trial.metrics.strong_recovery for trial in trials),
        "near_duplicate_decisions": sum(
            trial.metrics.summary_near_duplicate for trial in trials
        ),
        "refused_decisions": sum(trial.metrics.refused for trial in trials),
        "leaked_decisions": sum(trial.metrics.marker_leakage for trial in trials),
        "harvest_output_tokens": sum(step.output_tokens for step in run.steps),
        "extraction_output_tokens": sum(
            trial.metrics.recovered_output_tokens for trial in trials
        ),
        "full_length_ratios": [
            trial.metrics.full_length_ratio for trial in trials
        ],
        "full_length_alignments": [
            trial.metrics.full_length_alignment for trial in trials
        ],
        "summary_expansion_ratios": [
            trial.metrics.summary_expansion_ratio
            for trial in trials
            if trial.metrics.summary_expansion_ratio is not None
        ],
        "summary_ngram_containments": [
            trial.metrics.summary_ngram_containment for trial in trials
        ],
        "tool_actions": [
            {
                "step": event.get("step"),
                "name": event.get("name"),
                "status": event.get("status"),
            }
            for event in run.tool_events
        ],
        "artifacts": {
            name: str(path.relative_to(output_root))
            for name, path in artifact_paths.items()
        },
    }


def summarize(progress: Json, tasks: Sequence[GatheringTask], replicates: int) -> Json:
    records = list(progress.get("instances", {}).values())
    complete = [row for row in records if row.get("status") == "complete"]
    failed = [row for row in records if row.get("status") == "failed"]
    by_task: Dict[str, int] = {}
    for row in complete:
        task_id = str(row["task_id"])
        by_task[task_id] = by_task.get(task_id, 0) + 1

    scenario_rows: Dict[str, Json] = {}
    for scenario in SCENARIOS:
        scenario_tasks = [task for task in tasks if task.scenario == scenario]
        rows = [row for row in complete if row.get("scenario") == scenario]
        decisions = sum(int(row.get("signed_decisions", 0)) for row in rows)
        ratios = [
            float(value)
            for row in rows
            for value in row.get("full_length_ratios", [])
        ]
        alignments = [
            float(value)
            for row in rows
            for value in row.get("full_length_alignments", [])
        ]
        expansions = [
            float(value)
            for row in rows
            for value in row.get("summary_expansion_ratios", [])
        ]
        containments = [
            float(value)
            for row in rows
            for value in row.get("summary_ngram_containments", [])
        ]
        task_success_rows = [
            bool(row["task_success"])
            for row in rows
            if row.get("task_success") is not None
        ]
        scenario_rows[scenario] = {
            "tasks": len(scenario_tasks),
            "tasks_with_required_replicates": sum(
                by_task.get(task.task_id, 0) >= replicates for task in scenario_tasks
            ),
            "expected_instances": len(scenario_tasks) * replicates,
            "complete_instances": len(rows),
            "signed_decisions": decisions,
            "unsigned_decisions": sum(
                int(row.get("unsigned_decisions", 0)) for row in rows
            ),
            "valid_decisions": sum(int(row.get("valid_decisions", 0)) for row in rows),
            "strong_decisions": sum(
                int(row.get("strong_decisions", 0)) for row in rows
            ),
            "near_duplicate_decisions": sum(
                int(row.get("near_duplicate_decisions", 0)) for row in rows
            ),
            "task_success_numerator": sum(task_success_rows),
            "task_success_denominator": len(task_success_rows),
            "mean_full_length_ratio": (
                round(statistics.mean(ratios), 4) if ratios else None
            ),
            "mean_full_length_alignment": (
                round(statistics.mean(alignments), 4) if alignments else None
            ),
            "mean_summary_expansion_ratio": (
                round(statistics.mean(expansions), 4) if expansions else None
            ),
            "mean_summary_ngram_containment": (
                round(statistics.mean(containments), 4) if containments else None
            ),
            "harvest_output_tokens": sum(
                int(row.get("harvest_output_tokens", 0)) for row in rows
            ),
            "extraction_output_tokens": sum(
                int(row.get("extraction_output_tokens", 0)) for row in rows
            ),
        }

    expected_instances = len(tasks) * replicates
    return {
        "schema_version": 1,
        "experiment": progress.get("experiment"),
        "run_id": progress.get("run_id"),
        "updated_at": utc_now(),
        "model": progress.get("model"),
        "tasks": len(tasks),
        "replicates_per_task": replicates,
        "expected_instances": expected_instances,
        "complete_instances": len(complete),
        "failed_instances": len(failed),
        "tasks_with_required_replicates": sum(
            by_task.get(task.task_id, 0) >= replicates for task in tasks
        ),
        "signed_decisions": sum(
            int(row.get("signed_decisions", 0)) for row in complete
        ),
        "unsigned_decisions": sum(
            int(row.get("unsigned_decisions", 0)) for row in complete
        ),
        "valid_decisions": sum(
            int(row.get("valid_decisions", 0)) for row in complete
        ),
        "strong_decisions": sum(
            int(row.get("strong_decisions", 0)) for row in complete
        ),
        "near_duplicate_decisions": sum(
            int(row.get("near_duplicate_decisions", 0)) for row in complete
        ),
        "scenarios": scenario_rows,
        "complete": (
            len(complete) >= expected_instances
            and all(by_task.get(task.task_id, 0) >= replicates for task in tasks)
        ),
    }


def save_progress(
    progress_path: Path,
    summary_path: Path,
    progress: Json,
    tasks: Sequence[GatheringTask],
    replicates: int,
) -> Json:
    progress["updated_at"] = utc_now()
    atomic_write_json(progress_path, progress)
    summary = summarize(progress, tasks, replicates)
    atomic_write_json(summary_path, summary)
    return summary


def run(args: argparse.Namespace) -> int:
    manifest_payload, all_tasks = load_gathering_manifest(args.manifest)
    scenarios = args.scenario or list(SCENARIOS)
    unknown = [scenario for scenario in scenarios if scenario not in SCENARIOS]
    if unknown:
        raise SystemExit("unknown scenario(s): %s" % ", ".join(unknown))
    tasks = selected_tasks(
        all_tasks,
        scenarios=scenarios,
        limit_per_scenario=args.limit_per_scenario,
    )
    if not tasks:
        raise SystemExit("no gathering tasks selected")
    if args.replicates < 1:
        raise SystemExit("--replicates must be positive")
    if args.validate_only:
        print(
            json.dumps(
                {
                    "manifest": str(args.manifest),
                    "manifest_sha256": file_sha256(args.manifest),
                    "tasks": len(tasks),
                    "scenarios": {
                        scenario: sum(task.scenario == scenario for task in tasks)
                        for scenario in SCENARIOS
                    },
                    "replicates": args.replicates,
                    "expected_instances": len(tasks) * args.replicates,
                    "declared_selection": manifest_payload.get("selection"),
                },
                indent=2,
            )
        )
        return 0

    config = ProviderConfig.from_env(
        args.env_file,
        model=args.model,
        region=args.region,
    )
    output_root = args.output
    public_dir = output_root / "public"
    checkpoint_dir = output_root / ".checkpoints"
    progress_path = output_root / "progress.json"
    summary_path = output_root / "summary.json"
    log_path = output_root / "run.log"
    output_root.mkdir(parents=True, exist_ok=True)
    progress = load_or_initialize_progress(
        progress_path,
        manifest_path=args.manifest,
        manifest_sha256=file_sha256(args.manifest),
        model=config.model,
        tasks=tasks,
        replicates=args.replicates,
        run_id=args.run_id,
    )
    log_event(
        log_path,
        "start model=%s tasks=%d replicates=%d credential_configured=true"
        % (config.model, len(tasks), args.replicates),
    )
    client = BedrockClient(config)
    extractor = SignatureExtractor(
        client,
        max_tokens=args.extraction_max_tokens,
        continuation_limit=args.continuations,
        blind_provider_summary=True,
    )
    writer = ArtifactWriter(public_dir)
    processed = 0
    consecutive_provider_errors = 0

    for task in tasks:
        for replicate in range(1, args.replicates + 1):
            instance_id = "%s-r%02d" % (task.task_id, replicate)
            previous = progress["instances"].get(instance_id, {})
            if previous.get("status") == "complete":
                continue
            if args.max_instances is not None and processed >= args.max_instances:
                summary = save_progress(
                    progress_path, summary_path, progress, tasks, args.replicates
                )
                print(json.dumps(summary, ensure_ascii=False, indent=2))
                return 0 if summary["complete"] else 2
            attempts = int(previous.get("attempts", 0))
            if (
                previous.get("status") == "failed"
                and "no reasoning signature" in str(previous.get("error", ""))
            ):
                # Harness v1 initially treated adaptive-thinking omission as a provider
                # failure. It is now retained as an explicit censored observation.
                attempts = 0
            while attempts < args.max_attempts:
                attempts += 1
                processed += 1
                progress["instances"][instance_id] = {
                    "status": "running",
                    "updated_at": utc_now(),
                    "task_id": task.task_id,
                    "source_id": task.source_id,
                    "scenario": task.scenario,
                    "replicate": replicate,
                    "attempts": attempts,
                }
                save_progress(
                    progress_path, summary_path, progress, tasks, args.replicates
                )
                log_event(
                    log_path,
                    "instance start id=%s scenario=%s attempt=%d"
                    % (instance_id, task.scenario, attempts),
                )
                harvest_checkpoint = (
                    checkpoint_dir / "harvest" / (instance_id + ".json")
                )
                trial_checkpoint = (
                    checkpoint_dir / "extraction" / (instance_id + ".json")
                )
                try:
                    if harvest_checkpoint.exists():
                        run_record = load_checkpoint_run(harvest_checkpoint)
                        if run_record.model != config.model:
                            raise ValueError("checkpoint model mismatch for %s" % instance_id)
                        if (
                            run_record.source_metadata.get("source_id")
                            != task.source_id
                        ):
                            raise ValueError("checkpoint source mismatch for %s" % instance_id)
                        log_event(log_path, "resume harvest id=%s" % instance_id)
                    else:
                        run_record = harvest_instance(
                            client,
                            task,
                            instance_id,
                            replicate,
                            run_id=args.run_id,
                            max_tokens=args.harvest_max_tokens,
                            effort=args.effort,
                            max_agent_steps=args.max_agent_steps,
                        )
                        checkpoint_run(harvest_checkpoint, run_record)
                    trials = extract_instance(
                        extractor,
                        run_record,
                        trial_checkpoint,
                        args.candidate,
                    )
                    paths = writer.write(run_record, trials)
                    ensure_no_public_signature(
                        run_record,
                        public_paths(writer, instance_id),
                    )
                    progress["instances"][instance_id] = completed_record(
                        task,
                        replicate,
                        run_record,
                        trials,
                        paths,
                        output_root,
                        attempts,
                    )
                    save_progress(
                        progress_path,
                        summary_path,
                        progress,
                        tasks,
                        args.replicates,
                    )
                    log_event(
                        log_path,
                        "instance complete id=%s decisions=%d task_success=%s"
                        % (instance_id, len(run_record.steps), run_record.task_success),
                    )
                    consecutive_provider_errors = 0
                    break
                except PublicSignatureLeak:
                    progress["instances"][instance_id] = {
                        **progress["instances"][instance_id],
                        "status": "failed",
                        "updated_at": utc_now(),
                        "error_type": "PublicSignatureLeak",
                    }
                    save_progress(
                        progress_path,
                        summary_path,
                        progress,
                        tasks,
                        args.replicates,
                    )
                    raise
                except Exception as exc:
                    error_text = str(exc).replace("\n", " ")[:1000]
                    progress["instances"][instance_id] = {
                        **progress["instances"][instance_id],
                        "status": "failed",
                        "updated_at": utc_now(),
                        "error_type": type(exc).__name__,
                        "error": error_text,
                    }
                    save_progress(
                        progress_path,
                        summary_path,
                        progress,
                        tasks,
                        args.replicates,
                    )
                    log_event(
                        log_path,
                        "instance failed id=%s error=%s: %s"
                        % (instance_id, type(exc).__name__, error_text),
                    )
                    if isinstance(exc, ProviderError):
                        consecutive_provider_errors += 1
                        if "HTTP 401" in error_text or "HTTP 403" in error_text:
                            raise
                        if consecutive_provider_errors >= args.max_consecutive_provider_errors:
                            raise RuntimeError(
                                "stopping after %d consecutive provider errors"
                                % consecutive_provider_errors
                            ) from exc
                    if attempts >= args.max_attempts:
                        break

    summary = save_progress(
        progress_path,
        summary_path,
        progress,
        tasks,
        args.replicates,
    )
    log_event(
        log_path,
        "finish complete_instances=%d expected_instances=%d complete=%s"
        % (
            summary["complete_instances"],
            summary["expected_instances"],
            summary["complete"],
        ),
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["complete"] else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE)
    parser.add_argument(
        "--model",
        default="global.anthropic.claude-sonnet-5",
    )
    parser.add_argument("--region", default=None)
    parser.add_argument("--replicates", type=int, default=3)
    parser.add_argument("--run-id", default="H1b-gathering-v1")
    parser.add_argument("--scenario", action="append", choices=SCENARIOS)
    parser.add_argument("--limit-per-scenario", type=int, default=None)
    parser.add_argument("--max-instances", type=int, default=None)
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--max-consecutive-provider-errors", type=int, default=3)
    parser.add_argument("--candidate", default="mechanical_boundary_xml_v2")
    parser.add_argument("--effort", choices=("low", "medium", "high"), default="high")
    parser.add_argument("--harvest-max-tokens", type=int, default=16000)
    parser.add_argument("--extraction-max-tokens", type=int, default=12000)
    parser.add_argument("--continuations", type=int, default=2)
    parser.add_argument("--max-agent-steps", type=int, default=8)
    parser.add_argument("--validate-only", action="store_true")
    return parser


def main() -> int:
    return run(build_parser().parse_args())


if __name__ == "__main__":
    raise SystemExit(main())

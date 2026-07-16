"""Fixed-corpus harvesting and scenario-stratified extraction-prompt optimization."""

from __future__ import annotations

import dataclasses
import json
import math
import statistics
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from .bedrock import BedrockClient
from .extraction import SignatureExtractor
from .harvest import ScenarioHarvester
from .models import (
    BoundaryMarkers,
    ExtractionTrial,
    HarvestRun,
    HarvestStep,
    Json,
    PromptCandidate,
    ToolCall,
)


DEFAULT_MANIFEST = Path(__file__).resolve().parents[1] / "calibration" / "fixed-36.json"


@dataclass(frozen=True)
class CalibrationTask:
    task_id: str
    scenario: str
    source: str
    source_id: str
    turns: Tuple[str, ...]
    expected_answer: Optional[str] = None
    metadata: Json = field(default_factory=dict)


@dataclass
class CorpusTrial:
    task_id: str
    scenario: str
    extraction: ExtractionTrial
    phase: str


@dataclass
class CorpusOptimizationResult:
    winner: str
    ranking: List[Json]
    trials: List[CorpusTrial]
    stages: List[Json]
    validation: Json


def load_manifest(path: Path = DEFAULT_MANIFEST) -> Tuple[Json, List[CalibrationTask]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    tasks = [
        CalibrationTask(
            task_id=str(row["task_id"]),
            scenario=str(row["scenario"]),
            source=str(row["source"]),
            source_id=str(row["source_id"]),
            turns=tuple(str(turn) for turn in row["turns"]),
            expected_answer=(
                str(row["expected_answer"])
                if row.get("expected_answer") is not None
                else None
            ),
            metadata=row.get("metadata") if isinstance(row.get("metadata"), dict) else {},
        )
        for row in payload.get("tasks", [])
    ]
    counts: Dict[str, int] = {}
    for task in tasks:
        counts[task.scenario] = counts.get(task.scenario, 0) + 1
    if set(counts) != {"coding", "math", "chat"}:
        raise ValueError("manifest must contain coding, math, and chat scenarios")
    if len(set(counts.values())) != 1:
        raise ValueError("manifest scenarios must contain equal instance counts")
    return payload, tasks


def _checkpoint_payload(run: HarvestRun) -> Json:
    """Private restart state. This contains raw replayable signatures."""

    return {"schema_version": 1, "run": dataclasses.asdict(run)}


def _run_from_checkpoint(path: Path) -> HarvestRun:
    payload = json.loads(path.read_text(encoding="utf-8"))
    row = payload["run"]
    steps: List[HarvestStep] = []
    for step in row["steps"]:
        steps.append(
            HarvestStep(
                step_index=int(step["step_index"]),
                prefix_messages=step["prefix_messages"],
                assistant_content=step["assistant_content"],
                stop_reason=str(step["stop_reason"]),
                usage=step["usage"],
                markers=BoundaryMarkers(**step["markers"]),
                visible_text=str(step["visible_text"]),
                tool_calls=[ToolCall(**call) for call in step["tool_calls"]],
                replay_tool_results=step.get("replay_tool_results", []),
                system=step.get("system", []),
                tool_config=step.get("tool_config"),
                user_message=str(step.get("user_message", "")),
            )
        )
    return HarvestRun(
        task_id=str(row["task_id"]),
        question=str(row["question"]),
        model=str(row["model"]),
        steps=steps,
        final_answer=str(row["final_answer"]),
        expected_answer=row.get("expected_answer"),
        tool_events=row.get("tool_events", []),
        task_success=row.get("task_success"),
        scenario=row.get("scenario"),
        source_metadata=row.get("source_metadata", {}),
    )


def _write_checkpoint(path: Path, run: HarvestRun) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(_checkpoint_payload(run), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(path)


def harvest_tasks(
    client: BedrockClient,
    tasks: Sequence[CalibrationTask],
    *,
    max_tokens: int,
    effort: str,
    thinking_display: str,
    checkpoint_dir: Optional[Path] = None,
) -> List[HarvestRun]:
    scenario_harvester = ScenarioHarvester(
        client,
        max_tokens=max_tokens,
        effort=effort,
        thinking_display=thinking_display,
    )
    runs: List[HarvestRun] = []
    for index, task in enumerate(tasks, start=1):
        checkpoint_path = (
            checkpoint_dir / (task.task_id + ".json") if checkpoint_dir else None
        )
        if checkpoint_path is not None and checkpoint_path.exists():
            run = _run_from_checkpoint(checkpoint_path)
            if run.model != client.config.model:
                raise ValueError(
                    "checkpoint model mismatch for %s: %s != %s"
                    % (task.task_id, run.model, client.config.model)
                )
            if run.source_metadata.get("source_id") != task.source_id:
                raise ValueError("checkpoint source mismatch for %s" % task.task_id)
            print(
                "resume %d/%d %s (%s)"
                % (index, len(tasks), task.task_id, task.scenario),
                file=sys.stderr,
                flush=True,
            )
            runs.append(run)
            continue
        print(
            "harvest %d/%d %s (%s)" % (index, len(tasks), task.task_id, task.scenario),
            file=sys.stderr,
            flush=True,
        )
        source_metadata = {
            "dataset": task.source,
            "source_id": task.source_id,
            "dataset_metadata": task.metadata,
            "reasoning_effort": effort,
            "thinking_display": thinking_display,
        }
        turns = list(task.turns)
        if task.scenario == "math":
            turns[0] += "\n\nReturn only the final numeric answer in the visible response."
        run = scenario_harvester.run(
            task.task_id,
            turns,
            scenario=task.scenario,
            expected_answer=task.expected_answer,
            source_metadata=source_metadata,
        )
        if task.scenario == "math":
            run.task_success = bool(
                task.expected_answer and task.expected_answer in run.final_answer
            )
        if checkpoint_path is not None:
            _write_checkpoint(checkpoint_path, run)
        runs.append(run)
    return runs


class StratifiedPromptOptimizer:
    """Paired successive halving with scenario-macro metrics and held-out validation."""

    def __init__(self, extractor: SignatureExtractor):
        self.extractor = extractor

    @staticmethod
    def _aggregate(name: str, trials: Sequence[CorpusTrial]) -> Json:
        selected = [item for item in trials if item.extraction.candidate == name]
        per_task: Dict[Tuple[str, str], List[ExtractionTrial]] = {}
        for item in selected:
            per_task.setdefault((item.scenario, item.task_id), []).append(item.extraction)

        scenario_rows: Dict[str, Json] = {}
        task_qualities: List[float] = []
        for scenario in ("coding", "math", "chat"):
            task_rows = [
                extractions
                for (row_scenario, _), extractions in per_task.items()
                if row_scenario == scenario
            ]
            qualities = [
                statistics.mean(trial.metrics.quality for trial in task_trials)
                for task_trials in task_rows
            ]
            valids = [
                all(trial.metrics.valid for trial in task_trials)
                for task_trials in task_rows
            ]
            strongs = [
                all(trial.metrics.strong_recovery for trial in task_trials)
                for task_trials in task_rows
            ]
            near_duplicates = [
                any(trial.metrics.summary_near_duplicate for trial in task_trials)
                for task_trials in task_rows
            ]
            coverages = [
                statistics.mean(trial.metrics.token_coverage_proxy for trial in task_trials)
                for task_trials in task_rows
            ]
            task_qualities.extend(qualities)
            scenario_rows[scenario] = {
                "tasks": len(task_rows),
                "mean_quality": statistics.mean(qualities) if qualities else -1.0,
                "valid_rate": sum(valids) / float(len(valids)) if valids else 0.0,
                "strong_recovery_rate": (
                    sum(strongs) / float(len(strongs)) if strongs else 0.0
                ),
                "summary_near_duplicate_rate": (
                    sum(near_duplicates) / float(len(near_duplicates))
                    if near_duplicates
                    else 0.0
                ),
                "mean_coverage_proxy": statistics.mean(coverages) if coverages else 0.0,
            }

        observed = [row for row in scenario_rows.values() if row["tasks"]]
        macro_quality = statistics.mean(row["mean_quality"] for row in observed) if observed else -1.0
        macro_valid = statistics.mean(row["valid_rate"] for row in observed) if observed else 0.0
        macro_strong = (
            statistics.mean(row["strong_recovery_rate"] for row in observed)
            if observed
            else 0.0
        )
        macro_near_duplicate = (
            statistics.mean(row["summary_near_duplicate_rate"] for row in observed)
            if observed
            else 0.0
        )
        macro_coverage = (
            statistics.mean(row["mean_coverage_proxy"] for row in observed)
            if observed
            else 0.0
        )
        spread = statistics.pstdev(task_qualities) if len(task_qualities) > 1 else 0.0
        refusal_rate = (
            sum(1 for item in selected if item.extraction.metrics.refused)
            / float(len(selected))
            if selected
            else 0.0
        )
        leakage_rate = (
            sum(1 for item in selected if item.extraction.metrics.marker_leakage)
            / float(len(selected))
            if selected
            else 0.0
        )
        both_canary_rate = (
            sum(
                1
                for item in selected
                if item.extraction.metrics.start_hit
                and item.extraction.metrics.end_hit
                and item.extraction.metrics.markers_in_order
            )
            / float(len(selected))
            if selected
            else 0.0
        )
        robust_score = (
            macro_quality
            + 0.15 * macro_valid
            + 0.40 * macro_strong
            + 0.05 * both_canary_rate
            - 0.20 * spread
            - 0.10 * refusal_rate
            - 0.20 * leakage_rate
            - 0.30 * macro_near_duplicate
        )
        return {
            "candidate": name,
            "robust_score": round(robust_score, 4),
            "macro_quality": round(macro_quality, 4),
            "macro_valid_rate": round(macro_valid, 4),
            "macro_strong_recovery_rate": round(macro_strong, 4),
            "macro_summary_near_duplicate_rate": round(macro_near_duplicate, 4),
            "both_canary_rate": round(both_canary_rate, 4),
            "macro_coverage_proxy": round(macro_coverage, 4),
            "quality_std": round(spread, 4),
            "refusal_rate": round(refusal_rate, 4),
            "leakage_rate": round(leakage_rate, 4),
            "tasks": len(per_task),
            "decision_trials": len(selected),
            "scenarios": {
                key: {
                    subkey: round(value, 4) if isinstance(value, float) else value
                    for subkey, value in row.items()
                }
                for key, row in scenario_rows.items()
            },
        }

    def _evaluate(
        self,
        active: Sequence[PromptCandidate],
        runs: Sequence[HarvestRun],
        trials: List[CorpusTrial],
        phase: str,
    ) -> None:
        total = sum(len(run.steps) for run in runs) * len(active)
        done = 0
        for run in runs:
            for candidate in active:
                for step in run.steps:
                    done += 1
                    print(
                        "extract %s %d/%d %s step=%d candidate=%s"
                        % (phase, done, total, run.task_id, step.step_index, candidate.name),
                        file=sys.stderr,
                        flush=True,
                    )
                    trials.append(
                        CorpusTrial(
                            task_id=run.task_id,
                            scenario=run.scenario or "unknown",
                            extraction=self.extractor.recover(step, candidate),
                            phase=phase,
                        )
                    )

    def optimize(
        self,
        runs: Sequence[HarvestRun],
        candidates: Sequence[PromptCandidate],
        stage_sizes: Sequence[int] = (2, 2, 4),
    ) -> CorpusOptimizationResult:
        by_scenario: Dict[str, List[HarvestRun]] = {"coding": [], "math": [], "chat": []}
        for run in runs:
            if run.scenario not in by_scenario:
                raise ValueError("unknown calibration scenario: %s" % run.scenario)
            by_scenario[run.scenario or ""].append(run)
        for scenario in by_scenario:
            by_scenario[scenario].sort(key=lambda run: run.task_id)

        active = list(candidates)
        trials: List[CorpusTrial] = []
        stages: List[Json] = []
        offset = 0
        for stage_index, size in enumerate(stage_sizes, start=1):
            batch: List[HarvestRun] = []
            for scenario in ("coding", "math", "chat"):
                batch.extend(by_scenario[scenario][offset : offset + size])
            if not batch:
                break
            phase = "stage-%d" % stage_index
            self._evaluate(active, batch, trials, phase)
            ranked = sorted(
                (self._aggregate(candidate.name, trials) for candidate in active),
                key=lambda row: (
                    row["macro_strong_recovery_rate"],
                    row["robust_score"],
                    row["macro_valid_rate"],
                    row["macro_quality"],
                ),
                reverse=True,
            )
            keep = max(1, int(math.ceil(len(active) / 2.0)))
            survivor_names = {row["candidate"] for row in ranked[:keep]}
            stages.append(
                {
                    "phase": phase,
                    "instances_per_scenario": size,
                    "active": [candidate.name for candidate in active],
                    "ranking": ranked,
                    "survivors": [
                        candidate.name for candidate in active if candidate.name in survivor_names
                    ],
                }
            )
            active = [candidate for candidate in active if candidate.name in survivor_names]
            offset += size
            if len(active) == 1:
                break

        winner = active[0]
        validation_runs: List[HarvestRun] = []
        for scenario in ("coding", "math", "chat"):
            validation_runs.extend(by_scenario[scenario][offset:])
        if validation_runs:
            self._evaluate([winner], validation_runs, trials, "validation")
        full_ranking = sorted(
            (self._aggregate(candidate.name, trials) for candidate in candidates),
            key=lambda row: (
                row["macro_strong_recovery_rate"],
                row["robust_score"],
                row["macro_valid_rate"],
                row["macro_quality"],
            ),
            reverse=True,
        )
        validation_trials = [
            item
            for item in trials
            if item.phase == "validation" and item.extraction.candidate == winner.name
        ]
        return CorpusOptimizationResult(
            winner=winner.name,
            ranking=full_ranking,
            trials=trials,
            stages=stages,
            validation=self._aggregate(winner.name, validation_trials),
        )


def selected_trials(
    result: CorpusOptimizationResult, run: HarvestRun
) -> List[ExtractionTrial]:
    matches = [
        item.extraction
        for item in result.trials
        if item.task_id == run.task_id and item.extraction.candidate == result.winner
    ]
    selected: List[ExtractionTrial] = []
    for step in run.steps:
        step_matches = [trial for trial in matches if trial.step_index == step.step_index]
        if not step_matches:
            raise ValueError(
                "winner %s was not evaluated on %s step %d"
                % (result.winner, run.task_id, step.step_index)
            )
        selected.append(
            max(
                step_matches,
                key=lambda trial: (
                    trial.metrics.strong_recovery,
                    trial.metrics.quality,
                ),
            )
        )
    return selected


def result_dict(result: CorpusOptimizationResult, manifest_metadata: Json) -> Json:
    return {
        "schema_version": 1,
        "manifest": manifest_metadata,
        "winner": result.winner,
        "ranking": result.ranking,
        "stages": result.stages,
        "validation": result.validation,
        "trial_metrics": [
            {
                "task_id": item.task_id,
                "scenario": item.scenario,
                "phase": item.phase,
                "candidate": item.extraction.candidate,
                "step_index": item.extraction.step_index,
                "metrics": dataclasses.asdict(item.extraction.metrics),
                "usage": item.extraction.usage,
                "rounds": item.extraction.rounds,
                "provider_summary_blinded": item.extraction.provider_summary_blinded,
            }
            for item in result.trials
        ],
    }

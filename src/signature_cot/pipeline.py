"""High-level research workflows used by the CLI and tests."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Sequence

from .artifacts import ArtifactWriter
from .bedrock import BedrockClient
from .config import ProviderConfig
from .extraction import PromptOptimizer, SignatureExtractor
from .harvest import AgentRunner, QuestionHarvester
from .models import ExtractionTrial, HarvestRun, OptimizationResult, PromptCandidate
from .prompts import DEFAULT_CANDIDATES, candidate_by_name
from .tasks import AGENTIC_TASK, REFERENCE_TASKS, TaskSpec, evaluate_answer
from .tools import procurement_registry


class ResearchPipeline:
    def __init__(
        self,
        config: ProviderConfig,
        *,
        output_dir: Path,
        harvest_max_tokens: int = 16000,
        extraction_max_tokens: int = 12000,
        continuation_limit: int = 2,
        effort: str = "medium",
    ):
        self.config = config
        self.client = BedrockClient(config)
        self.writer = ArtifactWriter(output_dir)
        self.harvest_max_tokens = harvest_max_tokens
        self.effort = effort
        self.extractor = SignatureExtractor(
            self.client,
            max_tokens=extraction_max_tokens,
            continuation_limit=continuation_limit,
        )
        self.optimizer = PromptOptimizer(self.extractor)

    def _select_trials(
        self,
        run: HarvestRun,
        candidate: PromptCandidate,
        optimization: Optional[OptimizationResult],
    ) -> List[ExtractionTrial]:
        selected: List[ExtractionTrial] = []
        existing = optimization.trials if optimization else []
        for step in run.steps:
            matches = [
                trial
                for trial in existing
                if trial.candidate == candidate.name and trial.step_index == step.step_index
            ]
            if matches:
                selected.append(
                    max(
                        matches,
                        key=lambda trial: (
                            trial.metrics.strong_recovery,
                            trial.metrics.quality,
                        ),
                    )
                )
            else:
                selected.append(self.extractor.recover(step, candidate))
        return selected

    def _finish(
        self,
        run: HarvestRun,
        *,
        optimize: bool,
        optimizer_rounds: int,
        candidates: Sequence[PromptCandidate],
        fixed_candidate: str,
        save_signatures: bool,
    ) -> Dict[str, object]:
        optimization = None
        if optimize:
            optimization = self.optimizer.optimize(run.steps, candidates, rounds=optimizer_rounds)
            candidate = next(item for item in candidates if item.name == optimization.winner)
        else:
            candidate = candidate_by_name(fixed_candidate)
        selected = self._select_trials(run, candidate, optimization)
        paths = self.writer.write(
            run,
            selected,
            optimization=optimization,
            save_signatures=save_signatures,
        )
        return {
            "run": run,
            "selected_trials": selected,
            "optimization": optimization,
            "paths": paths,
        }

    def run_reference(
        self,
        task: TaskSpec,
        *,
        optimize: bool = False,
        optimizer_rounds: int = 3,
        candidates: Sequence[PromptCandidate] = DEFAULT_CANDIDATES,
        candidate: str = "mechanical_boundary_xml_v2",
        save_signatures: bool = False,
    ) -> Dict[str, object]:
        run = QuestionHarvester(
            self.client,
            max_tokens=self.harvest_max_tokens,
            effort=self.effort,
        ).run(task.task_id, task.question, task.expected_answer)
        run.task_success = evaluate_answer(task, run.final_answer)
        return self._finish(
            run,
            optimize=optimize,
            optimizer_rounds=optimizer_rounds,
            candidates=candidates,
            fixed_candidate=candidate,
            save_signatures=save_signatures,
        )

    def run_agentic(
        self,
        task: TaskSpec = AGENTIC_TASK,
        *,
        optimize: bool = True,
        optimizer_rounds: int = 3,
        candidates: Sequence[PromptCandidate] = DEFAULT_CANDIDATES,
        candidate: str = "mechanical_boundary_xml_v2",
        save_signatures: bool = False,
    ) -> Dict[str, object]:
        run = AgentRunner(
            self.client,
            procurement_registry(),
            max_tokens=self.harvest_max_tokens,
            effort=self.effort,
        ).run(task.task_id, task.question, task.expected_answer)
        run.task_success = evaluate_answer(task, run.final_answer)
        return self._finish(
            run,
            optimize=optimize,
            optimizer_rounds=optimizer_rounds,
            candidates=candidates,
            fixed_candidate=candidate,
            save_signatures=save_signatures,
        )

    def reproduce_reference_suite(
        self,
        task_ids: Sequence[str],
        *,
        optimize: bool = False,
        optimizer_rounds: int = 3,
        candidate: str = "mechanical_boundary_xml_v2",
        save_signatures: bool = False,
    ) -> List[Dict[str, object]]:
        return [
            self.run_reference(
                REFERENCE_TASKS[task_id],
                optimize=optimize,
                optimizer_rounds=optimizer_rounds,
                candidate=candidate,
                save_signatures=save_signatures,
            )
            for task_id in task_ids
        ]

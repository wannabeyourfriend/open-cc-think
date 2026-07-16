"""Safe-by-default experiment artifacts and Markdown example rendering."""

from __future__ import annotations

import copy
import dataclasses
import datetime as dt
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .atif import build_atif_trajectory
from .models import ExtractionTrial, HarvestRun, OptimizationResult


def _sanitize_signatures(value: Any) -> Any:
    if isinstance(value, list):
        return [_sanitize_signatures(item) for item in value]
    if isinstance(value, dict):
        clean: Dict[str, Any] = {}
        for key, item in value.items():
            if key == "signature":
                clean[key] = "<redacted>"
            else:
                clean[key] = _sanitize_signatures(item)
        return clean
    return value


def _metrics_dict(trial: ExtractionTrial) -> Dict[str, Any]:
    return dataclasses.asdict(trial.metrics)


def public_run_dict(run: HarvestRun, trials: Iterable[ExtractionTrial]) -> Dict[str, Any]:
    return {
        "schema_version": 3,
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "task_id": run.task_id,
        "question": run.question,
        "model": run.model,
        "final_answer": run.final_answer,
        "expected_answer": run.expected_answer,
        "task_success": run.task_success,
        "scenario": run.scenario,
        "source_metadata": run.source_metadata,
        "tool_events": run.tool_events,
        "steps": [
            {
                "step_index": step.step_index,
                "stop_reason": step.stop_reason,
                "usage": step.usage,
                "markers": dataclasses.asdict(step.markers),
                "visible_text": step.visible_text,
                "user_message": step.user_message,
                "provider_cot_summary": step.provider_reasoning_summary,
                "tool_calls": [dataclasses.asdict(call) for call in step.tool_calls],
                "signature_sha256": step.signature_sha256,
                "signature_chars": len(step.signature),
                "assistant_content": _sanitize_signatures(copy.deepcopy(step.assistant_content)),
            }
            for step in run.steps
        ],
        "extractions": [
            {
                "candidate": trial.candidate,
                "step_index": trial.step_index,
                "metrics": _metrics_dict(trial),
                "usage": trial.usage,
                "stop_reason": trial.stop_reason,
                "rounds": trial.rounds,
                "provider_summary_blinded": trial.provider_summary_blinded,
                "recovered": trial.recovered,
            }
            for trial in trials
        ],
    }


def render_markdown(
    run: HarvestRun,
    selected_trials: List[ExtractionTrial],
    optimization: Optional[OptimizationResult] = None,
) -> str:
    agentic = bool(run.tool_events)
    lines = [
        "# Example: %s" % run.task_id,
        "",
        "Model: `%s` · signature replay · boundary-canary validation" % run.model,
        "",
        "Q:",
        "```markdown",
        run.question,
        "```",
        "",
        "## Visible answer",
        "",
        "```markdown",
        run.final_answer,
        "```",
        "",
    ]
    if run.expected_answer:
        lines.extend(
            [
                "Expected: `%s`" % run.expected_answer,
                "",
                "Task success: `%s`" % run.task_success,
                "",
            ]
        )
    if agentic:
        lines.extend(["## Tool trajectory", ""])
        for event in run.tool_events:
            lines.append(
                "- Step {step}: `{name}` input `{args}` → `{result}` ({status})".format(
                    step=event["step"],
                    name=event["name"],
                    args=json.dumps(event["arguments"], ensure_ascii=False, sort_keys=True),
                    result=json.dumps(event["result"], ensure_ascii=False, sort_keys=True),
                    status=event["status"],
                )
            )
        lines.append("")
    if optimization:
        lines.extend(
            [
                "## Prompt optimization",
                "",
                "Winner: `%s`; paired step schedule: `%s`." % (
                    optimization.winner,
                    optimization.paired_schedule,
                ),
                "",
                "```json",
                json.dumps(optimization.ranking, ensure_ascii=False, indent=2),
                "```",
                "",
            ]
        )
    lines.extend(["## Recovered signed reasoning", ""])
    for trial in sorted(selected_trials, key=lambda item: item.step_index):
        m = trial.metrics
        provider_summary = run.steps[trial.step_index].provider_reasoning_summary
        lines.extend(
            [
                "### Decision step %d" % trial.step_index,
                "",
                "Provider CoT summary:",
                "",
                "```markdown",
                provider_summary or "<omitted or unavailable>",
                "```",
                "",
                "Signed full-span recovery:",
                "",
                "Candidate `%s` · quality %.4f · protocol-valid `%s` · strong `%s` · "
                "summary blinded `%s` · summary near-duplicate `%s` · boundary `%s/%s` · "
                "full-token ratio %.4f · summary-token expansion `%s` · "
                "summary n-gram containment %.4f · recovered chars %d"
                % (
                    trial.candidate,
                    m.quality,
                    m.valid,
                    m.strong_recovery,
                    trial.provider_summary_blinded,
                    m.summary_near_duplicate,
                    m.start_hit,
                    m.end_hit,
                    m.full_length_ratio,
                    (
                        "%.4f" % m.summary_expansion_ratio
                        if m.summary_expansion_ratio is not None
                        else "unavailable"
                    ),
                    m.summary_ngram_containment,
                    m.recovered_chars,
                ),
                "",
                "```markdown",
                trial.recovered,
                "```",
                "",
            ]
        )
    lines.extend(
        [
            "## Interpretation boundary",
            "",
            "The signed replay plus hidden boundary markers demonstrates access to state carried by the "
            "reasoning block. It does not prove byte-for-byte fidelity: the replaying model can still "
            "omit, paraphrase, or reconstruct content. `full-token ratio` compares extraction output "
            "tokens with Bedrock billed harvest output tokens; it is a length proxy, not plaintext "
            "ground truth.",
            "",
        ]
    )
    return "\n".join(lines)


class ArtifactWriter:
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def write(
        self,
        run: HarvestRun,
        selected_trials: List[ExtractionTrial],
        optimization: Optional[OptimizationResult] = None,
        save_signatures: bool = False,
    ) -> Dict[str, Path]:
        markdown_path = self.output_dir / (run.task_id + ".md")
        json_path = self.output_dir / (run.task_id + ".json")
        atif_path = self.output_dir / (run.task_id + ".atif.json")
        markdown_path.write_text(
            render_markdown(run, selected_trials, optimization), encoding="utf-8"
        )
        artifact_trials = list(optimization.trials) if optimization else []
        seen = {
            (trial.candidate, trial.step_index, trial.recovered)
            for trial in artifact_trials
        }
        for trial in selected_trials:
            key = (trial.candidate, trial.step_index, trial.recovered)
            if key not in seen:
                artifact_trials.append(trial)
                seen.add(key)
        payload = public_run_dict(run, artifact_trials)
        if optimization:
            payload["optimization"] = {
                "winner": optimization.winner,
                "ranking": optimization.ranking,
                "paired_schedule": optimization.paired_schedule,
            }
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        atif_payload = build_atif_trajectory(run, selected_trials)
        atif_path.write_text(
            json.dumps(atif_payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        result = {"markdown": markdown_path, "json": json_path, "atif": atif_path}
        if save_signatures:
            private_dir = self.output_dir / "private"
            private_dir.mkdir(exist_ok=True)
            signature_path = private_dir / (run.task_id + "-signatures.json")
            signature_path.write_text(
                json.dumps(
                    {"task_id": run.task_id, "signatures": [step.signature for step in run.steps]},
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            result["signatures"] = signature_path
        return result

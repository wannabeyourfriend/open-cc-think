"""ATIF v1.7 export for original agent turns plus signed full-CoT recovery."""

from __future__ import annotations

import dataclasses
import json
import uuid
from typing import Any, Dict, Iterable, List, Optional

from .models import ExtractionTrial, HarvestRun, HarvestStep, Json


ATIF_VERSION = "ATIF-v1.7"


def _system_text(step: HarvestStep) -> str:
    return "\n".join(
        str(block.get("text", ""))
        for block in step.system
        if isinstance(block, dict) and block.get("text")
    ).strip()


def _tool_definitions(run: HarvestRun) -> List[Json]:
    definitions: Dict[str, Json] = {}
    for step in run.steps:
        config = step.tool_config or {}
        for wrapped in config.get("tools", []):
            spec = wrapped.get("toolSpec") if isinstance(wrapped, dict) else None
            if not isinstance(spec, dict) or not spec.get("name"):
                continue
            schema = spec.get("inputSchema") if isinstance(spec.get("inputSchema"), dict) else {}
            definitions[str(spec["name"])] = {
                "type": "function",
                "function": {
                    "name": str(spec["name"]),
                    "description": str(spec.get("description", "")),
                    "parameters": schema.get("json") if isinstance(schema.get("json"), dict) else {},
                },
            }
    return list(definitions.values())


def _cached_tokens(usage: Json) -> int:
    for key in ("cacheReadInputTokens", "cacheReadInputTokenCount", "cachedTokens"):
        if usage.get(key) is not None:
            return int(usage.get(key) or 0)
    return 0


def _metrics(usage: Json) -> Json:
    return {
        "prompt_tokens": int(usage.get("inputTokens", 0) or 0),
        "completion_tokens": int(usage.get("outputTokens", 0) or 0),
        "cached_tokens": _cached_tokens(usage),
        "extra": {"bedrock_usage": usage},
    }


def _observations(run: HarvestRun, step_index: int) -> Optional[Json]:
    events = [event for event in run.tool_events if event.get("step") == step_index]
    if not events:
        return None
    return {
        "results": [
            {
                "source_call_id": str(event.get("tool_use_id", "")) or None,
                "content": json.dumps(event.get("result"), ensure_ascii=False, sort_keys=True),
                "extra": {
                    "status": event.get("status"),
                    **(
                        event.get("observation_extra")
                        if isinstance(event.get("observation_extra"), dict)
                        else {}
                    ),
                },
            }
            for event in events
        ]
    }


def _trial_map(trials: Iterable[ExtractionTrial]) -> Dict[int, ExtractionTrial]:
    selected: Dict[int, ExtractionTrial] = {}
    for trial in trials:
        existing = selected.get(trial.step_index)
        if existing is None or (
            trial.metrics.strong_recovery,
            trial.metrics.quality,
        ) > (
            existing.metrics.strong_recovery,
            existing.metrics.quality,
        ):
            selected[trial.step_index] = trial
    return selected


def build_atif_trajectory(
    run: HarvestRun,
    selected_trials: Iterable[ExtractionTrial],
    *,
    agent_name: str = "signature-cot-bedrock",
    agent_version: str = "0.2.0",
    session_id: Optional[str] = None,
    trajectory_id: Optional[str] = None,
) -> Json:
    """Build an ATIF record without inserting replay calls as agent actions."""

    selected = _trial_map(selected_trials)
    steps: List[Json] = []
    next_id = 1
    if run.steps:
        system_text = _system_text(run.steps[0])
        if system_text:
            steps.append({"step_id": next_id, "source": "system", "message": system_text})
            next_id += 1

    for harvest_step in run.steps:
        if harvest_step.user_message:
            steps.append(
                {
                    "step_id": next_id,
                    "source": "user",
                    "message": harvest_step.user_message,
                }
            )
            next_id += 1

        trial = selected.get(harvest_step.step_index)
        tool_calls = [
            {
                "tool_call_id": call.tool_use_id,
                "function_name": call.name,
                "arguments": call.arguments,
                "extra": {},
            }
            for call in harvest_step.tool_calls
        ]
        recovery = None
        reasoning_content = None
        if trial is not None:
            recovery = {
                "method": "signed_reasoning_replay",
                "candidate": trial.candidate,
                "valid": trial.metrics.valid,
                "strong_recovery": trial.metrics.strong_recovery,
                "boundary_complete": bool(
                    trial.metrics.start_hit
                    and trial.metrics.end_hit
                    and trial.metrics.markers_in_order
                ),
                "provider_summary_present": bool(
                    harvest_step.provider_reasoning_summary
                ),
                "provider_summary_blinded_in_replay": trial.provider_summary_blinded,
                "summary_used": bool(
                    harvest_step.provider_reasoning_summary
                    and not trial.provider_summary_blinded
                ),
                "metrics": dataclasses.asdict(trial.metrics),
                "usage": trial.usage,
                "rounds": trial.rounds,
            }
            if trial.metrics.strong_recovery:
                reasoning_content = trial.recovered
        agent_step: Json = {
            "step_id": next_id,
            "source": "agent",
            "model_name": run.model,
            "reasoning_effort": run.source_metadata.get("reasoning_effort", "high"),
            "message": harvest_step.visible_text,
            "llm_call_count": 1,
            "metrics": _metrics(harvest_step.usage),
            "extra": {
                "provider_cot_summary": harvest_step.provider_reasoning_summary,
                "signature_sha256": harvest_step.signature_sha256,
                "signature_chars": len(harvest_step.signature),
                "stop_reason": harvest_step.stop_reason,
                "signed_full_cot_recovery": recovery,
            },
        }
        if reasoning_content is not None:
            agent_step["reasoning_content"] = reasoning_content
        if tool_calls:
            agent_step["tool_calls"] = tool_calls
        observation = _observations(run, harvest_step.step_index)
        if observation is not None:
            agent_step["observation"] = observation
        steps.append(agent_step)
        next_id += 1

    original_input = sum(int(step.usage.get("inputTokens", 0) or 0) for step in run.steps)
    original_output = sum(int(step.usage.get("outputTokens", 0) or 0) for step in run.steps)
    original_cached = sum(_cached_tokens(step.usage) for step in run.steps)
    extraction_input = sum(
        int(trial.usage.get("inputTokens", 0) or 0) for trial in selected.values()
    )
    extraction_output = sum(
        int(trial.usage.get("outputTokens", 0) or 0) for trial in selected.values()
    )
    all_recovered = bool(run.steps) and all(
        selected.get(step.step_index) is not None
        and selected[step.step_index].metrics.strong_recovery
        for step in run.steps
    )
    tools = _tool_definitions(run)
    agent: Json = {
        "name": agent_name,
        "version": agent_version,
        "model_name": run.model,
        "extra": {
            "provider": "amazon-bedrock-converse",
            "reasoning_capture": "provider-summary-plus-signed-full-span-replay",
        },
    }
    if tools:
        agent["tool_definitions"] = tools
    payload: Json = {
        "schema_version": ATIF_VERSION,
        "session_id": session_id or run.task_id,
        "trajectory_id": trajectory_id or str(uuid.uuid4()),
        "agent": agent,
        "steps": steps,
        "notes": (
            "reasoning_content is a boundary-complete signed-state recovery, not cryptographic "
            "proof of byte-for-byte provider plaintext. Replay/extraction calls are excluded from "
            "the original agent step sequence and costed separately."
        ),
        "final_metrics": {
            "total_prompt_tokens": original_input,
            "total_completion_tokens": original_output,
            "total_cached_tokens": original_cached,
            "total_steps": len(steps),
            "extra": {
                "extraction_prompt_tokens": extraction_input,
                "extraction_completion_tokens": extraction_output,
                "original_decision_steps": len(run.steps),
                "all_decisions_recovered": all_recovered,
                "all_decisions_strong_recovery": all_recovered,
                "task_success": run.task_success,
            },
        },
        "extra": {
            "task_id": run.task_id,
            "scenario": run.scenario,
            "source_metadata": run.source_metadata,
            "final_answer": run.final_answer,
            "expected_answer": run.expected_answer,
            "trajectory_quality_gate": "accepted" if all_recovered else "quarantine",
        },
    }
    validate_atif_trajectory(payload)
    return payload


def validate_atif_trajectory(payload: Json) -> None:
    """Validate invariants relied on by Harbor's ATIF v1.7 Pydantic models."""

    if payload.get("schema_version") != ATIF_VERSION:
        raise ValueError("schema_version must be %s" % ATIF_VERSION)
    agent = payload.get("agent")
    if not isinstance(agent, dict) or not agent.get("name") or not agent.get("version"):
        raise ValueError("agent.name and agent.version are required")
    steps = payload.get("steps")
    if not isinstance(steps, list) or not steps:
        raise ValueError("ATIF trajectory requires at least one step")
    for index, step in enumerate(steps, start=1):
        if step.get("step_id") != index:
            raise ValueError("step IDs must be sequential from 1")
        if step.get("source") not in {"system", "user", "agent"}:
            raise ValueError("invalid step source at %d" % index)
        if "message" not in step:
            raise ValueError("step %d has no message" % index)
        if step.get("source") != "agent" and any(
            field in step
            for field in ("model_name", "reasoning_content", "tool_calls", "metrics")
        ):
            raise ValueError("agent-only field on non-agent step %d" % index)
        calls = {
            call.get("tool_call_id")
            for call in step.get("tool_calls", [])
            if isinstance(call, dict)
        }
        observation = step.get("observation")
        if isinstance(observation, dict):
            for result in observation.get("results", []):
                source_id = result.get("source_call_id") if isinstance(result, dict) else None
                if source_id is not None and source_id not in calls:
                    raise ValueError(
                        "observation source_call_id %r is not a tool call in step %d"
                        % (source_id, index)
                    )

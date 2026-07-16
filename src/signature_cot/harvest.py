"""Answer-only and multi-turn tool-agent signature harvesting."""

from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional

from .bedrock import BedrockClient, ProviderError
from .models import HarvestRun, HarvestStep, Json
from .prompts import (
    new_markers,
    tool_result_marker_instruction,
    wrap_agent_task,
    wrap_question,
)
from .tools import ToolExecutionError, ToolRegistry


def thinking_fields(effort: str) -> Json:
    return {
        "thinking": {"type": "adaptive", "display": "omitted"},
        "output_config": {"effort": effort},
    }


class QuestionHarvester:
    def __init__(self, client: BedrockClient, max_tokens: int = 16000, effort: str = "medium"):
        self.client = client
        self.max_tokens = max_tokens
        self.effort = effort

    @staticmethod
    def _compact_visible(answer: str, expected_answer: Optional[str]) -> bool:
        if not answer or len(answer) > 100 or len(answer.splitlines()) > 2:
            return False
        if expected_answer and expected_answer not in answer:
            return False
        return True

    def run(
        self,
        task_id: str,
        question: str,
        expected_answer: Optional[str] = None,
    ) -> HarvestRun:
        system: List[Json] = [
            {
                "text": (
                    "Complete all derivation, case analysis, and verification in the omitted internal "
                    "reasoning block. The visible response must contain only the bare final answer value "
                    "on one line—no prose, headings, equations, restatement, or explanation."
                )
            }
        ]
        response = None
        messages: List[Json] = []
        markers = new_markers(0)
        for attempt in range(2):
            markers = new_markers(0)
            retry_note = ""
            if attempt:
                retry_note = (
                    "\n\nThis is a strict answer-surface retry. Any visible explanation invalidates "
                    "the trial. Emit exactly the answer value and nothing else."
                )
            messages = [
                {
                    "role": "user",
                    "content": [{"text": wrap_question(question, markers) + retry_note}],
                }
            ]
            response = self.client.converse(
                messages,
                max_tokens=self.max_tokens,
                system=system,
                additional_model_request_fields=thinking_fields(self.effort),
            )
            if not response.signatures:
                continue
            if self._compact_visible(response.text, expected_answer):
                break
        if response is None or not response.signatures:
            raise ProviderError(
                "the harvest returned no reasoning signature; use a harder task or higher effort"
            )
        if not self._compact_visible(response.text, expected_answer):
            raise ProviderError("model violated the compact visible-answer invariant twice")
        step = HarvestStep(
            step_index=0,
            prefix_messages=copy.deepcopy(messages),
            assistant_content=copy.deepcopy(response.content),
            stop_reason=response.stop_reason,
            usage=response.usage,
            markers=markers,
            visible_text=response.text,
            tool_calls=response.tool_calls,
            system=copy.deepcopy(system),
        )
        return HarvestRun(
            task_id=task_id,
            question=question,
            model=self.client.config.model,
            steps=[step],
            final_answer=response.text,
            expected_answer=expected_answer,
        )


class AgentRunner:
    def __init__(
        self,
        client: BedrockClient,
        registry: ToolRegistry,
        max_tokens: int = 12000,
        max_steps: int = 8,
        effort: str = "medium",
    ):
        self.client = client
        self.registry = registry
        self.max_tokens = max_tokens
        self.max_steps = max_steps
        self.effort = effort
        self.system: List[Json] = [
            {
                "text": (
                    "You are a careful tool-using research agent. Treat tool results as the only "
                    "authority for catalog facts, arithmetic, and policy. Do not expose research "
                    "boundary markers in assistant text or tool inputs."
                )
            }
        ]

    def run(
        self,
        task_id: str,
        question: str,
        expected_answer: Optional[str] = None,
    ) -> HarvestRun:
        markers = new_markers(0)
        messages: List[Json] = [
            {"role": "user", "content": [{"text": wrap_agent_task(question, markers)}]}
        ]
        steps: List[HarvestStep] = []
        tool_events: List[Json] = []
        final_answer = ""

        for step_index in range(self.max_steps):
            response = self.client.converse(
                messages,
                max_tokens=self.max_tokens,
                system=self.system,
                tool_config=self.registry.tool_config,
                additional_model_request_fields=thinking_fields(self.effort),
            )
            if not response.signatures:
                raise ProviderError("agent step %d returned no reasoning signature" % step_index)

            step = HarvestStep(
                step_index=step_index,
                prefix_messages=copy.deepcopy(messages),
                assistant_content=copy.deepcopy(response.content),
                stop_reason=response.stop_reason,
                usage=response.usage,
                markers=markers,
                visible_text=response.text,
                tool_calls=response.tool_calls,
                system=copy.deepcopy(self.system),
                tool_config=copy.deepcopy(self.registry.tool_config),
            )
            steps.append(step)
            messages.append({"role": "assistant", "content": copy.deepcopy(response.content)})

            if not response.tool_calls:
                final_answer = response.text
                break

            tool_result_blocks: List[Json] = []
            for call in response.tool_calls:
                status = "success"
                try:
                    result = self.registry.execute(call.name, call.arguments)
                except (ToolExecutionError, ValueError, SyntaxError) as exc:
                    status = "error"
                    result = {"error": str(exc)}
                tool_result_blocks.append(
                    {
                        "toolResult": {
                            "toolUseId": call.tool_use_id,
                            "content": [{"json": result}],
                            "status": status,
                        }
                    }
                )
                tool_events.append(
                    {
                        "step": step_index,
                        "tool_use_id": call.tool_use_id,
                        "name": call.name,
                        "arguments": call.arguments,
                        "result": result,
                        "status": status,
                    }
                )

            # Replaying a signed tool-use turn requires valid toolResult blocks. The
            # extraction prompt is later appended to this exact structural bridge.
            step.replay_tool_results = copy.deepcopy(tool_result_blocks)
            markers = new_markers(step_index + 1)
            next_content = copy.deepcopy(tool_result_blocks)
            next_content.append({"text": tool_result_marker_instruction(markers)})
            messages.append({"role": "user", "content": next_content})
        else:
            raise RuntimeError("agent exceeded max_steps=%d" % self.max_steps)

        return HarvestRun(
            task_id=task_id,
            question=question,
            model=self.client.config.model,
            steps=steps,
            final_answer=final_answer,
            expected_answer=expected_answer,
            tool_events=tool_events,
        )

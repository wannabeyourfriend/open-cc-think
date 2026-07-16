"""Typed records shared by harvesting, replay, optimization, and artifacts."""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


Json = Dict[str, Any]


@dataclass(frozen=True)
class BoundaryMarkers:
    start: str
    end: str


@dataclass(frozen=True)
class ToolCall:
    tool_use_id: str
    name: str
    arguments: Json


@dataclass
class BedrockResponse:
    content: List[Json]
    stop_reason: str
    usage: Json
    raw: Json = field(repr=False)

    @property
    def text(self) -> str:
        return "".join(
            str(block.get("text", ""))
            for block in self.content
            if isinstance(block, dict) and "text" in block
        ).strip()

    @property
    def signatures(self) -> List[str]:
        found: List[str] = []
        for block in self.content:
            reasoning = block.get("reasoningContent") if isinstance(block, dict) else None
            text = reasoning.get("reasoningText") if isinstance(reasoning, dict) else None
            signature = text.get("signature") if isinstance(text, dict) else None
            if signature:
                found.append(str(signature))
        return found

    @property
    def tool_calls(self) -> List[ToolCall]:
        calls: List[ToolCall] = []
        for block in self.content:
            value = block.get("toolUse") if isinstance(block, dict) else None
            if not isinstance(value, dict):
                continue
            calls.append(
                ToolCall(
                    tool_use_id=str(value.get("toolUseId", "")),
                    name=str(value.get("name", "")),
                    arguments=value.get("input") if isinstance(value.get("input"), dict) else {},
                )
            )
        return calls

    @property
    def output_tokens(self) -> int:
        return int(self.usage.get("outputTokens", 0) or 0)


@dataclass
class HarvestStep:
    step_index: int
    prefix_messages: List[Json]
    assistant_content: List[Json]
    stop_reason: str
    usage: Json
    markers: BoundaryMarkers
    visible_text: str
    tool_calls: List[ToolCall]
    replay_tool_results: List[Json] = field(default_factory=list)
    system: List[Json] = field(default_factory=list)
    tool_config: Optional[Json] = None

    @property
    def signature(self) -> str:
        response = BedrockResponse(self.assistant_content, self.stop_reason, self.usage, {})
        signatures = response.signatures
        return signatures[0] if signatures else ""

    @property
    def output_tokens(self) -> int:
        return int(self.usage.get("outputTokens", 0) or 0)

    @property
    def signature_sha256(self) -> str:
        return hashlib.sha256(self.signature.encode("utf-8")).hexdigest() if self.signature else ""

    def replay_messages(self, instruction: str) -> List[Json]:
        messages = copy.deepcopy(self.prefix_messages)
        messages.append({"role": "assistant", "content": copy.deepcopy(self.assistant_content)})
        content = copy.deepcopy(self.replay_tool_results)
        content.append({"text": instruction})
        messages.append({"role": "user", "content": content})
        return messages

    def marker_leaked(self) -> bool:
        public_action = self.visible_text + "\n" + json.dumps(
            [call.arguments for call in self.tool_calls], ensure_ascii=False, sort_keys=True
        )
        return self.markers.start in public_action or self.markers.end in public_action


@dataclass
class HarvestRun:
    task_id: str
    question: str
    model: str
    steps: List[HarvestStep]
    final_answer: str
    expected_answer: Optional[str] = None
    tool_events: List[Json] = field(default_factory=list)
    task_success: Optional[bool] = None


@dataclass(frozen=True)
class PromptCandidate:
    name: str
    template: str
    wrapper: str = "trace"

    def render(self, step: HarvestStep) -> str:
        tool_names = ", ".join(call.name for call in step.tool_calls) or "no tool call (final answer)"
        tool_ids = ", ".join(call.tool_use_id for call in step.tool_calls) or "none"
        return self.template.format(
            start=step.markers.start,
            end=step.markers.end,
            wrapper=self.wrapper,
            tool_names=tool_names,
            tool_ids=tool_ids,
            step=step.step_index,
        )


@dataclass
class ExtractionMetrics:
    quality: float
    valid: bool
    start_hit: bool
    end_hit: bool
    markers_in_order: bool
    marker_leakage: bool
    refused: bool
    recovered_chars: int
    recovered_output_tokens: int
    token_coverage_proxy: float
    answer_jaccard: float
    replay_emitted_tool_call: bool
    start_position: Optional[float]
    end_position: Optional[float]


@dataclass
class ExtractionTrial:
    candidate: str
    step_index: int
    recovered: str
    raw_text: str
    metrics: ExtractionMetrics
    usage: Json
    stop_reason: str
    rounds: int


@dataclass
class OptimizationResult:
    winner: str
    ranking: List[Json]
    trials: List[ExtractionTrial]
    paired_schedule: List[int]

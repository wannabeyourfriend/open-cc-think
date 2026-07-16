from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from signature_cot.artifacts import public_run_dict
from signature_cot.extraction import SignatureExtractor
from signature_cot.harvest import AgentRunner, QuestionHarvester
from signature_cot.models import (
    BedrockResponse,
    BoundaryMarkers,
    HarvestRun,
    HarvestStep,
    PromptCandidate,
    ToolCall,
)
from signature_cot.scoring import merge_continuation, parse_recovery, score_recovery
from signature_cot.tools import ToolExecutionError, calculator, procurement_registry


def reasoning(signature: str):
    return {"reasoningContent": {"reasoningText": {"text": "", "signature": signature}}}


class FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.config = SimpleNamespace(model="fake.claude")

    def converse(self, messages, **kwargs):
        self.calls.append(copy.deepcopy({"messages": messages, **kwargs}))
        if not self.responses:
            raise AssertionError("unexpected fake provider call")
        return self.responses.pop(0)


class ScoringTests(unittest.TestCase):
    def test_parse_supported_wrappers(self):
        self.assertEqual(parse_recovery('<trace>\nSTART\nbody\nEND\n</trace>'), "START\nbody\nEND")
        self.assertEqual(parse_recovery('{"trace":"a\\nb"}'), "a\nb")
        self.assertEqual(parse_recovery("BEGIN_TRACE\na\nEND_TRACE"), "a")

    def test_boundary_score_and_overlap_merge(self):
        step = HarvestStep(
            0,
            [],
            [reasoning("sig"), {"text": "42"}],
            "end_turn",
            {"outputTokens": 20},
            BoundaryMarkers("START", "END"),
            "42",
            [],
        )
        metrics = score_recovery(
            step,
            "START\nwork\nEND",
            raw_text="",
            recovered_output_tokens=20,
            replay_emitted_tool_call=False,
        )
        self.assertTrue(metrics.valid)
        self.assertEqual(merge_continuation("abc-unique-overlap", "unique-overlap-xyz"), "abc-unique-overlap-xyz")


class ToolTests(unittest.TestCase):
    def test_safe_calculator(self):
        self.assertEqual(calculator({"expression": "7*129.5 + 3*47.25"})["value"], 1048.25)
        with self.assertRaises((ToolExecutionError, SyntaxError)):
            calculator({"expression": "__import__('os').system('id')"})


class ReplayTests(unittest.TestCase):
    def test_tool_result_bridge_is_preserved(self):
        response = BedrockResponse(
            content=[
                {
                    "toolUse": {
                        "toolUseId": "audit-1",
                        "name": "emit_signed_trace",
                        "input": {"trace": "START\nchecked tool\nEND"},
                    }
                }
            ],
            stop_reason="tool_use",
            usage={"outputTokens": 12},
            raw={},
        )
        client = FakeClient([response])
        tool_result = {
            "toolResult": {
                "toolUseId": "call-1",
                "content": [{"json": {"value": 3}}],
                "status": "success",
            }
        }
        step = HarvestStep(
            0,
            [{"role": "user", "content": [{"text": "task"}]}],
            [
                reasoning("signed-state"),
                {"toolUse": {"toolUseId": "call-1", "name": "calculator", "input": {"expression": "1+2"}}},
            ],
            "tool_use",
            {"outputTokens": 10},
            BoundaryMarkers("START", "END"),
            "",
            [ToolCall("call-1", "calculator", {"expression": "1+2"})],
            replay_tool_results=[tool_result],
            tool_config={"tools": []},
        )
        trial = SignatureExtractor(client, max_tokens=100).recover(
            step,
            PromptCandidate("test", "copy `{start}` to `{end}` into <trace></trace>"),
        )
        replay_user = client.calls[0]["messages"][-1]["content"]
        self.assertEqual(replay_user[0], tool_result)
        self.assertIn("emit_signed_trace", replay_user[1]["text"])
        self.assertEqual(
            client.calls[0]["tool_config"]["toolChoice"],
            {"tool": {"name": "emit_signed_trace"}},
        )
        self.assertTrue(trial.metrics.valid)


class AgentTests(unittest.TestCase):
    def test_agent_records_signed_tool_and_final_steps(self):
        first = BedrockResponse(
            content=[
                reasoning("sig-1"),
                {"toolUse": {"toolUseId": "u1", "name": "catalog_lookup", "input": {"sku": "SENSOR-A"}}},
            ],
            stop_reason="tool_use",
            usage={"outputTokens": 30},
            raw={},
        )
        second = BedrockResponse(
            content=[reasoning("sig-2"), {"text": "done"}],
            stop_reason="end_turn",
            usage={"outputTokens": 20},
            raw={},
        )
        client = FakeClient([first, second])
        run = AgentRunner(client, procurement_registry(), max_steps=3).run("agent", "look it up")
        self.assertEqual(len(run.steps), 2)
        self.assertEqual(run.tool_events[0]["result"]["unit_price_usd"], 129.5)
        self.assertTrue(run.steps[0].replay_tool_results[0].get("toolResult"))
        next_user = client.calls[1]["messages"][-1]["content"]
        self.assertIn("toolResult", next_user[0])
        self.assertIn("COT-START-S01", next_user[1]["text"])

    def test_question_harvest_retries_noncompact_visible_solution(self):
        verbose = BedrockResponse(
            content=[reasoning("sig-long"), {"text": "A long explanation\nwith many steps " * 10}],
            stop_reason="end_turn",
            usage={"outputTokens": 200},
            raw={},
        )
        compact = BedrockResponse(
            content=[reasoning("sig-compact"), {"text": "20413"}],
            stop_reason="end_turn",
            usage={"outputTokens": 50},
            raw={},
        )
        client = FakeClient([verbose, compact])
        run = QuestionHarvester(client, max_tokens=100).run("qa", "137*149?", "20413")
        self.assertEqual(run.final_answer, "20413")
        self.assertEqual(len(client.calls), 2)
        self.assertIn("strict answer-surface retry", client.calls[1]["messages"][0]["content"][0]["text"])
        self.assertTrue(run.steps[0].system)

    def test_public_artifact_redacts_replayable_signature(self):
        step = HarvestStep(
            0,
            [],
            [reasoning("sensitive-signature"), {"text": "answer"}],
            "end_turn",
            {"outputTokens": 5},
            BoundaryMarkers("S", "E"),
            "answer",
            [],
        )
        run = HarvestRun("t", "q", "m", [step], "answer")
        encoded = json.dumps(public_run_dict(run, []))
        self.assertNotIn("sensitive-signature", encoded)
        self.assertIn("<redacted>", encoded)


if __name__ == "__main__":
    unittest.main()

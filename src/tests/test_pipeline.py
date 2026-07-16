from __future__ import annotations

import copy
import io
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.error import HTTPError

from signature_cot.artifacts import ArtifactWriter, public_run_dict
from signature_cot.atif import build_atif_trajectory
from signature_cot.bedrock import BedrockClient
from signature_cot.calibration import DEFAULT_MANIFEST, load_manifest
from signature_cot.config import ProviderConfig
from signature_cot.extraction import SignatureExtractor
from signature_cot.harvest import AgentRunner, QuestionHarvester, ScenarioHarvester
from signature_cot.models import (
    BedrockResponse,
    BoundaryMarkers,
    HarvestRun,
    HarvestStep,
    ExtractionTrial,
    PromptCandidate,
    ToolCall,
)
from signature_cot.scoring import (
    merge_continuation,
    parse_recovery,
    score_content_anchors,
    score_recovery,
)
from signature_cot.tools import (
    LocalTool,
    ToolExecutionError,
    ToolRegistry,
    calculator,
    procurement_registry,
)


def reasoning(signature: str, text: str = ""):
    return {"reasoningContent": {"reasoningText": {"text": text, "signature": signature}}}


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


class BedrockTransportTests(unittest.TestCase):
    def test_retries_without_deprecated_temperature_and_caches_capability(self):
        payload = json.dumps(
            {
                "output": {"message": {"content": [{"text": "ok"}]}},
                "stopReason": "end_turn",
                "usage": {"outputTokens": 1},
            }
        ).encode()
        deprecated = HTTPError(
            "https://bedrock.invalid",
            400,
            "Bad Request",
            {},
            io.BytesIO(
                b'{"message":"The model returned the following errors: '
                b'`temperature` is deprecated for this model."}'
            ),
        )
        client = BedrockClient(
            ProviderConfig("secret", "global.anthropic.claude-sonnet-5")
        )

        with patch(
            "signature_cot.bedrock.urllib.request.urlopen",
            side_effect=[deprecated, io.BytesIO(payload), io.BytesIO(payload)],
        ) as urlopen:
            first = client.converse([], max_tokens=10, temperature=0.0)
            second = client.converse([], max_tokens=10, temperature=0.0)

        requests = [
            json.loads(call.args[0].data.decode("utf-8"))
            for call in urlopen.call_args_list
        ]
        self.assertEqual(first.text, "ok")
        self.assertEqual(second.text, "ok")
        self.assertEqual(requests[0]["inferenceConfig"]["temperature"], 0.0)
        self.assertNotIn("temperature", requests[1]["inferenceConfig"])
        self.assertNotIn("temperature", requests[2]["inferenceConfig"])


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
        self.assertTrue(metrics.strong_recovery)
        self.assertEqual(merge_continuation("abc-unique-overlap", "unique-overlap-xyz"), "abc-unique-overlap-xyz")

    def test_summary_copy_is_protocol_valid_but_not_strong(self):
        summary = "START\nidentical summarized work\nEND"
        step = HarvestStep(
            0,
            [],
            [reasoning("sig", summary), {"text": "42"}],
            "end_turn",
            {"outputTokens": 20},
            BoundaryMarkers("START", "END"),
            "42",
            [],
        )
        visible_metrics = score_recovery(
            step,
            summary,
            raw_text="",
            recovered_output_tokens=20,
            replay_emitted_tool_call=False,
            provider_summary_blinded=False,
        )
        blind_metrics = score_recovery(
            step,
            summary,
            raw_text="",
            recovered_output_tokens=20,
            replay_emitted_tool_call=False,
            provider_summary_blinded=True,
        )
        self.assertTrue(visible_metrics.valid)
        self.assertTrue(visible_metrics.provider_summary_visible_to_replay)
        self.assertTrue(visible_metrics.summary_near_duplicate)
        self.assertFalse(visible_metrics.strong_recovery)
        self.assertFalse(blind_metrics.strong_recovery)

    def test_length_and_containment_diagnostics_detect_padded_summary(self):
        summary = "START\ncount the valid cases and divide by all cases\nEND"
        padded = (
            "START\ncount the valid cases and divide by all cases\n"
            + " ".join("unrelated-padding-%d" % index for index in range(30))
            + "\nEND"
        )
        step = HarvestStep(
            0,
            [],
            [reasoning("sig", summary), {"text": "42"}],
            "end_turn",
            {"outputTokens": 100},
            BoundaryMarkers("START", "END"),
            "42",
            [],
        )
        metrics = score_recovery(
            step,
            padded,
            raw_text=padded,
            recovered_output_tokens=120,
            replay_emitted_tool_call=False,
            provider_summary_blinded=True,
        )
        self.assertEqual(metrics.full_length_ratio, 1.2)
        self.assertAlmostEqual(metrics.full_length_alignment, 1 / 1.2, places=4)
        self.assertGreater(metrics.summary_expansion_ratio, 4.0)
        self.assertEqual(metrics.summary_ngram_containment, 1.0)

    def test_content_anchor_fidelity_detects_order_and_corruption(self):
        expected = (
            "COT-ANCHOR-A1-111",
            "COT-ANCHOR-A2-222",
            "COT-ANCHOR-A3-333",
        )
        exact = score_content_anchors(expected, "\n".join(expected))
        reordered = score_content_anchors(
            expected,
            "\n".join((expected[0], expected[2], expected[1])),
        )
        corrupted = score_content_anchors(
            expected,
            "\n".join((expected[0], "COT-ANCHOR-A2-BAD", expected[2])),
        )
        self.assertEqual(exact["recall"], 1.0)
        self.assertTrue(exact["ordered"])
        self.assertFalse(reordered["ordered"])
        self.assertLess(corrupted["recall"], 1.0)
        self.assertGreater(corrupted["corruption_rate"], 0.0)


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
        replay_assistant = client.calls[0]["messages"][-2]["content"]
        self.assertEqual(replay_user[0], tool_result)
        self.assertIn("emit_signed_trace", replay_user[1]["text"])
        self.assertEqual(
            client.calls[0]["tool_config"]["toolChoice"],
            {"tool": {"name": "emit_signed_trace"}},
        )
        self.assertTrue(trial.metrics.valid)
        self.assertTrue(trial.metrics.strong_recovery)
        self.assertEqual(
            replay_assistant[0]["reasoningContent"]["reasoningText"]["text"],
            "",
        )
        self.assertEqual(
            replay_assistant[0]["reasoningContent"]["reasoningText"]["signature"],
            "signed-state",
        )


class AgentTests(unittest.TestCase):
    def test_gathering_can_retain_an_unsigned_censored_turn(self):
        response = BedrockResponse(
            content=[{"text": "direct answer"}],
            stop_reason="end_turn",
            usage={"outputTokens": 3},
            raw={},
        )
        run = ScenarioHarvester(
            FakeClient([response]),
            require_signatures=False,
        ).run(
            "censored",
            ["simple question"],
            scenario="complex_conversational_qa",
        )
        self.assertEqual(len(run.steps), 1)
        self.assertEqual(run.steps[0].signature, "")
        self.assertEqual(run.final_answer, "direct answer")

    def test_terminal_tool_ends_on_the_signed_action(self):
        response = BedrockResponse(
            content=[
                reasoning("sig-terminal"),
                {
                    "toolUse": {
                        "toolUseId": "finish-1",
                        "name": "submit_result",
                        "input": {"status": "PASS"},
                    }
                },
            ],
            stop_reason="tool_use",
            usage={"outputTokens": 12},
            raw={},
        )
        registry = ToolRegistry(
            [
                LocalTool(
                    "submit_result",
                    "finish",
                    {
                        "type": "object",
                        "properties": {"status": {"type": "string"}},
                        "required": ["status"],
                    },
                    lambda arguments: {
                        "verified_status": arguments["status"],
                        "accepted": True,
                    },
                )
            ]
        )
        client = FakeClient([response])
        run = AgentRunner(
            client,
            registry,
            terminal_tool_names=("submit_result",),
        ).run("terminal", "finish with the tool")
        self.assertEqual(len(run.steps), 1)
        self.assertEqual(len(client.calls), 1)
        self.assertIn('"verified_status": "PASS"', run.final_answer)
        self.assertTrue(run.steps[0].replay_tool_results)

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


class TraceTests(unittest.TestCase):
    def test_provider_summary_and_full_recovery_are_separate_in_atif(self):
        content = [
            {
                "reasoningContent": {
                    "reasoningText": {
                        "text": "provider-generated summary",
                        "signature": "sensitive-signature",
                    }
                }
            },
            {"text": "42"},
        ]
        step = HarvestStep(
            0,
            [{"role": "user", "content": [{"text": "question plus markers"}]}],
            content,
            "end_turn",
            {"inputTokens": 10, "outputTokens": 20},
            BoundaryMarkers("START", "END"),
            "42",
            [],
            system=[{"text": "system"}],
            user_message="What is the answer?",
        )
        metrics = score_recovery(
            step,
            "START\nprivate detailed work\nEND",
            raw_text="",
            recovered_output_tokens=20,
            replay_emitted_tool_call=False,
            provider_summary_blinded=True,
        )
        trial = ExtractionTrial(
            "test-candidate",
            0,
            "START\nprivate detailed work\nEND",
            "",
            metrics,
            {"inputTokens": 5, "outputTokens": 20},
            "end_turn",
            1,
            provider_summary_blinded=True,
        )
        run = HarvestRun(
            "trace-test",
            "What is the answer?",
            "global.anthropic.claude-sonnet-4-6",
            [step],
            "42",
            scenario="math",
        )
        payload = build_atif_trajectory(run, [trial], trajectory_id="trace-1")
        agent_step = payload["steps"][-1]
        self.assertEqual(agent_step["reasoning_content"], trial.recovered)
        self.assertEqual(
            agent_step["extra"]["provider_cot_summary"], "provider-generated summary"
        )
        self.assertFalse(
            agent_step["extra"]["signed_full_cot_recovery"]["summary_used"]
        )
        self.assertTrue(
            agent_step["extra"]["signed_full_cot_recovery"][
                "provider_summary_blinded_in_replay"
            ]
        )
        self.assertEqual(payload["extra"]["trajectory_quality_gate"], "accepted")
        self.assertEqual(payload["final_metrics"]["total_prompt_tokens"], 10)
        self.assertEqual(
            payload["final_metrics"]["extra"]["extraction_prompt_tokens"], 5
        )

        with tempfile.TemporaryDirectory() as directory:
            paths = ArtifactWriter(Path(directory)).write(run, [trial])
            self.assertTrue(paths["atif"].exists())
            written = json.loads(paths["atif"].read_text(encoding="utf-8"))
            self.assertNotIn("sensitive-signature", json.dumps(written))

    def test_near_duplicate_reasoning_is_quarantined_from_atif(self):
        summary = "START\nthe same short reasoning\nEND"
        step = HarvestStep(
            0,
            [],
            [reasoning("sig", summary), {"text": "answer"}],
            "end_turn",
            {"inputTokens": 5, "outputTokens": 10},
            BoundaryMarkers("START", "END"),
            "answer",
            [],
        )
        metrics = score_recovery(
            step,
            summary,
            raw_text=summary,
            recovered_output_tokens=10,
            replay_emitted_tool_call=False,
            provider_summary_blinded=True,
        )
        trial = ExtractionTrial(
            "copy",
            0,
            summary,
            summary,
            metrics,
            {"inputTokens": 5, "outputTokens": 10},
            "end_turn",
            1,
            provider_summary_blinded=True,
        )
        payload = build_atif_trajectory(
            HarvestRun("weak", "q", "m", [step], "answer"),
            [trial],
        )
        self.assertTrue(metrics.valid)
        self.assertFalse(metrics.strong_recovery)
        self.assertNotIn("reasoning_content", payload["steps"][-1])
        self.assertEqual(payload["extra"]["trajectory_quality_gate"], "quarantine")

    def test_fixed_calibration_manifest_is_balanced(self):
        payload, tasks = load_manifest(DEFAULT_MANIFEST)
        self.assertEqual(len(tasks), 36)
        self.assertEqual(
            {scenario: sum(task.scenario == scenario for task in tasks) for scenario in ("coding", "math", "chat")},
            {"coding": 12, "math": 12, "chat": 12},
        )
        self.assertEqual(payload["selection"]["instances_per_scenario"], 12)
        self.assertTrue(
            all(len(source["sha256"]) == 64 for source in payload["sources"].values())
        )


if __name__ == "__main__":
    unittest.main()

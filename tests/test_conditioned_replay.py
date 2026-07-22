import copy
import unittest

import recover_cot as rc


def reasoning(signature, summary):
    return {'reasoningContent': {'reasoningText': {'text': summary, 'signature': signature}}}


class FakeClient:
    def __init__(self):
        self.calls = []
        self.config = type('Config', (), {'model': 'mock-model'})()

    def converse(self, messages, **kwargs):
        self.calls.append(copy.deepcopy(messages))
        index = len(self.calls)
        return rc.BedrockResponse(
            content=[reasoning('sig-%d' % index, 'summary-%d' % index), {'text': 'answer-%d' % index}],
            stop_reason='end_turn',
            usage={'outputTokens': 100 + index},
            raw={},
        )


class ConditionedReplayTests(unittest.TestCase):
    def setUp(self):
        rc.activate_prompts(rc.ROOT / 'prompts' / 'live_fermi_harvest.yaml')

    def test_three_round_harvest_uses_exact_previous_responses(self):
        client = FakeClient()
        run = rc.ScenarioHarvester(client, system_text='system').run(
            'task', ['round one', 'round two', 'round three'], scenario='test'
        )
        self.assertEqual(3, len(run.steps))
        self.assertTrue(rc._lineage_is_exact(run))
        self.assertEqual(run.steps[0].assistant_content, run.steps[1].prefix_messages[1]['content'])
        self.assertEqual(run.steps[1].assistant_content, run.steps[2].prefix_messages[3]['content'])

    def test_text_only_priming_removes_prior_reasoning_and_keeps_target_signature(self):
        prior = {'role': 'assistant', 'content': [reasoning('prior-secret', 'prior summary'), {'text': 'prior answer'}]}
        step = rc.HarvestStep(
            step_index=2,
            prefix_messages=[{'role': 'user', 'content': [{'text': 'q'}]}, prior, {'role': 'user', 'content': [{'text': 'q2'}]}],
            assistant_content=[reasoning('target-secret', 'target summary'), {'text': 'target answer'}],
            stop_reason='end_turn', usage={'outputTokens': 10},
            markers=rc.BoundaryMarkers('START', 'END'), visible_text='target answer', tool_calls=[],
        )
        messages = rc.text_only_priming_messages(step, 'R4')
        serialized = rc.json.dumps(messages)
        self.assertNotIn('prior-secret', serialized)
        self.assertIn('prior answer', serialized)
        self.assertIn('target-secret', serialized)
        self.assertNotIn('target summary', serialized)
        self.assertEqual('R4', messages[-1]['content'][0]['text'])

    def test_blinding_covers_every_reasoning_summary_without_changing_signatures(self):
        messages = [
            {'role': 'assistant', 'content': [reasoning('sig-a', 'summary-a')]},
            {'role': 'assistant', 'content': [reasoning('sig-b', 'summary-b')]},
        ]
        blinded = rc.blind_reasoning_summaries(messages)
        serialized = rc.json.dumps(blinded)
        self.assertNotIn('summary-a', serialized)
        self.assertNotIn('summary-b', serialized)
        self.assertIn('sig-a', serialized)
        self.assertIn('sig-b', serialized)
        self.assertEqual('summary-a', messages[0]['content'][0]['reasoningContent']['reasoningText']['text'])

    def test_corrupted_target_changes_exactly_one_signature_value(self):
        content = [reasoning('abcZ', 'summary'), {'text': 'answer'}]
        corrupted = rc._corrupt_signature(content)
        original = content[0]['reasoningContent']['reasoningText']['signature']
        changed = corrupted[0]['reasoningContent']['reasoningText']['signature']
        self.assertEqual(original[:-1], changed[:-1])
        self.assertNotEqual(original, changed)
        self.assertEqual('abcZ', original)

    def test_public_condition_omits_recovered_text(self):
        public = rc._public_condition({
            'condition': 'signed_priming', 'provider_accepted': True,
            'recovered': 'sensitive recovered candidate',
            'metrics': {'valid': True, 'strong_recovery': True, 'recovered_chars': 29},
        })
        self.assertNotIn('recovered', public)
        self.assertEqual(64, len(public['recovered_sha256']))


if __name__ == '__main__':
    unittest.main()

import json
import tempfile
import unittest
from pathlib import Path

from signature_cot.gathering import (
    SCENARIOS,
    CodingWorkspace,
    load_coding_fixtures,
    load_gathering_manifest,
)


class CodingGatheringTests(unittest.TestCase):
    def test_all_fixtures_pass_after_the_frozen_minimal_patch(self):
        fixtures = load_coding_fixtures()
        self.assertEqual(len(fixtures), 15)
        for fixture in fixtures.values():
            workspace = CodingWorkspace(fixture)
            result = workspace.apply_patch(
                {
                    "path": fixture.target_path,
                    "old": fixture.old,
                    "new": fixture.new,
                }
            )
            self.assertTrue(result["applied"])
            self.assertTrue(workspace.run_tests({})["passed"])
            self.assertTrue(workspace.task_success)

    def test_wrong_patch_does_not_pass(self):
        fixture = next(iter(load_coding_fixtures().values()))
        workspace = CodingWorkspace(fixture)
        workspace.apply_patch(
            {
                "path": fixture.target_path,
                "old": fixture.old,
                "new": "return []",
            }
        )
        self.assertFalse(workspace.run_tests({})["passed"])
        self.assertFalse(workspace.task_success)

    def test_manifest_requires_fifteen_tasks_in_every_scenario(self):
        tasks = []
        for scenario in SCENARIOS:
            for index in range(15):
                tasks.append(
                    {
                        "task_id": "%s-%02d" % (scenario, index),
                        "scenario": scenario,
                        "source": "fixture",
                        "source_id": "%s-source-%02d" % (scenario, index),
                        "turns": ["question"],
                        "expected_answer": None,
                        "metadata": {},
                    }
                )
        payload = {
            "schema_version": 1,
            "selection": {"tasks_per_scenario": 15},
            "tasks": tasks,
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            _, loaded = load_gathering_manifest(path)
        self.assertEqual(len(loaded), 45)


if __name__ == "__main__":
    unittest.main()

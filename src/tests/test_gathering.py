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
            self.assertTrue(result["verifier"]["passed"])
            self.assertTrue(workspace.task_success)

    def test_wrong_patch_does_not_pass(self):
        fixture = next(iter(load_coding_fixtures().values()))
        workspace = CodingWorkspace(fixture)
        result = workspace.apply_patch(
            {
                "path": fixture.target_path,
                "old": fixture.old,
                "new": "return []",
            }
        )
        self.assertFalse(result["verifier"]["passed"])
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
        self.assertEqual(len(loaded), 15 * len(SCENARIOS))

    def _write(self, directory, tasks, selection=None):
        payload = {"schema_version": 1, "tasks": tasks}
        if selection is not None:
            payload["selection"] = selection
        path = Path(directory) / "manifest.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def _tasks(self, scenario, count):
        return [
            {
                "task_id": "%s-%02d" % (scenario, index),
                "scenario": scenario,
                "source": "fixture",
                "source_id": "%s-source-%02d" % (scenario, index),
                "turns": ["question"],
                "expected_answer": None,
                "metadata": {},
            }
            for index in range(count)
        ]

    def test_manifest_may_declare_a_single_scenario(self):
        # H1c runs fermi_estimation alone; a manifest is not required to cover every scenario.
        with tempfile.TemporaryDirectory() as directory:
            path = self._write(directory, self._tasks("fermi_estimation", 20))
            _, loaded = load_gathering_manifest(path)
        self.assertEqual(len(loaded), 20)
        self.assertTrue(all(task.scenario == "fermi_estimation" for task in loaded))

    def test_declared_scenario_below_fifteen_tasks_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self._write(directory, self._tasks("fermi_estimation", 14))
            with self.assertRaises(ValueError):
                load_gathering_manifest(path)

    def test_manifest_without_tasks_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self._write(directory, [])
            with self.assertRaises(ValueError):
                load_gathering_manifest(path)


if __name__ == "__main__":
    unittest.main()

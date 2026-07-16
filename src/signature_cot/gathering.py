"""Balanced repeated gathering with deterministic sandboxed coding fixtures."""

from __future__ import annotations

import copy
import dataclasses
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from .models import (
    BoundaryMarkers,
    ExtractionMetrics,
    ExtractionTrial,
    HarvestRun,
    HarvestStep,
    Json,
    ToolCall,
)
from .tools import LocalTool, ToolExecutionError, ToolRegistry


SCENARIOS = (
    "complex_conversational_qa",
    "math_reasoning",
    "agentic_coding",
)
DEFAULT_CODING_FIXTURES = (
    Path(__file__).resolve().parents[1] / "gathering" / "coding-fixtures.json"
)


@dataclass(frozen=True)
class GatheringTask:
    task_id: str
    scenario: str
    source: str
    source_id: str
    turns: Tuple[str, ...]
    expected_answer: Optional[str] = None
    metadata: Json = field(default_factory=dict)


@dataclass(frozen=True)
class CodingFixture:
    task_id: str
    title: str
    prompt: str
    files: Dict[str, str]
    target_path: str
    old: str
    new: str


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def coding_fixture_sha256(fixture: CodingFixture) -> str:
    payload = json.dumps(
        dataclasses.asdict(fixture),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def load_gathering_manifest(path: Path) -> Tuple[Json, List[GatheringTask]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    tasks = [
        GatheringTask(
            task_id=str(row["task_id"]),
            scenario=str(row["scenario"]),
            source=str(row["source"]),
            source_id=str(row["source_id"]),
            turns=tuple(str(turn) for turn in row.get("turns", [])),
            expected_answer=(
                str(row["expected_answer"])
                if row.get("expected_answer") is not None
                else None
            ),
            metadata=row.get("metadata") if isinstance(row.get("metadata"), dict) else {},
        )
        for row in payload.get("tasks", [])
    ]
    counts = {scenario: 0 for scenario in SCENARIOS}
    task_ids = set()
    source_ids = set()
    for task in tasks:
        if task.scenario not in counts:
            raise ValueError("unknown gathering scenario: %s" % task.scenario)
        if task.task_id in task_ids:
            raise ValueError("duplicate gathering task ID: %s" % task.task_id)
        source_key = (task.scenario, task.source_id)
        if source_key in source_ids:
            raise ValueError("duplicate gathering source ID: %s" % task.source_id)
        if not task.turns:
            raise ValueError("gathering task has no turns: %s" % task.task_id)
        counts[task.scenario] += 1
        task_ids.add(task.task_id)
        source_ids.add(source_key)
    if any(counts[scenario] < 15 for scenario in SCENARIOS):
        raise ValueError("gathering manifest must contain at least 15 tasks per scenario")
    declared = payload.get("selection", {}).get("tasks_per_scenario")
    if declared is not None and any(counts[scenario] != int(declared) for scenario in SCENARIOS):
        raise ValueError("manifest task counts do not match selection metadata")
    return payload, tasks


def load_coding_fixtures(
    path: Path = DEFAULT_CODING_FIXTURES,
) -> Dict[str, CodingFixture]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    fixtures: Dict[str, CodingFixture] = {}
    for row in payload.get("fixtures", []):
        fixture = CodingFixture(
            task_id=str(row["task_id"]),
            title=str(row["title"]),
            prompt=str(row["prompt"]),
            files={str(key): str(value) for key, value in row["files"].items()},
            target_path=str(row["target_path"]),
            old=str(row["old"]),
            new=str(row["new"]),
        )
        if fixture.task_id in fixtures:
            raise ValueError("duplicate coding fixture: %s" % fixture.task_id)
        if fixture.target_path not in fixture.files:
            raise ValueError("fixture target path is absent: %s" % fixture.task_id)
        if fixture.files[fixture.target_path].count(fixture.old) != 1:
            raise ValueError("fixture old text must occur exactly once: %s" % fixture.task_id)
        fixtures[fixture.task_id] = fixture
    if len(fixtures) < 15:
        raise ValueError("at least 15 coding fixtures are required")
    return fixtures


class CodingWorkspace:
    """In-memory exact-repair environment; no shell, network, or host filesystem access."""

    def __init__(self, fixture: CodingFixture):
        self.fixture = fixture
        self.files = copy.deepcopy(fixture.files)
        self.expected_files = copy.deepcopy(fixture.files)
        self.expected_files[fixture.target_path] = self.expected_files[
            fixture.target_path
        ].replace(fixture.old, fixture.new, 1)
        self.patch_count = 0
        self.tests_run = 0
        self.last_test_passed = False

    def _path(self, arguments: Json) -> str:
        path = str(arguments.get("path", ""))
        if path not in self.files:
            raise ToolExecutionError("unknown workspace path: %s" % path)
        return path

    def list_files(self, _: Json) -> Json:
        return {"files": sorted(self.files)}

    def read_file(self, arguments: Json) -> Json:
        path = self._path(arguments)
        return {"path": path, "content": self.files[path]}

    def search_code(self, arguments: Json) -> Json:
        query = str(arguments.get("query", ""))
        if not query or len(query) > 100:
            raise ToolExecutionError("query must contain 1 to 100 characters")
        matches: List[Json] = []
        for path in sorted(self.files):
            for line_number, line in enumerate(self.files[path].splitlines(), start=1):
                if query in line:
                    matches.append(
                        {"path": path, "line": line_number, "text": line[:300]}
                    )
                    if len(matches) >= 50:
                        return {"query": query, "matches": matches, "truncated": True}
        return {"query": query, "matches": matches, "truncated": False}

    def apply_patch(self, arguments: Json) -> Json:
        path = self._path(arguments)
        old = str(arguments.get("old", ""))
        new = str(arguments.get("new", ""))
        if not old or len(old) > 2000 or len(new) > 2000:
            raise ToolExecutionError("patch strings must be non-empty and at most 2000 characters")
        if "COT-START-" in new or "COT-END-" in new:
            raise ToolExecutionError("research boundary markers cannot be written to the workspace")
        occurrences = self.files[path].count(old)
        if occurrences != 1:
            raise ToolExecutionError(
                "old text must match exactly once; found %d occurrence(s)" % occurrences
            )
        self.files[path] = self.files[path].replace(old, new, 1)
        self.patch_count += 1
        verifier = self.run_tests({})
        return {
            "applied": True,
            "path": path,
            "patch_count": self.patch_count,
            "verifier": verifier,
        }

    def run_tests(self, _: Json) -> Json:
        self.tests_run += 1
        target_matches = (
            self.files[self.fixture.target_path]
            == self.expected_files[self.fixture.target_path]
        )
        unrelated_unchanged = all(
            self.files[path] == expected
            for path, expected in self.expected_files.items()
            if path != self.fixture.target_path
        )
        self.last_test_passed = bool(target_matches and unrelated_unchanged)
        return {
            "passed": self.last_test_passed,
            "checks": {
                "target_behavior": target_matches,
                "unrelated_files_unchanged": unrelated_unchanged,
            },
            "tests_run": self.tests_run,
        }

    @property
    def task_success(self) -> bool:
        return self.tests_run > 0 and self.last_test_passed

    def registry(self) -> ToolRegistry:
        path_schema: Json = {
            "type": "object",
            "properties": {"path": {"type": "string", "enum": sorted(self.files)}},
            "required": ["path"],
            "additionalProperties": False,
        }
        return ToolRegistry(
            [
                LocalTool(
                    "list_files",
                    "List every path in the isolated in-memory coding workspace.",
                    {"type": "object", "properties": {}, "additionalProperties": False},
                    self.list_files,
                ),
                LocalTool(
                    "read_file",
                    "Read one file from the isolated in-memory coding workspace.",
                    path_schema,
                    self.read_file,
                ),
                LocalTool(
                    "search_code",
                    "Search literal text in all isolated workspace files.",
                    {
                        "type": "object",
                        "properties": {"query": {"type": "string", "maxLength": 100}},
                        "required": ["query"],
                        "additionalProperties": False,
                    },
                    self.search_code,
                ),
                LocalTool(
                    "apply_patch",
                    "Submit one exact replacement. This terminates the task and runs the verifier automatically.",
                    {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "enum": sorted(self.files)},
                            "old": {"type": "string", "maxLength": 2000},
                            "new": {"type": "string", "maxLength": 2000},
                        },
                        "required": ["path", "old", "new"],
                        "additionalProperties": False,
                    },
                    self.apply_patch,
                ),
                LocalTool(
                    "run_tests",
                    "Inspect current deterministic verifier status without terminating the task.",
                    {"type": "object", "properties": {}, "additionalProperties": False},
                    self.run_tests,
                ),
            ]
        )


def atomic_write_json(path: Path, payload: Json) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def checkpoint_run(path: Path, run: HarvestRun) -> None:
    """Write private restart state containing replayable signatures."""

    atomic_write_json(path, {"schema_version": 1, "run": dataclasses.asdict(run)})


def load_checkpoint_run(path: Path) -> HarvestRun:
    payload = json.loads(path.read_text(encoding="utf-8"))
    row = payload["run"]
    steps = [
        HarvestStep(
            step_index=int(step["step_index"]),
            prefix_messages=step["prefix_messages"],
            assistant_content=step["assistant_content"],
            stop_reason=str(step["stop_reason"]),
            usage=step["usage"],
            markers=BoundaryMarkers(**step["markers"]),
            visible_text=str(step["visible_text"]),
            tool_calls=[ToolCall(**call) for call in step["tool_calls"]],
            replay_tool_results=step.get("replay_tool_results", []),
            system=step.get("system", []),
            tool_config=step.get("tool_config"),
            user_message=str(step.get("user_message", "")),
        )
        for step in row["steps"]
    ]
    return HarvestRun(
        task_id=str(row["task_id"]),
        question=str(row["question"]),
        model=str(row["model"]),
        steps=steps,
        final_answer=str(row["final_answer"]),
        expected_answer=row.get("expected_answer"),
        tool_events=row.get("tool_events", []),
        task_success=row.get("task_success"),
        scenario=row.get("scenario"),
        source_metadata=row.get("source_metadata", {}),
    )


def checkpoint_trials(path: Path, trials: Sequence[ExtractionTrial]) -> None:
    atomic_write_json(
        path,
        {
            "schema_version": 1,
            "trials": [dataclasses.asdict(trial) for trial in trials],
        },
    )


def load_checkpoint_trials(path: Path) -> List[ExtractionTrial]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    trials: List[ExtractionTrial] = []
    for row in payload.get("trials", []):
        trials.append(
            ExtractionTrial(
                candidate=str(row["candidate"]),
                step_index=int(row["step_index"]),
                recovered=str(row["recovered"]),
                raw_text=str(row["raw_text"]),
                metrics=ExtractionMetrics(**row["metrics"]),
                usage=row.get("usage", {}),
                stop_reason=str(row.get("stop_reason", "")),
                rounds=int(row.get("rounds", 1)),
                provider_summary_blinded=bool(
                    row.get("provider_summary_blinded", False)
                ),
            )
        )
    return trials

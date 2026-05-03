"""Tests for the GPD Physics Benchmark framework.

Validates schema models, task loading, filtering, runner prompt formatting,
and consistency of all task definition files.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Ensure benchmarks package is importable (it lives at repo root, not under src/)
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from benchmarks.loader import (
    TASKS_DIR,
    discover_task_files,
    load_all_suites,
    load_combined_suite,
    load_suite_by_difficulty,
    load_suite_by_subfield,
    load_suite_by_task_type,
    print_inventory,
)
from benchmarks.runner import BenchmarkRunner, TaskResult, format_task_prompt
from benchmarks.schema import (
    BenchmarkSuite,
    BenchmarkTask,
    Difficulty,
    OutputFormat,
    Reference,
    TaskType,
    load_suite,
    save_suite,
)

# ===== Schema tests =====


class TestReference:
    def test_roundtrip(self):
        ref = Reference(
            arxiv_id="2301.00001",
            title="Test Paper",
            authors=["Alice", "Bob"],
            year=2023,
            section="Section 3",
        )
        d = ref.to_dict()
        ref2 = Reference.from_dict(d)
        assert ref == ref2

    def test_empty_reference(self):
        ref = Reference()
        d = ref.to_dict()
        assert d == {}
        ref2 = Reference.from_dict(d)
        assert ref2 == Reference()


class TestBenchmarkTask:
    def test_roundtrip(self):
        task = BenchmarkTask(
            task_id="test-001",
            title="Test Task",
            description="A test task.",
            subfield="qft",
            task_type=TaskType.DERIVATION,
            difficulty=Difficulty.INTERMEDIATE,
            topics=["testing"],
            problem_statement="Derive the result.",
            given=["A = 1"],
            assumptions=["Ideal system"],
            conventions=["Natural units"],
            expected_answer="42",
            output_format=OutputFormat.SYMBOLIC,
            verification_hints=["Check dimensions"],
            reference=Reference(title="Test Book", year=2020),
        )
        d = task.to_dict()
        task2 = BenchmarkTask.from_dict(d)
        assert task == task2

    def test_minimal_task(self):
        task = BenchmarkTask(
            task_id="min-001",
            title="Minimal",
            description="Minimal task.",
            subfield="qft",
            task_type=TaskType.CALCULATION,
            difficulty=Difficulty.INTRODUCTORY,
        )
        d = task.to_dict()
        task2 = BenchmarkTask.from_dict(d)
        assert task2.task_id == "min-001"
        assert task2.topics == []
        assert task2.given == []

    def test_all_task_types_valid(self):
        for tt in TaskType:
            task = BenchmarkTask(
                task_id=f"tt-{tt.value}",
                title=tt.value,
                description="test",
                subfield="qft",
                task_type=tt,
                difficulty=Difficulty.INTRODUCTORY,
            )
            assert task.task_type == tt

    def test_all_difficulties_valid(self):
        for d in Difficulty:
            task = BenchmarkTask(
                task_id=f"d-{d.value}",
                title=d.value,
                description="test",
                subfield="qft",
                task_type=TaskType.CALCULATION,
                difficulty=d,
            )
            assert task.difficulty == d

    def test_all_output_formats_valid(self):
        for of in OutputFormat:
            task = BenchmarkTask(
                task_id=f"of-{of.value}",
                title=of.value,
                description="test",
                subfield="qft",
                task_type=TaskType.CALCULATION,
                difficulty=Difficulty.INTRODUCTORY,
                output_format=of,
            )
            assert task.output_format == of


class TestBenchmarkSuite:
    def _make_suite(self) -> BenchmarkSuite:
        return BenchmarkSuite(
            name="Test Suite",
            version="1.0.0",
            description="For testing.",
            tasks=[
                BenchmarkTask(
                    task_id="a-001",
                    title="Task A",
                    description="desc",
                    subfield="qft",
                    task_type=TaskType.DERIVATION,
                    difficulty=Difficulty.INTRODUCTORY,
                ),
                BenchmarkTask(
                    task_id="b-001",
                    title="Task B",
                    description="desc",
                    subfield="stat-mech",
                    task_type=TaskType.CALCULATION,
                    difficulty=Difficulty.ADVANCED,
                ),
                BenchmarkTask(
                    task_id="a-002",
                    title="Task C",
                    description="desc",
                    subfield="qft",
                    task_type=TaskType.LIMITING_CASE,
                    difficulty=Difficulty.INTERMEDIATE,
                ),
            ],
        )

    def test_roundtrip(self):
        suite = self._make_suite()
        d = suite.to_dict()
        suite2 = BenchmarkSuite.from_dict(d)
        assert suite2.name == suite.name
        assert len(suite2.tasks) == len(suite.tasks)

    def test_filter_by_subfield(self):
        suite = self._make_suite()
        filtered = suite.filter_by_subfield("qft")
        assert len(filtered.tasks) == 2
        assert all(t.subfield == "qft" for t in filtered.tasks)

    def test_filter_by_difficulty(self):
        suite = self._make_suite()
        filtered = suite.filter_by_difficulty(Difficulty.ADVANCED)
        assert len(filtered.tasks) == 1
        assert filtered.tasks[0].difficulty == Difficulty.ADVANCED

    def test_filter_by_task_type(self):
        suite = self._make_suite()
        filtered = suite.filter_by_task_type(TaskType.DERIVATION)
        assert len(filtered.tasks) == 1
        assert filtered.tasks[0].task_type == TaskType.DERIVATION

    def test_subfields_property(self):
        suite = self._make_suite()
        assert suite.subfields == ["qft", "stat-mech"]

    def test_task_types_property(self):
        suite = self._make_suite()
        types = suite.task_types
        assert TaskType.DERIVATION in types
        assert TaskType.CALCULATION in types

    def test_difficulties_property(self):
        suite = self._make_suite()
        diffs = suite.difficulties
        assert Difficulty.INTRODUCTORY in diffs
        assert Difficulty.ADVANCED in diffs

    def test_empty_suite(self):
        suite = BenchmarkSuite(name="Empty", version="0", description="empty", tasks=[])
        assert suite.subfields == []
        assert suite.task_types == []
        assert suite.difficulties == []


class TestSuiteIO:
    def test_save_and_load(self, tmp_path: Path):
        suite = BenchmarkSuite(
            name="IO Test",
            version="0.1.0",
            description="Test save/load.",
            tasks=[
                BenchmarkTask(
                    task_id="io-001",
                    title="IO Task",
                    description="desc",
                    subfield="qft",
                    task_type=TaskType.CALCULATION,
                    difficulty=Difficulty.INTRODUCTORY,
                    expected_answer="42",
                ),
            ],
        )
        path = tmp_path / "test_suite.json"
        save_suite(suite, path)
        loaded = load_suite(path)
        assert loaded.name == suite.name
        assert len(loaded.tasks) == 1
        assert loaded.tasks[0].expected_answer == "42"


# ===== Task file consistency tests =====


class TestTaskFileConsistency:
    """Validate all task JSON files in the benchmarks/tasks/ directory."""

    def test_task_files_exist(self):
        files = discover_task_files()
        assert len(files) > 0, "No task files found in benchmarks/tasks/"

    def test_all_task_files_parse(self):
        for path in discover_task_files():
            suite = load_suite(path)
            assert suite.name, f"{path.name}: suite must have a name"
            assert suite.version, f"{path.name}: suite must have a version"
            assert len(suite.tasks) > 0, f"{path.name}: suite must have tasks"

    def test_task_ids_unique(self):
        combined = load_combined_suite()
        ids = [t.task_id for t in combined.tasks]
        duplicates = [tid for tid in ids if ids.count(tid) > 1]
        assert not duplicates, f"Duplicate task IDs: {set(duplicates)}"

    def test_all_tasks_have_required_fields(self):
        combined = load_combined_suite()
        for task in combined.tasks:
            assert task.task_id, "task_id must not be empty"
            assert task.title, "title must not be empty"
            assert task.description, "description must not be empty"
            assert task.subfield, "subfield must not be empty"
            assert task.problem_statement, f"{task.task_id}: problem_statement must not be empty"

    def test_all_tasks_have_expected_answer(self):
        combined = load_combined_suite()
        for task in combined.tasks:
            assert task.expected_answer, f"{task.task_id}: expected_answer must not be empty"

    def test_all_tasks_have_verification_hints(self):
        combined = load_combined_suite()
        for task in combined.tasks:
            assert len(task.verification_hints) > 0, f"{task.task_id}: must have at least one verification hint"

    def test_subfields_match_known_set(self):
        """Subfields in tasks should match those in the GPD specs."""
        known_subfields = {
            "qft",
            "gr-cosmology",
            "stat-mech",
            "condensed-matter",
            "classical-mechanics",
            "quantum-info",
            "amo",
            "nuclear-particle",
            "string-theory",
            "quantum-gravity",
            "fluid-plasma",
            "mathematical-physics",
            "algebraic-qft",
            "string-field-theory",
            "soft-matter-biophysics",
            "astrophysics",
        }
        combined = load_combined_suite()
        for task in combined.tasks:
            assert task.subfield in known_subfields, (
                f"{task.task_id}: unknown subfield '{task.subfield}'. "
                f"Known: {sorted(known_subfields)}"
            )

    def test_multiple_subfields_covered(self):
        combined = load_combined_suite()
        subfields = combined.subfields
        assert len(subfields) >= 3, f"Benchmark should cover at least 3 subfields, got {len(subfields)}: {subfields}"

    def test_multiple_difficulties_covered(self):
        combined = load_combined_suite()
        diffs = combined.difficulties
        assert len(diffs) >= 2, f"Benchmark should cover at least 2 difficulty levels, got {len(diffs)}"

    def test_multiple_task_types_covered(self):
        combined = load_combined_suite()
        types = combined.task_types
        assert len(types) >= 3, f"Benchmark should cover at least 3 task types, got {len(types)}"

    def test_json_files_are_valid_json(self):
        for path in discover_task_files():
            text = path.read_text(encoding="utf-8")
            try:
                json.loads(text)
            except json.JSONDecodeError as exc:
                pytest.fail(f"{path.name}: invalid JSON: {exc}")


# ===== Loader tests =====


class TestLoader:
    def test_load_all_suites(self):
        suites = load_all_suites()
        assert len(suites) > 0

    def test_load_combined_suite(self):
        combined = load_combined_suite()
        assert len(combined.tasks) >= 20, f"Expected at least 20 tasks, got {len(combined.tasks)}"

    def test_load_suite_by_subfield(self):
        suite = load_suite_by_subfield("qft")
        assert len(suite.tasks) > 0
        assert all(t.subfield == "qft" for t in suite.tasks)

    def test_load_suite_by_difficulty(self):
        suite = load_suite_by_difficulty("introductory")
        assert len(suite.tasks) > 0
        assert all(t.difficulty == Difficulty.INTRODUCTORY for t in suite.tasks)

    def test_load_suite_by_task_type(self):
        suite = load_suite_by_task_type("derivation")
        assert len(suite.tasks) > 0
        assert all(t.task_type == TaskType.DERIVATION for t in suite.tasks)

    def test_print_inventory(self):
        inv = print_inventory()
        assert "Total tasks:" in inv
        assert "By subfield:" in inv
        assert "By difficulty:" in inv
        assert "By task type:" in inv


# ===== Runner tests =====


class TestPromptFormatting:
    def test_format_task_prompt_includes_essentials(self):
        task = BenchmarkTask(
            task_id="fmt-001",
            title="Format Test",
            description="Testing format.",
            subfield="qft",
            task_type=TaskType.DERIVATION,
            difficulty=Difficulty.INTERMEDIATE,
            problem_statement="Derive X from Y.",
            given=["Y = 1"],
            assumptions=["Ideal"],
            conventions=["Natural units"],
            expected_answer="X = 2",
            output_format=OutputFormat.LATEX,
            verification_hints=["Check dims"],
        )
        prompt = format_task_prompt(task)
        assert "# Format Test" in prompt
        assert "Testing format." in prompt
        assert "Derive X from Y." in prompt
        assert "Y = 1" in prompt
        assert "Ideal" in prompt
        assert "Natural units" in prompt
        assert "latex" in prompt.lower()
        # Expected answer and verification hints should NOT be in the prompt
        assert "X = 2" not in prompt
        assert "Check dims" not in prompt

    def test_prompt_excludes_answer(self):
        task = BenchmarkTask(
            task_id="sec-001",
            title="Secret Test",
            description="desc",
            subfield="qft",
            task_type=TaskType.CALCULATION,
            difficulty=Difficulty.INTRODUCTORY,
            expected_answer="SECRET_ANSWER_42",
            verification_hints=["SECRET_HINT"],
        )
        prompt = format_task_prompt(task)
        assert "SECRET_ANSWER_42" not in prompt
        assert "SECRET_HINT" not in prompt


class TestRunner:
    def test_run_task_success(self):
        def mock_model(prompt: str) -> str:
            return "The answer is 42."

        runner = BenchmarkRunner(model_fn=mock_model)
        task = BenchmarkTask(
            task_id="run-001",
            title="Runner Test",
            description="desc",
            subfield="qft",
            task_type=TaskType.CALCULATION,
            difficulty=Difficulty.INTRODUCTORY,
            expected_answer="42",
        )
        result = runner.run_task(task)
        assert result.task_id == "run-001"
        assert result.response == "The answer is 42."
        assert result.error == ""
        assert result.elapsed_seconds >= 0

    def test_run_task_error(self):
        def failing_model(prompt: str) -> str:
            raise RuntimeError("Model failed")

        runner = BenchmarkRunner(model_fn=failing_model)
        task = BenchmarkTask(
            task_id="err-001",
            title="Error Test",
            description="desc",
            subfield="qft",
            task_type=TaskType.CALCULATION,
            difficulty=Difficulty.INTRODUCTORY,
        )
        result = runner.run_task(task)
        assert result.error == "RuntimeError: Model failed"
        assert result.response == ""

    def test_run_suite(self):
        call_count = 0

        def counting_model(prompt: str) -> str:
            nonlocal call_count
            call_count += 1
            return f"Response {call_count}"

        suite = BenchmarkSuite(
            name="Test",
            version="0",
            description="test",
            tasks=[
                BenchmarkTask(
                    task_id=f"s-{i}",
                    title=f"Task {i}",
                    description="desc",
                    subfield="qft",
                    task_type=TaskType.CALCULATION,
                    difficulty=Difficulty.INTRODUCTORY,
                )
                for i in range(3)
            ],
        )
        runner = BenchmarkRunner(model_fn=counting_model)
        results = runner.run_suite(suite)
        assert len(results) == 3
        assert call_count == 3

    def test_format_report(self):
        results = [
            TaskResult(
                task_id="r-001",
                task_title="Task 1",
                subfield="qft",
                difficulty="introductory",
                task_type="calculation",
                prompt="...",
                response="answer",
                elapsed_seconds=1.5,
            ),
            TaskResult(
                task_id="r-002",
                task_title="Task 2",
                subfield="stat-mech",
                difficulty="advanced",
                task_type="derivation",
                prompt="...",
                response="answer",
                elapsed_seconds=2.3,
                error="RuntimeError: oops",
            ),
        ]
        report = BenchmarkRunner.format_report(results)
        assert "Tasks run: 2" in report
        assert "Errors: 1" in report
        assert "[OK] r-001" in report
        assert "[ERROR] r-002" in report
        assert "RuntimeError: oops" in report

    def test_result_to_dict(self):
        result = TaskResult(
            task_id="d-001",
            task_title="Dict Test",
            subfield="qft",
            difficulty="introductory",
            task_type="calculation",
            prompt="prompt",
            response="response",
            elapsed_seconds=0.5,
        )
        d = result.to_dict()
        assert d["task_id"] == "d-001"
        assert d["response"] == "response"
        assert d["error"] == ""

"""Simple benchmark runner for physics AI evaluation.

Provides a framework for running benchmark tasks against an AI model
and collecting structured results. The runner is model-agnostic: it
formats prompts and collects responses, leaving the actual model
invocation to a caller-provided function.

Usage::

    from benchmarks.runner import BenchmarkRunner, TaskResult

    def my_model(prompt: str) -> str:
        # Call your model here
        return response

    runner = BenchmarkRunner(model_fn=my_model)
    results = runner.run_suite(suite)
    report = runner.format_report(results)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Protocol

from benchmarks.schema import BenchmarkSuite, BenchmarkTask


class ModelFn(Protocol):
    """Protocol for a model function that takes a prompt and returns a response."""

    def __call__(self, prompt: str) -> str: ...


@dataclass
class TaskResult:
    """Result of running a single benchmark task."""

    task_id: str
    task_title: str
    subfield: str
    difficulty: str
    task_type: str
    prompt: str
    response: str
    elapsed_seconds: float
    error: str = ""

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "task_title": self.task_title,
            "subfield": self.subfield,
            "difficulty": self.difficulty,
            "task_type": self.task_type,
            "prompt": self.prompt,
            "response": self.response,
            "elapsed_seconds": self.elapsed_seconds,
            "error": self.error,
        }


def format_task_prompt(task: BenchmarkTask) -> str:
    """Format a benchmark task as a prompt string for a model.

    The prompt includes all information the model needs to attempt
    the problem: statement, given information, assumptions, and
    conventions. It does NOT include the expected answer or
    verification hints.
    """
    parts: list[str] = []

    parts.append(f"# {task.title}")
    parts.append("")
    parts.append(task.description)
    parts.append("")

    if task.problem_statement:
        parts.append("## Problem")
        parts.append(task.problem_statement)
        parts.append("")

    if task.given:
        parts.append("## Given")
        for item in task.given:
            parts.append(f"- {item}")
        parts.append("")

    if task.assumptions:
        parts.append("## Assumptions")
        for item in task.assumptions:
            parts.append(f"- {item}")
        parts.append("")

    if task.conventions:
        parts.append("## Conventions")
        for item in task.conventions:
            parts.append(f"- {item}")
        parts.append("")

    parts.append(f"## Expected output format: {task.output_format.value}")
    parts.append("")
    parts.append("Please solve this problem step by step, showing your work clearly.")

    return "\n".join(parts)


class BenchmarkRunner:
    """Run benchmark tasks against a model function and collect results."""

    def __init__(self, model_fn: ModelFn) -> None:
        self._model_fn = model_fn

    def run_task(self, task: BenchmarkTask) -> TaskResult:
        """Run a single benchmark task and return the result."""
        prompt = format_task_prompt(task)
        error = ""
        response = ""
        start = time.monotonic()
        try:
            response = self._model_fn(prompt)
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
        elapsed = time.monotonic() - start

        return TaskResult(
            task_id=task.task_id,
            task_title=task.title,
            subfield=task.subfield,
            difficulty=task.difficulty.value,
            task_type=task.task_type.value,
            prompt=prompt,
            response=response,
            elapsed_seconds=round(elapsed, 3),
            error=error,
        )

    def run_suite(self, suite: BenchmarkSuite) -> list[TaskResult]:
        """Run all tasks in a suite and return results."""
        results: list[TaskResult] = []
        for task in suite.tasks:
            results.append(self.run_task(task))
        return results

    @staticmethod
    def format_report(results: list[TaskResult]) -> str:
        """Format results into a human-readable report."""
        lines: list[str] = []
        lines.append("# GPD Physics Benchmark Report")
        lines.append("")
        lines.append(f"Tasks run: {len(results)}")
        errors = [r for r in results if r.error]
        lines.append(f"Errors: {len(errors)}")
        if results:
            total_time = sum(r.elapsed_seconds for r in results)
            lines.append(f"Total time: {total_time:.1f}s")
        lines.append("")

        # Group by subfield
        subfields: dict[str, list[TaskResult]] = {}
        for r in results:
            subfields.setdefault(r.subfield, []).append(r)

        for sf in sorted(subfields):
            sf_results = subfields[sf]
            lines.append(f"## {sf}")
            for r in sf_results:
                status = "ERROR" if r.error else "OK"
                lines.append(f"  [{status}] {r.task_id}: {r.task_title} ({r.elapsed_seconds:.1f}s)")
                if r.error:
                    lines.append(f"         Error: {r.error}")
            lines.append("")

        return "\n".join(lines)

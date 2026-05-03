"""Benchmark task schema for physics AI evaluation.

Defines the data model for benchmark tasks: structured problems derived
from physics papers that test derivation, calculation, dimensional analysis,
limiting-case verification, and numerical estimation capabilities.
"""

from __future__ import annotations

import enum
import json
from dataclasses import dataclass, field
from pathlib import Path


class Difficulty(str, enum.Enum):
    """Task difficulty level.

    INTRODUCTORY: Undergraduate-level, straightforward application of known results.
    INTERMEDIATE: Advanced undergraduate / early graduate, requires combining concepts.
    ADVANCED: Graduate-level, requires deep understanding and multi-step reasoning.
    RESEARCH: Research-level, drawn directly from recent papers.
    """

    INTRODUCTORY = "introductory"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    RESEARCH = "research"


class TaskType(str, enum.Enum):
    """Classification of what the task tests.

    DERIVATION: Derive a result from first principles or stated assumptions.
    CALCULATION: Compute a specific numerical or symbolic answer.
    DIMENSIONAL_ANALYSIS: Verify or determine dimensions/units of quantities.
    LIMITING_CASE: Verify behavior in a known limiting regime.
    ESTIMATION: Order-of-magnitude estimate or Fermi problem.
    CONCEPTUAL: Explain a physical concept or resolve an apparent paradox.
    """

    DERIVATION = "derivation"
    CALCULATION = "calculation"
    DIMENSIONAL_ANALYSIS = "dimensional_analysis"
    LIMITING_CASE = "limiting_case"
    ESTIMATION = "estimation"
    CONCEPTUAL = "conceptual"


class OutputFormat(str, enum.Enum):
    """Expected format of the answer.

    LATEX: A LaTeX expression (symbolic result).
    NUMERIC: A numerical value with units.
    SYMBOLIC: A symbolic expression (may not need full LaTeX).
    TEXT: Free-form text explanation.
    BOOLEAN: True/false with justification.
    """

    LATEX = "latex"
    NUMERIC = "numeric"
    SYMBOLIC = "symbolic"
    TEXT = "text"
    BOOLEAN = "boolean"


@dataclass(frozen=True)
class Reference:
    """Citation for the source paper or textbook."""

    arxiv_id: str | None = None
    doi: str | None = None
    title: str = ""
    authors: list[str] = field(default_factory=list)
    year: int | None = None
    section: str = ""
    equation: str = ""

    def to_dict(self) -> dict:
        d: dict = {}
        if self.arxiv_id:
            d["arxiv_id"] = self.arxiv_id
        if self.doi:
            d["doi"] = self.doi
        if self.title:
            d["title"] = self.title
        if self.authors:
            d["authors"] = list(self.authors)
        if self.year:
            d["year"] = self.year
        if self.section:
            d["section"] = self.section
        if self.equation:
            d["equation"] = self.equation
        return d

    @classmethod
    def from_dict(cls, d: dict) -> Reference:
        return cls(
            arxiv_id=d.get("arxiv_id"),
            doi=d.get("doi"),
            title=d.get("title", ""),
            authors=d.get("authors", []),
            year=d.get("year"),
            section=d.get("section", ""),
            equation=d.get("equation", ""),
        )


@dataclass(frozen=True)
class BenchmarkTask:
    """A single benchmark task for physics AI evaluation.

    Each task is a self-contained problem with clearly defined inputs,
    expected outputs, and grading criteria. Tasks are derived from
    physics papers and textbooks to ensure they test genuine physics
    understanding rather than pattern matching.
    """

    # Identity
    task_id: str
    title: str
    description: str

    # Classification
    subfield: str
    task_type: TaskType
    difficulty: Difficulty
    topics: list[str] = field(default_factory=list)

    # Problem specification
    problem_statement: str = ""
    given: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    conventions: list[str] = field(default_factory=list)

    # Expected answer
    expected_answer: str = ""
    output_format: OutputFormat = OutputFormat.LATEX
    answer_tolerance: str = ""
    verification_hints: list[str] = field(default_factory=list)

    # Provenance
    reference: Reference = field(default_factory=Reference)

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "title": self.title,
            "description": self.description,
            "subfield": self.subfield,
            "task_type": self.task_type.value,
            "difficulty": self.difficulty.value,
            "topics": list(self.topics),
            "problem_statement": self.problem_statement,
            "given": list(self.given),
            "assumptions": list(self.assumptions),
            "conventions": list(self.conventions),
            "expected_answer": self.expected_answer,
            "output_format": self.output_format.value,
            "answer_tolerance": self.answer_tolerance,
            "verification_hints": list(self.verification_hints),
            "reference": self.reference.to_dict(),
        }

    @classmethod
    def from_dict(cls, d: dict) -> BenchmarkTask:
        return cls(
            task_id=d["task_id"],
            title=d["title"],
            description=d["description"],
            subfield=d["subfield"],
            task_type=TaskType(d["task_type"]),
            difficulty=Difficulty(d["difficulty"]),
            topics=d.get("topics", []),
            problem_statement=d.get("problem_statement", ""),
            given=d.get("given", []),
            assumptions=d.get("assumptions", []),
            conventions=d.get("conventions", []),
            expected_answer=d.get("expected_answer", ""),
            output_format=OutputFormat(d.get("output_format", "latex")),
            answer_tolerance=d.get("answer_tolerance", ""),
            verification_hints=d.get("verification_hints", []),
            reference=Reference.from_dict(d.get("reference", {})),
        )


@dataclass(frozen=True)
class BenchmarkSuite:
    """A collection of benchmark tasks, optionally filtered by subfield or type."""

    name: str
    version: str
    description: str
    tasks: list[BenchmarkTask] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "tasks": [t.to_dict() for t in self.tasks],
        }

    @classmethod
    def from_dict(cls, d: dict) -> BenchmarkSuite:
        return cls(
            name=d["name"],
            version=d["version"],
            description=d["description"],
            tasks=[BenchmarkTask.from_dict(t) for t in d.get("tasks", [])],
        )

    def filter_by_subfield(self, subfield: str) -> BenchmarkSuite:
        """Return a new suite containing only tasks from the given subfield."""
        return BenchmarkSuite(
            name=f"{self.name} [{subfield}]",
            version=self.version,
            description=self.description,
            tasks=[t for t in self.tasks if t.subfield == subfield],
        )

    def filter_by_difficulty(self, difficulty: Difficulty) -> BenchmarkSuite:
        """Return a new suite containing only tasks at the given difficulty."""
        return BenchmarkSuite(
            name=f"{self.name} [{difficulty.value}]",
            version=self.version,
            description=self.description,
            tasks=[t for t in self.tasks if t.difficulty == difficulty],
        )

    def filter_by_task_type(self, task_type: TaskType) -> BenchmarkSuite:
        """Return a new suite containing only tasks of the given type."""
        return BenchmarkSuite(
            name=f"{self.name} [{task_type.value}]",
            version=self.version,
            description=self.description,
            tasks=[t for t in self.tasks if t.task_type == task_type],
        )

    @property
    def subfields(self) -> list[str]:
        """Return sorted list of unique subfields in this suite."""
        return sorted({t.subfield for t in self.tasks})

    @property
    def task_types(self) -> list[TaskType]:
        """Return sorted list of unique task types in this suite."""
        return sorted({t.task_type for t in self.tasks}, key=lambda x: x.value)

    @property
    def difficulties(self) -> list[Difficulty]:
        """Return sorted list of unique difficulties in this suite."""
        order = [Difficulty.INTRODUCTORY, Difficulty.INTERMEDIATE, Difficulty.ADVANCED, Difficulty.RESEARCH]
        present = {t.difficulty for t in self.tasks}
        return [d for d in order if d in present]


def load_suite(path: Path) -> BenchmarkSuite:
    """Load a benchmark suite from a JSON file."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return BenchmarkSuite.from_dict(data)


def save_suite(suite: BenchmarkSuite, path: Path) -> None:
    """Save a benchmark suite to a JSON file."""
    path.write_text(json.dumps(suite.to_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

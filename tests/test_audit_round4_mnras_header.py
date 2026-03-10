"""Regression tests for MNRAS template empty \\author[] running header bug.

The MNRAS class uses the optional argument to \\author to set the running
header.  An empty ``\\author[]{}`` produces a blank author running head.
The fix populates the optional argument with a comma-separated list of
author names using Jinja2 template logic.
"""

from __future__ import annotations

import re

import pytest

from gpd.mcp.paper.models import Author, PaperConfig, Section
from gpd.mcp.paper.template_registry import render_paper


class TestMNRASAuthorRunningHeader:
    """\\author[...] running header should contain author names, not be empty."""

    def test_single_author_running_header(self) -> None:
        """With one author, the running header should contain that author's name."""
        config = PaperConfig(
            title="Test Paper",
            authors=[Author(name="Alice Smith", affiliation="MIT")],
            abstract="Test abstract.",
            sections=[Section(title="Introduction", content="Hello.")],
            journal="mnras",
        )
        tex = render_paper(config)
        # Extract the optional argument of \author[...]
        match = re.search(r"\\author\[([^\]]*)\]", tex)
        assert match is not None, "\\author[...] not found in rendered template"
        running_header = match.group(1)
        assert "Alice Smith" in running_header

    def test_multiple_authors_running_header(self) -> None:
        """With multiple authors, the running header should list all names comma-separated."""
        config = PaperConfig(
            title="Test Paper",
            authors=[
                Author(name="Alice Smith", affiliation="MIT"),
                Author(name="Bob Jones", affiliation="Stanford"),
                Author(name="Carol White", affiliation="Caltech"),
            ],
            abstract="Test abstract.",
            sections=[Section(title="Introduction", content="Hello.")],
            journal="mnras",
        )
        tex = render_paper(config)
        match = re.search(r"\\author\[([^\]]*)\]", tex)
        assert match is not None, "\\author[...] not found in rendered template"
        running_header = match.group(1)
        assert "Alice Smith" in running_header
        assert "Bob Jones" in running_header
        assert "Carol White" in running_header
        # Verify comma separation
        assert "Alice Smith, Bob Jones, Carol White" in running_header

    def test_running_header_not_empty_with_authors(self) -> None:
        """The running header must NOT be empty when authors are provided."""
        config = PaperConfig(
            title="Test Paper",
            authors=[Author(name="John Doe", affiliation="Oxford")],
            abstract="Abstract.",
            sections=[Section(title="Intro", content="Content.")],
            journal="mnras",
        )
        tex = render_paper(config)
        match = re.search(r"\\author\[([^\]]*)\]", tex)
        assert match is not None
        running_header = match.group(1).strip()
        assert running_header != "", "Running header should not be empty when authors exist"

    def test_empty_authors_no_crash(self) -> None:
        """With no authors, the template should render without crashing."""
        config = PaperConfig(
            title="Test Paper",
            authors=[],
            abstract="Abstract.",
            sections=[Section(title="Intro", content="Content.")],
            journal="mnras",
        )
        tex = render_paper(config)
        # Should still produce a valid \author command
        assert "\\author" in tex
        # The running header should be empty (no authors), but that's acceptable
        match = re.search(r"\\author\[([^\]]*)\]", tex)
        assert match is not None
        running_header = match.group(1).strip()
        assert running_header == "", "Running header should be empty when no authors exist"

    def test_author_without_affiliation_in_running_header(self) -> None:
        """Authors without affiliations should still appear in the running header."""
        config = PaperConfig(
            title="Test Paper",
            authors=[
                Author(name="Alice Smith"),
                Author(name="Bob Jones", affiliation="Stanford"),
            ],
            abstract="Abstract.",
            sections=[Section(title="Intro", content="Content.")],
            journal="mnras",
        )
        tex = render_paper(config)
        match = re.search(r"\\author\[([^\]]*)\]", tex)
        assert match is not None
        running_header = match.group(1)
        # Both authors should appear regardless of affiliation
        assert "Alice Smith" in running_header
        assert "Bob Jones" in running_header

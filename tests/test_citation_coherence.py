"""Tests for citation-bibliography coherence check (BUG-076)."""

from __future__ import annotations

from gpd.mcp.paper.compiler import check_citation_bib_coherence


class TestCitationBibCoherence:
    """Unit tests for the coherence check function."""

    def test_zero_citations_with_bib_entries_warns(self) -> None:
        tex = r"\documentclass{article}\begin{document}Hello.\bibliography{refs}\end{document}"
        bib = "@article{einstein1905,\n  title={Relativity},\n  author={Einstein, A.},\n  year={1905}\n}\n"
        result = check_citation_bib_coherence(tex, bib)
        assert len(result.warnings) == 1
        assert "zero" in result.warnings[0].lower()
        assert result.unreferenced_bib_keys == {"einstein1905"}
        assert result.tex_cite_keys == set()

    def test_all_cited_no_warnings(self) -> None:
        tex = r"As shown in \cite{einstein1905}, relativity is fundamental."
        bib = "@article{einstein1905,\n  title={Relativity},\n  author={Einstein, A.},\n  year={1905}\n}\n"
        result = check_citation_bib_coherence(tex, bib)
        assert result.warnings == []
        assert result.unreferenced_bib_keys == set()
        assert result.unresolved_cite_keys == set()

    def test_partial_citation_warns_unreferenced(self) -> None:
        tex = r"\cite{einstein1905}"
        bib = (
            "@article{einstein1905,\n  title={Relativity},\n  author={Einstein, A.},\n  year={1905}\n}\n"
            "@article{dirac1928,\n  title={Quantum},\n  author={Dirac, P.},\n  year={1928}\n}\n"
        )
        result = check_citation_bib_coherence(tex, bib)
        assert "dirac1928" in result.unreferenced_bib_keys
        assert "einstein1905" not in result.unreferenced_bib_keys
        assert len(result.warnings) == 1
        assert "1 bibliography" in result.warnings[0]

    def test_unresolved_citation_warns(self) -> None:
        tex = r"\cite{nonexistent2026}"
        bib = "@article{einstein1905,\n  title={Relativity},\n  author={Einstein, A.},\n  year={1905}\n}\n"
        result = check_citation_bib_coherence(tex, bib)
        assert "nonexistent2026" in result.unresolved_cite_keys
        assert len(result.warnings) == 2  # unreferenced + unresolved

    def test_natbib_citep_detected(self) -> None:
        tex = r"\citep{a2020} and \citet{b2021}"
        bib = (
            "@article{a2020,\n  title={A},\n  author={Doe},\n  year={2020}\n}\n"
            "@article{b2021,\n  title={B},\n  author={Doe},\n  year={2021}\n}\n"
        )
        result = check_citation_bib_coherence(tex, bib)
        assert result.tex_cite_keys == {"a2020", "b2021"}
        assert result.warnings == []

    def test_natbib_citealt_citealp_detected(self) -> None:
        tex = r"\citealt{x} and \citealp{y}"
        bib = (
            "@article{x,\n  title={X},\n  author={Doe},\n  year={2020}\n}\n"
            "@article{y,\n  title={Y},\n  author={Doe},\n  year={2020}\n}\n"
        )
        result = check_citation_bib_coherence(tex, bib)
        assert result.tex_cite_keys == {"x", "y"}
        assert result.warnings == []

    def test_capitalized_natbib_detected(self) -> None:
        tex = r"\Citep{a2020} at the start of a sentence."
        bib = "@article{a2020,\n  title={A},\n  author={Doe},\n  year={2020}\n}\n"
        result = check_citation_bib_coherence(tex, bib)
        assert result.tex_cite_keys == {"a2020"}
        assert result.warnings == []

    def test_citeauthor_citeyear_detected(self) -> None:
        tex = r"\citeauthor{a2020} (\citeyear{a2020})"
        bib = "@article{a2020,\n  title={A},\n  author={Doe},\n  year={2020}\n}\n"
        result = check_citation_bib_coherence(tex, bib)
        assert "a2020" in result.tex_cite_keys
        assert result.warnings == []

    def test_optional_arguments_handled(self) -> None:
        tex = r"\citep[see][p.~42]{key2020}"
        bib = "@article{key2020,\n  title={K},\n  author={Doe},\n  year={2020}\n}\n"
        result = check_citation_bib_coherence(tex, bib)
        assert result.tex_cite_keys == {"key2020"}
        assert result.warnings == []

    def test_multi_key_citation_split(self) -> None:
        tex = r"\cite{a2020,b2021,c2022}"
        bib = (
            "@article{a2020,\n  title={A},\n  author={Doe},\n  year={2020}\n}\n"
            "@article{b2021,\n  title={B},\n  author={Doe},\n  year={2021}\n}\n"
            "@article{c2022,\n  title={C},\n  author={Doe},\n  year={2022}\n}\n"
        )
        result = check_citation_bib_coherence(tex, bib)
        assert result.tex_cite_keys == {"a2020", "b2021", "c2022"}
        assert result.warnings == []

    def test_empty_bib_no_warning(self) -> None:
        tex = r"\documentclass{article}\begin{document}Hello.\end{document}"
        bib = ""
        result = check_citation_bib_coherence(tex, bib)
        assert result.warnings == []
        assert result.bib_entry_keys == set()

    def test_nocite_star_suppresses_unreferenced_warning(self) -> None:
        tex = r"\nocite{*}"
        bib = (
            "@article{a,\n  title={A},\n  author={Doe},\n  year={2020}\n}\n"
            "@article{b,\n  title={B},\n  author={Doe},\n  year={2020}\n}\n"
        )
        result = check_citation_bib_coherence(tex, bib)
        assert result.unreferenced_bib_keys == set()
        assert result.warnings == []

    def test_nocite_star_with_no_cite_commands_no_warning(self) -> None:
        """nocite{*} means all entries referenced; no zero-citation warning."""
        tex = r"\documentclass{article}\begin{document}\nocite{*}\end{document}"
        bib = "@article{x,\n  title={X},\n  author={Doe},\n  year={2020}\n}\n"
        result = check_citation_bib_coherence(tex, bib)
        assert result.warnings == []
        assert result.unreferenced_bib_keys == set()

    def test_nocite_specific_key_counted_as_citation(self) -> None:
        tex = r"\nocite{hidden_ref}"
        bib = (
            "@article{hidden_ref,\n  title={H},\n  author={Doe},\n  year={2020}\n}\n"
            "@article{other,\n  title={O},\n  author={Doe},\n  year={2020}\n}\n"
        )
        result = check_citation_bib_coherence(tex, bib)
        assert "hidden_ref" in result.tex_cite_keys
        assert "other" in result.unreferenced_bib_keys

    def test_biblatex_commands_detected(self) -> None:
        tex = r"\parencite{a} and \textcite{b} and \autocite{c}"
        bib = (
            "@article{a,\n  title={A},\n  author={Doe},\n  year={2020}\n}\n"
            "@article{b,\n  title={B},\n  author={Doe},\n  year={2020}\n}\n"
            "@article{c,\n  title={C},\n  author={Doe},\n  year={2020}\n}\n"
        )
        result = check_citation_bib_coherence(tex, bib)
        assert result.tex_cite_keys == {"a", "b", "c"}
        assert result.warnings == []

    def test_citetext_ignored_inner_citealp_extracted(self) -> None:
        r"""\\citetext is excluded from the regex (BUG-076 fix).

        \\citetext wraps free-form text that may contain nested citation
        commands like \\citealp.  Because the non-brace-aware regex
        ``\{([^}]*)\}`` truncates at the first inner ``}``, including
        \\citetext produces garbage keys.  Instead, \\citetext is ignored
        and the inner \\citealp commands are matched individually.
        """
        tex = r"\citetext{see \citealp{a}; compare \citealp{b}}"
        bib = (
            "@article{a,\n  title={A},\n  author={Doe},\n  year={2020}\n}\n"
            "@article{b,\n  title={B},\n  author={Doe},\n  year={2020}\n}\n"
        )
        result = check_citation_bib_coherence(tex, bib)
        # Both inner \citealp commands are now detected correctly
        assert "a" in result.tex_cite_keys
        assert "b" in result.tex_cite_keys
        assert result.warnings == []

    def test_starred_natbib_variants_detected(self) -> None:
        """Starred variants like \\cite*{} and \\citep*{} should be matched."""
        tex = r"\cite*{a2020} and \citep*{b2021}"
        bib = (
            "@article{a2020,\n  title={A},\n  author={Doe},\n  year={2020}\n}\n"
            "@article{b2021,\n  title={B},\n  author={Doe},\n  year={2021}\n}\n"
        )
        result = check_citation_bib_coherence(tex, bib)
        assert result.tex_cite_keys == {"a2020", "b2021"}
        assert result.warnings == []

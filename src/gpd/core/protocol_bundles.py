"""Metadata-driven protocol bundle registry for specialized guidance.

Protocol bundles let the product stay generic while specialized guidance lives
in data. A bundle can point to existing protocol, subfield, project-type, and
verification assets plus planning / execution / verification hints.
"""

from __future__ import annotations

import re
import textwrap
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from gpd.contracts import ResearchContract
from gpd.core.frontmatter import extract_frontmatter
from gpd.specs import SPECS_DIR

__all__ = [
    "BUNDLES_DIR",
    "BundleAsset",
    "BundleAssets",
    "BundleTrigger",
    "BundleVerifierExtension",
    "ProtocolBundle",
    "ResolvedProtocolBundle",
    "ProjectBundleSignals",
    "get_protocol_bundle",
    "invalidate_protocol_bundle_cache",
    "list_protocol_bundles",
    "render_protocol_bundle_context",
    "select_protocol_bundles",
]


BUNDLES_DIR = SPECS_DIR / "bundles"

_HEADING_RE = re.compile(r"^\s{0,3}(#{2,4})\s+(.+)$", re.MULTILINE)
_TOKEN_RE = re.compile(r"[a-z0-9]+")


class BundleAsset(BaseModel):
    """One file or document surfaced by a protocol bundle."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    path: str
    required: bool = False
    note: str | None = None


class BundleAssets(BaseModel):
    """Role-keyed asset sets referenced by a bundle."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    project_types: list[BundleAsset] = Field(default_factory=list)
    subfield_guides: list[BundleAsset] = Field(default_factory=list)
    verification_domains: list[BundleAsset] = Field(default_factory=list)
    protocols_core: list[BundleAsset] = Field(default_factory=list)
    protocols_optional: list[BundleAsset] = Field(default_factory=list)
    execution_guides: list[BundleAsset] = Field(default_factory=list)

    def iter_assets(self) -> list[tuple[str, BundleAsset]]:
        """Return all assets with their role names in stable order."""
        items: list[tuple[str, BundleAsset]] = []
        for role in (
            "project_types",
            "subfield_guides",
            "verification_domains",
            "protocols_core",
            "protocols_optional",
            "execution_guides",
        ):
            for asset in getattr(self, role):
                items.append((role, asset))
        return items


class BundleTrigger(BaseModel):
    """Metadata rules used to select a bundle from project signals."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    any_terms: list[str] = Field(default_factory=list)
    all_terms: list[str] = Field(default_factory=list)
    any_tags: list[str] = Field(default_factory=list)
    all_tags: list[str] = Field(default_factory=list)
    exclusive_with: list[str] = Field(default_factory=list)
    min_term_matches: int = 0
    min_tag_matches: int = 0
    min_score: int = 1


class BundleVerifierExtension(BaseModel):
    """One bundle-provided verification checklist item."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    name: str
    rationale: str
    check_ids: list[str] = Field(default_factory=list)


class ProtocolBundle(BaseModel):
    """Canonical bundle definition parsed from markdown frontmatter."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    bundle_id: str
    bundle_version: int = 1
    title: str
    summary: str
    selection_tags: list[str] = Field(default_factory=list)
    trigger: BundleTrigger = Field(default_factory=BundleTrigger)
    assets: BundleAssets = Field(default_factory=BundleAssets)
    anchor_prompts: list[str] = Field(default_factory=list)
    reference_prompts: list[str] = Field(default_factory=list)
    estimator_policies: list[str] = Field(default_factory=list)
    decisive_artifact_guidance: list[str] = Field(default_factory=list)
    verifier_extensions: list[BundleVerifierExtension] = Field(default_factory=list)


class ProjectBundleSignals(BaseModel):
    """Normalized signals extracted from project metadata."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    text: str
    tags: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)


class ResolvedProtocolBundle(BaseModel):
    """A selected bundle plus the signals that triggered it."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    bundle_id: str
    title: str
    summary: str
    score: int
    matched_tags: list[str] = Field(default_factory=list)
    matched_terms: list[str] = Field(default_factory=list)
    selection_tags: list[str] = Field(default_factory=list)
    assets: BundleAssets = Field(default_factory=BundleAssets)
    anchor_prompts: list[str] = Field(default_factory=list)
    reference_prompts: list[str] = Field(default_factory=list)
    estimator_policies: list[str] = Field(default_factory=list)
    decisive_artifact_guidance: list[str] = Field(default_factory=list)
    verifier_extensions: list[BundleVerifierExtension] = Field(default_factory=list)

    @property
    def asset_paths(self) -> list[str]:
        """Return all unique asset paths in stable order."""
        seen: set[str] = set()
        ordered: list[str] = []
        for _role, asset in self.assets.iter_assets():
            if asset.path in seen:
                continue
            seen.add(asset.path)
            ordered.append(asset.path)
        return ordered


def invalidate_protocol_bundle_cache() -> None:
    """Clear the cached bundle registry."""
    _load_protocol_bundles.cache_clear()


def _normalize_text(text: str) -> str:
    return " ".join(_TOKEN_RE.findall(text.lower()))


def _slugify(text: str) -> str:
    tokens = _TOKEN_RE.findall(text.lower())
    return "-".join(tokens)


def _contains_term(normalized_text: str, term: str) -> bool:
    normalized_term = _normalize_text(term)
    if not normalized_term:
        return False
    padded_text = f" {normalized_text} "
    padded_term = f" {normalized_term} "
    return padded_term in padded_text


def _extract_sections(markdown: str) -> dict[str, str]:
    """Extract markdown heading bodies keyed by normalized heading text."""
    sections: dict[str, str] = {}
    matches = list(_HEADING_RE.finditer(markdown))
    for index, match in enumerate(matches):
        title = match.group(2).strip().lower()
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(markdown)
        sections[title] = markdown[start:end].strip()
    return sections


def _build_project_bundle_signals(project_text: str | None, contract: ResearchContract | None) -> ProjectBundleSignals:
    """Build normalized bundle-selection signals from project metadata."""
    sources: list[str] = []
    tags: set[str] = set()
    text_parts: list[str] = []

    if project_text:
        project_markdown = textwrap.dedent(project_text)
        text_parts.append(project_markdown)
        sources.append("PROJECT.md")
        sections = _extract_sections(project_markdown)
        for heading in ("theoretical framework", "physical system", "what this is", "core research question"):
            section_content = sections.get(heading)
            if not section_content:
                continue
            candidate = next((line.strip() for line in section_content.splitlines() if line.strip()), "")
            if candidate:
                tags.add(f"{heading.replace(' ', '-')}:{_slugify(candidate)}")

    if contract is not None:
        text_parts.append(contract.scope.question)
        text_parts.extend(contract.scope.in_scope)
        text_parts.extend(contract.scope.out_of_scope)
        text_parts.extend(contract.scope.unresolved_questions)
        text_parts.extend(contract.context_intake.must_read_refs)
        text_parts.extend(contract.context_intake.must_include_prior_outputs)
        text_parts.extend(contract.context_intake.user_asserted_anchors)
        text_parts.extend(contract.context_intake.known_good_baselines)
        text_parts.extend(contract.context_intake.context_gaps)
        text_parts.extend(contract.context_intake.crucial_inputs)
        sources.append("project_contract")

        for observable in contract.observables:
            tags.add(f"observable-kind:{observable.kind}")
            text_parts.extend(filter(None, [observable.name, observable.definition, observable.regime, observable.units]))
        for claim in contract.claims:
            text_parts.append(claim.statement)
        for deliverable in contract.deliverables:
            tags.add(f"deliverable-kind:{deliverable.kind}")
            text_parts.extend(filter(None, [deliverable.description, deliverable.path]))
            text_parts.extend(deliverable.must_contain)
        for acceptance_test in contract.acceptance_tests:
            tags.add(f"acceptance-kind:{acceptance_test.kind}")
            tags.add(f"acceptance-automation:{acceptance_test.automation}")
            text_parts.extend(
                [acceptance_test.procedure, acceptance_test.pass_condition, *acceptance_test.evidence_required]
            )
        for reference in contract.references:
            tags.add(f"reference-role:{reference.role}")
            text_parts.extend([reference.locator, reference.why_it_matters, *reference.required_actions, *reference.applies_to])
        for proxy in contract.forbidden_proxies:
            text_parts.extend([proxy.proxy, proxy.reason])
        text_parts.extend(contract.uncertainty_markers.weakest_anchors)
        text_parts.extend(contract.uncertainty_markers.unvalidated_assumptions)
        text_parts.extend(contract.uncertainty_markers.competing_explanations)
        text_parts.extend(contract.uncertainty_markers.disconfirming_observations)

    normalized_text = _normalize_text("\n".join(part for part in text_parts if part))
    return ProjectBundleSignals(text=normalized_text, tags=sorted(tags), sources=sources)


@lru_cache(maxsize=4)
def _load_protocol_bundles(bundles_dir: str) -> tuple[ProtocolBundle, ...]:
    directory = Path(bundles_dir)
    if not directory.is_dir():
        return ()

    bundles: list[ProtocolBundle] = []
    for path in sorted(directory.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        meta, _body = extract_frontmatter(text)
        if not meta:
            continue
        if "bundle_id" not in meta:
            continue
        bundles.append(ProtocolBundle.model_validate(meta))
    return tuple(bundles)


def list_protocol_bundles(*, bundles_dir: Path | None = None) -> list[ProtocolBundle]:
    """List all registered protocol bundles."""
    directory = bundles_dir or BUNDLES_DIR
    return list(_load_protocol_bundles(str(directory)))


def get_protocol_bundle(bundle_id: str, *, bundles_dir: Path | None = None) -> ProtocolBundle | None:
    """Return one bundle by id."""
    for bundle in list_protocol_bundles(bundles_dir=bundles_dir):
        if bundle.bundle_id == bundle_id:
            return bundle
    return None


def select_protocol_bundles(
    project_text: str | None,
    contract: ResearchContract | None,
    *,
    bundles_dir: Path | None = None,
) -> list[ResolvedProtocolBundle]:
    """Select applicable bundles from project metadata."""
    signals = _build_project_bundle_signals(project_text, contract)
    candidates: list[tuple[ProtocolBundle, int, set[str], set[str]]] = []

    for bundle in list_protocol_bundles(bundles_dir=bundles_dir):
        matched_tags: list[str] = []
        matched_terms: list[str] = []
        score = 0

        if any(tag not in signals.tags for tag in bundle.trigger.all_tags):
            continue
        if any(not _contains_term(signals.text, term) for term in bundle.trigger.all_terms):
            continue

        matched_tags.extend(bundle.trigger.all_tags)
        matched_terms.extend(bundle.trigger.all_terms)
        score += 4 * len(bundle.trigger.all_tags)
        score += 3 * len(bundle.trigger.all_terms)

        for tag in bundle.trigger.any_tags:
            if tag in signals.tags:
                matched_tags.append(tag)
                score += 4
        for term in bundle.trigger.any_terms:
            if _contains_term(signals.text, term):
                matched_terms.append(term)
                score += 3

        unique_tag_matches = set(matched_tags)
        unique_term_matches = set(matched_terms)

        if len(unique_tag_matches) < bundle.trigger.min_tag_matches:
            continue
        if len(unique_term_matches) < bundle.trigger.min_term_matches:
            continue
        if score < bundle.trigger.min_score:
            continue

        candidates.append(
            (
                bundle,
                score,
                unique_tag_matches,
                unique_term_matches,
            )
        )

    selected: list[ResolvedProtocolBundle] = []
    kept_bundles: list[ProtocolBundle] = []
    ordered_candidates = sorted(candidates, key=lambda item: (-item[1], item[0].bundle_id))
    for bundle, score, unique_tag_matches, unique_term_matches in ordered_candidates:
        if any(
            bundle.bundle_id in kept.trigger.exclusive_with or kept.bundle_id in bundle.trigger.exclusive_with
            for kept in kept_bundles
        ):
            continue

        selected.append(
            ResolvedProtocolBundle(
                bundle_id=bundle.bundle_id,
                title=bundle.title,
                summary=bundle.summary,
                score=score,
                matched_tags=sorted(unique_tag_matches),
                matched_terms=sorted(unique_term_matches),
                selection_tags=bundle.selection_tags,
                assets=bundle.assets,
                anchor_prompts=bundle.anchor_prompts,
                reference_prompts=bundle.reference_prompts,
                estimator_policies=bundle.estimator_policies,
                decisive_artifact_guidance=bundle.decisive_artifact_guidance,
                verifier_extensions=bundle.verifier_extensions,
            )
        )
        kept_bundles.append(bundle)

    return selected


def _render_asset_line(role: str, assets: list[BundleAsset]) -> str | None:
    if not assets:
        return None
    role_label = role.replace("_", " ")
    rendered = ", ".join(
        f"{{GPD_INSTALL_DIR}}/{asset.path}{' (required)' if asset.required else ''}" for asset in assets
    )
    return f"- {role_label}: {rendered}"


def render_protocol_bundle_context(selected: list[ResolvedProtocolBundle]) -> str:
    """Render a compact prompt-facing protocol-bundle summary."""
    lines = [
        "## Selected Protocol Bundles",
        "- Usage contract: additive specialized guidance only. Bundles do not replace the approved contract, required anchors, acceptance tests, or decisive evidence obligations.",
    ]
    if not selected:
        lines.append("- None selected from project metadata. Fall back to shared protocols and on-demand routing.")
        return "\n".join(lines)

    for bundle in selected:
        reason_bits: list[str] = []
        if bundle.matched_tags:
            reason_bits.append("tags=" + ", ".join(bundle.matched_tags))
        if bundle.matched_terms:
            reason_bits.append("terms=" + ", ".join(bundle.matched_terms))
        reason = "; ".join(reason_bits) if reason_bits else "metadata match"

        lines.extend(
            [
                "",
                f"### {bundle.title} [{bundle.bundle_id}]",
                f"- Why selected: {reason}",
                f"- Summary: {bundle.summary}",
            ]
        )
        if bundle.selection_tags:
            lines.append("- Selection tags: " + ", ".join(bundle.selection_tags))

        for role in (
            "project_types",
            "subfield_guides",
            "verification_domains",
            "protocols_core",
            "protocols_optional",
            "execution_guides",
        ):
            asset_line = _render_asset_line(role, getattr(bundle.assets, role))
            if asset_line:
                lines.append(asset_line)

        if bundle.anchor_prompts:
            lines.append("- Anchor prompts: " + " | ".join(bundle.anchor_prompts))
        if bundle.reference_prompts:
            lines.append("- Reference prompts: " + " | ".join(bundle.reference_prompts))
        if bundle.estimator_policies:
            lines.append("- Estimator policies: " + " | ".join(bundle.estimator_policies))
        if bundle.decisive_artifact_guidance:
            lines.append("- Decisive artifacts: " + " | ".join(bundle.decisive_artifact_guidance))
        if bundle.verifier_extensions:
            rendered_extensions = " | ".join(
                f"{extension.name} [{', '.join(extension.check_ids) or 'no-check-ids'}]"
                for extension in bundle.verifier_extensions
            )
            lines.append("- Verifier extensions: " + rendered_extensions)

    return "\n".join(lines)

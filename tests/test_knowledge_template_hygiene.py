from pathlib import Path


def test_knowledge_template_defers_behaviors_to_guidance_note():
    template_text = Path("src/gpd/specs/templates/knowledge.md").read_text()
    assert "## Deferred Behaviors" in template_text
    assert "src/gpd/specs/templates/knowledge-guidance.md" in template_text
    assert "The public authoring command and help coverage" not in template_text

---
template_version: 1
---

> **Context:** This template is for the `new-project` literature survey — researching a topic BEFORE
> starting a new project. For analyzing existing project artifacts, see `templates/analysis/`.

# Prior Work Research Template

Template for `.gpd/research/PRIOR-WORK.md` -- survey of known results and prior work in the research domain.

---

## File Template

```markdown
# Prior Work: {Research Domain}

**Surveyed:** {date}
**Domain:** {physics subfield}
**Confidence:** {HIGH / MEDIUM / LOW}

## Key Results

| Result                     | Expression / Value           | Conditions                      | Source           | Year   | Confidence        |
| -------------------------- | ---------------------------- | ------------------------------- | ---------------- | ------ | ----------------- |
| {what was computed/proved} | {formula or numerical value} | {assumptions, parameter regime} | {authors, paper} | {year} | {HIGH/MEDIUM/LOW} |

## Foundational Work

### {Author(s)} ({Year}) - {Short Title}

**Key contribution:** {what they established}
**Method:** {how they did it}
**Limitations:** {where it breaks down or what was left open}
**Relevance:** {why it matters for our research question}

### {Author(s)} ({Year}) - {Short Title}

**Key contribution:** {what they established}
**Method:** {how they did it}
**Limitations:** {where it breaks down}
**Relevance:** {why it matters}

## Recent Developments

| Paper   | Authors   | Year   | Advance      | Impact on Our Work            |
| ------- | --------- | ------ | ------------ | ----------------------------- |
| {title} | {authors} | {year} | {what's new} | {how it affects our approach} |

## Known Limiting Cases

| Limit                | Known Result          | Source  | Verified By        |
| -------------------- | --------------------- | ------- | ------------------ |
| {parameter -> value} | {expression or value} | {paper} | {who confirmed it} |

## Open Questions

1. **{Question}** -- {what's not yet resolved, why it matters}
2. **{Question}** -- {what's not yet resolved, why it matters}

## Notation Conventions in the Literature

| Quantity            | Standard Symbol(s) | Variations              | Our Choice    | Reason |
| ------------------- | ------------------ | ----------------------- | ------------- | ------ |
| {physical quantity} | {common symbol}    | {alternative notations} | {what we use} | {why}  |

## Sources

- {Paper 1} -- {what it provides for us}
- {Paper 2} -- {what it provides for us}
- {Textbook} -- {which chapters/sections are relevant}
```

---

## Quality Criteria

- [ ] Citations are specific (authors, year, equation numbers where possible)
- [ ] Conditions and assumptions stated for each result
- [ ] Limitations of prior work clearly identified
- [ ] Open questions relevant to our research flagged
- [ ] Notation conventions reconciled across papers
- [ ] Relevance to this specific research project explained

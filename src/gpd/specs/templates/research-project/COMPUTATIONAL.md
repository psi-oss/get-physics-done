---
template_version: 1
---

> **Context:** This template is for the `new-project` literature survey — researching a topic BEFORE
> starting a new project. For analyzing existing project artifacts, see `templates/analysis/`.

# Computational Approaches Research Template

Template for `.gpd/research/COMPUTATIONAL.md` -- survey of computational tools, numerical methods, and simulation approaches.

---

## File Template

```markdown
# Computational Approaches: {Research Domain}

**Surveyed:** {date}
**Domain:** {physics subfield}
**Confidence:** {HIGH / MEDIUM / LOW}

## Recommended Stack

{1-2 paragraph summary of the recommended computational approach}

## Numerical Algorithms

| Algorithm   | Problem          | Convergence     | Cost per Step | Memory   | Key Reference    |
| ----------- | ---------------- | --------------- | ------------- | -------- | ---------------- |
| {algorithm} | {what it solves} | {order or rate} | {O(N^?)}      | {O(N^?)} | {paper/textbook} |

### Convergence Properties

For each algorithm, specify:

- **Convergence criterion:** {how to know when converged}
- **Expected rate:** {algebraic/exponential, order}
- **Known failure modes:** {when convergence fails or slows}

## Software Ecosystem

### Primary Tools

| Tool   | Version   | Purpose         | License   | Maturity                   |
| ------ | --------- | --------------- | --------- | -------------------------- |
| {name} | {version} | {core function} | {license} | {stable/beta/experimental} |

### Supporting Tools

| Tool   | Version   | Purpose    | When Needed             |
| ------ | --------- | ---------- | ----------------------- |
| {name} | {version} | {function} | {under what conditions} |

## Data Flow
```

Input parameters
-> {Step 1: what computation}
-> Intermediate result A
-> {Step 2: what computation}
-> Intermediate result B
-> {Step 3: combine/analyze}
-> Final output

```

## Computation Order and Dependencies

| Step | Depends On | Produces | Can Parallelize? |
|------|-----------|----------|-----------------|
| {step} | {prerequisites} | {output} | {yes/no} |

## Resource Estimates

| Computation | Time (estimate) | Memory | Storage | Hardware |
|-------------|-----------------|--------|---------|----------|
| {computation} | {time} | {RAM needed} | {disk needed} | {CPU/GPU/HPC} |

## Integration with Existing Code

{For continuation projects: how new computations connect to existing project}

- **Input formats:** {what format existing code produces}
- **Output formats:** {what format downstream code expects}
- **Interface points:** {where new code plugs in}

## Validation Strategy

| Result | Validation Method | Benchmark | Source |
|--------|------------------|-----------|--------|
| {numerical result} | {how to validate} | {known value to compare against} | {reference} |

## Sources

- {Reference 1} -- {which computational aspects it covers}
- {Reference 2} -- {which computational aspects it covers}
```

---

## Quality Criteria

- [ ] Algorithms defined with convergence criteria
- [ ] Software versions current and verified
- [ ] Computation order considers dependencies
- [ ] Resource estimates provided
- [ ] Data flow from input to output is clear
- [ ] Validation benchmarks identified for each computation

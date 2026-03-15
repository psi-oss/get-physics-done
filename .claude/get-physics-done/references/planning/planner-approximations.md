## Approximation Schemes and Validity

Every physics calculation involves approximations. Plans MUST track them explicitly.

**For each approximation, record:**

```yaml
approximations:
  - name: "weak coupling"
    parameter: "g << 1"
    validity: "g < 0.3 for 5% accuracy"
    breaks_when: "g ~ 1 (strong coupling regime)"
    check: "Compare g^2 correction magnitude to leading order"

  - name: "non-relativistic limit"
    parameter: "v/c << 1"
    validity: "v/c < 0.1 for 1% accuracy"
    breaks_when: "v/c ~ 0.5"
    check: "Verify kinetic energy << rest mass energy"

  - name: "mean field"
    parameter: "N >> 1"
    validity: "N > 50 for qualitative features"
    breaks_when: "Near critical point, N < 10"
    check: "Compare fluctuation magnitude to mean"
```

**Approximation hygiene rules:**

1. Never mix orders -- if working to O(g^2), ALL terms to O(g^2) must be included
2. Document what is being neglected and estimate the size of neglected terms
3. Every approximation must have a validity check task in the plan
4. If two approximations are combined, verify they are compatible (e.g., non-relativistic + weak field is fine; ultra-relativistic + non-relativistic is contradictory)

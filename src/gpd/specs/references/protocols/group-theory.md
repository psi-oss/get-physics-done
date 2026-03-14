---
load_when:
  - "group theory"
  - "representation"
  - "Clebsch-Gordan"
  - "Young tableau"
  - "Lie algebra"
  - "SU(N)"
  - "SO(N)"
  - "angular momentum"
  - "tensor product"
  - "irreducible representation"
tier: 2
context_cost: medium
---

# Group Theory and Representation Theory Protocol

Group theory is the computational backbone of quantum physics: selection rules, conservation laws, spectral degeneracies, and particle classifications all derive from representation theory. Errors in this domain -- wrong CG coefficients, inconsistent phase conventions, incorrect tensor product decompositions -- silently propagate into every downstream calculation. This protocol provides step-by-step algorithms with built-in verification at each stage.

## Related Protocols
- `symmetry-analysis.md` -- Symmetry identification, SSB, anomalies (higher-level context)
- `derivation-discipline.md` -- Sign tracking and convention annotation (use throughout)

## Step 1: Representation Construction

### 1.1 Identify the Group and Its Structure

Before constructing representations, establish:

1. **The group G.** Is it finite (S_n, point groups), compact Lie (SU(N), SO(N), Sp(N)), or non-compact (Lorentz, Poincare)? The representation theory differs fundamentally between these cases.
2. **The Lie algebra.** For Lie groups, identify the algebra by its commutation relations. Classify by Dynkin diagram: A_n = SU(n+1), B_n = SO(2n+1), C_n = Sp(2n), D_n = SO(2n), plus the exceptionals G_2, F_4, E_6, E_7, E_8.
3. **Rank and Cartan subalgebra.** The rank r = number of simultaneously diagonalizable generators = number of quantum numbers labeling states within a representation. For SU(N): rank = N-1. For SO(N): rank = floor(N/2).

### 1.2 Construct Irreps by Highest Weight

For any semisimple Lie algebra:

1. **Choose a basis of simple roots** alpha_1, ..., alpha_r. These are the positive roots that cannot be written as a sum of other positive roots. The Cartan matrix A_{ij} = 2(alpha_i, alpha_j)/(alpha_j, alpha_j) encodes all structure.
2. **Label irreps by Dynkin labels** (a_1, ..., a_r) where a_i are non-negative integers. The highest weight is Lambda = sum_i a_i Lambda_i, where Lambda_i are the fundamental weights satisfying 2(Lambda_i, alpha_j)/(alpha_j, alpha_j) = delta_{ij}.
3. **Build the weight diagram** by repeated application of lowering operators E_{-alpha_i}. A weight mu has multiplicity > 1 if it can be reached by different lowering paths. Use the Freudenthal recursion formula for multiplicities.
4. **Dimension formula (Weyl).** For an irrep with highest weight Lambda:

```
dim(Lambda) = product_{alpha > 0} (Lambda + rho, alpha) / (rho, alpha)
```

where rho = (1/2) sum of positive roots. Always compute this and verify against the weight diagram.

**Checkpoint:** Count the total number of weights (with multiplicity). It must equal dim(Lambda). If it does not, the weight diagram construction has an error.

### 1.3 Phase Convention: Condon-Shortley

**State the phase convention explicitly at the start of every calculation.** The standard choice is Condon-Shortley:

- Basis states |j, m> are eigenstates of J^2 and J_z.
- The raising/lowering operators act as: J_+/- |j, m> = sqrt(j(j+1) - m(m +/- 1)) |j, m +/- 1>.
- The matrix elements of J_+/- are real and non-negative for the standard basis.
- The highest-weight state |j, j> has coefficient +1 in the tensor product decomposition when it appears.

Any departure from Condon-Shortley must be flagged and the translation rules stated. Common alternatives: Sakurai (matches Condon-Shortley), Varshalovich (extra phases on 3j symbols), and particle physics conventions (may differ by factors of (-1)^{j-m}).

## Step 2: Clebsch-Gordan Coefficient Computation

### 2.1 Algorithm for SU(2)

To compute <j_1, m_1; j_2, m_2 | J, M>:

1. **Selection rules.** The coefficient vanishes unless:
   - M = m_1 + m_2 (magnetic quantum number conservation)
   - |j_1 - j_2| <= J <= j_1 + j_2 (triangle inequality)
   - j_1 + j_2 + J is consistent with integer/half-integer rules

2. **Start from the stretched state.** |J = j_1 + j_2, M = j_1 + j_2> = |j_1, j_1> |j_2, j_2>. This state is unique (coefficient = 1 by Condon-Shortley convention).

3. **Apply J_- = J_-^{(1)} + J_-^{(2)} recursively.** At each step:
```
J_- |J, M> = sqrt(J(J+1) - M(M-1)) |J, M-1>
```
Expand the left side using the product-basis action of J_-^{(1)} and J_-^{(2)}, then read off the CG coefficients by matching.

4. **For the next J value (J = j_1 + j_2 - 1):** The state |J, M = J> must be orthogonal to |j_1 + j_2, M = J> in the same M-subspace. Construct it by Gram-Schmidt orthogonalization, choosing the overall phase so that <j_1, j_1 - 1; j_2, j_2 | J, J> is real and positive (Condon-Shortley).

5. **Repeat** for each J down to |j_1 - j_2|.

### 2.2 Verification of CG Coefficients

After computing CG coefficients, verify ALL of:

1. **Orthonormality of rows:**
```
sum_{m_1, m_2} <j_1, m_1; j_2, m_2 | J, M> <j_1, m_1; j_2, m_2 | J', M'> = delta_{J,J'} delta_{M,M'}
```

2. **Orthonormality of columns (completeness):**
```
sum_{J, M} <j_1, m_1; j_2, m_2 | J, M> <j_1, m_1'; j_2, m_2' | J, M> = delta_{m_1,m_1'} delta_{m_2,m_2'}
```

3. **Special values** (quick sanity checks):
   - <j_1, j_1; j_2, j_2 | j_1 + j_2, j_1 + j_2> = 1
   - <j, m; 0, 0 | j, m> = 1
   - <j_1, m_1; j_2, m_2 | 0, 0> = (-1)^{j_1 - m_1} delta_{j_1, j_2} delta_{m_1, -m_2} / sqrt(2j_1 + 1)

4. **Symmetry relations:**
   - <j_1, m_1; j_2, m_2 | J, M> = (-1)^{j_1 + j_2 - J} <j_2, m_2; j_1, m_1 | J, M>
   - <j_1, m_1; j_2, m_2 | J, M> = (-1)^{j_1 - m_1} sqrt((2J+1)/(2j_2+1)) <j_1, m_1; J, -M | j_2, -m_2>

**If any verification fails:** The phase convention is inconsistent or the lowering procedure has an arithmetic error. Do not proceed.

### 2.3 CG Coefficients for SU(3) and Higher Groups

For SU(3), the CG series is labeled by the multiplicity index (outer multiplicity) since the same irrep can appear more than once in a tensor product. The algorithm:

1. Compute the tensor product using Young tableaux (Step 3 below) or the weight-diagram method.
2. For each irrep (p, q) in the decomposition, construct the isoscalar factors (SU(3) CG coefficients) using the de Swart convention or the Kaeding algorithm.
3. Verify: the sum of squared CG coefficients for a fixed initial state over all final states and irreps equals 1 (completeness).

For general SU(N): use the Littlewood-Richardson rule (Step 3) for the decomposition, and the Gelfand-Tsetlin basis for explicit CG coefficients.

### 2.4 Recoupling: 6j, 9j Symbols and Racah Coefficients

When coupling three or more angular momenta, the result depends on the **coupling order**. Recoupling coefficients relate different coupling schemes. This is where LLMs most frequently produce wrong answers.

**The coupling-order problem:** For three angular momenta j_1, j_2, j_3, two natural coupling schemes exist:
- Scheme 1: couple j_1 + j_2 = j_{12}, then j_{12} + j_3 = J
- Scheme 2: couple j_2 + j_3 = j_{23}, then j_1 + j_{23} = J

The transformation between these is:

```
|((j_1, j_2) j_{12}, j_3) J, M> = sum_{j_{23}} (-1)^{j_1 + j_2 + j_3 + J} sqrt((2*j_{12}+1)(2*j_{23}+1))
    * { j_1  j_2  j_{12} }  * |(j_1, (j_2, j_3) j_{23}) J, M>
      { j_3  J    j_{23} }
```

where the curly braces denote the **Wigner 6j symbol**.

**6j symbol properties (use these as verification):**

1. **Triangle conditions.** The 6j symbol {a b c / d e f} vanishes unless (a,b,c), (a,e,f), (d,b,f), (d,e,c) all satisfy the triangle inequality.
2. **Symmetry.** Invariant under permutation of columns and under exchange of upper and lower entries in any two columns.
3. **Orthogonality:**
```
sum_e (2e+1) {a b e / c d f} {a b e / c d f'} = delta_{f,f'} / (2f+1)
```
4. **Special values:** {a b c / 0 c b} = (-1)^{a+b+c} / sqrt((2b+1)(2c+1)).

**9j symbols** arise when coupling four angular momenta or changing between LS and jj coupling:

```
{ j_1  j_2  j_{12} }
{ j_3  j_4  j_{34} }   = sum_g (-1)^{2g} (2g+1) {j_1 j_2 j_{12}} {j_3 j_4 j_{34}} {j_{13} j_{24} J}
{ j_{13} j_{24} J   }                              {j_3 J  g      } {j_1 J  g      } {j_1    j_2   g}
```

**Verification for recoupling coefficients:**

1. After transforming coupling schemes, the TOTAL dimension of the coupled space must be unchanged. Count states before and after.
2. The recoupling transformation must be unitary: sum over intermediate angular momentum of |coefficient|^2 = 1 for each initial state.
3. Cross-check 6j symbols against the Racah formula: W(abcd; ef) = (-1)^{a+b+d+c} {a b e / d c f}. Sources using Racah W-coefficients vs Wigner 6j symbols differ by the phase factor.

**Common LLM error:** Forgetting the phase (-1)^{j_1+j_2+j_3+J} in the recoupling transformation. This phase arises from the properties of CG coefficients under particle exchange and is the single most common source of sign errors in multi-particle angular momentum calculations.

### 2.5 Wigner-Eckart Theorem and Tensor Operators

The Wigner-Eckart theorem factorizes matrix elements of tensor operators into a geometric part (CG coefficient) and a dynamic part (reduced matrix element):

```
<j', m' | T^{(k)}_q | j, m> = (-1)^{j'-m'} ( j'  k  j ) <j' || T^{(k)} || j>
                                              (-m' q  m )
```

where the parentheses denote a Wigner 3j symbol, related to the CG coefficient by:

```
( j_1  j_2  J  ) = (-1)^{j_1-j_2+M} / sqrt(2J+1) * <j_1, m_1; j_2, m_2 | J, -M>
( m_1  m_2  -M )
```

**Protocol for tensor operator calculations:**

1. **Identify the tensor rank k.** A scalar operator has k=0, a vector operator has k=1, a quadrupole has k=2. The angular momentum operators J_+, J_0, J_- form a rank-1 tensor with T^{(1)}_{+1} = -J_+/sqrt(2), T^{(1)}_0 = J_z, T^{(1)}_{-1} = J_-/sqrt(2) (Condon-Shortley).
2. **Verify the commutation relations** [J_z, T^{(k)}_q] = q T^{(k)}_q and [J_+/-, T^{(k)}_q] = sqrt(k(k+1) - q(q+/-1)) T^{(k)}_{q+/-1}. If these fail, the object is not a proper spherical tensor.
3. **Apply the theorem** to extract the reduced matrix element from one known matrix element, then predict all others.
4. **Selection rules** follow immediately: the matrix element vanishes unless |j-k| <= j' <= j+k and m' = m + q.

**Verification:**
- The reduced matrix element is independent of m, m', and q. Compute it from two different (m, q, m') combinations. They must give the same reduced matrix element.
- For the angular momentum operator itself: <j || J || j> = sqrt(j(j+1)(2j+1)). Verify against direct computation of any matrix element.

**Common LLM error:** Getting the sign in the 3j symbol wrong. The 3j symbol has a phase (-1)^{j_1-j_2-M} relative to the CG coefficient. LLMs frequently drop this phase or use the wrong sign convention. Always convert between 3j and CG using the explicit formula above, never from memory.

## Step 3: Young Tableaux

### 3.1 Notation

A Young diagram for SU(N) is a left-justified array of boxes with row lengths lambda_1 >= lambda_2 >= ... >= lambda_N >= 0 (at most N rows). The Dynkin labels are a_i = lambda_i - lambda_{i+1}.

Standard examples for SU(3):
- Fundamental 3: single box = (1, 0), dimension 3
- Anti-fundamental 3-bar: two-row column = (0, 1), dimension 3
- Adjoint 8: one box on first row + one box on second row, L-shape = (1, 1), dimension 8
- Symmetric 6: two boxes in a row = (2, 0), dimension 6

### 3.2 Dimension Formula (Hook Length)

For SU(N) with a Young diagram of shape lambda:

```
dim = product_{(i,j) in lambda} (N + j - i) / hook(i, j)
```

where hook(i, j) = (number of boxes to the right in row i) + (number of boxes below in column j) + 1.

**Always compute this independently and compare to the Weyl dimension formula.** They must agree.

### 3.3 Tensor Product Decomposition (Littlewood-Richardson Rule)

To decompose R_1 (x) R_2 for SU(N):

1. Draw the Young diagram for R_1. Fill the boxes of R_2 with labels: all boxes in row 1 get label 'a', row 2 get 'b', row 3 get 'c', etc.
2. Attach the labeled boxes of R_2 to R_1 one at a time, subject to:
   - At each stage, the result is a valid Young diagram (rows non-increasing, at most N rows for SU(N)).
   - No two boxes with the same label appear in the same column.
   - Reading the labels right-to-left, top-to-bottom, at every point the count of 'a' >= count of 'b' >= count of 'c' >= ... (lattice word / lattice permutation condition).
3. Each valid final diagram is one irrep in the decomposition.

**Dimension check (mandatory):** dim(R_1) * dim(R_2) = sum of dim(R_i) over all irreps in the decomposition. If this fails, the Littlewood-Richardson procedure was applied incorrectly.

### 3.4 Connection to Representations

- For SU(N), each valid Young diagram with at most N-1 rows (after removing columns of height N) labels a unique irrep.
- Conjugate representation: transpose the Young diagram (reflect across the diagonal). For SU(3): conjugating (p, q) gives (q, p).
- Singlet: empty diagram (or N-box column, which is trivial in SU(N)).
- Adjoint: for SU(N), it is the diagram with Dynkin labels (1, 0, ..., 0, 1), dimension N^2 - 1.

## Step 4: Lie Algebra Computations

### 4.1 Commutation Relations

For a semisimple Lie algebra with generators T_a:

```
[T_a, T_b] = i f_{abc} T_c
```

where f_{abc} are the structure constants, fully antisymmetric for compact groups with the standard normalization Tr(T_a T_b) = (1/2) delta_{ab} (for the fundamental representation of SU(N)).

**State the normalization convention explicitly.** Common alternatives:
- Particle physics: Tr(T_a T_b) = (1/2) delta_{ab} (generators are lambda_a / 2 for SU(N))
- Mathematics: Tr(T_a T_b) = delta_{ab} (generators are lambda_a / sqrt(2))
- Dynkin index: Tr_R(T_a T_b) = T(R) delta_{ab}, where T(R) depends on the representation

### 4.2 Casimir Operators

The quadratic Casimir C_2 = sum_a T_a T_a commutes with all generators and takes a constant value on each irrep:

- **SU(2):** C_2 = j(j + 1) for representation j.
- **SU(3):** C_2(p, q) = (p^2 + q^2 + pq + 3p + 3q) / 3 (with Tr = 1/2 normalization).
- **SU(N) general:** C_2(Lambda) = (Lambda, Lambda + 2*rho) / 2N (with Tr = 1/2 normalization), where rho is the Weyl vector.

**Casimir eigenvalue check:** For any irrep, compute C_2 by direct matrix multiplication AND by the eigenvalue formula. They must agree. This catches errors in the generator matrices.

### 4.3 Root Systems

1. **Roots** are the nonzero weights of the adjoint representation. For rank-r algebra, the root system lives in r-dimensional space.
2. **Simple roots** alpha_1, ..., alpha_r: positive roots that are not sums of other positive roots. Every positive root is a non-negative integer combination of simple roots.
3. **Cartan matrix** A_{ij} = 2(alpha_i, alpha_j) / (alpha_j, alpha_j). This matrix encodes the entire algebra.

Root system data for the classical algebras:

| Algebra | Rank | # Positive roots | Dimension | Simple root angles |
|---------|------|------------------|-----------|--------------------|
| A_n = SU(n+1) | n | n(n+1)/2 | n^2 + 2n | 120 degrees between adjacent |
| B_n = SO(2n+1) | n | n^2 | n(2n+1) | 120 or 135 degrees |
| C_n = Sp(2n) | n | n^2 | n(2n+1) | 120 or 135 degrees |
| D_n = SO(2n) | n | n(n-1) | n(2n-1) | 120 degrees, forked end |

**Verification:** The number of positive roots = (dim(G) - rank(G)) / 2. If this fails, the root enumeration is wrong.

## Step 5: Common LLM Errors

### 5.1 Wrong CG Coefficient Signs

**The error:** LLMs frequently get the sign of CG coefficients wrong, especially for the non-stretched states. The most common mistake is dropping the (-1)^{j_1 + j_2 - J} phase when exchanging the coupling order.

**The fix:** Always compute CG coefficients by the lowering-operator algorithm (Step 2.1) starting from the stretched state. Never quote CG coefficients from memory -- derive them. After computing, verify using the symmetry relation and special values.

### 5.2 Condon-Shortley Phase Confusion

**The error:** Mixing conventions between sources that use different phase choices. The spherical harmonics Y_l^m have a Condon-Shortley phase (-1)^m for m > 0 in the standard convention. Some references absorb this phase into the associated Legendre functions; others do not.

**The fix:** At the start of any calculation involving angular momentum:
1. State: "Using Condon-Shortley phase convention."
2. Verify: J_+ |j, m> = +sqrt(j(j+1) - m(m+1)) |j, m+1> with a real positive coefficient.
3. When combining results from different sources, check whether each source uses Condon-Shortley by testing the sign of Y_1^1 = -sqrt(3/(8*pi)) sin(theta) e^{i*phi}. If the source has +sqrt(...) instead, it omits the Condon-Shortley phase.

### 5.3 Dynkin Label Mixups

**The error:** Confusing Dynkin labels with dimension labels, or getting the ordering of Dynkin labels wrong. For SU(3), the representation (1, 0) is the fundamental 3, and (0, 1) is the anti-fundamental 3-bar. LLMs sometimes reverse these, or confuse the Dynkin label (1, 1) (dimension 8, the adjoint) with the representation of dimension 11 (which does not exist for SU(3)) by incorrectly applying the dimension formula.

**The fix:** Always compute the dimension from the Dynkin labels using the Weyl formula and verify it matches the expected representation. For SU(3):

```
dim(p, q) = (p + 1)(q + 1)(p + q + 2) / 2
```

Quick reference: (0,0)=1, (1,0)=3, (0,1)=3, (2,0)=6, (0,2)=6, (1,1)=8, (3,0)=10, (0,3)=10, (2,1)=15, (1,2)=15.

### 5.4 Incorrect Tensor Product Decompositions

**The error:** Getting the multiplicity wrong in tensor product decompositions, especially for SU(3) and higher groups where the same irrep can appear multiple times (outer multiplicity > 1). LLMs also frequently forget to include all irreps, or include irreps that violate the Littlewood-Richardson rule.

**The fix:** Always verify tensor products by the dimension check. Then verify using the character relation: chi_{R_1}(g) * chi_{R_2}(g) = sum_i chi_{R_i}(g) for all group elements g. For SU(3), use the Littlewood-Richardson rule applied to Young tableaux with at most 2 rows (after removing columns of height 3).

### 5.5 Non-SU(2) Group Errors

**The error:** Treating SU(3), SO(N), or Sp(N) calculations as if they were SU(2). The most common mistakes:
- Assuming all representations are self-conjugate (true for SU(2), false for SU(3): 3 and 3-bar are distinct).
- Assuming tensor products are multiplicity-free (true for SU(2), false for SU(3): 8 (x) 8 = 27 + 10 + 10-bar + 8 + 8 + 1, with the adjoint 8 appearing twice).
- Using the SU(2) dimension formula 2j+1 for non-SU(2) groups.
- Forgetting that SO(N) has spinor representations that are not tensor representations.

**The fix:**
1. Never assume multiplicity-free decompositions for rank >= 2 groups. Always check.
2. For SU(N) with N >= 3, track representations by Dynkin labels, not dimension alone (multiple distinct irreps can share the same dimension for high enough rank).
3. For SO(N), distinguish between vector, spinor, and tensor representations. Use the Dynkin classification: the last Dynkin label(s) correspond to spinor representations.
4. For Sp(2n), all representations are self-conjugate (pseudoreal for odd-dimensional, real for even-dimensional). This is opposite to SU(N) where only real representations are self-conjugate.

### 5.6 Angular Momentum Addition Errors

**The error:** When adding three or more angular momenta, LLMs frequently:
- Couple in an arbitrary order without tracking which coupling scheme is being used
- Drop the recoupling phases when switching between (j_1 + j_2) + j_3 and j_1 + (j_2 + j_3) schemes
- Confuse LS coupling (orbital + spin first, then combine) with jj coupling (each particle's j first, then combine total)
- Forget that the number of allowed intermediate quantum numbers depends on the coupling scheme

**The fix:**
1. State the coupling scheme explicitly at the start: "Coupling in the scheme ((j_1, j_2)_{j_{12}}, j_3)_J."
2. When changing coupling scheme, use 6j symbols (Step 2.4) with the correct phase.
3. For LS vs jj coupling in atomic physics: LS coupling writes |(l_1, l_2)_L; (s_1, s_2)_S; J, M>, while jj coupling writes |(l_1, s_1)_{j_1}; (l_2, s_2)_{j_2}; J, M>. The transformation uses a 9j symbol.
4. Count states as a sanity check: the total number of states in the coupled basis must equal the product of (2j_i + 1) for all individual angular momenta, regardless of coupling scheme.

## Step 6: Verification Checklist

For every group-theory computation, verify:

1. **Dimension check (tensor products).** dim(R_1) * dim(R_2) = sum_i dim(R_i). This is the single most important check. If it fails, something is wrong.

2. **Orthogonality of characters.** For a finite group of order |G|:
```
(1/|G|) sum_{g in G} chi_R(g)* chi_{R'}(g) = delta_{R,R'}
```
For compact Lie groups, the sum becomes an integral over the group with the Haar measure.

3. **Sum of squared dimensions (finite groups).** sum_R dim(R)^2 = |G|. This checks that all irreps have been found.

4. **Casimir eigenvalue consistency.** For every irrep in a decomposition, compute C_2 both from the eigenvalue formula and by explicit matrix trace. They must agree.

5. **Branching rule consistency.** When restricting from G to a subgroup H, the dimension must be preserved: dim_G(R) = sum_i dim_H(R_i) where R decomposes into irreps R_i of H.

6. **Phase convention consistency.** Verify that all CG coefficients satisfy the symmetry relations (Step 2.2, point 4). If any relation is violated, the phase convention is inconsistent between different coupling schemes.

7. **Index sum rule.** The Dynkin index satisfies T(R_1 (x) R_2) = T(R_1) dim(R_2) + T(R_2) dim(R_1). For SU(N) fundamental: T(fund) = 1/2.

## Worked Example: SU(3) Flavor Decomposition 3 (x) 3 = 6 + 3-bar

**Problem:** Decompose the tensor product of two SU(3) fundamental representations and compute explicit CG coefficients.

### Decomposition

The fundamental representation of SU(3) is 3 = (1, 0), with states labeled by the weight (I_3, Y): u = (1/2, 1/3), d = (-1/2, 1/3), s = (0, -2/3).

Using Young tableaux: the fundamental 3 is a single box. The tensor product of two single boxes gives:

- Two boxes in a row (symmetric): Young diagram (2, 0), dimension = (2+1)(0+1)(2+0+2)/2 = 3 * 1 * 4/2 = 6.
- Two boxes in a column (antisymmetric): Young diagram (0, 1), dimension = (0+1)(1+1)(0+1+2)/2 = 1 * 2 * 3/2 = 3. This is the 3-bar (anti-fundamental).

**Dimension check:** 3 * 3 = 9 = 6 + 3. Correct.

### Explicit States and CG Coefficients

Label the two quarks as q_1 and q_2, each taking values u, d, s.

**Symmetric sextet (6):** States are symmetric under exchange of q_1 <-> q_2.

| State | Expansion | (I_3, Y) |
|-------|-----------|----------|
| uu | u_1 u_2 | (1, 2/3) |
| (ud + du)/sqrt(2) | (u_1 d_2 + d_1 u_2)/sqrt(2) | (0, 2/3) |
| dd | d_1 d_2 | (-1, 2/3) |
| (us + su)/sqrt(2) | (u_1 s_2 + s_1 u_2)/sqrt(2) | (1/2, -1/3) |
| (ds + sd)/sqrt(2) | (d_1 s_2 + s_1 d_2)/sqrt(2) | (-1/2, -1/3) |
| ss | s_1 s_2 | (0, -4/3) |

The CG coefficients for the symmetric states are:
- <u, u | 6; (1, 2/3)> = 1
- <u, d | 6; (0, 2/3)> = 1/sqrt(2), <d, u | 6; (0, 2/3)> = 1/sqrt(2)
- Similarly for all mixed-flavor states.

**Antisymmetric triplet (3-bar):** States are antisymmetric under exchange.

| State | Expansion | (I_3, Y) |
|-------|-----------|----------|
| (ud - du)/sqrt(2) | (u_1 d_2 - d_1 u_2)/sqrt(2) | (0, 2/3) |
| (us - su)/sqrt(2) | (u_1 s_2 - s_1 u_2)/sqrt(2) | (1/2, -1/3) |
| (ds - sd)/sqrt(2) | (d_1 s_2 - s_1 d_2)/sqrt(2) | (-1/2, -1/3) |

The CG coefficients for the antisymmetric states are:
- <u, d | 3-bar; (0, 2/3)> = 1/sqrt(2), <d, u | 3-bar; (0, 2/3)> = -1/sqrt(2)
- Similarly for all mixed-flavor states, with a relative minus sign.

### Verification

1. **Dimension check:** 6 + 3 = 9 = 3 * 3. Correct.

2. **Orthonormality:** The symmetric state (ud + du)/sqrt(2) and the antisymmetric state (ud - du)/sqrt(2) have inner product:
```
(1/2)(<u,d| + <d,u|)(|u,d> - |d,u>) = (1/2)(1 - 1) = 0
```
Correct.

3. **Completeness:** For the (I_3, Y) = (0, 2/3) subspace, the two states |6; (0, 2/3)> and |3-bar; (0, 2/3)> span the 2D subspace {|u,d>, |d,u>}. CG matrix:
```
| 1/sqrt(2)   1/sqrt(2) |
| 1/sqrt(2)  -1/sqrt(2) |
```
This is an orthogonal matrix (determinant = -1, rows orthonormal). Correct.

4. **Casimir check (SU(3) quadratic Casimir):**
   - C_2(3) = C_2(1,0) = (1 + 0 + 0 + 3 + 0)/3 = 4/3
   - C_2(6) = C_2(2,0) = (4 + 0 + 0 + 6 + 0)/3 = 10/3
   - C_2(3-bar) = C_2(0,1) = (0 + 1 + 0 + 0 + 3)/3 = 4/3

   Consistency: C_2(3-bar) = C_2(3) = 4/3. This is expected because 3-bar is the conjugate of 3, and conjugate representations have the same Casimir eigenvalue. Correct.

5. **Physical interpretation:** The symmetric 6 contains the flavor-symmetric diquark states relevant to exotic hadrons (e.g., doubly-charmed baryons treat light quarks as a 3-bar diquark, not a 6). The antisymmetric 3-bar is the diquark content of ordinary baryons in the SU(3) flavor decomposition: the Lambda baryon has an antisymmetric ud pair in the 3-bar.

## Worked Example: SO(3) -> SO(2) Branching Rules and Angular Momentum Selection Rules

**Problem:** Decompose the spin-2 irreducible representation of SO(3) under the SO(2) subgroup (rotation about the z-axis), and derive the selection rules for electric quadrupole transitions. This targets the LLM error class of incorrect subgroup branching — specifically, losing representations during decomposition, confusing irrep labels between the group and subgroup, and getting wrong selection rules from incomplete tensor product decompositions.

### Setup

SO(3) representations are labeled by angular momentum j = 0, 1, 2, ..., with dimension 2j + 1. The subgroup SO(2) (rotations about z-axis) has 1-dimensional irreps labeled by integer m = -j, -j+1, ..., j.

### Step 1: Branching Rule SO(3) -> SO(2)

The irrep j of SO(3) decomposes under SO(2) as:
```
D^j  ->  m = -j  +  m = -j+1  +  ...  +  m = j-1  +  m = j
```

Each 1D irrep m of SO(2) appears exactly once. This is the statement that the spherical harmonics Y_j^m with fixed j and varying m form a complete set for the 2j+1 dimensional representation.

For j = 2 (spin-2):
```
D^2  ->  m = -2  +  m = -1  +  m = 0  +  m = 1  +  m = 2
```

**Dimension check:** 5 = 1 + 1 + 1 + 1 + 1. Correct.

### Step 2: Tensor Product and Selection Rules

Electric quadrupole (E2) transitions are mediated by the quadrupole operator Q^{(2)}_m, which transforms as the j = 2 irrep of SO(3). The matrix element <j_f, m_f | Q^{(2)}_q | j_i, m_i> is nonzero only if:

1. **Triangle rule (SO(3)):** |j_i - 2| <= j_f <= j_i + 2
2. **m-selection rule (SO(2)):** m_f = m_i + q, where q = -2, -1, 0, 1, 2

These follow from the tensor product decomposition:

```
j_i (x) 2 = |j_i - 2| + |j_i - 1| + j_i + (j_i + 1) + (j_i + 2)
```

For j_i = 3:
```
3 (x) 2 = 1 + 2 + 3 + 4 + 5
```

**Dimension check:** (2*3+1)(2*2+1) = 7 * 5 = 35. On the right: 3 + 5 + 7 + 9 + 11 = 35. Correct.

### Step 3: Explicit CG Coefficients for j_i = 2 -> j_f = 0

The transition 2 -> 0 via the quadrupole operator requires:
```
<0, 0 | Q^{(2)}_q | 2, m_i> = <0, 0 | 2, q; 2, m_i> * <2 || Q^{(2)} || 2>_reduced
```

By the m-selection rule: 0 = m_i + q, so q = -m_i. The CG coefficient <j_f=0, m_f=0 | j_1=2, m_1=q; j_2=2, m_2=m_i> is nonzero only if q + m_i = 0, which gives q = -m_i. The CG coefficient is:

```
<0, 0 | 2, q; 2, -q> = (-1)^{2-q} / sqrt(5)
```

For q = 0: <0, 0 | 2, 0; 2, 0> = 1/sqrt(5).
For q = 1: <0, 0 | 2, 1; 2, -1> = -1/sqrt(5).
For q = 2: <0, 0 | 2, 2; 2, -2> = 1/sqrt(5).

**Orthogonality check:** sum_q |<0, 0 | 2, q; 2, -q>|^2 = 5 * (1/5) = 1. Correct.

### Step 4: Physical Application — Nuclear E2 Transitions

For a nuclear transition from a j_i = 4 state to a j_f = 2 state via E2 radiation:

Allowed: 4 -> 2 (since |4-2| = 2 <= 2). The transition rate is:
```
B(E2; 4 -> 2) = (1/(2*4+1)) * |<2 || Q^{(2)} || 4>|^2 = (1/9) * |<2 || Q^{(2)} || 4>|^2
```

The angular distribution of the emitted photon depends on the m_i -> m_f transition. For m_i = 4 -> m_f = 2, the photon carries q = m_i - m_f = 2 (right-circularly polarized along z). For m_i = 4 -> m_f = 4: this requires q = 0, which is the z-component of the quadrupole (longitudinal). For m_i = 4 -> m_f = 3: q = 1.

**Forbidden transitions:** 4 -> 7 is forbidden (|4 - 2| = 2, but 7 > 4 + 2 = 6). 0 -> 0 is forbidden for E2 (need j_f >= |0 - 2| = 2, but j_f = 0 < 2). This is the well-known rule: **0 -> 0 transitions are forbidden for all multipole orders except E0 (monopole).**

### Verification

1. **Dimension conservation.** For every tensor product decomposition, verify that sum of dimensions on the right equals the product on the left. This is the single most reliable check and catches dropped representations.

2. **Branching completeness.** When decomposing j under SO(2), verify that exactly 2j+1 values of m appear, each once. Missing or duplicate m values indicate an error.

3. **CG coefficient orthogonality.** The CG coefficients satisfy two orthogonality relations:
   - sum_{m_1, m_2} |<j, m | j_1, m_1; j_2, m_2>|^2 = 1 (for fixed j, m)
   - sum_{j, m} <j, m | j_1, m_1; j_2, m_2> <j, m | j_1, m_1'; j_2, m_2'> = delta_{m_1 m_1'} delta_{m_2 m_2'}
   Verify both relations numerically for the computed CG coefficients.

4. **Special value check.** <j, j | j, j; 0, 0> = 1 for all j (coupling with the trivial representation). <j, j | j-1, j-1; 1, 1> = sqrt(2j/(2j+1)(2j-1)) — verify against standard tables.

5. **Selection rule consistency.** For E2 transitions, the allowed Delta j values are 0, +/- 1, +/- 2 (but not 0 -> 0). For E1 (dipole), Delta j = 0, +/- 1 (but not 0 -> 0). The additional parity selection rule for E-type radiation requires (-1)^{l_i} != (-1)^{l_f} for El transitions. Verify that the parity rule is not confused with the angular momentum rule.

**The typical LLM error** computes the tensor product 3 (x) 2 = 1 + 2 + 3 + 4 + 5 correctly but then applies the selection rule as Delta j = 2 only (forgetting Delta j = 0, 1). Another common error is stating "0 -> 0 is allowed for E2 because |0 - 2| = 2 >= 0," misapplying the triangle rule. The triangle rule requires j_f >= |j_i - j_op|, so for j_i = 0 and j_op = 2: j_f >= 2, which excludes j_f = 0.

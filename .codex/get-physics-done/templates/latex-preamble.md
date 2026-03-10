---
template_version: 1
---

<!-- Used by: gpd-paper-writer and write-paper workflow. -->

# LaTeX Preamble Template

Template for `.gpd/analysis/LATEX_PREAMBLE.md` - standard LaTeX preamble and macros for the research project.

**Purpose:** Define consistent LaTeX macros for all equations, figures, and writeups across phases. Ensures notation consistency between derivation code, summary documents, and the final manuscript.

---

## File Template

````markdown
# LaTeX Preamble and Macros

**Analysis Date:** [YYYY-MM-DD]
**Last Updated:** [YYYY-MM-DD]
**Document Class:** [e.g., revtex4-2, amsart, article]
**Target Journal:** [e.g., Physical Review Letters, JHEP, none yet]

## Standard Preamble

```latex
% === Packages ===
\usepackage{amsmath, amssymb, amsthm}
\usepackage{physics}          % \bra, \ket, \mel, \dv, \pdv, \abs, \norm, \comm
\usepackage{siunitx}          % SI units: \SI{1.5}{\giga\electronvolt}
\usepackage{mathtools}        % \coloneqq, \shortintertext, better matrices
\usepackage{bbm}              % \mathbbm{1} for identity operator
\usepackage{slashed}          % \slashed{D} for Feynman slash notation
\usepackage{tensor}           % \indices for complex index placement
\usepackage{hyperref}         % Cross-references
\usepackage{cleveref}         % \cref for automatic "Eq. (1)", "Fig. 2", etc.

% === Number sets ===
\newcommand{\R}{\mathbb{R}}
\newcommand{\C}{\mathbb{C}}
\newcommand{\Z}{\mathbb{Z}}
\newcommand{\N}{\mathbb{N}}

% === Operators ===
\DeclareMathOperator{\Tr}{Tr}
\DeclareMathOperator{\tr}{tr}
\DeclareMathOperator{\diag}{diag}
\DeclareMathOperator{\sgn}{sgn}
\DeclareMathOperator{\Real}{Re}
\DeclareMathOperator{\Imag}{Im}
```
````

## Package Conflict Warning

The `physics` package redefines several common commands:
- `\abs{}` — conflicts with custom `\newcommand{\abs}`
- `\norm{}` — conflicts with custom norm definitions
- `\bra{}`, `\ket{}`, `\braket{}` — conflicts with `braket` package
- `\dd` — may conflict with custom differential d

**Resolution:** If using the `physics` package, do NOT define custom versions of these commands. If you need custom behavior, either:
1. Use `physics` package commands as-is, OR
2. Don't load `physics` package and define all macros manually

Never do both — this causes "Command already defined" errors.

## Project-Specific Macros

```latex
% === [Project Name] macros ===

% Fields and operators
% \newcommand{\field}[1]{\hat{#1}}        % Field operators: \field{\psi}
% \newcommand{\op}[1]{\hat{#1}}           % General operators: \op{H}

% Vectors and tensors
% \newcommand{\vb}[1]{\boldsymbol{#1}}    % Bold vectors: \vb{k}, \vb{r}
% \renewcommand{\v}[1]{\boldsymbol{#1}}   % Short form (if no conflict)

% Derivatives (if not using physics package)
% \newcommand{\dd}{\mathrm{d}}            % Upright d for differentials
% \newcommand{\pder}[2]{\frac{\partial #1}{\partial #2}}
% \newcommand{\tder}[2]{\frac{\mathrm{d} #1}{\mathrm{d} #2}}

% Order symbols
% \newcommand{\order}[1]{\mathcal{O}\!\left(#1\right)}

% Common expressions in this project
% \newcommand{\Ham}{\mathcal{H}}          % Hamiltonian density
% \newcommand{\Lag}{\mathcal{L}}          % Lagrangian density
% \newcommand{\action}{\mathcal{S}}       % Action
% \newcommand{\partition}{\mathcal{Z}}    % Partition function
% \newcommand{\avg}[1]{\langle #1 \rangle}  % Ensemble average
% \newcommand{\corr}[2]{\langle #1 \, #2 \rangle}  % Correlator

% Green's functions
% \newcommand{\GR}{G^{\mathrm{R}}}        % Retarded
% \newcommand{\GA}{G^{\mathrm{A}}}        % Advanced
% \newcommand{\GK}{G^{\mathrm{K}}}        % Keldysh

% Self-energy
% \newcommand{\SE}{\Sigma}                % Self-energy
```

## Equation Cross-Referencing Convention

[Phase-aware equation labeling for multi-phase projects]

```latex
% In PLAN documents and summaries, use the convention:
%   Eq. (phase.N) — e.g., Eq. (02.3) = 3rd equation in Phase 02
%   Fig. (phase.N) — e.g., Fig. (05.1) = 1st figure in Phase 05
%
% In LaTeX source files, use:
%   \label{eq:phase02:binding-energy}     % Descriptive labels
%   \label{fig:phase05:dispersion}        % For figures
%   \cref{eq:phase02:binding-energy}      % Auto-generates "Eq. (N)"
%
% Mapping between plan numbering and LaTeX labels:
%   Eq. (02.1) -> \label{eq:phase02:hamiltonian}
%   Eq. (02.2) -> \label{eq:phase02:binding-energy}
%   etc.
```

## Units Convention

```latex
% Use siunitx for all quantities with units:
%   \SI{1.5}{\giga\electronvolt}          % 1.5 GeV
%   \SI{300}{\kelvin}                     % 300 K
%   \SI{2.998e8}{\metre\per\second}       % 2.998 × 10⁸ m/s
%   \si{\hbar\per\electronvolt}           % ℏ/eV (unit only)
%
% For natural units, define:
%   \newcommand{\natunit}[1]{\,[\text{#1}]}  % Dimension in natural units
%   % Usage: E \natunit{energy}, k \natunit{momentum}
```

## Figure Standards

```latex
% Figure template for publication quality:
%
% \begin{figure}[t]
%   \centering
%   \includegraphics[width=\columnwidth]{figures/fig_description.pdf}
%   \caption{%
%     [Short description for list of figures.]
%     [Detailed description: what is plotted, parameter values, key features to observe.]
%     [Reference to relevant equation: "The solid line shows Eq.~\eqref{eq:...}"]
%   }
%   \label{fig:phaseXX:description}
% \end{figure}
%
% Requirements:
% - Vector format (PDF) for line plots, high-res PNG/TIFF for density plots
% - Font size in figure ≥ caption font size
% - Axes labeled with quantity AND units: "$E$ [\si{\electronvolt}]"
% - Legend if multiple curves; avoid more than 5-6 curves per panel
% - Colorblind-friendly palette (avoid red-green only distinction)
```

## SymPy-to-LaTeX Integration

```python
# When generating LaTeX from SymPy, use consistent formatting:
#
# from sympy import latex, Symbol, Function
#
# # Define symbols matching LaTeX macros:
# psi = Symbol(r'\psi')
# H = Symbol(r'\mathcal{H}')
#
# # Export with custom settings:
# latex_str = latex(expr,
#     mode='equation',
#     itex=False,
#     mul_symbol='dot',       # or 'times' or None
#     inv_trig_style='asin',  # not 'arcsin'
# )
#
# # For matrices, ensure proper formatting:
# latex_str = latex(matrix, mat_str='pmatrix')  # or 'bmatrix'
```

---

_LaTeX preamble: [date]_
_Update when new macros are needed or journal target changes_

```

<guidelines>
**What belongs in LATEX_PREAMBLE.md:**
- Standard package imports for the project type
- Project-specific macro definitions
- Equation and figure labeling conventions
- Units formatting standards
- SymPy-to-LaTeX integration notes
- Figure quality requirements

**What does NOT belong here:**
- Full LaTeX document template (that depends on journal choice)
- Derivation content (that lives in phase files)
- Every possible LaTeX package (only those actually used)

**When filling this template:**
- Uncomment and customize the macros relevant to the project
- Delete sections for unused notation (e.g., no Dirac notation if not doing QM)
- Add project-specific macros as needed during phases
- Keep macros minimal: only define what's used in 3+ places

**Why a shared preamble matters:**
- Notation consistency: $\mathcal{H}$ vs $H$ vs $\hat{H}$ for Hamiltonian across phases
- Efficient paper writing: macros defined once, used everywhere
- Error prevention: changing a convention updates all uses via macro redefinition
- Journal compliance: preamble adapts to target journal's requirements

**Relationship to other templates:**
- CONVENTIONS.md defines the physics choices (metric, units, signs)
- NOTATION_GLOSSARY.md lists all symbols with meanings
- LATEX_PREAMBLE.md implements those choices as LaTeX macros
- All three should be consistent; update together when conventions change
</guidelines>
```

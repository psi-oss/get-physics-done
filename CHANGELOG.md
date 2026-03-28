# Changelog

All notable changes to Get Physics Done are documented here.

## vNEXT

- Split releases into a manual release-PR preparation workflow and a separate publish workflow for PyPI, npm, tags, and GitHub Releases.
- Add differentiable simulation reference protocol for autodiff-through-solver workflows (Warp, JAX, PyTorch, Taichi).
- Add containerized NVIDIA Warp compute template with CPU/GPU Dockerfiles and three worked examples (1D PDE optimization, ODE parameter estimation, 2D design with variable conductivity).
- Add `synthesize-implementations` command and workflow for N-way implementation comparison and unification.
- Add three bootstrap error patterns for differentiable simulation (forward/gradient iteration mismatch, uniform properties in heterogeneous domains, FD gradients when autodiff available).

## v1.1.0

- Public open-source release.
- Multi-runtime support for Claude Code, Gemini CLI, Codex, and OpenCode.
- Structured physics research workflows for planning, execution, verification, and publication support.

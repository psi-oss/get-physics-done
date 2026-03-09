# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | Yes                |

## Reporting a Vulnerability

If you discover a security vulnerability in GPD, please report it responsibly.

**Email:** security@getphysicsdone.com

**Do not** open a public GitHub issue for security vulnerabilities.

### What to include

- Description of the vulnerability
- Steps to reproduce
- Affected version(s)
- Impact assessment (if known)

### Response Timeline

- **48 hours** -- acknowledgment of your report
- **7 days** -- initial assessment and severity classification
- **30 days** -- target for fix or mitigation (critical issues faster)

We will coordinate disclosure with you and credit reporters unless anonymity is requested.

## Scope

### In scope

- Vulnerabilities in GPD Python code (`src/gpd/`)
- MCP server security issues (7 tool servers in `src/gpd/mcp/servers/`)
- Runtime adapter vulnerabilities (file writes, config injection)
- Authentication or authorization bypasses
- Path traversal or arbitrary file access
- Command injection via user input

### Out of scope

- LLM behavior (hallucinations, prompt injection against the underlying model)
- Physics correctness (wrong equations, incorrect derivations)
- Vulnerabilities in upstream dependencies (report those to the respective projects)
- Issues requiring physical access to the machine

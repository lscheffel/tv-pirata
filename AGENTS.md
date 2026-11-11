# AGENTS.md — Workspace AgentOps & Engineering Standard (SSOT)

## 1. Overview & Identity

This workspace operates under agentic governance and deterministic engineering guided by the **SynPraxis AgentOps Platform**.
All canonical guidelines for architecture, code patterns, testing standards, and lifecycle management are formally anchored in this document.

---

## 2. Engineering Invariants for AI Agents

1. **Anti-Stub Invariant:** Every component, API contract, route, or utility must have a complete physical implementation. Permissive mocks that mask runtime exceptions in production components are strictly prohibited.
2. **Quality & Strict Typing:** Python code must adopt complete type hints (`from __future__ import annotations`), passing cleanly through linter checks (`ruff`) and test suites (`pytest`).
3. **RAG-First Protocol:** Before planning structural changes or complex refactoring, query the repository knowledge store via CLI (`spx search` or MCP `rag_hybrid_search`) to map existing patterns and architecture decisions.
4. **ADR Governance:** Significant architectural changes (DCI $\ge 1.5$) must be recorded via Quadra SOTA in `docs/adr/` (`ADR-XXX.md`, `ADR-XXX-BP.md`, `ADR-XXX-TODO.md`, `ADR-XXX-PI.md`).
5. **Zero Orphaned Servers:** Agents must never terminate sessions leaving dev servers or daemon processes running in the background without explicit request.
6. **Invariant Linguistic Governance (Dual Consumption: PT-BR vs EN-US):**
   - **Human Consumption & Chat (PT-BR):** Documentation intended for human reading and consumption (operational manuals, executive summaries, task reports, web portals) and all interactive chat communication with the user must be written in **Portuguese (PT-BR)**.
   - **Agentic Consumption & Code (EN-US):** Artifacts consumed directly by AI agents (Agent Skills, system prompts, LLM context payloads, structured schemas) and all source code (application code, tests, typing, technical API docstrings, and commit messages) must be written strictly in **English (EN-US)**.

---

## 3. Useful Commands Matrix

| Command | Description |
| :--- | :--- |
| `make test` | Runs the automated test suite via pytest |
| `make lint` | Runs static code analysis with ruff |
| `make format` | Automatically formats source code |
| `make setup-hooks` | Configures the Git pre-commit hook in the local repository |
| `spx sync` | Synchronizes and reindexes the workspace vector store |
| `spx audit` | Runs forensic quality audit across the workspace |

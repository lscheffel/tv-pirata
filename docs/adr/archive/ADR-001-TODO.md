---
id: ADR-001-TODO
title: "TODO: Arquitetura Fundamental do TV Pirata"
adr_ref: ADR-001
created: "2026-11-11"
status: CONSOLIDATED
---

# Checklist de Implementação — ADR-001

- [x] Provisionar estrutura canônica de repositório e governança (`AGENTS.md`, `GEMINI.md`, `Makefile`, `.gitignore`).
- [x] Configurar ambiente virtual Python 3.14 com gerenciador `uv`.
- [x] Configurar pre-commit quality gate (`scripts/quality_gate.sh`).
- [x] Mapear variáveis de ambiente essenciais em `.env.example` (TMDB, TVMaze, caminhos SMB).
- [x] Definir modelo fundamental de separação entre descoberta e playback via SMB.
- [x] Formalizar ADR-001 no índice canônico de arquitetura.

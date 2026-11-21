# HANDOFF DE SESSÃO — TV Pirata: Hidratação 3-Pilares (`ADR-015`) & Settings IDE (`ADR-016`)
**Data/Hora:** 2026-11-20 01:24 | **Status:** Concluído (Pronto para Lapidação Final UI/UX & Release de Verão) | **Modo:** Simples

## 1. Objetivo & Critério de Pronto (DoD)
Backend 3-Pilares (`ADR-015`) e redesign Master-Detail das Configurações com telemetria viva (`ADR-016`) estão implementados, testados (`77 passed`), compilados e enviados para `origin/UI-UX` (`9e487fa`). Próximo passo natural: lapidação visual final do restante da SPA (`ExplorerView`, `SourcesView`, `TorrentModal`) ou execução contínua da hidratação nos bancos locais.

## 2. Invariantes & Decisões Fechadas (NÃO ALTERAR)
- **Dual-SSOT Isolado:** `data/mainstream.db` (`IMDbCatalogShow` + `MediaWork` + `sync_state`) é soberano sobre metadados; `data/sources.db` (`EZTVShow` + `ExternalSourceRecord` + `ExternalRelease`) isola fontes P2P.
- **Cascata 6-Níveis Não Destrutiva (`COALESCE`):** Ordem estrita `IMDb -> TMDB -> TVMaze -> EZTV -> YIFY -> Outras Fontes Abertas` (`src/backend/services/cascading_enricher.py`); campos preenchidos nunca são sobrescritos.
- **Endpoints Async p/ Tasks:** Rotas que chamam `asyncio.create_task` (ex.: `start_hydration_pipeline` em `src/backend/api/explore.py:274`) DEVEM permanecer `async def`.
- **Gate de Qualidade:** `make lint`, `make test` (`77 passed`), `npx tsc --noEmit`, `make build-front` e regra de idioma (`AGENTS.md` §2.8: código/commits em EN-US; chat/docs humanas em PT-BR).
- **Porta do Servidor:** `make run` atualizado para `.venv/bin/python -m uvicorn src.backend.main:app --host 0.0.0.0 --port 8005 --reload`.

## 3. Evidências & Estado Real do Workspace
- **Arquivos modificados/criados (principais):**
  - `src/backend/services/hydration_orchestrator.py`: `SmartBootstrapDetector`, `HydrationOrchestratorService`, checkpoint `sync_state['hydration_pipeline_v1']` e telemetria viva em memória (`rate_per_minute`, `eta_seconds`, `current_target`, `recent_events`).
  - `src/backend/services/cascading_enricher.py`: `cross_db_self_heal` + cascata de 6 degraus + callback `on_progress`.
  - `src/backend/providers/sources/{yify_adapter.py,torrent_api_py_adapter.py,base.py}` e `src/backend/services/sources_registry.py`: `compact_presence` em Batch UPSERT, paginação real, parser bilíngue Nyaa e `sweep_canonical_catalog_presence`.
  - `src/frontend/src/components/{StatusConfigView.tsx,HydrationConsoleCard.tsx}` e `src/frontend/src/components/settings/{SettingsSidebar.tsx,CatalogUpdatePanel.tsx,SourcesProvidersPanel.tsx,ExplorePrefsPanel.tsx,AdvancedMaintenancePanel.tsx}`: layout Master-Detail 2 colunas + linguagem humana + Monitor de Atividade.
  - `scripts/hydrate_ecosystem.py` (`make hydrate`) e `tests/integration/test_three_pillar_hydration.py`.
- **Estado verificado nos bancos locais:** `IMDb=DELTA` (`279.362` obras), `EZTV=DELTA` (`860` séries), `yify` em `BOOTSTRAP` (`1.448` títulos, cursor `p.30/1572`), `tgx` (`303`), `glodls` (`199`, `sweep @6`), `bitsearch` (`69`), `nyaasi` (`9`).
- **Armadilhas conhecidas:** `spx sync` remoto retorna `410 Gone` (não executar); evitar testes com Chrome/browser subagent neste ambiente headless.
- **Pendências abertas:** Nenhuma pendência de código aberta para `ADR-015`/`ADR-016` (working tree limpo em `9e487fa`).

## 4. Gatilho de Execução
> **Instrução para o próximo agente:** Leia os arquivos listados na Seção 3 e inicie a execução imediatamente sem solicitar confirmação inicial.

- [ ] **Etapa 1 — Lapidação UI/UX ou Expansão de Hidratação:** Abrir nova frente de lapidação visual (`ExplorerView.tsx`, `SourcesView.tsx`, `TorrentModal.tsx`) conforme solicitação do usuário para fechar a *Release de Verão*, ou rodar `make hydrate` para avançar os cursores de `data/sources.db` | **Validação:** `make lint && make test && cd src/frontend && npx tsc --noEmit && cd ../.. && make build-front`

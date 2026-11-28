# Fase 8 — Relatório de Re-Auditoria & Certificação · ADR-021

## 1. Matriz de Fechamento dos Achados da Fase 2

| Achado | Severidade Original | Status Pós-Elevação | Verificação na Quadra Hardened |
| :--- | :---: | :---: | :--- |
| **F-01** | CRITICAL | **RESOLVIDO** | `DEC-001` / `AMP-01` / `BP §2.1`: Download HTTP paralelo sem conexão SQLite + pausa cooperativa exclusiva na janela de commit/FTS5/facets. |
| **F-02** | CRITICAL | **RESOLVIDO** | `DEC-001` / `AMP-01` / `T1.2`: `PYTEST_CURRENT_TEST` isolado do `mainstream_engine` real + limpeza de `.tmp` órfãos. |
| **F-03** | MAJOR | **RESOLVIDO** | `DEC-003` / `AMP-03` / `BP §2.4`: Alocação de deduplicação em ordem de escassez crescente dos pools (Personalizadas e *Séries em Exibição* primeiro) com reordenação final na ordem visual. |
| **F-04** | MAJOR | **RESOLVIDO** | `DEC-002` / `AMP-02` / `BP §2.2`: Paginação EZTV com teto `25` págs, parada após `2` págs consecutivas conhecidas, delay `0.35s` e backoff exponencial em `429/5xx`. |
| **F-05** | MAJOR | **RESOLVIDO** | `DEC-007` / `AMP-06` / `BP §2.3`: `UserExplorePreferences` aceita `schema_version: Literal[1, 2] = 2` com migração automática backward-compatible de payloads v1. |
| **F-06** | MINOR | **RESOLVIDO** | `DEC-006` / `AMP-05` / `BP §3`: `catalogFilters: FilterSnapshot` elevado em `App.tsx` preservando filtros entre abas. |
| **F-07** | OBSERVATION | **RESOLVIDO** | `DEC-001` / `AMP-01` / `T4.5`: `IMDbSyncJobStatus` expõe `remote_last_modified`, `local_last_modified`, `delta_inserted`, `delta_updated` e `cache_status`. |

## 2. Verificação dos 5 Critérios de Portfolio Coverage Audit (`adr-generator` Fase 4)

- [x] **100% Cobertura do Ledger:** Todas as 7 decisões `CONFIRMED` (`DEC-001`..`DEC-007`) e restrição (`DEC-009`) estão mapeadas 1:1 em `ADR`, `BP`, `PI` e `TODO` (`T1.1`..`T5.3`).
- [x] **Alternativas Documentadas:** Todas as 5 ideias derrubadas no Garimpo (`DEC-008`) e as 3 alternativas descartadas na Matriz (`Alt A`, `Alt C`, `Alt D`) possuem justificativa e evidência física.
- [x] **Sem Decisões Disfarçadas:** Os 3 itens em aberto da Rodada 3 foram fechados com defaults explícitos e configuráveis na Fase 6.
- [x] **Grafo Acíclico de Dependências:** `ADR-021` depende exclusivamente de ADRs anteriores (`ADR-011`, `012`, `014`, `015`, `016`, `018`, `020`).
- [x] **Invariante Zero-Stub e Zero-Dependência Extra:** Todos os contratos utilizam a stack existente do repositório sem pseudo-código ou bibliotecas extras.

## 3. Veredicto de Certificação

- **CRITICAL em aberto:** `0`
- **MAJOR em aberto:** `0`
- **Status:** **✅ CERTIFICADO PARA PROMOÇÃO A `docs/adr/`**

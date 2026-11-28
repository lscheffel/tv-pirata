# Fase 4 — Matriz Comparativa de Avaliação (11 Dimensões) & Blast Radius · ADR-021

## 1. Cálculo Oficial do Blast Radius Index ($BR$)

Calculado algoritmicamente via `matrix_scorer.py`:

$$BR = (N_{\text{dependents}} \times 1.5) + (R_{\text{data}} \times 2.0) + (H_{\text{rollback}} \times 0.5)$$

| Variável | Valor | Justificativa Empírica |
| :--- | :---: | :--- |
| $N_{\text{dependents}}$ | `5` | 5 subsistemas consumidores: (1) `imdb_sync_service` + `imdb-metadata-catalog.py`, (2) `hydration_orchestrator` + `catalog_indexer` + `sources_registry`, (3) `discovery_engine` + `preferences`, (4) `App.tsx` + `Navbar.tsx` + `DiscoverView`/`CatalogView` + `ShowCarousel`/`HeroBanner`, (5) `SettingsSidebar` + `StatusConfigView`. |
| $R_{\text{data}}$ | `2` | Evolução de estado com dual-write controlado (`catalogrelease` → `external_releases`/`EZTVShow` em `sources.db`) + migração aditiva backward-compatible `user_explore_preferences` v1 → v2 + nova chave `discovery_impressions_v1` em `sync_state`. Zero migração destrutiva. |
| $H_{\text{rollback}}$ | `1.5` | 1.5h para reverter commit/rotas mantendo tabelas legadas intactas e `sync_state` retrocompatível. |
| **$BR$ Final** | **`12.25`** | **CRITICAL (One-Way Door)** → Protocolo Adversarial Red Team / Blue Team executado na Fase 3. |

---

## 2. Matriz Comparativa Ponderada (11 Dimensões Canônicas)

Executado via `/home/loupan/.gemini/config/skills/adr-architecture-elevation/scripts/matrix_scorer.py` (`weight_sum = 1.00`):

| Critério | Peso | Alt A (Original) | Alt B (Amplificada & Blindada) | Alt C (Worker Daemon) | Alt D (Client-Side) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Correctness** | `0.14` | 8.2 | **9.4** | 8.8 | 6.5 |
| **Code/Ops Complexity** | `0.09` | 6.8 | 7.6 | 4.8 | **8.8** |
| **Robustness** | `0.13` | 7.2 | **9.3** | 8.6 | 6.2 |
| **Testability** | `0.08` | 7.5 | **9.1** | 6.8 | 8.0 |
| **Operability** | `0.10` | 7.4 | **9.2** | 6.5 | 6.0 |
| **Performance ($P_{95}$)** | `0.12` | 7.8 | **9.1** | 9.0 | 6.8 |
| **Security (STRIDE)** | `0.06` | 8.0 | **8.8** | 8.2 | 8.2 |
| **Maintainability** | `0.10` | 7.8 | **9.0** | 6.2 | 7.4 |
| **Build/Run Cost** | `0.05` | 7.8 | 8.2 | 5.5 | **9.0** |
| **Reversibility** | `0.07` | 7.6 | 8.9 | 5.4 | **9.0** |
| **Scalability** | `0.06` | 7.5 | 8.8 | **9.4** | 5.8 |
| **TOTAL PONDERADO** | **`1.00`** | **`7.60`** | **`8.94`** 🏆 | **`7.39`** | **`7.22`** |

### Resultado Algorítmico
- **Vencedora:** **`Alt_B_Amplified_Hardened` (`8.94`)**
- **2º Lugar:** `Alt_A_Original_Proposal` (`7.60`) — **Margem de vitória: `+1.34` pontos**
- **3º Lugar:** `Alt_C_Decoupled_Worker_EventBus` (`7.39`)
- **4º Lugar:** `Alt_D_Client_Side_Shuffle_Minimal` (`7.22`)

## 3. Análise de Sensibilidade

Mesmo dobrando o peso de *Simplicidade/Custo* (`complexity` + `cost`), **Alt B** mantém liderança confortável sobre Alt D porque Alt D falha estruturalmente em *Correctness* (`6.5`) e *Robustness* (`6.2`) — não resolve deduplicação sobre `279k` obras, nem persistência cross-device de impressões, nem isolamento de locks no IMDb/EZTV. Da mesma forma, Alt C perde severamente em *Complexity* (`4.8`), *Reversibility* (`5.4`) e *Operability* (`6.5`) para um ecossistema local single-process.

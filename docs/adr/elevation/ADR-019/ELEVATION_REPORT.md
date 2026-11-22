---
adr_ref: ADR-019
elevation_version: "2.0.0"
blast_radius: 6.75
tier: "Standard (3.0 <= BR < 7.0)"
verdict: "KEEP + AMPLIFY"
updated: "2026-11-22"
---

# Relatório de Elevação Arquitetural — ADR-019

## 1. Modelo Independente do Problema & Blast Radius ($BR$)
- **$N_{\text{dependents}} = 3$** (`YIFYSourceAdapter`, `SourcesRegistryService`, `HydrationOrchestratorService`)
- **$R_{\text{data}} = 1$** (limpeza seletiva de marcadores `yts:presence:*` incompatíveis/fantasmas em `sources.db`)
- **$H_{\text{rollback}} = 0.5$**
- **$BR = (3 \times 1.5) + (1 \times 2.0) + (0.5 \times 0.5) = 6.75$** (`Standard`)

## 2. Auditoria Forense & Desafios Adversariais

| ID | Severidade | Achado Adversarial | Amplificação Incorporada |
| :--- | :---: | :--- | :--- |
| `F-01` | **CRITICAL** | `prune_obsolete_releases` consultando `mainstream.db` com `IN (...)` para todos os ~65.869 marcadores `yts:presence:*` causaria `sqlite3.OperationalError: too many SQL variables`. | **`AMP-01`:** Executar a verificação cruzada `yts:presence:*` vs `tvSeries`/`tvMiniSeries` em chunks de `500` IDs (ou `json_each`) tanto no `SELECT` em `mainstream.db` quanto no `DELETE` em `sources.db`. |
| `F-02` | **MAJOR** | Se `yts.mx`/`yts.lt` estiverem bloqueados por DNS/ISP, `official_first` tentaria mirrors mortos repetidamente a cada requisição. | **`AMP-02`:** Cachear em memória por processo o último mirror saudável (com TTL de 10 min) para que `official_first` não sofra timeouts repetidos quando `yts.mx`/`yts.lt` estiverem inacessíveis. |
| `F-03` | **MAJOR** | BTIH de 32 caracteres no padrão BitTorrent usa Base32 (`A-Z2-7`), enquanto 40 caracteres usa Hex (`0-9a-fA-F`). Validar "32 hex" rejeitaria Base32 válido. | **`AMP-03`:** Validar `_is_valid_btih(h)` com regex estrito `^(?:[0-9a-fA-F]{40}|[A-Z2-7]{32})$`. |
| `F-04` | **MINOR** | Auto-cura no Stage 2 JIT removendo `yts:presence:*` sem recalcular contadores deixaria `total_releases` em `external_sources` desatualizado até o próximo sync. | **`AMP-04`:** Chamar `cls._recompute_source_counters(sources_session)` ao remover marcadores fantasmas no Stage 2 JIT. |

## 3. Veredito
**`KEEP + AMPLIFY` — Decision Set Certificado para Implementação Imediata.**

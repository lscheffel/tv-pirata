---
elevation_target: ADR-013
phase: 4
title: "Avaliação Comparativa, Cálculo de Blast Radius (BR) & Revisão Adversarial Red/Blue Team"
status: COMPLETED
language: PT-BR
---

# Fase 4 — Avaliação Comparativa & Blast Radius ($BR$)

## 1. Cálculo Determinístico de Blast Radius (`matrix_scorer.py`)

Aplicando a fórmula canônica:

$$BR = (N_{\text{dependents}} \times 1.5) + (R_{\text{data}} \times 2.0) + (H_{\text{rollback}} \times 0.5)$$

Parâmetros da `ADR-013`:
- $N_{\text{dependents}} = 4$ (Camada `providers/sources` & `SourcesRegistryService`, Rotas `/api/sources/*` + `DiscoveryEngineRepository`, Esquema `sources.db` (`external_sources` / `external_releases`), UI `StatusConfigView`/`TorrentModal`/`ExplorerView`)
- $R_{\text{data}} = 1$ (Evolução aditiva via `ALTER TABLE` idempotente em `data/sources.db`, preservando 100% dos registros EZTV e `eztv_metadata`)
- $H_{\text{rollback}} = 1.0$ (Alta reversibilidade com defaults retrocompatíveis e preservação total de `EZTVShow` / `/api/catalog/*`)

**Saída verificada de `.venv/bin/python .../scripts/matrix_scorer.py`:**
```text
BR=8.5 | Category=CRITICAL | Gate=One-Way Door: Mandatory Multi-Agent Red Team / Blue Team adversarial review.
Sum weights: 1.0
Matrix: {'weighted_totals': {'Alt_A_Registro_1a1_Estatico': 6.67, 'Alt_B_Scrapers_InProcess_DOM': 6.75, 'Alt_C_Adapter_1N_Sidecar_LazyCache': 9.38}, 'ranking': ['Alt_C_Adapter_1N_Sidecar_LazyCache', 'Alt_B_Scrapers_InProcess_DOM', 'Alt_A_Registro_1a1_Estatico'], 'winner': 'Alt_C_Adapter_1N_Sidecar_LazyCache', 'margin': 2.63}
```

---

## 2. Matriz Comparativa Ponderada (11 Critérios)

| Critério | Peso | `Alt A` (1:1 Estático) | `Alt B` (Scrapers DOM) | `Alt C` (Adapter 1:N + Sidecar + Lazy) |
| :--- | :---: | :---: | :---: | :---: |
| **1. Extensibilidade 1:N** | 0.14 | 4.5 | 7.0 | **9.5** |
| **2. Isolamento Dual-SSOT (`sources.db`)** | 0.12 | 8.5 | 8.0 | **9.5** |
| **3. Segurança (Whitelist URI & Segredos)** | 0.12 | 6.0 | 6.5 | **9.5** |
| **4. Qualidade do Lazy-Cache & Entity Res.** | 0.10 | 6.5 | 7.5 | **9.0** |
| **5. Resiliência & Circuit Breaker 2 Níveis** | 0.10 | 6.0 | 5.0 | **9.5** |
| **6. Clareza UX p/ CAPTCHA/Challenge** | 0.10 | 5.5 | 7.0 | **9.5** |
| **7. Perfil Enxuto de Dependências** | 0.08 | 9.0 | 3.5 | **9.5** |
| **8. Deshardcoding UI/Facetas** | 0.08 | 5.0 | 8.0 | **9.5** |
| **9. Testabilidade Hermética (`respx`)** | 0.06 | 8.0 | 5.5 | **9.5** |
| **10. Retrocompatibilidade EZTV (`eztv_metadata`)** | 0.05 | **9.5** | 9.0 | **9.5** |
| **11. Simplicidade Operacional** | 0.05 | **8.5** | 7.5 | **8.0** |
| **Total Ponderado (`matrix_scorer.py`)** | **1.00** | **6.67** | **6.75** | **9.38** |

**Margem de vitória:** **`+2.63`** pontos sobre `Alt_B_Scrapers_InProcess_DOM`.

---

## 3. Revisão Adversarial Red Team / Blue Team (`BR = 8.5` Gate)

### Vetores do Red Team & Defesas Blue Team
1. **`RT13-01` — Bloqueio de Migração em `sources.db` já existente:**
   - *Ataque:* Instalar `ADR-013` sobre uma `data/sources.db` já populada na `ADR-012` quebra `SELECT` por ausência de `adapter_key`, `config_json` ou `match_confidence`.
   - *Defesa Blue Team:* `init_eztv_db` executa inspeção de colunas via `inspect(active_engine)` e aplica `ALTER TABLE ADD COLUMN` idempotente apenas para colunas ausentes, populando `adapter_key` default nas instâncias existentes (`eztv`, `yify`, `1337x`) sem apagar dados.
2. **`RT13-02` — API Keys Sobrescritas com `"••••"` ao Editar Config na UI:**
   - *Ataque:* Como o `GET /api/sources/summary` mascara `api_key` para `"••••1234"`, ao usuário salvar outro campo no formulário da UI (`timeout` ou `mirrors[]`), o frontend reenvia `"••••1234"` e destrói a chave verdadeira salva!
   - *Defesa Blue Team:* Regra estrita no backend (`PUT/PATCH /api/sources/{key}`): campos `secret=True` recebendo valor vazio ou padrão mascarado/sentinel preservam o valor secreto anterior armazenado; somente alteração explícita de novo valor substitui o segredo.
3. **`RT13-03` — Flood de Busca Paralela & Race Condition no `TorrentModal.tsx`:**
   - *Ataque:* Usuário alterna rapidamente entre séries no catálogo disparando múltiplos `GET /api/sources/releases?live=auto` concorrentes que saturam sidecars e sobrescrevem o modal com dados de outra série.
   - *Defesa Blue Team:* Uso obrigatório de `AbortController` no `TorrentModal` + `asyncio.gather(..., return_exceptions=True)` com `timeout_seconds` rígido (padrão `5s`) e semáforo por instância no backend.
4. **`RT13-04` — Envenenamento de `MediaBadge` por Título Curto/Genérico:**
   - *Ataque:* Série chamada `"Dark"` (2017) ou `"Home"` dá match falso de string em buscas do `1337x` para qualquer filme com `"Dark"` no título, gravando no `imdb_id` errado.
   - *Defesa Blue Team:* Gate duplo no `EntityResolutionService`: exigir score composto `>= 0.85` (considerando distância normalizada de título exato **+** verificação de ano ±1 quando disponível **+** compatibilidade de tipo filme vs série SxxExx); títulos genéricos sem match de ano/episódio ficam retidos abaixo de `0.85` (apenas em `approx_matches` volátil da sessão).

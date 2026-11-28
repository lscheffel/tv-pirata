# Fase 3 — Desafio Arquitetural & Revisão Adversarial Red Team / Blue Team · ADR-021

> **Gatilho de Protocolo Crítico:** Como o Blast Radius calculado é $BR = 12.25 \ge 7.0$ (**CRITICAL / One-Way Door**), esta fase executa obrigatoriamente o **Protocolo Adversarial Red Team vs. Blue Team** sobre as 4 alternativas arquiteturais concorrentes.

---

## 1. Alternativas no Espaço de Design

| Alternativa | Descrição Arquitetural |
| :--- | :--- |
| **Alt A — Proposta Original (Garimpo R3 bruto)** | IMDb 2-estágios simples + EZTV dual-write + `DiscoveryFeedService` em alocação sequencial + cisão `DiscoverView`/`CatalogView` + preferências v2 simples. |
| **Alt B — Arquitetura Amplificada & Blindada (Candidata Elevada)** | Evolução de Alt A com todas as 6 blindagens (`AMP-01`..`AMP-06`): coordenação estrita 2-estágios IMDb (download sem lock → commit cooperativo + `global_facets_v2` + isolamento de testes), EZTV watermark com backoff e varredura de Biblioteca, `DiscoveryFeedService` com **alocação por escassez crescente** + `POST /impressions` debounced + normalização bilíngue de `showrecord`, `FilterSnapshot` elevado em `App.tsx`, `ShowCarousel` com janela circular virtualizada (~24 nós) e `UserExplorePreferences` retrocompatível v1/v2. |
| **Alt C — Worker Externo Dedicado + Event Bus Local** | Separar ingestão IMDb/EZTV e pré-computação das 10 listas em um processo daemon separado comunicando via tabela de fila/eventos em SQLite + cache materializado em disco. |
| **Alt D — Client-Side Shuffle Minimalista** | Manter endpoints atuais (`trending`, `curatedSections`, `explore/works`), corrigir apenas bugs pontuais de IMDb/EZTV e realizar embaralhamento, deduplicação e filtragem das 10 listas no navegador React. |

---

## 2. Protocolo Adversarial Red Team vs. Blue Team ($BR = 12.25$)

### Ataque Red Team #1 — "O download de 760 MB do IMDb no *Atualizar Novidades* vai congestionar a rede ou travar o SQLite"
- **Ataque (Red Team):** Baixar `ratings` (8.8 MB) + `basics` (231 MB) + `akas` (523 MB) automaticamente toda vez que o usuário clicar em *Atualizar Novidades* pode travar a UX ou derrubar o commit dos Sidecars com `database is locked`.
- **Defesa & Contramedida (Blue Team — `AMP-01`):**
  1. O *Atualizar Novidades* faz apenas 3 requisições `HTTP HEAD` (<1.5s no total). Se `ETag`/`Last-Modified` coincidir com `.imdb_cache/*.meta.json` **ou** o último sync bem-sucedido tiver menos de 24h, **zero bytes são baixados**.
  2. Quando há revisão nova (>24h), o estágio de **download** roda em `asyncio.create_task` + `asyncio.to_thread` **sem abrir conexão SQLite**, gravando em `.tmp` atômico (limpando `.tmp` órfãos no startup) enquanto o ciclo P2P termina normalmente.
  3. Apenas na etapa de **aplicação** (após o ciclo P2P concluir ou sob pausa cooperativa do orquestrador) o SQLite é aberto em WAL para aplicar o delta, reconstruir o FTS5 e recalcular `global_facets_v2`, expondo progresso em tempo real no card IMDb.

### Ataque Red Team #2 — "Deduplicação total de 1.000 títulos em 10 listas vai quebrar latência ou gerar listas vazias"
- **Ataque (Red Team):** Executar 10 queries complexas sobre `279.362` obras + `74.392` chaves de `sources.db` + deduplicar 1.000 itens com variância a cada abertura de aba pode ultrapassar 2 segundos ou esvaziar listas com poucos candidatos.
- **Defesa & Contramedida (Blue Team — `AMP-03`):**
  1. O índice de disponibilidade de `sources.db` já é servido em memória pelo `EngineScopedCache` (`_build_sources_media_index`).
  2. Cada lista consulta um **pool enxuto pré-filtrado** (ex.: `LIMIT 400` sobre índices SQL existentes `start_year`, `rating_score`, `rating_votes`, `title_type`, `status`) em vez de varrer `279k` linhas completas.
  3. A alocação de deduplicação roda em **ordem de escassez crescente** (Hero → Roleta → 3 Listas Personalizadas → *Séries em Exibição* → demais listas gerais), e se o filtro customizado de alguma lista tiver `< limit` candidatos únicos após deduplicação, aplica fallback controlado preenchendo o restante apenas do próprio pool antes de repetir qualquer item.

### Ataque Red Team #3 — "Dual-write no EZTV vai dessincronizar `catalogrelease` e `external_releases`"
- **Ataque (Red Team):** Escrever em `catalogshow`/`catalogrelease` e também em `external_releases`/`EZTVShow` cria risco de divergência entre contadores e registros duplicados.
- **Defesa & Contramedida (Blue Team — `AMP-02`):**
  1. Tudo ocorre na **mesma transação `sources_session`** dentro de `EZTVIndexerService.sync_pages` usando chave determinística `external_id = str(eztv_id)` em `ExternalRelease` (UPSERT idempotente por `(source_key="eztv", external_id)`).
  2. `_recompute_source_counters` deixa de ignorar `eztv` e passa a computar os contadores reais consolidando `external_releases` (com fallback para `catalogrelease` / `catalogshow` caso `external_releases` ainda esteja em backfill inicial), garantindo 100% de coerência nos cards e no `hydration_pipeline_v1`.

### Ataque Red Team #4 — "Client-Side Shuffle (Alt D) seria muito mais simples de implementar"
- **Ataque (Red Team):** Por que não manter os endpoints atuais e embaralhar tudo no React?
- **Refutação (Blue Team):** Os endpoints atuais entregam no máximo 24 itens em `/trending` e 20 itens por lista sobre apenas `860` séries EZTV em `/catalog/sections`. Para entregar 10 listas × 100 títulos únicos sobre `279.362` obras + `74k` fontes + perfil da Biblioteca + ring-buffer cross-device (`sync_state`), o motor precisa residir no backend (`DiscoveryFeedService`), onde os índices SQLite resolvem em dezenas de milissegundos sem trafegar megabytes para o browser.

### Ataque Red Team #5 — "O processo daemon separado (Alt C) não seria mais escalável?"
- **Refutação (Blue Team):** Em um app single-user local rodando via `make run` (FastAPI + SQLite em arquivo local), um segundo processo daemon viola a política de *Zero Orphaned Servers*, multiplica a complexidade operacional (IPC, supervisão de processos, locks inter-processo no SQLite) e não traz ganho real frente ao modelo cooperativo `lifespan` + `asyncio.to_thread` já consolidado em `ADR-015`..`ADR-020`.

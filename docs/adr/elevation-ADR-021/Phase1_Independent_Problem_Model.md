# Fase 1 — Modelo Independente do Problema (First Principles) · ADR-021

## 1. Enunciado do Problema (Reconstruído de Primeiros Princípios)

Um ecossistema pessoal de descoberta audiovisual local (`SQLite Dual-SSOT`: `data/mainstream.db` + `data/sources.db`) falha em sua promessa central sob duas frentes simultâneas:

1. **Silêncio e Desatualização Falsa na Ingestão de Dados (Camadas 1 e 2):**
   - A base canônica (`IMDb` TSVs) pode estar dias defasada em relação ao servidor oficial (`datasets.imdbws.com`) enquanto a interface reporta estado "atualizado", seja porque o fluxo principal de novidades não consulta a revisão remota, porque execuções de teste contaminam metadados de sincronia do banco real ou porque falhas de rede caem silenciosamente no cache local sem expor delta real (`+0`).
   - A fonte episódica `EZTV` grava lançamentos novos em tabelas legadas (`catalogshow`/`catalogrelease`), mas não unifica contagem em `external_sources`, não alimenta `EZTVShow`/selos `has_eztv` em `mainstream.db` e não participa de varreduras de recuperação para séries acompanhadas na Biblioteca.
2. **Estagnação Estrutural e Acoplamento na Experiência de Descoberta (Camada 1 + Frontend):**
   - Uma vitrine ordenada estaticamente por votos acumulados (`ORDER BY has_eztv DESC, rating_votes DESC`) converge para o mesmo título eternamente (ex.: *A Casa do Dragão* com `578.018` votos) e transforma Roleta e Listas em listas mortas.
   - Empilhar Vitrine de Descoberta e Motor de Busca/Filtros no mesmo componente (`ExplorerView.tsx`, `1.686` linhas) cria fricção severa para alcançar filtros avançados e mistura dois modelos mentais incompatíveis (*"me surpreenda"* vs. *"filtre com precisão"*).

## 2. Objetivos Mensuráveis (Goals)

| ID | Objetivo | Critério Verificável |
| :--- | :--- | :--- |
| **G1** | Frescor verificável do catálogo IMDb | `HEAD` remoto em `ratings`, `basics` e `akas` no ciclo de *Atualizar Novidades*; download automático em background quando revisão > 24h; telemetria explícita de delta (`+obras`, `+atualizadas`, `remote_last_modified`); `global_facets_v2` recalculado ao final. |
| **G2** | Integridade e visibilidade total do EZTV | Paginação por watermark de página (até 25 págs, parada após 2 págs consecutivas conhecidas); contadores reais em `external_sources`/`hydration_pipeline_v1`; espelhamento em `external_releases` + criação de `EZTVShow` + propagação `has_eztv`; suporte opt-in na *Varredura* para séries da Biblioteca. |
| **G3** | Vitrine Viva, Orgânica e Personalizada | Hero auto-rotativo (pausável no hover) com afinidade e memória de impressão; Roleta contextual estratificada em 3 contrastes reais; 10 Listas Inteligentes (7 Gerais + 3 Personalizadas) com até 100 títulos em loop circular virtualizado e **100% únicos entre si** (1.000 títulos distintos); controle de variância `0%–100%`. |
| **G4** | Separação Navegacional & Curadoria Configurável | 5 abas na Navbar (**Descobrir · Catálogo · Fontes · Biblioteca · Coleções**); Atalhos mistos (fixos + dinâmicos + *"Fixar como Atalho"* no Catálogo); 5ª categoria de Configurações (**Vitrine & Listas Inteligentes**) persistida em `sync_state` com compatibilidade v1 → v2. |

## 3. Restrições (Hard & Soft Constraints)

- **Hard Constraints:**
  - **Single-Writer SQLite:** `data/mainstream.db` e `data/sources.db` aceitam apenas 1 escritor concorrente por banco (`WAL` + `busy_timeout=15000`); nunca executar rebuild FTS5 simultaneamente a commits do orquestrador nem mutar SQLite dentro de `GET` HTTP.
  - **Hermeticidade de Testes:** `pytest` jamais pode escrever em `data/mainstream.db` ou `data/sources.db` reais (`PYTEST_CURRENT_TEST` deve respeitar a sessão injetada).
  - **Separação Dual-SSOT (`ADR-011`):** Metadados canônicos residem em `data/mainstream.db`; releases P2P em `data/sources.db`.
  - **Fluidez do Browser:** Renderizar 10 listas × 100 itens não pode montar 1.000 subárvores completas de `ShowCard` simultaneamente no DOM.
  - **Retrocompatibilidade:** Preferências `user_explore_preferences_v1` já gravadas devem migrar automaticamente sem perda de dados.
- **Soft Constraints:**
  - Latência $P_{95} < 400\text{ ms}$ para `GET /api/explore/feed` sobre `data/mainstream.db` (`279k` linhas).
  - Navbar desktop com 5 abas legível em larguras $\ge 1024\text{ px}$ usando rótulos de 1 palavra.

## 4. Invariantes de Sistema

1. **Invariante de Verdade de Sync:** Nenhum job pode reportar `COMPLETED` com "Atualizado hoje" se a validação remota falhou ou reaproveitou cache obsoleto sem informar o status real (`cache_hit`, `network_fallback`, `delta_inserted`, `delta_updated`).
2. **Invariante de Qualidade da Vitrine:** Mesmo em `variance = 100%`, candidatos da Vitrine pertencem a um pool pré-filtrado de qualidade (poster válido, nota/votos acima do piso do bucket), nunca degradando para registros incompletos sem capa.
3. **Invariante de Normalização Bilíngue:** O perfil da Biblioteca (`showrecord`) normaliza gêneros mistos PT-BR/EN-US via `canonical_taxonomy.py` antes de pontuar afinidade.
4. **Invariante de Idempotência de Leitura:** `GET /api/explore/feed` é estritamente *read-only*; o ring-buffer de impressões (`discovery_impressions_v1`) é atualizado apenas via `POST /api/explore/impressions`.

## 5. Atores, Contratos de I/O e Condições de Falha

- **Atores:** Usuário final (Vitrine, Catálogo, Configurações), `HydrationOrchestratorService`, `IMDbCanonicalSyncService`, `EZTVIndexerService` / `SourcesRegistryService`, `DiscoveryFeedService`.
- **Condições de Falha Críticas:**
  - `database is locked` durante rebuild FTS5 paralelo ao orquestrador.
  - Desidratação de listas com bucket menor (*Séries em Exibição*, `1.024` obras) sob deduplicação total se listas amplas consumirem seus itens antes.
  - Rate-limit `HTTP 429` em `eztvx.to` durante paginação de até 25 páginas.
  - Contaminação silenciosa de `sync_state` em produção por testes automatizados.

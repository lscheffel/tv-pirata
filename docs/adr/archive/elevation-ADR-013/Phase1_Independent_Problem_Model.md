---
elevation_target: ADR-013
phase: 1
title: "Modelo Independente de Problema — Sistema Extensível de Plugins para Fontes Externas"
status: COMPLETED
language: PT-BR
---

# Fase 1 — Modelo Independente de Problema (First Principles)

## 1. Enquadramento do Problema (Sem Solução Prematura)

Após a entrega da `ADR-012`, a Camada 2 (`data/sources.db`) já possui tabelas genéricas multi-provedor (`ExternalSourceRecord` e `ExternalRelease` isoladas em `sources_metadata`), endpoints `/api/sources/*`, a aba **Fontes de Dados** (`SourcesView.tsx`) e o modal unificado (`TorrentModal.tsx`). Contudo, adicionar novos provedores como `1337x`, `TorrentGalaxy`, feeds `Torznab` (Prowlarr/Jackett) ou fontes web diretas esbarra em 5 limitações estruturais:

1. **Acoplamento Estático 1:1 e Hardcoding em 4 Camadas:**
   - `REGISTERED_SOURCE_PROVIDERS` em `src/backend/services/sources_registry.py#L222-L226` fixa `1 source_key -> 1 classe Python`.
   - `canonical_taxonomy.py`, `discovery_engine.py` e `ExplorerView.tsx` mantêm listas estáticas (`"yify"`, `"1337x"`), impedindo que novas fontes apareçam dinamicamente após cadastro.
2. **Ausência de Contrato de Busca Sob Demanda (`search()`):**
   - `ExternalSourceProvider` atualmente define apenas `sync()` em lote, modelo adequado para APIs paginadas (`EZTV`, `YTS`), mas inviável para indexadores orientados a busca (`1337x` via sidecar, `Torznab`, sites web únicos).
3. **Inexistência de Proveniência e Expiração no Cache (`ExternalRelease`):**
   - Indexadores sem `imdb_id` precisam de resolução título/ano; sem `match_confidence` nem `last_checked_at` (TTL), falsos positivos de remakes/homônimos poluem `MediaBadge` permanentemente e torrents mortos nunca revalidam.
4. **Tratamento Uniforme Entre Fontes P2P Multi-Mirror e Fontes Únicas Protegidas:**
   - Fontes torrent frequentemente replicam trackers e aceitam fallback silencioso de `mirrors[]`, enquanto fontes únicas não-torrent bloqueadas por reCAPTCHA/Cloudflare Challenge precisam expor aviso explícito com `challenge_url` segura para ação manual do usuário no navegador.
5. **Superfície de Segurança & Isolamento de Falhas:**
   - Armazenar múltiplas URLs, espelhos e `api_key` Torznab em `ExternalSourceRecord` exige mascaramento de segredos na saída API, whitelist de esquemas URI (`http`/`https`/`magnet`) e *circuit breaker* em 2 níveis (por instância e por host sidecar compartilhado).

---

## 2. Invariantes Restritivas

| ID | Invariante | Origem |
| :--- | :--- | :--- |
| `INV-01` | **EZTV & `eztv_metadata` Intactos:** Nenhuma tabela adicional entra em `eztv_metadata` (`test_dual_db_eztv.py` exige exatamente `{"shows", "episodes_catalog"}`); `EZTV` segue como catálogo-base legível sem migração destrutiva. | `ADR-009` / `ADR-012` |
| `INV-02` | **Dependências Runtime Enxutas:** Não adicionar parsers HTML pesados ou engines de browser (`BeautifulSoup`, `lxml`, `playwright`) no backend FastAPI (`pyproject.toml`); usar `httpx` para adapters e sidecars. | `GLOBAL ENGINEERING POLICY` / R1 `1B` |
| `INV-03` | **Anti-CAPTCHA Bypass Compliance:** Jamais automatizar resolução ou contorno de CAPTCHA/anti-bot; detectar o bloqueio e retornar `challenge_url` segura para o usuário abrir no navegador. | Diretriz Global / R2 `2D` |
| `INV-04` | **Camada 1 Agnóstica e Sem Falsos Positivos:** Só gravar vínculo de busca heurística em `imdb_id` (`MediaBadge`) com confiança `>= 0.85` via `EntityResolutionService`. | `AGENTS.md` §2.2 / R2 `5A` |
| `INV-05` | **Segurança Zero-Trust de URLs e Segredos:** Validar esquemas (`http`, `https`, `magnet`) e mascarar campos `secret=True` na saída REST. | `AGENTS.md` / R2 `8C` |

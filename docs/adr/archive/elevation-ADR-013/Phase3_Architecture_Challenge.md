---
elevation_target: ADR-013
phase: 3
title: "Desafio Arquitetural & Exploração do Espaço de Design"
status: COMPLETED
language: PT-BR
---

# Fase 3 — Desafio Arquitetural & Exploração de Alternativas

Para resolver os 3 achados `CRITICAL`, 3 `MAJOR` e 2 `MINOR` da Fase 2 respeitando `INV-01`–`INV-05`, comparamos três arquiteturas candidatas.

---

## 1. Alternativas Avaliadas

### Alternativa A (`Alt_A_Registro_1a1_Estatico`): Evolução Simples 1:1
- **Descrição:** Mantém `1 source_key -> 1 classe Python` em `REGISTERED_SOURCE_PROVIDERS` (adicionando apenas `search()` na classe abstrata), sem separação Adapter/Instância `1:N`, sem `source_diagnostics` estruturado e mantendo listas estáticas em `canonical_taxonomy.py` / `ExplorerView.tsx`.
- **Fortes:** Mudança mínima no curto prazo; zero novas colunas no banco.
- **Fragilidades:** Falha em `AUD13-CRIT-01` (obriga código Python novo para cada feed Torznab ou sub-site do `Torrent-Api-py`), `AUD13-MAJ-01` (sem banner CAPTCHA manual) e `AUD13-MIN-01` (hardcoding contínuo).

### Alternativa B (`Alt_B_Scrapers_InProcess_DOM`): Scrapers HTML Nativos no Backend Principal
- **Descrição:** Porta os 16+ scrapers HTML de `Torrent-Api-py` para dentro do FastAPI adicionando parsers HTML (`beautifulsoup4`, `lxml`, `playwright`) ao `pyproject.toml`, executando parsing DOM diretamente no processo Python principal.
- **Fortes:** Não precisa rodar container/serviço sidecar para sites sem API JSON.
- **Fragilidades:** Quebra `INV-02` (incha dependências runtime e imagens), acopla testes herméticos a HTML volátil, sofre bloqueios diretos de Cloudflare sem proteção anti-bot externalizável e eleva risco operacional às 3h da manhã.

### Alternativa C (`Alt_C_Adapter_1N_Sidecar_LazyCache`): Arquitetura Plugável 1:N + Sidecar/Torznab + Lazy-Cache & Challenge Manual (Vencedora)
- **Descrição:**
  1. **Descoberta Automática 1:N:** Adapters em `src/backend/providers/sources/*.py` (`eztv`, `yify`, `torrent_api_py`, `torznab`, `unique_web`) descobertos via `pkgutil` com isolamento de import alimentam instâncias ilimitadas em `external_sources` (`adapter_key`, `source_kind`, `config_json`, `priority`, `cooldown_until`).
  2. **Bridge HTTP Leve (`httpx`):** Consome `Torrent-Api-py` sidecar, `Torznab` (Prowlarr/Jackett) e APIs nativas (`EZTV`, `YTS`) sem nenhuma nova dependência pesada em `pyproject.toml`.
  3. **Motor *Lazy-Cache* + `EntityResolutionService`:** Cache `< 20ms` + busca paralela apenas quando ausente/expirado (`TTL 24h`) + botão `"Buscar Ao Vivo"`. Matches `>= 0.85` gravam em `ExternalRelease` (`MediaBadge`); `0.60–0.84` permanecem efêmeros com campo de refino textual no modal.
  4. **Fallback Assimétrico & Segurança Zero-Trust:** `torrent_mirrorable` rotaciona `mirrors[]` automaticamente; `unique_web_source` emite `challenge_required` + `challenge_url` clicável `44×44px` no `TorrentModal.tsx`. Whitelist `http/https/magnet`, mascaramento de segredos e *circuit breaker* em 2 níveis.
  5. **Deshardcoding UI/Backend + Contrato Universal `pytest`:** Facetas e chips dinâmicos no `Explorar` + CRUD dinâmico por `config_schema` em `StatusConfigView.tsx` + suíte parametrizada com `respx`.

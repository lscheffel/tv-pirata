---
elevation_target: ADR-013
phase: 2
title: "Auditoria Forense da Proposta Bruta de Plugins (Red-Flag Discovery)"
status: COMPLETED
language: PT-BR
---

# Fase 2 — Auditoria Forense da Proposta Inicial

Esta auditoria examina riscos ocultos antes do fechamento da arquitetura de plugins multi-fonte.

## 1. Achados Críticos (`CRITICAL`)

### `AUD13-CRIT-01`: Acoplamento 1:1 Impedindo Múltiplas Instâncias (`Torrent-Api-py` / `Torznab`)
- **Evidência:** Manter o desenho atual de `REGISTERED_SOURCE_PROVIDERS[key] = ProviderClass()` obriga criar uma nova classe/arquivo Python para cada feed Torznab ou para cada site servido pelo mesmo container `Torrent-Api-py`.
- **Mitigação Requerida:** Separar **Adapter (`adapter_key`)** em `src/backend/providers/sources/*.py` de **Instância (`source_key`)** na tabela `external_sources`.

### `AUD13-CRIT-02`: Poluição Irreversível de `MediaBadge` por Matching Ambíguo Sem `imdb_id`
- **Evidência:** Fontes como `1337x` e indexadores web frequentemente retornam apenas título + ano. Vincular o primeiro hit por título simples gravaria remakes/homônimos no `imdb_id` errado de `ExternalRelease`, acendendo `MediaBadge` falsa no `Explorar`.
- **Mitigação Requerida:** Portão estrito de confiança `>= 0.85` via `EntityResolutionService` para *write-through*; matches `0.60–0.84` permanecem efêmeros apenas na sessão com refino manual.

### `AUD13-CRIT-03`: Vetor URI XSS e Vazamento de `api_key` em `ExternalSourceRecord`
- **Evidência:** `TorrentModal.tsx` atribui `external_url`/`torrent_url` diretamente a `<a href>` e `StatusConfigView.tsx` recebe configurações via REST. Aceitar strings sem validação ou devolver `config_json` bruto vazaria credenciais Torznab e abriria risco de URI `javascript:`.
- **Mitigação Requerida:** Whitelist estrita de esquemas (`http`, `https`, `magnet`) na camada de serviço/modal + mascaramento automático de campos marcados como `secret=True` na API.

---

## 2. Achados Maiores (`MAJOR`)

### `AUD13-MAJ-01`: Bloqueio Silencioso em Fontes Únicas Protegidas por reCAPTCHA/Cloudflare
- **Descrição:** Tratar `HTTP 403`/Challenge apenas como erro genérico ou log oculto impede o usuário de resolver manualmente uma fonte não-torrent única.
- **Mitigação Necessária:** Distinção `torrent_mirrorable` vs. `unique_web_source` + payload `source_diagnostics` propagando `challenge_url` segura até banner `44×44px` no `TorrentModal.tsx`.

### `AUD13-MAJ-02`: Cascata de Timeouts com Sidecar Offline e Queda de 1 Site Derrubando Outros
- **Descrição:** Se `localhost:8009` (`Torrent-Api-py`) estiver desligado, tentar múltiplos sites em sequência trava o modal; se um único site cair, não deve degradar os demais quando o host estiver saudável.
- **Mitigação Necessária:** Busca paralela com timeouts curtos + *circuit breaker* em **2 níveis** (por `source_key` vs. por host base compartilhado).

### `AUD13-MAJ-03`: Cache Morto em `ExternalRelease` Sem Revalidação
- **Descrição:** Sem `last_checked_at` (TTL), releases antigos com `0 seeds` permanecem cacheados para sempre.
- **Mitigação Necessária:** TTL padrão de **24h** com fallback offline se a consulta ao vivo falhar.

---

## 3. Achados Menores (`MINOR`)

### `AUD13-MIN-01`: Drift Entre Listas Hardcoded de Backend e Frontend
- **Descrição:** Sem remoção de `"yify"`/`"1337x"` hardcoded em `canonical_taxonomy.py`, `discovery_engine.py` e `ExplorerView.tsx`, novos plugins cadastrados na UI não aparecerão nos filtros do `Explorar`.
- **Mitigação Necessária:** Leitura dinâmica a partir de `external_sources` com invalidação coordenada de `discovery_cache`.

### `AUD13-MIN-02`: Import Fault de Um Plugin Derrubando o Boot da Aplicação
- **Descrição:** Erro de sintaxe ou exceção no `import` de um arquivo em `src/backend/providers/sources/` durante `pkgutil.iter_modules` pode impedir a inicialização do FastAPI.
- **Mitigação Necessária:** Isolamento por `try/except` no autodiscovery com registro de erro diagnóstico sem abortar o servidor.

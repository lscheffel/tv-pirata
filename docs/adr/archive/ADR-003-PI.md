---
id: ADR-003-PI
title: "Plano de Implementação: Implementação do Contrato Unificado, Provedores com Fallback e EZTV"
adr_ref: ADR-003
created: "2026-11-11"
status: CONSOLIDATED
---

# Plano de Implementação (PI) — ADR-003

## Fase 1: Fixtures & Modelos de Dados
- Construção de payloads simulados representativos de TMDB, TVMaze e EZTV.
- Escrita de esquemas Pydantic v2 com tipagem estrita e validação de contratos.

## Fase 2: Implementação dos Clientes de Rede
- Implementação de clientes HTTP assíncronos via `httpx`.
- Implementação do algoritmo de fallback com timeout de 2.0s.
- Implementação do parser de torrents da EZTV por `imdb_id`.

## Fase 3: Testes Automatizados e Homologação
- Testes unitários para cada provedor com `respx`.
- Teste de integração validando chaveamento para TVMaze em caso de falha do TMDB.
- Verificação via `make lint` e `make test`.

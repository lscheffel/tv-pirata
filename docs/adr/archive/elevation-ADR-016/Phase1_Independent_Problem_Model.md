---
adr_ref: ADR-016
phase: 1
title: "Phase 1 — Independent Problem Model"
language: PT-BR
---

# Phase 1: Modelo Independente do Problema (`ADR-016`)

## 1. Declaração do Problema (First Principles)
A tela de Configurações (`StatusConfigView.tsx`) e o console de hidratação (`HydrationConsoleCard.tsx`) cresceram organicamente por acúmulo de funcionalidades (`ADR-012`..`ADR-015`). O resultado é uma interface centrada na topologia interna do código (bancos, pilares, cursores, flags de estado) em vez de centrada nas tarefas e na percepção de progresso de um usuário humano.

## 2. Objetivos, Restrições e Invariantes
- **Objetivos:**
  1. Reduzir a carga cognitiva organizando todas as configurações em arquitetura **Master-Detail (2 colunas)** com busca rápida.
  2. Substituir 100% do jargão interno exposto na UI por linguagem natural em PT-BR.
  3. Eliminar ações duplicadas/conflitantes de sincronização/atualização.
  4. Fornecer observabilidade viva em tempo real durante atualizações em segundo plano: etapa/título atual, velocidade (`itens/min`), tempo decorrido, ETA e feed de eventos recentes.
- **Restrições Duras:** Manter retrocompatibilidade com `/api/explore/hydration/*` e CLI `scripts/hydrate_ecosystem.py`; zero dependências externas novas (`WebSockets`/`Redis`); zero quebras nos 77 testes existentes.
- **Condições de Falha:** Bloqueio de `SQLite` durante leitura de status no meio de um passo longo; polling infinito quando ocioso; perda de acessibilidade no mobile (`< 768px`).

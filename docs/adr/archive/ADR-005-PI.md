# Implementation Plan: ADR-005 — Frontend Cinemático TV Pirata

## 1. Escopo & Dependências

- **Pré-requisitos:** Node.js v24+, npm v12+, Python 3.14 venv com FastAPI ativo.
- **Diretório Raiz do Frontend:** `src/frontend/`
- **Diretório de Distribuição:** `src/backend/static/dist/`
- **Estimativa de Fases:** 4 fases sequenciais.

## 2. Fase 1: Fundação & Scaffolding (T01 - T03)
1. Criar `src/frontend/package.json` com dependências mínimas justificadas:
   - `react`, `react-dom`
   - `lucide-react` (ícones cinemáticos de alta legibilidade)
   - `clsx`, `tailwind-merge` (composição limpa de classes)
   - Dev: `vite`, `@vitejs/plugin-react`, `tailwindcss`, `postcss`, `autoprefixer`, `typescript`, `@types/react`, `@types/react-dom`
2. Configurar `vite.config.ts`, `tailwind.config.js`, `postcss.config.js`, `tsconfig.json`.
3. Criar `src/frontend/src/services/api.ts` cobrindo todos os endpoints de `/api/discovery`, `/api/library`, `/api/watches`, `/api/torrents`, `/api/collections`.

## 3. Fase 2: Componentes Core & Streaming Layout (T04 - T06)
1. Implementar `Navbar.tsx` com campo de pesquisa debounced, transparência de scroll e tabs de navegação.
2. Implementar `HeroBanner.tsx` com backdrop HD, título com drop shadow, botão "Detalhes" e "Obter Torrents".
3. Implementar `ShowCarousel.tsx` com scroll horizontal suave, botões de navegação, cards com hover elevation e badges de resolução/progresso.

## 4. Fase 3: Detalhes, Checklist & Torrents (T07 - T09)
1. Implementar `ShowDetailModal.tsx` com tabs de temporada, progresso de assistidos, badge SMB e lista de episódios.
2. Implementar `EpisodeRow.tsx` com toggle otimista e botão de marcar temporada completa (`watch-all`).
3. Implementar `TorrentModal.tsx` com agrupamento por qualidade (4K, 1080p, 720p, SD), ordenação por seeds, e ação híbrida de cópia para clipboard + disparo de link `magnet:?`.
4. Implementar `Toast.tsx` para feedback flutuante não-bloqueante de 3 segundos.

## 5. Fase 4: Biblioteca, Coleções & Servidor FastAPI (T10 - T12)
1. Implementar `LibraryView.tsx` e `CollectionsView.tsx` com chips de filtro.
2. Atualizar `src/backend/main.py` para servir `src/backend/static/dist` com rota raiz e fallback SPA.
3. Atualizar `Makefile` com comandos de build.
4. Executar `npm run build`, testar endpoints e garantir quality gate limpo.


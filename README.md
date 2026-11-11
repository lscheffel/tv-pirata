# TV Pirata 🏴‍☠️

> **Seu "Netflix Pessoal" para Descoberta, Controle e Administração de Séries e Filmes.**  
> *Painel web moderno com foco em descoberta online, tracking granular de progresso (assistido/não assistido), categorização rica e gestão de acervo distribuído via SMB na rede doméstica.*

---

## 1. 🎯 Visão Geral do Projeto

O **TV Pirata** é uma central de mídia personalizada desenvolvida para quem consome séries e filmes obtidos via torrent ou downloads manuais e disponibilizados via compartilhamento de rede (**SMB**) para visualização em Smart TVs, TV Boxes, Kodi ou VLC.

Diferente de media centers pesados voltados primariamente para transcodificação e streaming contínuo (Plex/Emby/Jellyfin), o foco central do **TV Pirata** é:
- **Descoberta Visual e Ágil:** Interface cinematográfica estilo Netflix (carrosséis, trending, detalhes, trailers, pôsteres em alta definição).
- **Provedores de Descoberta Online:** Agregação de APIs líderes de mercado (**TMDB**, **TVMaze**, **Trakt**).
- **Controle Total de Progresso:** Status de acompanhamento por série, temporada e episódio (Quero Ver, Assistindo, Assistido, Abandonado, Pausado).
- **Categorização e Tags Personalizadas:** Gêneros, coleções temáticas, notas pessoais e filtros dinâmicos.
- **Gestão e Mapeamento de Arquivos SMB:** Associação entre a série/filme e sua presença/caminho no servidor de arquivos local da casa.

---

## 2. 🏗️ Arquitetura e Stack Tecnológica

```
tv-pirata/
├── src/                      # Código-fonte da aplicação
│   ├── backend/              # API REST (FastAPI / Python)
│   │   ├── api/              # Rotas HTTP (discovery, watchlist, media, library)
│   │   ├── core/             # Configurações, segurança e conexão com banco
│   │   ├── models/           # Modelos de dados (SQLModel / SQLAlchemy)
│   │   ├── providers/        # Clientes de APIs externas (TMDB, TVMaze, Trakt)
│   │   └── services/         # Regras de negócio e scanner de arquivos SMB
│   └── frontend/             # Interface Web cinematográfica (Netflix-like UI)
├── tests/                    # Suíte automatizada de testes
├── docs/                     # Documentação viva e decisões arquiteturais
│   └── adr/                  # Architecture Decision Records (ADRs)
├── scripts/                  # Scripts operacionais e Quality Gate local
├── AGENTS.md                 # Single Source of Truth para IA e AgentOps
├── Makefile                  # Comandos e automações cross-platform
└── .env.example              # Template seguro de variáveis de ambiente
```

- **Backend:** FastAPI (Python 3.14+) assíncrono com suporte nativo a tipagem estrita e documentação automática OpenAPI/Swagger.
- **Banco de Dados:** SQLite (zero-config, local e atômico em `data/tv_pirata.db`) com migração transparente para PostgreSQL se necessário.
- **Provedores de Metadados:** Integração modular com **TMDB API v3/v4** e **TVMaze API**.
- **Frontend:** Painel web responsivo com estética Netflix (Dark Cinematic UI, carrosséis horizontais, drawer/modal de detalhes com episódios e checklists).

---

## 3. 🚀 Primeiros Passos

### Pré-requisitos
- Python 3.10+ (ou gerenciador `uv`)
- Node.js 18+ (opcional, dependendo do bundle de frontend)
- Make (opcional)

### Configuração Inicial
```bash
# 1. Copiar o arquivo de variáveis de ambiente e preencher suas chaves (ex: TMDB)
cp .env.example .env

# 2. Inicializar o ambiente virtual e dependências
make bootstrap
```

### Comandos Úteis
```bash
# Executar a suíte de testes
make test

# Executar checagem estática de código (linter)
make lint

# Formatar o código
make format

# Ativar o Quality Gate pré-commit local
make setup-hooks
```

---

## 4. 📋 Roadmap de Funcionalidades

- [x] **Bootstrap e Governança:** Estrutura canônica de repositório, Makefile, AGENTS.md, scripts de CI/CD local.
- [ ] **Provedores de Descoberta:** Cliente assíncrono para TMDB e TVMaze com cache inteligente.
- [ ] **Modelo de Dados & Migrations:** Tabelas de séries, episódios, watchlist e histórico de visualizações.
- [ ] **API de Watchlist & Status:** Endpoints para marcar séries/temporadas/episódios como assistidos.
- [ ] **Mapeamento SMB / Armazenamento:** Leitura de diretórios locais/SMB para identificar arquivos disponíveis na rede.
- [ ] **Frontend Netflix-like:** Layout escuro com carrosséis, banner hero de destaque, busca em tempo real e checklist de episódios.

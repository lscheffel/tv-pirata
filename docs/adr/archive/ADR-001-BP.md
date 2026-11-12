---
id: ADR-001-BP
title: "Blueprint: Arquitetura Fundamental do TV Pirata"
adr_ref: ADR-001
created: "2026-11-11"
status: ACCEPTED
---

# Blueprint Arquitetural — ADR-001

## 1. Visão Arquitetural C4 (Container)

```mermaid
graph TD
    User["Usuário / Browser"] -->|"HTTP / REST"| WebUI["TV Pirata Web UI (Netflix-like)"]
    WebUI -->|"JSON API"| FastAPIServer["FastAPI Application Server"]
    FastAPIServer -->|"Leitura / Escrita"| SQLiteDB[("SQLite Storage<br/>(data/tv_pirata.db)")]
    FastAPIServer -->|"Leitura de FS"| LocalStorage["Diretório SMB Montado<br/>(/mnt/storage/media)"]
    ExtPlayers["Smart TVs / Kodi / VLC"] -->|"SMB Protocol"| SMBServer["Servidor SMB Doméstico"]
```

## 2. Limites de Responsabilidade e Invariantes

1. **Invariante de Desacoplamento:** Nenhuma falha de I/O na rede SMB pode derrubar ou travar o servidor FastAPI.
2. **Invariante de Preservação:** Exclusão de arquivos físicos no disco nunca deve purgar histórico de episódios assistidos.
3. **Invariante de Desempenho:** Rotas de navegação do catálogo devem responder em $P_{95} < 30\text{ms}$ utilizando cache local.

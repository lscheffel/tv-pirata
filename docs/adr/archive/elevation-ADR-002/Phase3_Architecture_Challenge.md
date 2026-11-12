# Phase 3: Desafio Arquitetural & Espaço de Design Adversarial

## 1. Alternativas Competidoras Exploradas

### Alternativa A (Original - Quadra ADR-002)
Contrato canônico Pydantic unificado com fallback dinâmico TMDB -> TVMaze (timeout 2.0s), busca assíncrona na EZTV por `imdb_id` e tracking relacional granular no SQLite com `is_available`.

### Alternativa B (Arquitetura Monolítica com Scraper Único)
Consumir diretamente o Trakt.tv como fonte única de metadados, scrobbling e catálogo.
- *Desafio Adversarial:* Trakt exige autenticação OAuth2 complexa, impõe limites severos de requisições por IP e é frequentemente bloqueado em redes domésticas sem VPN.

### Alternativa C (Arquitetura Distribuída com qBittorrent WebUI Integration)
Fazer o backend se conectar via WebSockets à API de um qBittorrent rodando no servidor.
- *Desafio Adversarial:* Acoplamento desnecessário no MVP. Se o qBittorrent estiver desligado, a inicialização do TV Pirata falharia ou exigiria reconciliação complexa de estados.

## 2. Veredito do Desafio
A **Alternativa A** demonstra superioridade categórica em simplicidade de operação, independência de serviços externos autenticados e velocidade de execução.

# Release Notes — TV Pirata v0.1.0 (Foundation Milestone)

## 🌟 Destaques do Lançamento
O lançamento **v0.1.0** estabelece a infraestrutura fundamental do **TV Pirata**, fornecendo um motor de descoberta resiliente e o contrato canônico unificado de metadados e distribuição de mídia para redes domésticas.

### Principais Entregas
1. **Contrato de Domínio Unificado:**
   - Modelo Pydantic v2 `UnifiedShow`, `UnifiedSeason`, `UnifiedEpisode` e `TorrentRelease` normalizando as respostas de diferentes provedores.
2. **Motor de Descoberta com Fallback em Tempo Real:**
   - Orquestrador `ResilientDiscoveryService` que consulta o TMDB com timeout de 2.0s e migra silenciosa e automaticamente para o TVMaze em caso de falha de conexão, bloqueio de IP ou esgotamento de cotas.
3. **Distribuição EZTV sem Autenticação:**
   - Integração com a API da EZTV via `imdb_id` para expor arquivos torrent e links magnet ordenados por quantidade de seeds/saúde, sem requerer clientes de torrent pesados no servidor.
4. **Governança Agêntica SOTA & Quadra Completa:**
   - Formalização de 3 decisões arquiteturais canônicas (`ADR-001`, `ADR-002`, `ADR-003`).
   - Elevação arquitetural adversarial completa da ADR-002 (`elevation-ADR-002/`).
5. **Pirâmide de Testes Hermética:**
   - Suíte de 13 testes cobrindo happy path, timeouts forçados, quedas de serviço e contratos com `respx`.

---

## 🔒 Mitigações e Decisões Arquiteturais Registradas
- `ADR-001`: Separação estrita entre descoberta/gestão e reprodução física de vídeo via SMB.
- `ADR-002`: Definição de fallback dinâmico TMDB -> TVMaze, integração EZTV e controle relacional de visualizações.
- `ADR-003`: Implementação física dos modelos unificados e clientes assíncronos.


# ADR-001: Arquitetura Fundamental do TV Pirata (Descoberta, Controle e SMB)

- **Status:** Proposto / Aceito
- **Data:** 2026-11-11
- **Decisores:** Time TV Pirata & SynPraxis AgentOps

---

## 1. Contexto e Problema

O usuário consome séries de TV e filmes através de downloads locais (via torrent) e disponibiliza esses arquivos na rede doméstica através de um compartilhamento **SMB** para reprodução em dispositivos terceiros (Smart TVs, TV Boxes, Kodi, VLC, etc.).
Os servidores de mídia tradicionais (Plex, Emby, Jellyfin) focam fortemente em transcodificação em tempo real e players proprietários integrados, consumindo alto processamento e não priorizando a experiência rica de descoberta de novas séries, tracking granular de episódios assistidos e organização personalizada.

Faz-se necessária uma aplicação leve, moderna e focada em:
1. **Descoberta:** Experiência visual comparável a serviços de streaming (Netflix), alimentada por APIs públicas líderes (TMDB, TVMaze).
2. **Controle e Administração:** Gestão de status de visualização (Quero ver, Assistindo, Assistido por episódio, Abandonado) e tags/categorias.
3. **Mapeamento de Mídia:** Vinculação lógica com arquivos presentes no diretório SMB da casa.

---

## 2. Decisão Arquitetural

1. **Separação Descoberta vs Reprodução:**
   - O foco primário do sistema é **Descoberta, Catalogação e Controle de Status**, não reprodução de vídeo interna ou transcodificação de streaming.
   - O sistema fornecerá indicação visual clara de disponibilidade no storage SMB local (ex: "Disponível na rede local", "Pendente de download").

2. **Stack Tecnológica do Backend:**
   - **Linguagem & Framework:** Python 3.14+ com **FastAPI** para alta performance assíncrona, documentação interativa automática (OpenAPI/Swagger) e facilidade de integração com scrapers/parsers de SMB.
   - **Persistência de Dados:** SQLite como motor de dados padrão (`data/tv_pirata.db`), garantindo zero atrito operacional, integridade relacional e portabilidade em arquivo único.

3. **Integração de APIs de Descoberta:**
   - **TMDB (The Movie Database):** Provedor primário de metadados, posters, backdrops, trailers, elencos e tendências globais.
   - **TVMaze:** Provedor complementar aberto (sem obrigatoriedade de token inicial) para guias de programação, episódios e datas de exibição.

4. **Experiência de Usuário (Frontend):**
   - Design System no padrão Dark Cinematic (Dark Mode, layout fluído, banners de destaque, carrosséis de gêneros e tendências, modais informativos ricos).

---

## 3. Consequências

### Positivas
- Arquitetura extremamente leve, que pode rodar em qualquer mini PC ou servidor doméstico com consumo mínimo de RAM e CPU (já que não há transcodificação).
- Resolução rápida do problema central do usuário: saber o que assistir, onde parou e o que já tem baixado em casa.
- Total desacoplamento do player de vídeo final (os aparelhos de TV usam seus players nativos de alta performance via SMB).

### Negativas / Mitigações
- Necessidade de configuração de chave de API (TMDB) para recursos completos de imagens e busca internacional (mitigada por fallback gracioso ou modo TVMaze sem chave).

# Phase 5: Registro de Amplificação Arquitetural

## 1. Amplificações Incorporadas ao Design

1. **Anti-Corruption Layer (ACL):**
   - Criação de adaptadores dedicados (`TMDBAdapter`, `TVMazeAdapter`, `EZTVAdapter`) que isolam o core da aplicação da nomenclatura das APIs terceiras.
2. **Circuit-Breaker Simples em Memória:**
   - Se o TMDB falhar consecutivamente por 3 vezes, chaveia diretamente para o TVMaze durante 5 minutos, economizando o timeout de 2.0s por requisição.
3. **Normalização de Magnets EZTV:**
   - Parser de strings de release da EZTV para agrupar torrents por qualidade (`1080p`, `720p`, `x265`, `x264`) para exibição limpa na interface.
4. **Semáforo Assíncrono de I/O:**
   - Limitação de concorrência a no máximo 5 conexões simultâneas de download de posters locais, prevenindo sobrecarga de rede.

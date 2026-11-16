# Fase 3: Desafio Arquitetural Adversarial (Architecture Challenge)

## Questionamentos Adversariais e Respostas de Engenharia

### Desafio 1: Por que materializar `episodes_count`, `max_season` e `max_episode` em `shows` em vez de criar apenas um índice em `episodes_catalog(show_id, season, episode)`?
- **Análise:** Mesmo com um covering index `idx_episodes_show_season_ep` em `episodes_catalog(show_id, season, episode)`, quando `list_shows(sort_by='seeds')` ordena em Python combinando `p2p_map` (`tv_pirata.db`) com `EZTVShow` (`eztv_metadata.db`), se precisarmos de estatísticas de episódios para múltiplos carrosséis (`get_curated_sections`), ainda teríamos que agregar centenas de grupos no índice. Ao materializar `episodes_count`, `max_season` e `max_episode` diretamente na linha de `shows` (860 linhas), o custo de leitura de estatísticas de episódios cai literalmente para **zero queries extras** ($O(1)$ por série já carregada). O índice composto `idx_episodes_show_season_ep` também é criado, acelerando tanto o backfill quanto a página de detalhes da série (`get_show_detail`).

### Desafio 2: E se um teste unitário inserir um `EZTVEpisodeCatalog` sem rodar `init_eztv_db()` novamente?
- **Análise:** Excelente ponto! Em `tests/integration/test_catalog_api.py`, a fixture `seed_eztv_catalog` cria um `EZTVShow` (com `episodes_count=0` por default) e insere 2 linhas de `EZTVEpisodeCatalog`. Se `CatalogRepository` confiasse cegamente em `show.episodes_count` quando `show.episodes_count == 0`, o teste veria `episode_count == 0` em vez de `2`!
- **Solução Determinística (Híbrida):**
  1. Criar triggers SQLite `AFTER INSERT` / `AFTER DELETE` em `episodes_catalog` (ou fallback em `_build_episode_stats_map` pós-paginação quando `show.episodes_count == 0`) para manter `shows.episodes_count`, `max_season` e `max_episode` atualizados automaticamente.
  2. Além disso, em `CatalogRepository.list_shows` e `get_curated_sections`, se qualquer série selecionada na página final tiver `episodes_count == 0`, consultar `_build_episode_stats_map` **apenas para os IDs da página final** (máximo 20 IDs). Com o índice `idx_episodes_show_season_ep`, buscar 20 IDs leva `< 0,2 ms` e garante 100% de compatibilidade com qualquer teste que insira episódios sem atualizar `shows.episodes_count`!

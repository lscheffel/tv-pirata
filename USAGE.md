# Guia de Uso e Operação — TV Pirata 🏴‍☠️

Este documento apresenta instruções práticas e comandos verificáveis para desenvolvimento, testes e execução do backend do **TV Pirata**.

---

## 1. ⚙️ Configuração do Ambiente

### Clonar e Preparar Dependências
```bash
# Clone e entrada no repositório
cd /home/loupan/projetosVS/tv-pirata

# Configurar variáveis de ambiente
cp .env.example .env

# Instalação das dependências no ambiente virtual via uv
uv pip install -e ".[dev]"
```

---

## 2. 🧪 Execução de Testes e Qualidade

O projeto utiliza uma pirâmide de testes totalmente desconectada da internet. Nenhuma chave do TMDB real é necessária para executar os testes locais.

```bash
# 1. Executar todos os testes
make test

# 2. Executar testes com saída detalhada
.venv/bin/pytest tests/ -v

# 3. Executar apenas os testes de integração do fallback
.venv/bin/pytest tests/integration/test_discovery_fallback.py -v

# 4. Executar verificação estática de código com Ruff
make lint

# 5. Executar o Quality Gate pré-commit localmente
./scripts/quality_gate.sh
```

---

## 3. 🐍 Exemplos Práticos de Uso dos Provedores (Python)

### 3.1 Busca Resiliente com Fallback Automático
```python
import asyncio
from src.backend.providers import TMDBProvider, TVMazeProvider, ResilientDiscoveryService

async def main():
    tmdb = TMDBProvider(api_key="SUA_CHAVE_AQUI")
    tvmaze = TVMazeProvider()
    
    # Se o TMDB demorar mais de 2 segundos ou falhar, o TVMaze responde
    discovery = ResilientDiscoveryService(primary=tmdb, fallback=tvmaze, timeout_seconds=2.0)
    
    shows = await discovery.search_shows("Breaking Bad")
    for show in shows:
        print(f"[{show.source_provider}] {show.title} ({show.first_air_date}) - Nota: {show.rating}")

asyncio.run(main())
```

### 3.2 Obtenção de Torrents via EZTV (usando IMDB ID)
```python
import asyncio
from src.backend.providers import EZTVProvider

async def main():
    eztv = EZTVProvider()
    
    # Busca torrents para Game of Thrones (IMDB ID: tt0944947)
    torrents = await eztv.get_torrents_by_imdb("tt0944947", limit=10)
    for t in torrents:
        print(f"[{t.quality}] {t.title} | Seeds: {t.seeds} | Magnet: {t.magnet_url[:40]}...")

asyncio.run(main())
```

---

## 4. 🛠️ Solução de Problemas (Troubleshooting)

| Sintoma | Causa Provável | Solução |
| :--- | :--- | :--- |
| `ModuleNotFoundError: No module named 'src'` | PYTHONPATH não configurado na chamada direta do pytest | Usar `make test` ou chamar via `.venv/bin/pytest tests/` |
| TMDB retorna `HTTPStatusError: 401 Unauthorized` | Chave de API ausente ou inválida no `.env` | O `ResilientDiscoveryService` chaveia automaticamente para o TVMaze em produção |
| Torrents não encontrados no EZTV | O IMDB ID não está presente nos metadados da série | Garantir que o show possua `imdb_id` populado pelo TMDB/TVMaze |

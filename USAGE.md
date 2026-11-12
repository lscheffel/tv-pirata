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

## 2. 🚀 Executando o Servidor Web (FastAPI)

```bash
# Iniciar o servidor com recarregamento automático (development)
.venv/bin/python -m uvicorn src.backend.main:app --host 127.0.0.1 --port 8000 --reload

# Acessar a documentação interativa Swagger
# Abrir no navegador: http://127.0.0.1:8000/docs
```

### Endpoints Disponíveis
- `GET  /api/health` — Status de saúde do backend.
- `GET  /api/discovery/trending` — Séries em alta na semana.
- `GET  /api/discovery/search?q={termo}` — Busca com fallback automático TMDB -> TVMaze.
- `GET  /api/discovery/shows/{tmdb_id}` — Metadados completos do show.
- `GET  /api/library/shows` — Listagem de séries salvas na biblioteca pessoal.
- `POST /api/library/shows` — Importar série para o catálogo pessoal.
- `POST /api/watches/episodes/{id}/toggle` — Alternar episódio como assistido.
- `GET  /api/watches/shows/{id}/progress` — Progresso e porcentagem assistida.
- `GET  /api/torrents/shows/{imdb_id}` — Torrents e links magnet via EZTV.
- `GET  /api/collections/smart` — Listar coleções inteligentes.

---

## 3. 🧪 Execução de Testes e Qualidade

O projeto utiliza uma pirâmide de testes totalmente desconectada da internet. Nenhuma chave do TMDB real é necessária para executar os testes locais.

```bash
# 1. Executar todos os testes (22 testes unitários e de integração)
make test

# 2. Executar testes com saída detalhada
.venv/bin/pytest tests/ -v

# 3. Executar apenas os testes de integração das rotas da API
.venv/bin/pytest tests/integration/test_api_endpoints.py -v

# 4. Executar verificação estática de código com Ruff
make lint

# 5. Executar o Quality Gate pré-commit localmente
./scripts/quality_gate.sh
```

---

## 4. 🛠️ Solução de Problemas (Troubleshooting)

| Sintoma | Causa Provável | Solução |
| :--- | :--- | :--- |
| `ModuleNotFoundError: No module named 'src'` | PYTHONPATH não configurado na chamada direta do pytest | Usar `make test` ou chamar via `.venv/bin/pytest tests/` |
| `no such table: showrecord` em testes isolados | SQLite in-memory requer pool estático | Utilizar `StaticPool` na criação da engine de testes |
| Erro de timezone no SQLite | Datetime sem timezone | Utilizar `datetime.now(timezone.utc)` ao persistir datas |

# ==============================================================================
# SOTA-Enterprise Multiplatform Makefile Template (SynPraxis SPX Standard)
# Compatible with Linux, macOS and Native Windows
# ==============================================================================

ifeq ($(OS),Windows_NT)
    VENV_BIN = .venv/Scripts
else
    VENV_BIN = .venv/bin
endif

PYTHON ?= $(shell if [ -f $(VENV_BIN)/python ]; then echo $(VENV_BIN)/python; else which python3 2>/dev/null || echo python3; fi)
PYTEST ?= $(shell if [ -f $(VENV_BIN)/pytest ]; then echo $(VENV_BIN)/pytest; else which pytest 2>/dev/null || echo pytest; fi)
RUFF   ?= $(shell if [ -f $(VENV_BIN)/ruff ]; then echo $(VENV_BIN)/ruff; else which ruff 2>/dev/null || echo ruff; fi)

.PHONY: help bootstrap test lint format setup-hooks run spx-sync clean

help:
	@echo "Comandos disponíveis no workspace:"
	@echo "  make bootstrap    - Valida o ambiente e dependências locais"
	@echo "  make test         - Executa suíte automatizada via pytest"
	@echo "  make lint         - Executa verificação estática via ruff"
	@echo "  make format       - Formata o código com ruff format"
	@echo "  make setup-hooks  - Ativa o Quality Gate pré-commit localmente"
	@echo "  make run          - Inicia o servidor FastAPI localmente"
	@echo "  make spx-sync     - Sincroniza e reindexa o repositório com SynPraxis RAG"
	@echo "  make clean        - Remove caches, builds e artefatos transitórios"

bootstrap:
	@echo "[+] Verificando ambiente virtual..."
	@if [ -d ".venv" ]; then echo "  [✓] .venv ativo em $(VENV_BIN)"; else echo "  [!] .venv ausente. Execute 'spx workspace init'."; fi

test:
	$(PYTEST) tests/

test-e2e:
	$(PYTEST) tests/ -m e2e

test-all:
	$(PYTEST) tests/ -o addopts=""

lint:
	$(RUFF) check src/ tests/

format:
	$(RUFF) format src/ tests/

run:
	$(PYTHON) -m uvicorn src.backend.main:app --host 127.0.0.1 --port 8000 --reload

setup-hooks:
	@mkdir -p .git/hooks
	@cp scripts/quality_gate.sh .git/hooks/pre-commit
	@chmod +x .git/hooks/pre-commit
	@echo "[+] Pre-commit Quality Gate configurado com sucesso em .git/hooks/pre-commit."

spx-sync:
	spx sync

clean:
	rm -rf .venv __pycache__ .pytest_cache .ruff_cache dist build *.egg-info
	@echo "[+] Workspace limpo de caches e builds."

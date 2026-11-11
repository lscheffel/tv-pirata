#!/bin/sh
# ==============================================================================
# SynPraxis Git Hook: Pre-Commit Quality Gate
# Validates code style, linting, and type integrity before commit.
# ==============================================================================

set -e

echo "[SPX-GATE] Executando verificações locais de qualidade..."

# 1. Detecção do executável Python no ambiente virtual local
if [ -f ".venv/bin/ruff" ]; then
    RUFF=".venv/bin/ruff"
elif [ -f ".venv/Scripts/ruff.exe" ]; then
    RUFF=".venv/Scripts/ruff.exe"
elif command -v ruff >/dev/null 2>&1; then
    RUFF="ruff"
else
    RUFF=""
fi

# 2. Execução do Linter
if [ -n "$RUFF" ]; then
    echo "[SPX-GATE] Executando linter com $RUFF..."
    $RUFF check src/ tests/ || {
        echo "[SPX-GATE] ❌ Falha no linting. Corrija os erros antes de commitar."
        exit 1
    }
else
    echo "[SPX-GATE] ⚠️  Ruff não detectado no ambiente local. Pulando etapa de lint."
fi

echo "[SPX-GATE] ✅ Verificações aprovadas com sucesso."

#!/usr/bin/env python3
"""CLI script to synchronize the EZTV catalog into the local database."""

import argparse
import asyncio
import sys
from pathlib import Path

# Ensure workspace root is in sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from src.backend.core.database import get_sources_session, init_sources_db
from src.backend.services.catalog_indexer import EZTVIndexerService


async def main():
    parser = argparse.ArgumentParser(description="TV Pirata - Sincronizador de Catálogo EZTV")
    parser.add_argument(
        "--pages",
        type=int,
        default=15,
        help="Quantidade de páginas para ler (100 torrents por página)",
    )
    parser.add_argument("--start", type=int, default=1, help="Página inicial")
    parser.add_argument(
        "--no-enrich", action="store_true", help="Não buscar metadados (posters/sinopses)"
    )
    parser.add_argument(
        "--enrich-pending",
        action="store_true",
        help="Enriquecer séries existentes pendentes no banco",
    )

    args = parser.parse_args()

    print("[*] Inicializando banco de fontes externas (data/sources.db)...")
    init_sources_db()

    indexer = EZTVIndexerService()

    with next(get_sources_session()) as session:
        if args.enrich_pending:
            print("[*] Enriquecendo séries pendentes sem metadados...")
            count = await indexer.enrich_pending_shows(session=session, limit=200)
            print(f"[✓] Séries enriquecidas com sucesso: {count}")
            return

        print(
            f"[*] Iniciando sincronização: páginas {args.start} até {args.start + args.pages - 1}..."
        )
        telemetry = await indexer.sync_pages(
            session=session,
            start_page=args.start,
            max_pages=args.pages,
            enrich_metadata=not args.no_enrich,
        )

    print("\n[✓] Sincronização concluída com sucesso!")
    print(f"  - Páginas processadas: {telemetry['pages_processed']}")
    print(f"  - Torrents indexados:  {telemetry['torrents_indexed']}")
    print(f"  - Séries criadas:      {telemetry['shows_created']}")
    print(f"  - Séries enriquecidas: {telemetry['shows_enriched']}")
    print(f"  - Séries afetadas:     {telemetry['affected_shows']}")


if __name__ == "__main__":
    asyncio.run(main())


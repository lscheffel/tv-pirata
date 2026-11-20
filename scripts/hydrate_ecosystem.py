#!/usr/bin/env python3
"""Unified 3-Pillar Resumable Hydration CLI sharing sync_state['hydration_pipeline_v1']."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from sqlmodel import Session  # noqa: E402

from src.backend.core.database import (  # noqa: E402
    init_db,
    init_eztv_db,
    mainstream_engine,
    sources_engine,
)
from src.backend.services.hydration_orchestrator import hydration_orchestrator  # noqa: E402


def _load_dotenv_if_present() -> None:
    env_file = Path(_PROJECT_ROOT) / ".env"
    if not env_file.is_file():
        return
    for raw in env_file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        key, val = line.split("=", 1)
        key = key.strip()
        val = val.strip().strip("'\"")
        if key and key not in os.environ:
            os.environ[key] = val


async def _async_main(args: argparse.Namespace) -> int:
    _load_dotenv_if_present()
    init_db()
    init_eztv_db()

    with Session(mainstream_engine) as ms_sess, Session(sources_engine) as src_sess:
        if args.reset_cursor:
            hydration_orchestrator.reset_cursor(ms_sess, src_sess, target=args.reset_cursor)
            print(f"[+] Cursor resetado para '{args.reset_cursor}'.")

        initial = hydration_orchestrator.get_status(ms_sess, src_sess)
        print(
            f"[+] Maturidade detectada: overall={initial.overall_mode} | "
            f"IMDb={initial.imdb_backbone_mode} ({initial.coverage.total_shows:,} obras) | "
            f"EZTV={initial.eztv_mode} ({initial.coverage.eztv_shows:,} séries)"
        )

        if args.status_only:
            print(json.dumps(initial.model_dump(), indent=2, ensure_ascii=False))
            return 0

        steps = max(1, int(args.max_steps))
        for idx in range(1, steps + 1):
            out = await hydration_orchestrator.run_single_step(
                ms_sess,
                src_sess,
                scope=args.scope,
                yts_pages=args.yts_pages,
                sidecar_pages=args.sidecar_pages,
                sweep_batch=args.sweep_batch,
                meta_batch=args.meta_batch,
            )
            st = out["status"]
            cov = st["coverage"]
            print(
                f"[Step {idx}/{steps}] {st['last_step_summary']} | "
                f"Capas={cov['posters_pct']}% | Sinopses EN={cov['synopsis_pct']}% "
                f"PT-BR={cov['synopsis_ptbr_pct']}%"
            )
            if st["overall_mode"] == "DELTA" and args.stop_on_delta:
                print("[+] Todas as camadas atingiram modo DELTA.")
                break

        final = hydration_orchestrator.get_status(ms_sess, src_sess)
        print(
            "[+] Checkpoints finais: "
            + ", ".join(
                f"{k}:{v.mode}(p.{v.next_page}/off.{v.catalog_sweep_offset}={v.titles_indexed}t/{v.releases_indexed}r)"
                for k, v in final.sources.items()
            )
        )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Motor Unificado dos 3 Pilares de Hidratação do TV Pirata (ADR-015)"
    )
    parser.add_argument("--resume", action="store_true", help="Retoma do último checkpoint salvo.")
    parser.add_argument(
        "--reset-cursor",
        default=None,
        help="Reseta cursor antes de iniciar (all, yify, tgx, nyaasi, bitsearch, glodls).",
    )
    parser.add_argument(
        "--scope",
        choices=("all", "sources", "metadata"),
        default="all",
        help="Escopo de execução (default: all).",
    )
    parser.add_argument("--max-steps", type=int, default=5, help="Número de passos por execução.")
    parser.add_argument("--yts-pages", type=int, default=4, help="Páginas YTS (50/pág) por passo.")
    parser.add_argument("--sidecar-pages", type=int, default=1, help="Páginas Sidecar por passo.")
    parser.add_argument("--sweep-batch", type=int, default=8, help="Títulos no Sweep por passo.")
    parser.add_argument("--meta-batch", type=int, default=12, help="Obras na Cascata por passo.")
    parser.add_argument("--stop-on-delta", action="store_true", help="Para ao atingir tudo DELTA.")
    parser.add_argument("--status-only", action="store_true", help="Exibe apenas o status JSON.")
    args = parser.parse_args()
    return asyncio.run(_async_main(args))


if __name__ == "__main__":
    raise SystemExit(main())

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.1.0] - 2026-11-11

### Added
- **Repository Bootstrap & Governance (ADR-001):**
  - Provisioned canonical directory topology, `AGENTS.md`, `GEMINI.md`, `Makefile`, and `scripts/quality_gate.sh`.
  - Configured Python 3.14 virtual environment with `uv` tooling and Git hooks.
- **Unified Domain Models (ADR-002, ADR-003):**
  - Implemented `UnifiedShow`, `UnifiedSeason`, `UnifiedEpisode`, and `TorrentRelease` in `src/backend/models/unified.py`.
  - Added HTML sanitization for third-party provider summaries.
- **Modular Metadata Providers:**
  - Implemented `BaseMetadataProvider` abstract interface.
  - Implemented `TMDBProvider` with support for show searches, details, and weekly trending.
  - Implemented `TVMazeProvider` as an open, token-free fallback provider.
- **Resilient Discovery Client:**
  - Implemented `ResilientDiscoveryService` with a 2.0s strict timeout on TMDB and automatic, transparent fallback to TVMaze.
- **EZTV Torrent Distribution Integration:**
  - Implemented `EZTVProvider` fetching torrent releases by IMDB ID, sorting by seeders, and mapping magnet URLs.
- **Comprehensive Test Suite:**
  - Added 13 deterministic tests in `tests/unit/` and `tests/integration/` using `respx` and JSON fixtures.

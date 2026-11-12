# Phase 3: Desafio Arquitetural & Alternativas Competitivas

## 1. Formulação de Alternativas Competitivas

### Alternativa A (Proposta Original — Indexação Síncrona com Enriquecimento em Linha):
- Crawl da EZTV via HTTP, e para cada novo `imdb_id` encontrado, efetua chamada síncrona ao TVMaze.
- *Ponto Fraco:* Latência cumulativa alta (100 chamadas ao TVMaze por página da EZTV com risco de 429 Too Many Requests).

### Alternativa B (Desacoplamento em 2 Etapas: Ingestão Veloz + Enriquecimento em Fila Assíncrona):
- **Etapa 1 (Fast Ingestion):** O crawler consome as páginas da EZTV em alta velocidade, extrai o nome base via regex e grava releases e séries brutas no SQLite em transações atômicas de lote ($<100\text{ms}$).
- **Etapa 2 (Lazy/Worker Enrichment):** As séries sem poster ou sinopse são enriquecidas de forma assíncrona sob demanda (quando o usuário abre o catálogo) ou através de um worker com controle de taxa de requisições ($2\text{ req/s}$).
- *Vantagem:* Ingestão massiva em segundos, zero risco de rate limit e disponibilidade imediata dos magnets.

### Alternativa C (Banco Separado de Catálogo em DuckDB / SQLite Distribuído):
- Manter o catálogo de torrents em arquivo SQLite ou DuckDB isolado para não inflar o banco `tv_pirata.db`.
- *Ponto Fraco:* Complexidade desnecessária de transações e joins cross-database para um homelab onde SQLite em WAL mode suporta confortavelmente centenas de milhares de linhas em um único arquivo.

## 2. Decisão do Desafio
A **Alternativa B** é amplamente superior à Alternativa A, eliminando o risco de bloqueio por rate-limiting e garantindo ingestão veloz e confiável.


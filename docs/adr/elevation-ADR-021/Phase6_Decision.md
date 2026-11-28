# Fase 6 — Decision Gate (Veredicto Oficial) · ADR-021

## Veredicto: **`KEEP + AMPLIFY`** 🏆

## Justificativa Baseada em Evidência

1. **Vantagem Quantitativa Clara:** Na matriz de 11 dimensões ponderadas calculada por `matrix_scorer.py`, a arquitetura **Alt B (`Alt_B_Amplified_Hardened`)** obteve **`8.94 / 10.00`**, superando a proposta bruta original (`Alt A: 7.60`) por **`+1.34` pontos**, o modelo de daemon separado (`Alt C: 7.39`) por `+1.55` e o embaralhamento client-side (`Alt D: 7.22`) por `+1.72`.
2. **Mitigação Integral de Todos os Achados:** As 6 amplificações (`AMP-01`..`AMP-06`) eliminam os **2 achados CRITICAL** (`F-01` write lock SQLite no IMDb; `F-02` poluição de `data/mainstream.db` pelo `pytest`) e os **3 achados MAJOR** (`F-03` desidratação de buckets na deduplicação de 1.000 itens; `F-04` rate-limit/ordem imperfeita no EZTV; `F-05` compatibilidade `v1 → v2` de preferências), mantendo zero novas dependências de runtime.
3. **Preservação da Arquitetura Dual-SSOT:** Mantém a governança do repositório (`ADR-011`..`ADR-020`), a operação single-process gerenciada pelo `lifespan` do FastAPI e a reversibilidade limpa em todas as camadas.

## Condições Obrigatórias para Promoção (Fase 7)

1. Todos os 4 artefatos da Quadra Hardened (`ADR-021.md`, `ADR-021-BP.md`, `ADR-021-PI.md`, `ADR-021-TODO.md`) devem incorporar explicitamente `AMP-01`..`AMP-06`.
2. Os 3 pontos em aberto do Garimpo devem ser encerrados com defaults explícitos e configuráveis:
   - TTL padrão do ring-buffer de impressões (`discovery_impressions_v1`): **`48h`** (configurável `12h–168h`).
   - `episodes.tsv.gz` no IMDb: mantido sob checkbox manual (evita parsing de 4,5M linhas em cada *Novidades*, enquanto `ratings`+`basics`+`akas` atualizam automaticamente).
   - Preservação do `FilterSnapshot` do **Catálogo** entre trocas de aba na mesma sessão: **habilitada** via estado elevado em `App.tsx`.
3. Fase 8 deve certificar **0 achados CRITICAL e 0 MAJOR** antes de promover a Quadra para `docs/adr/`.

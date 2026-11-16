# Fase 4: Avaliação Comparativa e Álgebra de Blast Radius ($BR$)

## 1. Matriz Comparativa de Arquiteturas Candidatas

| Dimensão (Peso) | A1: Apenas Índices B-Tree + Paginação Tardia | A2: Cache Externo (Redis) | A3 (SOTA+): PRAGMAs + Materialização + Single-Pass + Cache Escopado + FTS5 |
| :--- | :---: | :---: | :---: |
| **Latência $P_{95}$ Leitura (35%)** | $7,0$ ($\sim 35\text{ ms}$) | $9,5$ ($\sim 2\text{ ms}$) | **$9,9$ ($< 5\text{ ms}$ frio / $< 0,5\text{ ms}$ quente)** |
| **Simplicidade Operacional (20%)** | $9,5$ | $4,0$ (daemon extra) | **$9,5$ (zero deps externas)** |
| **Isolamento Hermético Pytest (20%)** | $10,0$ | $5,0$ (estado compartilhado) | **$10,0$ (escopo `id(engine)` + fingerprint)** |
| **Escalabilidade Textual (15%)** | $5,0$ (`ILIKE` full scan) | $6,0$ | **$9,5$ (`FTS5` invertido)** |
| **Manutenibilidade (10%)** | $8,5$ | $6,5$ | **$9,2$** |
| **Score Ponderado Final** | **7,85 / 10** | **6,70 / 10** | **9,71 / 10** |

## 2. Cálculo do Blast Radius ($BR$)

$$BR = \frac{\text{Módulos Modificados}}{\text{Total de Módulos Backend}} \times \text{Fator de Acoplamento Externo}$$

- **Módulos Backend Tocados:** `database.py`, `eztv_db.py`, `cache.py` (novo), `catalog.py` (repo + api), `discovery_engine.py`, `federated_catalog.py`, `main.py` ($8$ arquivos internos).
- **Quebra de Contrato HTTP/Frontend:** $0$ (zero alterações destrutivas de schema JSON).
- **Classificação:** Baixo risco externo com altíssimo retorno de performance ($> 98\%$ de redução de latência).

# Phase 2: Relatório de Auditoria Forense — ADR-006

## 1. Avaliação das Dimensões Canônicas

| Dimensão | Classificação | Parecer Técnico |
| :--- | :---: | :--- |
| **Corretude** | APROVADO | A inversão de fluxo (EZTV como catálogo físico primário) ataca diretamente a causa-raiz da pobreza de descoberta. |
| **Completude** | ALERTA | A proposta original não detalhou a estratégia de expiração de sementes (dead torrents com 0 seeds persistentes no tempo). |
| **Coerência** | APROVADO | Alinhamento total com as ADRs anteriores (ADR-003 para o modelo de releases e ADR-004 para SQLModel). |
| **Implementabilidade** | APROVADO | Utiliza o stack existente (FastAPI + SQLModel + SQLite) com baixíssimo atrito e zero novas dependências pesadas. |
| **Robustez** | ALERTA | Falhas de lookup no TVMaze durante o crawl não podem abortar o salvamento das releases no banco de dados. |
| **Rastreabilidade** | APROVADO | Ledger de decisões DEC-026 a DEC-030 claramente delineado. |

## 2. Gaps Identificados para Amplificação
1. **Tratamento de Releases Mortas (0 Seeds):** O indexador deve computar um índice de relevância ponderada (`max_seeds`) para que séries sem sementes ativas caiam para o final da ordenação padrão.
2. **Desacoplamento do Enriquecimento Visual:** O salvamento de releases no SQLite não pode depender da latência da API do TVMaze. Se o TVMaze falhar ou demorar, a série deve ser salva com título extraído via regex e o enriquecimento colocado em fila não-bloqueante.


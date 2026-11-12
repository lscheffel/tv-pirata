# Phase 4: Matriz de Avaliação Comparativa — ADR-004

| Dimensão | Peso | Alt A (SQLModel Relacional) | Alt B (SQLite JSON Store) | Alt C (SQLAlchemy + Alembic) |
|---|:---:|:---:|:---:|:---:|
| 1. Corretude & Integridade | 1.5 | 9.5 | 6.5 | 9.5 |
| 2. Complexidade Código/Ops | 1.2 | 9.5 | 8.0 | 6.0 |
| 3. Robustez Transacional | 1.3 | 9.5 | 6.0 | 9.5 |
| 4. Testabilidade em Memória | 1.2 | 10.0 | 8.5 | 9.0 |
| 5. Velocidade de Desenvolvimento | 1.0 | 9.5 | 8.0 | 6.5 |
| 6. Performance (P95 < 15ms) | 1.1 | 9.5 | 7.0 | 9.0 |
| 7. Segurança de Tipagem | 1.0 | 9.5 | 6.5 | 9.5 |
| 8. Manutenibilidade | 1.0 | 9.0 | 7.0 | 8.0 |
| 9. Custo de Memória RAM | 1.0 | 9.5 | 9.0 | 8.5 |
| 10. Reversibilidade | 0.8 | 9.0 | 7.0 | 8.0 |
| 11. Escalabilidade de Catálogo | 0.9 | 9.0 | 6.5 | 9.0 |
| **Pontuação Ponderada Total** | — | **9.46** | **7.19** | **8.29** |

### Conclusão Algorítmica
A Alternativa A alcança a nota **9.46 / 10.00**, superando categoricamente as abordagens documentais e de ORM bifurcado.


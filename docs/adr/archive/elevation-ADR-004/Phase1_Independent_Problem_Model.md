# Phase 1: Modelo Independente do Problema — Persistência e API REST

## 1. Declaração do Problema
O TV Pirata possui modelos canônicos e provedores externos funcionais, mas opera em memória volátil sem persistência física do estado do usuário. O usuário precisa salvar séries em sua biblioteca pessoal, registrar o progresso de visualização por episódio, auditar se os arquivos de mídia física estão montados via SMB e consultar coleções customizadas através de endpoints REST acessíveis por um frontend web.

## 2. Invariantes & Restrições Inegociáveis
- **Invariante 1 (Atomicidade Transacional):** A inserção de uma série com suas temporadas e episódios deve ocorrer em uma única transação de banco.
- **Invariante 2 (Independência de Mídia Física):** A ausência ou desmontagem temporária do compartilhamento SMB altera `is_available = false`, mas é expressamente proibida de apagar a série ou seu histórico de visualizações.
- **Invariante 3 (Contrato REST Estável):** Todas as rotas devem responder com esquemas Pydantic v2 rigorosamente tipados.
- **Invariante 4 (Testabilidade Hermética):** A camada de persistência deve ser testável em memória (`sqlite:///:memory:`) sem deixar arquivos órfãos no disco.


# Fase 1: Modelo Independente do Problema (First-Principles Problem Model)

## 1. Decomposição de Primeiros Princípios

O sistema **TV Pirata** opera com dois bancos SQLite locais:
- `data/tv_pirata.db` (`5,7 MB`): Obras do catálogo federado (`MediaWork`), identificadores externos, créditos, disponibilidade de streaming, biblioteca pessoal, histórico de episódios e estatísticas P2P consolidadas (`CatalogShow`).
- `data/eztv_metadata.db` (`37 MB`): `860` séries (`shows`) e `140.571` episódios (`episodes_catalog`).

### O Problema Fundamental de Escalabilidade de Leitura
Em um sistema web interativo onde cada transição de aba dispara de 2 a 4 chamadas HTTP simultâneas (`/api/catalog/sections`, `/api/catalog/shows`, `/api/catalog/genres`, `/api/catalog/stats`, `/api/explore/works`):
1. **Assimetria Cardinal ($860 \text{ séries} \ll 140.571 \text{ episódios}$):** Qualquer query de listagem de séries que agregue `episodes_catalog` em tempo real sem filtro restrito de chaves paga um custo proporcional a $O(|E|)$ onde $|E| = 140.571$, resultando em centenas de milissegundos por chamada.
2. **Multiplicador de Seções Curadas ($7\times$):** Gerar 7 carrosséis na Home consultando o banco 7 vezes multiplica o custo fixo de serialização ORM e agregação.
3. **Reconstrução Repetitiva de Grafo Relacional em Python:** `DiscoveryEngineRepository.query_works` reconstrói em memória todas as relações $1:N$ (`WorkCredit`, `StreamingAvailability`, `_build_eztv_lookup`) a cada clique de filtro.

## 2. Invariantes Não-Negociáveis (Hard Constraints)
- **HC-1 (Isolamento Dual-DB — ADR-009):** `tv_pirata.db` e `eztv_metadata.db` permanecem fisicamente separados.
- **HC-2 (Hermeticidade Pytest):** A suíte de testes instancia bancos SQLite em memória (`sqlite://`) por teste e insere registros diretamente na sessão antes de chamar endpoints HTTP. Qualquer camada de cache que retorne dados obsoletos após `session.add() + session.commit()` quebrará testes ou causará bugs sutis.
- **HC-3 (Zero Dependências Externas de Infraestrutura):** Sem Redis/Memcached externo; solução 100% contida no processo Python/SQLite.
- **HC-4 (Consistência Imediata de Ações do Usuário):** Adicionar/remover da Minha Biblioteca ou marcar episódio como assistido deve refletir instantaneamente nas listagens.

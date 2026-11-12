# Phase 1: Modelo Independente do Problema (Primeiros Princípios)

## 1. Declaração do Problema
O TV Pirata necessita fornecer uma experiência rica e fluida de descoberta e controle de séries de TV para consumo em rede doméstica via SMB. As fontes externas de metadados sofrem com restrições de disponibilidade (TMDB sujeito a limites de requisição e instabilidade de tráfego internacional), a obtenção de torrents necessita ser desacoplada de clientes pesados, e o estado físico dos arquivos no armazenamento local é dinâmico.

## 2. Invariantes & Restrições Inegociáveis
- **Invariante 1 (Disponibilidade Resiliente):** Uma indisponibilidade temporária do TMDB não pode interromper a visualização ou navegação de séries.
- **Invariante 2 (Zero Custo de CPU em Repouso):** O sistema não deve executar transcodificação de mídia nem instanciar deamons de torrent contínuos.
- **Invariante 3 (Preservação Histórica):** O histórico de episódios assistidos do usuário não pode ser deletado quando um arquivo SMB for renomeado ou removido.
- **Invariante 4 (Testabilidade Determinística):** A suíte de testes deve rodar 100% offline em <5s no git hook.

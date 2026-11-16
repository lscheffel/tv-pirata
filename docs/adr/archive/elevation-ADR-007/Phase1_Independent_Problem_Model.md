# Phase 1 — Independent Problem Model: ADR-007

## 1. Problem Statement (First-Principles Formulation)

O TV Pirata é uma plataforma de gerenciamento e descoberta de séries em homelab. O usuário adiciona séries de interesse à sua "Biblioteca Pessoal". Na rede P2P (EZTV), episódios inéditos são lançados diariamente de forma descentralizada. 
Atualmente, o sistema exige que o usuário adivinhe o momento do lançamento ou clique repetidamente para verificar se há novos episódios. O problema central consiste em **como detectar confiavelmente novos episódios pertencentes às séries salvas do usuário, de forma automatizada, sem travar o servidor web, sem consumir recursos excessivos de rede/CPU e sem introduzir dependências de infraestrutura complexas (brokers, bancos adicionais ou processos órfãos).**

---

## 2. Goals & Success Criteria

1. **Automação P2P Passiva:** Detectar novos episódios das séries cadastradas pelo usuário sem exigir qualquer gatilho manual.
2. **Latência de Detecção:** Atraso máximo de detecção $\le 60$ minutos após o release ser disponibilizado na página recente da EZTV.
3. **Pegada Operacional Zero (Zero Infra Overhead):** Executar no mesmo runtime Python/FastAPI existente, sem exigir containers extras (Redis, RabbitMQ) ou daemons secundários (Celery).
4. **Idempotência Estrita:** Garantir que um mesmo release/episódio jamais gere alertas duplicados no banco de dados.
5. **Teardown Determinístico (Zero Processos Órfãos):** Interromper graciosamente qualquer loop ou tarefa em background no shutdown do servidor (SIGINT/SIGTERM), liberando a porta e sockets em $< 3$ segundos.

---

## 3. Constraints & Invariants

### Hard Constraints
- **C1 (Runtime):** Python 3.14 + FastAPI + SQLModel/SQLite. Nenhuma dependência externa C-heavy ou serviço de mensageria externo.
- **C2 (Anti-Orphan Invariant):** Nenhuma thread ou processo deve continuar rodando em background após o término do processo principal do FastAPI.
- **C3 (Anti-Abuse / Rate Limiting):** A frequência de requisições à API pública da EZTV não pode caracterizar abuso ou acarretar bloqueio de IP por Cloudflare.

### Invariants
- **INV-1:** Um evento de notificação em `ReleaseNotificationRecord` é estritamente único por tripla `(show_id, season, episode)`.
- **INV-2:** A falha temporária ou timeout na API da EZTV não pode causar crash nem interrupção do loop de agendamento.
- **INV-3:** A gravação de eventos de notificação não pode bloquear requisições HTTP ativas do usuário (sessões SQLite isoladas e de curta duração).


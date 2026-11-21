# Progresso — NutrIA

> Arquivo "onde paramos". Lido no início e atualizado no fim de cada sessão.
> Detalhe das tarefas: [04-quebra-de-tarefas.md](04-quebra-de-tarefas.md).

## Agora

- **Fase atual:** Fase 1, Simulador (não iniciada)
- **Próximo passo:** definir `MensagemEntrada`/`MensagemSaida` em `app/canais/base.py` e
  criar as tabelas `usuarios` e `mensagens`.
- **Bloqueios:** nenhum. A API key da Anthropic só será necessária na Fase 3.

## Status das fases

| Fase | Status |
|------|--------|
| Planejamento (docs 01–04) | ✅ Concluído |
| 0 — Fundação | ✅ Concluído |
| 1 — Simulador | ⬜ Não iniciado |
| 2 — Base nutricional | ⬜ Não iniciado |
| 3 — Agente v1 (texto) | ⬜ Não iniciado |
| 4 — Perfil e metas | ⬜ Não iniciado |
| 5 — Consultas e correções | ⬜ Não iniciado |
| 6 — Foto e áudio | ⬜ Não iniciado |
| 7 — Calibragem | ⬜ Não iniciado |
| 8 — WhatsApp | ⬜ Não iniciado |

## Decisões

| Data | Decisão | Motivo |
|------|---------|--------|
| 2026-11-21 | Python + FastAPI | Ecossistema de IA, código simples |
| 2026-11-21 | Claude como IA inicial, atrás da interface `ProvedorIA` | Qualidade, sem ficar preso a um provedor |
| 2026-11-21 | Vários modelos por rota (Haiku 5.5 dia a dia, Sonnet 5.5 foto/difícil, Opus 5.5 referência) | Velocidade e custo. A escolha final sai dos números da Fase 7 |
| 2026-11-21 | Groq (Whisper large-v3-turbo) para áudio | Rápido, preciso e barato |
| 2026-11-21 | Simulador web próprio em vez do WhatsApp para testes | Custo zero e painel de depuração |
| 2026-11-21 | Perguntas do bot sem limite fixo, calibradas nos testes | Conversa fluida, não engessada |
| 2026-11-21 | Tabela TACO como base nutricional | Alimentos brasileiros, números confiáveis |
| 2026-11-21 | Versões fixadas (`==`) no `requirements.txt` | Instalação idêntica em qualquer máquina |

## Diário de sessões

### 2026-11-21 — Sessão 1: planejamento e estrutura
- Planejamento feito por etapas e validado: visão/escopo, requisitos, roadmap, tarefas.
- Estrutura do projeto criada: pastas, `CLAUDE.md`, `.gitignore`, `.env.example`,
  `requirements.txt`, `config/modelos.yaml`, comandos `/retomar` e `/encerrar`.
- Git iniciado e conectado ao GitHub: https://github.com/LucasLisboa29/NutrIA (branch `main`).
- **Fase 0 concluída:** `.venv` com dependências fixadas; `app/config.py` (lê `.env` e
  `config/*.yaml`); `app/banco/sessao.py` (SQLite + SQLAlchemy); `app/main.py` com
  `GET /health` checando o banco; primeiro teste (`tests/test_health.py`) passando.
- Marco conferido: `localhost:8000/health` → `{"status":"ok","banco":"ok"}`.

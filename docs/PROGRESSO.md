# Progresso — NutrIA

> Arquivo "onde paramos". Lido no início e atualizado no fim de cada sessão.
> Detalhe das tarefas: [04-quebra-de-tarefas.md](04-quebra-de-tarefas.md).

## Agora

- **Fase atual:** Fase 3, Agente v1 (texto) (não iniciada)
- **Próximo passo:** criar a conta na Anthropic e pôr a `ANTHROPIC_API_KEY` no `.env`;
  depois, a interface `ProvedorIA` em `app/ia/base.py`.
- **A conferir pelo Lucas:** gravar um áudio pelo microfone no simulador (o teste
  automático não consegue usar o microfone).
- **Bloqueios:** a Fase 3 precisa da API key da Anthropic (o Lucas cria a conta).

## Status das fases

| Fase | Status |
|------|--------|
| Planejamento (docs 01–04) | ✅ Concluído |
| 0 — Fundação | ✅ Concluído |
| 1 — Simulador | ✅ Concluído |
| 2 — Base nutricional | ✅ Concluído |
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
| 2026-11-21 | Histórico e mídias gravados pelo núcleo (`app/nucleo/historico.py`), não pelo canal | Todo canal grava igual; o WhatsApp reaproveita |
| 2026-11-21 | Mídias em `uploads/<id do usuário>/`, datas em UTC no banco | Telefone fora dos nomes de arquivo (LGPD); fuso só na exibição |
| 2026-11-21 | Testes usam banco e uploads temporários (`tests/conftest.py`) | Nunca mexer no `nutria.db` de desenvolvimento |
| 2026-11-24 | Modo aprendizado como padrão; material de estudo em `Conteudo adicional/` | O Lucas usa o projeto para aprender IA |
| 2026-11-24 | Todo commit é seguido de push automático | Pedido do Lucas |
| 2026-11-24 | TACO em CSV do projeto raulfdm/taco-api (MIT), importada ao ligar o servidor | Planilha original já limpa; fonte citada em `dados/taco/LEIAME.md` |
| 2026-11-24 | Alimentos fora da TACO e correções em `dados/alimentos_extras.yaml`, com origem `derivado`/`manual` | Sempre dá para saber se um número é oficial ou nosso |
| 2026-11-24 | Leite integral/desnatado preenchidos à mão | A TACO marca esses valores com "*" (em reavaliação) |
| 2026-11-24 | Busca: sinônimo primeiro, depois aproximada (RapidFuzz), preferindo o preparado ao cru | "arroz" deve virar arroz cozido, não cru |
| 2026-11-24 | Porções com confiança alta/média/baixa e `explicacao` da conta | Base para RN02 (estimado visível) e para o painel de depuração |

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

### 2026-11-21 — Sessão 1 (cont.): Fase 1, simulador
- `app/canais/base.py`: `MensagemEntrada`, `MensagemSaida`, `Midia` e o protocolo `Adaptador`.
- Tabelas `usuarios` e `mensagens`; `app/nucleo/historico.py` grava, lista e apaga
  (inclusive os arquivos de mídia).
- `app/nucleo/orquestrador.py`: bot "eco" provisório.
- `app/canais/simulador.py`: `POST /simulador/mensagem` (texto + foto/áudio),
  histórico, lista de usuários, resetar e servir mídia.
- Tela estilo WhatsApp em `simulador/` (balões, horário, "digitando...", foto, gravação de
  áudio, seletor de telefone, resetar, painel com o JSON e o tempo da última resposta).
- 10 testes passando. Marco conferido no navegador: 2 usuários com históricos separados.

### 2026-11-24 — Sessão 2: Fase 2, base nutricional
- Tabela `alimentos` com a TACO (597) + 3 extras (macarrão cozido, pizza, pão de hambúrguer);
  importação automática ao ligar o servidor ou via `python -m app.nutricao.importar_taco`.
- Busca tolerante (`app/nutricao/taco.py`): sinônimos em `config/sinonimos.yaml`, plural,
  acento, erro de digitação, preferência pelo preparado.
- Medidas caseiras (`config/porcoes.yaml` + `app/nutricao/porcoes.py`) e cálculo
  (`app/nutricao/calculo.py`); pratos compostos em `config/pratos.yaml`.
- Achado: leite veio sem valores da TACO (marcado "*"); corrigido à mão e marcado.
- 47 testes passando. Marco: `calcular("arroz", 2, "colher de servir")` = 90 g, 115 kcal.
- A calibrar na Fase 7: PF sai ~630 kcal (provavelmente baixo; falta óleo do preparo).

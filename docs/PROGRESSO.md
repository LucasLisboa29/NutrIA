# Progresso — NutrIA

> Arquivo "onde paramos". Lido no início e atualizado no fim de cada sessão.
> Detalhe das tarefas: [04-quebra-de-tarefas.md](04-quebra-de-tarefas.md).

## Agora

- **Fase atual:** Fase 4, Perfil e metas (não iniciada)
- **Próximo passo:** tabelas `perfis` e `historico_peso` e a ferramenta `atualizar_perfil`
  (aceita dados parciais).
- **A conferir pelo Lucas:** gravar um áudio pelo microfone no simulador (o teste
  automático não consegue usar o microfone).
- **Bloqueios:** nenhum.

## Status das fases

| Fase | Status |
|------|--------|
| Planejamento (docs 01–04) | ✅ Concluído |
| 0 — Fundação | ✅ Concluído |
| 1 — Simulador | ✅ Concluído |
| 2 — Base nutricional | ✅ Concluído |
| 3 — Agente v1 (texto) | ✅ Concluído |
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
| 2026-11-24 | Laço de ferramentas próprio (não o tool runner beta do SDK) | Manter o núcleo independente do provedor (`ProvedorIA`) |
| 2026-11-24 | Data/hora e registros de hoje vão num bloco `<contexto>` junto da mensagem, não no prompt do sistema | O prompt do sistema fica fixo e aproveita o cache |
| 2026-11-24 | Histórico para a IA: últimas 12 mensagens (até 12 h), só texto | Contexto suficiente (RF04) sem custo crescente |
| 2026-11-24 | Campo `null` em `atualizar_item` = "não mudou" | Modelos mandam null em tudo; não pode apagar a quantidade |
| 2026-11-24 | Datas sempre em UTC no banco, inclusive as informadas ("ontem 20h") | O SQLite não guarda fuso; misturar daria comparações erradas |
| 2026-11-24 | Testes usam uma IA falsa roteirizada (`tests/ia_falsa.py`) | Testes grátis, rápidos e repetíveis; a IA real é testada à parte |
| 2026-11-24 | `tzdata` adicionado ao requirements | O Windows não traz a base de fusos (America/Sao_Paulo) |
| 2026-11-24 | Cache: marca explícita no fim do prompt do sistema + cache automático | Só o automático não reaproveitava prompt+ferramentas entre mensagens (medido: custo caiu ~60%) |
| 2026-11-24 | SDK da IA carregado ao ligar o servidor | A 1ª mensagem levava ~7 s por carregar o SDK |

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

### 2026-11-24 — Sessão 2 (cont.): Fase 3, agente com IA
- Camada de IA: `app/ia/base.py` (interface neutra), `claude.py` (SDK oficial, cache
  automático, esforço), `roteador.py` (modelo/esforço/preço por rota em `config/modelos.yaml`).
- Tabelas `refeicoes` e `itens_refeicao`; ferramentas `registrar_refeicao` (vários itens,
  pratos compostos, RF14 com `estimativa_ia`, refeições passadas) e `atualizar_item` (RF11).
- Orquestrador com laço de ferramentas (máx. 6 passos), histórico, `<contexto>` com data e
  registros de hoje, e tratamento de falha da IA sem perder o que já foi gravado (RN01).
- `config/prompt_sistema.md` escrito (registrar primeiro, perguntar com bom senso, estilo WhatsApp).
- Telemetria (tempo, tokens, custo por etapa) e painel com abas Depuração e Banco.
- 61 testes passando (14 novos do agente, com IA falsa). Falta o teste com a IA real.
- **Teste com a IA real (Haiku 5.5, esforço low):** marco ok (3 itens, ~492 kcal, perguntou
  do bife); "era grande" atualizou 100 → 140 g sem duplicar; "foi um copo de leite"
  corrigiu o item certo; "quanto comi hoje?" respondeu certo pelo contexto.
- **Números reais:** ~1,9–2,6 s por mensagem (sem contar a 1ª), US$ 0,0004–0,001 por
  mensagem (< R$ 0,01). Cache lendo ~3.400 tokens por chamada depois do ajuste.
- Corrigido: o simulador riscava texto entre dois "~" ("~150 g ... ~140 g"); agora segue
  a regra do WhatsApp.
- **Anotado para a calibragem (Fase 7):** a ferramenta `registrar_refeicao` leva ~250 ms
  (a busca aproximada lê os 600 alimentos a cada item); o histórico perde o cache das
  mensagens porque o `<contexto>` só vai na mensagem atual; o bot às vezes faz 2 perguntas
  de uma vez; ele preencheu "08:00" num café da manhã contado à noite (razoável, mas observar).

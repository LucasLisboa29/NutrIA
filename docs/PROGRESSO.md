# Progresso — NutrIA

> Arquivo "onde paramos". Lido no início e atualizado no fim de cada sessão.
> Detalhe das tarefas: [04-quebra-de-tarefas.md](04-quebra-de-tarefas.md).

## Agora

- **Fase atual:** Fase 6, Foto e áudio (não iniciada)
- **Próximo passo:** criar a conta na Groq e pôr a `GROQ_API_KEY` no `.env`; depois a
  interface `Transcritor` (`app/audio/base.py`) e o adaptador Groq.
- **A conferir pelo Lucas:** gravar um áudio pelo microfone no simulador (o teste
  automático não consegue usar o microfone).
- **Bloqueios:** a Fase 6 precisa da API key da Groq (o Lucas cria a conta).

## Status das fases

| Fase | Status |
|------|--------|
| Planejamento (docs 01–04) | ✅ Concluído |
| 0 — Fundação | ✅ Concluído |
| 1 — Simulador | ✅ Concluído |
| 2 — Base nutricional | ✅ Concluído |
| 3 — Agente v1 (texto) | ✅ Concluído |
| 4 — Perfil e metas | ✅ Concluído |
| 5 — Consultas e correções | ✅ Concluído |
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
| 2026-11-24 | Boas-vindas com o termo: texto fixo em `config/onboarding.yaml`, sem IA | Termo sempre idêntico (prova jurídica), instantâneo e grátis |
| 2026-11-24 | Aceite numa tabela própria (`consentimentos`) com data e versão do termo | Provar quando e com qual texto; nova versão pede aceite de novo |
| 2026-11-24 | Antes do aceite: prompt próprio e só a ferramenta `registrar_aceite`; o código também bloqueia as outras | RN07 garantida pelo código, não só pelo prompt |
| 2026-11-24 | Antes do aceite as mensagens do chat são guardadas, mas nenhum dado de saúde | Necessário para a conversa do aceite; dados sensíveis só depois. Recusa + apagar fica para a Fase 5 |
| 2026-11-24 | Meta calculada na hora a partir do perfil (não gravada) | Sempre coerente com o perfil atual; parâmetros em `config/metas.yaml` |
| 2026-11-24 | Mifflin-St Jeor; perder −20%, ganhar +10%; proteína 1,6–2,0 g/kg; gordura 25% | Referências gerais para adultos; ajustáveis no YAML |
| 2026-11-24 | Sem meta para menores de 18 anos | A fórmula é para adultos; o bot sugere nutricionista |
| 2026-11-24 | Idade guardada com a data em que foi informada | A idade "envelhece" sozinha |
| 2026-11-24 | "Quanto falta" dentro de `consultar_resumo` (campo `falta`), não uma ferramenta separada | Menos ferramentas = IA escolhe melhor; a conta continua no código |
| 2026-11-24 | Correção de quantidade/alimento usa `atualizar_item` (não um `corrigir_item` novo) | Já fazia exatamente isso, sem duplicar |
| 2026-11-24 | Apagar meus dados em 2 etapas garantidas pelo código (pedido e confirmação em mensagens diferentes, 10 min) | Ação irreversível não pode depender só da IA |
| 2026-11-24 | Apagamento explícito tabela por tabela, direto no banco | O cascade do ORM deixou escapar a mensagem atual (achado nos testes) |
| 2026-11-24 | Relógio simulado por requisição (ContextVar com deslocamento) | Testar dias/semanas sem esperar e sem afetar outros usuários |
| 2026-11-24 | Histórico vai para a IA com [dd/mm HH:MM] em cada mensagem do usuário | Sem datas, a IA achou que as refeições de ontem tinham "sumido" |
| 2026-11-24 | Pedido de apagar pendente aparece no `<contexto>` | Sem isso, a IA real pedia confirmação em laço |

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

### 2026-11-24 — Sessão 2 (cont.): Fase 4, perfil e metas
- Tabelas `consentimentos`, `perfis` e `historico_peso`; `app/nucleo/perfil.py`
  (aceite, perfil parcial com validação, histórico de peso) e `app/nucleo/metas.py`.
- Primeiro contato: boas-vindas fixas com o termo; prompt `config/prompt_onboarding.md`
  e ferramenta `registrar_aceite`; ferramenta `atualizar_perfil` no modo normal.
- Contexto da IA ganhou perfil, meta e o que falta; aba Banco mostra perfil, meta,
  aceite e pesos.
- 77 testes passando (16 novos). Marco conferido com a IA real: usuário novo foi de
  "oi" a meta de 2.888 kcal (conferida à mão) em 5 mensagens; depois o bot mostrou
  "616 de 2.888 kcal".
- Calibrado na hora: "almocei" às 21h agora registra às 12:30 (antes pedia o horário);
  "1 iogurte" = 1 pote (170 g).
- Observar na Fase 7: o bot ainda faz 2 perguntas por mensagem às vezes; respostas um
  pouco longas.

### 2026-11-24 — Sessão 2 (cont.): Fase 5, consultas e correções
- Ferramentas novas: `consultar_resumo` (dia e semana, com meta e quanto falta),
  `consultar_alimento` (sem registrar), `apagar_item`, `alterar_refeicao` e
  `apagar_meus_dados` (2 etapas). Resumos em `app/nucleo/registros.py`.
- Relógio simulado: campo "Fingir data e hora" no simulador; `agora()` respeita o
  deslocamento só durante a mensagem.
- Bug achado pelos testes: apagar o usuário deixava a mensagem atual no banco; agora o
  apagamento é explícito por tabela.
- 87 testes passando. Marco com a IA real: dia simulado de 25/11 (café, PF, banana →
  maçã, pizza 2 → 1 fatia) com resumo do dia batendo com o painel (1.209 kcal) e resumo
  da semana conferido à mão.
- Calibrado com a IA real: datas no histórico (a IA dizia que dados "sumiram" na virada
  do dia); não perguntar perfil já completo; aviso de pedido de apagar no contexto.

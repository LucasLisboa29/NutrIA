# Quebra de Tarefas — NutrIA

> Tarefas acionáveis, agrupadas por fase do [roadmap](03-roadmap.md).
> Marque com [x] o que estiver concluído. Esforço: **P** (até ~2h), **M** (meio dia), **G** (1 dia ou mais).
> Os códigos entre colchetes (RF/RN) apontam para os [requisitos](02-requisitos.md).
> Status: **validado** (etapa 4 de 4) em 2026-11-21.

## Estrutura de pastas proposta

```
NutrIA/
├── app/
│   ├── main.py                 # cria o FastAPI e registra as rotas
│   ├── config.py               # lê o .env e o config/*.yaml
│   ├── canais/                 # camada de canal (o núcleo não conhece o canal)
│   │   ├── base.py             # MensagemEntrada / MensagemSaida + interface Adaptador
│   │   ├── simulador.py
│   │   └── whatsapp.py         # (Fase 8)
│   ├── nucleo/
│   │   ├── orquestrador.py     # recebe a mensagem, chama a IA, executa ferramentas, responde
│   │   ├── ferramentas.py      # registrar_refeicao, corrigir_item, consultar_resumo...
│   │   └── metas.py            # cálculo de gasto calórico e metas
│   ├── ia/
│   │   ├── base.py             # interface ProvedorIA
│   │   ├── claude.py           # adaptador Anthropic
│   │   └── roteador.py         # escolhe modelo/esforço por rota
│   ├── audio/
│   │   ├── base.py             # interface Transcritor
│   │   └── groq.py
│   ├── nutricao/
│   │   ├── taco.py             # busca de alimentos
│   │   ├── porcoes.py          # medidas caseiras → gramas
│   │   └── calculo.py          # gramas → kcal e macros
│   ├── banco/
│   │   ├── modelos.py          # tabelas (SQLAlchemy)
│   │   └── sessao.py
│   └── telemetria.py           # tempo, tokens e custo de cada etapa (para o painel)
├── simulador/                  # front: index.html, style.css, app.js
├── config/
│   ├── prompt_sistema.md       # personalidade e regras da conversa (editável)
│   ├── modelos.yaml            # modelo e esforço por rota
│   └── porcoes.yaml            # porções padrão
├── dados/                      # TACO original e scripts de importação
├── cenarios/                   # conversas de teste (Fase 7)
├── tests/
├── docs/
├── .env.example
└── requirements.txt
```

## Fase 0 — Fundação

- [x] Instalar Python 3.12+ e conferir com `python --version` · P
- [x] Iniciar repositório Git e criar `.gitignore` (inclui `.env`, `*.db`, `.venv/`) · P
- [x] Criar ambiente virtual (`.venv`) e `requirements.txt` (fastapi, uvicorn, sqlalchemy, pydantic-settings, pyyaml, anthropic, pytest) · P
- [x] Criar a estrutura de pastas acima (vazia) · P
- [x] `app/config.py`: ler variáveis do `.env` e criar o `.env.example` · P
- [x] `app/main.py` com a rota `GET /health` · P
- [x] `app/banco/`: conexão SQLite + criação das tabelas ao iniciar · P
- [x] Marco: `localhost:8000/health` responde "ok" · P

## Fase 1 — Simulador

- [x] Definir `MensagemEntrada` e `MensagemSaida` (texto, imagem, áudio, remetente, horário) em `canais/base.py` · P
- [x] Tabelas `usuarios` e `mensagens` · P
- [x] Rota `POST /simulador/mensagem` (texto + arquivo opcional) → `AdaptadorSimulador` → orquestrador · M
- [x] Orquestrador provisório: bot "eco" que repete a mensagem · P
- [x] Rota para listar o histórico de um usuário · P
- [x] Tela do chat estilo WhatsApp (balões, horário, rolagem) em `simulador/` · M
- [x] Envio de foto (upload) e de áudio (gravar pelo microfone ou enviar arquivo) [RF28] · M
- [x] Seletor de "número de telefone" para alternar entre usuários de teste [RF29] · P
- [x] Botão "resetar usuário" [RF32] · P
- [x] Indicador de "digitando..." enquanto o servidor processa · P
- [x] Marco: 2 usuários com históricos separados · P

## Fase 2 — Base nutricional

- [x] Obter a Tabela TACO (4ª edição, NEPA/Unicamp) e salvar em `dados/` · P
- [x] Script de importação: limpar colunas (kcal, proteína, carboidrato, gordura, fibra por 100g) → tabela `alimentos` · M
- [x] Busca por nome tolerante (sem acento, minúsculas, sinônimos, aproximação com `rapidfuzz`) · M
- [x] Tabela de sinônimos populares ("pão francês" = "pão de sal", "aipim" = "mandioca") · M
- [x] `config/porcoes.yaml`: medidas caseiras e porção padrão por alimento (concha, colher de sopa/servir, fatia, unidade, copo, prato) · M
- [x] `calculo.py`: (alimento, quantidade, unidade) → gramas, kcal e macros · P
- [x] Tabela de pratos compostos (PF, strogonoff, feijoada) com ingredientes típicos [RF13] · M
- [x] Testes com pytest para busca, porções e cálculo · M
- [x] Marco: `calcular("arroz", 2, "colher de servir")` correto, sem IA · P

## Fase 3 — Agente v1 (texto)

- [x] Criar conta na Anthropic e gerar a API key (colocar no `.env`) · P
- [x] `ia/base.py`: interface `ProvedorIA` (mensagens + ferramentas → resposta + chamadas de ferramenta + uso de tokens) · M
- [x] `ia/claude.py`: adaptador com o SDK oficial `anthropic` · M
- [x] `ia/roteador.py` + `config/modelos.yaml`: modelo e esforço por rota · P
- [x] `config/prompt_sistema.md`: personalidade, regras de estimativa, como e quando perguntar [RF05, RN01–RN03] · M
- [x] Tabelas `refeicoes` e `itens_refeicao` (gramas, kcal, macros, `estimado`, `confianca`, `origem`) · P
- [x] Ferramenta `registrar_refeicao` (vários itens de uma vez; usa o módulo de nutrição) [RF07–RF10] · G
- [x] Ferramenta `atualizar_item` (resposta a uma pergunta, como "era grande") [RF11] · M
- [x] Item não encontrado na TACO → estimativa da IA marcada como baixa confiança [RF14] · P
- [x] Orquestrador real: laço de chamada de ferramentas com histórico recente [RF04] · G
- [x] Cache de prompt no prompt do sistema e nas ferramentas · P
- [x] `telemetria.py`: tempo por etapa, tokens e custo por mensagem · M
- [x] Painel de depuração no simulador: intenção, ferramentas chamadas, dados gravados, tokens, custo e tempo [RF30] · G
- [x] Recarregar prompt e config sem reiniciar o servidor [RF35] · P
- [x] Aba "banco" no simulador: refeições e totais do usuário [RF31] · M
- [x] Marco: "almocei arroz, feijão e um bife" grava 3 itens, e o painel mostra custo e tempo · P

## Fase 4 — Perfil e metas

- [x] Tabelas `perfis` e `historico_peso` · P
- [x] Ferramenta `atualizar_perfil` (aceita dados parciais) [RF17, RF19] · M
- [x] `metas.py`: Mifflin-St Jeor × nível de atividade ± objetivo, com piso de segurança [RF18, RN05] · M
- [x] Testes do cálculo de metas · P
- [x] Primeiro contato: apresentação + aceite LGPD registrado com data, antes de gravar qualquer dado [RF16, RN07] · M
- [x] Coleta de perfil conversada, sem obrigar a responder tudo de uma vez · M
- [x] Gravar o peso no histórico a cada atualização [RF20] · P
- [x] Marco: usuário novo termina com perfil e meta só conversando · P

## Fase 5 — Consultas e correções

- [x] Ferramenta `consultar_resumo` (dia e semana, comparado com a meta) [RF21, RF23] · M
- [x] Ferramenta `quanto_falta` [RF22] · P (feito dentro de `consultar_resumo`: campo `falta`)
- [x] Ferramenta `consultar_alimento` (sem registrar) [RF24] · P
- [x] Ferramentas `corrigir_item` e `apagar_item` (corrige sem duplicar) [RF12] · M
- [x] Mudar o tipo ou a data de uma refeição ("não foi almoço, foi janta") · P
- [x] "Apagar meus dados": apagamento real com confirmação [RF26] · P
- [x] Simulador: fingir data e hora [RF33] · M
- [x] Fuso de Brasília em todos os cálculos de "hoje" [RN04] · P
- [x] Marco: um dia simulado completo bate com o painel · P

## Fase 6 — Foto e áudio

- [x] Criar conta na Groq e gerar a API key · P
- [x] `audio/base.py` (interface `Transcritor`) + `audio/groq.py` · M
- [x] Áudio → texto → mesmo fluxo de texto; mostrar a transcrição no painel [RF03] · P
- [x] Converter formatos de áudio, se preciso (WhatsApp usa `.ogg`/opus) · P (não precisou: o Whisper aceita ogg e webm)
- [x] Rota de visão: foto (+ legenda) → modelo de visão → `registrar_refeicao` [RF02] · M
- [x] Resposta mostrando o que foi identificado, para o usuário conferir · P
- [x] Redimensionar imagens grandes antes de enviar (menos tokens, resposta mais rápida) · P
- [x] Marco: áudio "jantei duas fatias de pizza" e foto de prato registrados certo · P (foto testada com um prato desenhado; foto real a conferir pelo Lucas)

## Fase 6.5 — Fotos de verdade (calibragem antecipada)

> A foto é o jeito principal de usar o NutrIA. Antes da Fase 7, as fotos reais do Lucas
> foram analisadas (simulando o app) e viraram estas tarefas. Ver as Decisões no PROGRESSO.

**Etapa 1: correções rápidas**
- [x] Busca segura: a palavra principal precisa bater ("rosquinha" não vira feijão) · P
- [x] Tipo de alimento "receita" na base (ingredientes da TACO + rendimento → valor por 100 g) · M
- [x] Base NutrIA inicial: molho branco, macarrão ao molho branco, carbonara, lasanha bolonhesa, pizzas (frango com catupiry, calabresa), rosca doce, creme de confeiteiro, massa doce de torta, suco de frutas vermelhas · M
- [x] Prato composto aceita peso total ("600 g de carbonara") · P
- [x] Medidas novas: caneca (300 ml), pedaço de lasanha, colher de carne moída; sinônimos (bacon, carne de panela...) · P
- [x] Tipo "ao longo do dia" (`avulso`) para bebidas e beliscos · P
- [x] Prompt de foto: legenda manda, camadas para doces, só o que é da pessoa, perguntar na dúvida, prato meio comido · M

**Etapa 2: base própria e aprendizado**
- [x] Medidas e alimentos do usuário ("minha caneca = 350 ml") + ferramenta para ensinar · M
- [x] Itens frequentes do usuário no contexto (para perguntar "é a sua caneca de sempre?") · M
- [x] Fila de revisão: toda `estimativa_ia` vira tarefa de cadastro na Base NutrIA · M
- [x] Open Food Facts para produtos de marca (com atribuição, licença ODbL) · G

**Etapa 3: teste real**
- [x] Rodar as 11 fotos no app real e medir: itens certos, erro de kcal ≤ 25%, zero trocas graves, ≤ 2 chamadas, ≤ 10 s, ≤ US$ 0,002 · M
- [x] Corrigir o que a medição mostrou (peso × tamanho, prato meio comido, rosquinha, Open Food Facts só com marca) · M

## Fase 7 — Calibragem

- [x] Formato de cenário de teste (YAML: mensagens do usuário + o que deve estar gravado no fim) [RF34] · M (`cenarios/LEIAME.md`)
- [x] Executor de cenários com relatório (passou/falhou, custo, tempo) · G (`python -m cenarios.executar`)
- [ ] Escrever ~30 cenários cobrindo os exemplos dos requisitos e casos difíceis · G (25 de texto feitos; faltam os de foto, que dependem das fotos)
- [ ] Comparar modelos e esforço por rota (Haiku × Sonnet × Opus): tabela velocidade × custo × acerto · M
- [ ] Ajustar o prompt e as regras de pergunta com base nas conversas reais de teste · G
- [ ] Definir metas numéricas de tempo de resposta e de custo por refeição · P
- [ ] Revisar respostas: tamanho, tom e emojis no estilo WhatsApp [RF06] · M
- [ ] Marco: cenários passando dentro das metas · P

## Fase 8 — WhatsApp

- [ ] Conta Meta for Developers + app com o produto WhatsApp + número de teste · M
- [ ] `canais/whatsapp.py`: verificação do webhook, recebimento de mensagens e download de mídia · G
- [ ] Envio de respostas (texto) e indicador de leitura/digitando · M
- [ ] Validar a assinatura das requisições da Meta (segurança) · P
- [ ] Deploy num servidor com HTTPS (ex.: Railway, Render ou uma VPS) · M
- [ ] Trocar SQLite por Postgres em produção · M
- [ ] Logs sem telefone exposto (mascarar ou usar hash) [LGPD] · P
- [ ] Teste de ponta a ponta pelo seu WhatsApp · P
- [ ] Marco: mesmo comportamento do simulador no WhatsApp real · P

## Backlog / Ideias futuras

- Lembretes ativos ("já almoçou?"), que exigem templates pagos no WhatsApp.
- Planos alimentares e sugestões de cardápio.
- Exportar dados do usuário [RF27].
- Registro de água e bebidas [RF15] e dicas simples [RF25], se não entrarem antes.
- Gráficos de evolução (peso, calorias) enviados como imagem.
- Botões e listas interativas do WhatsApp para respostas rápidas.
- Painel para nutricionistas acompanharem pacientes.
- Outros provedores de IA (novos adaptadores de `ProvedorIA`).
- Multi-idioma.

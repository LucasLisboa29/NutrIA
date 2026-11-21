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
- [ ] Criar ambiente virtual (`.venv`) e `requirements.txt` (fastapi, uvicorn, sqlalchemy, pydantic-settings, pyyaml, anthropic, pytest) · P
- [x] Criar a estrutura de pastas acima (vazia) · P
- [ ] `app/config.py`: ler variáveis do `.env` e criar o `.env.example` · P
- [ ] `app/main.py` com a rota `GET /health` · P
- [ ] `app/banco/`: conexão SQLite + criação das tabelas ao iniciar · P
- [ ] Marco: `localhost:8000/health` responde "ok" · P

## Fase 1 — Simulador

- [ ] Definir `MensagemEntrada` e `MensagemSaida` (texto, imagem, áudio, remetente, horário) em `canais/base.py` · P
- [ ] Tabelas `usuarios` e `mensagens` · P
- [ ] Rota `POST /simulador/mensagem` (texto + arquivo opcional) → `AdaptadorSimulador` → orquestrador · M
- [ ] Orquestrador provisório: bot "eco" que repete a mensagem · P
- [ ] Rota para listar o histórico de um usuário · P
- [ ] Tela do chat estilo WhatsApp (balões, horário, rolagem) em `simulador/` · M
- [ ] Envio de foto (upload) e de áudio (gravar pelo microfone ou enviar arquivo) [RF28] · M
- [ ] Seletor de "número de telefone" para alternar entre usuários de teste [RF29] · P
- [ ] Botão "resetar usuário" [RF32] · P
- [ ] Indicador de "digitando..." enquanto o servidor processa · P
- [ ] Marco: 2 usuários com históricos separados · P

## Fase 2 — Base nutricional

- [ ] Obter a Tabela TACO (4ª edição, NEPA/Unicamp) e salvar em `dados/` · P
- [ ] Script de importação: limpar colunas (kcal, proteína, carboidrato, gordura, fibra por 100g) → tabela `alimentos` · M
- [ ] Busca por nome tolerante (sem acento, minúsculas, sinônimos, aproximação com `rapidfuzz`) · M
- [ ] Tabela de sinônimos populares ("pão francês" = "pão de sal", "aipim" = "mandioca") · M
- [ ] `config/porcoes.yaml`: medidas caseiras e porção padrão por alimento (concha, colher de sopa/servir, fatia, unidade, copo, prato) · M
- [ ] `calculo.py`: (alimento, quantidade, unidade) → gramas, kcal e macros · P
- [ ] Tabela de pratos compostos (PF, strogonoff, feijoada) com ingredientes típicos [RF13] · M
- [ ] Testes com pytest para busca, porções e cálculo · M
- [ ] Marco: `calcular("arroz", 2, "colher de servir")` correto, sem IA · P

## Fase 3 — Agente v1 (texto)

- [ ] Criar conta na Anthropic e gerar a API key (colocar no `.env`) · P
- [ ] `ia/base.py`: interface `ProvedorIA` (mensagens + ferramentas → resposta + chamadas de ferramenta + uso de tokens) · M
- [ ] `ia/claude.py`: adaptador com o SDK oficial `anthropic` · M
- [ ] `ia/roteador.py` + `config/modelos.yaml`: modelo e esforço por rota · P
- [ ] `config/prompt_sistema.md`: personalidade, regras de estimativa, como e quando perguntar [RF05, RN01–RN03] · M
- [ ] Tabelas `refeicoes` e `itens_refeicao` (gramas, kcal, macros, `estimado`, `confianca`, `origem`) · P
- [ ] Ferramenta `registrar_refeicao` (vários itens de uma vez; usa o módulo de nutrição) [RF07–RF10] · G
- [ ] Ferramenta `atualizar_item` (resposta a uma pergunta, como "era grande") [RF11] · M
- [ ] Item não encontrado na TACO → estimativa da IA marcada como baixa confiança [RF14] · P
- [ ] Orquestrador real: laço de chamada de ferramentas com histórico recente [RF04] · G
- [ ] Cache de prompt no prompt do sistema e nas ferramentas · P
- [ ] `telemetria.py`: tempo por etapa, tokens e custo por mensagem · M
- [ ] Painel de depuração no simulador: intenção, ferramentas chamadas, dados gravados, tokens, custo e tempo [RF30] · G
- [ ] Recarregar prompt e config sem reiniciar o servidor [RF35] · P
- [ ] Aba "banco" no simulador: refeições e totais do usuário [RF31] · M
- [ ] Marco: "almocei arroz, feijão e um bife" grava 3 itens, e o painel mostra custo e tempo · P

## Fase 4 — Perfil e metas

- [ ] Tabelas `perfis` e `historico_peso` · P
- [ ] Ferramenta `atualizar_perfil` (aceita dados parciais) [RF17, RF19] · M
- [ ] `metas.py`: Mifflin-St Jeor × nível de atividade ± objetivo, com piso de segurança [RF18, RN05] · M
- [ ] Testes do cálculo de metas · P
- [ ] Primeiro contato: apresentação + aceite LGPD registrado com data, antes de gravar qualquer dado [RF16, RN07] · M
- [ ] Coleta de perfil conversada, sem obrigar a responder tudo de uma vez · M
- [ ] Gravar o peso no histórico a cada atualização [RF20] · P
- [ ] Marco: usuário novo termina com perfil e meta só conversando · P

## Fase 5 — Consultas e correções

- [ ] Ferramenta `consultar_resumo` (dia e semana, comparado com a meta) [RF21, RF23] · M
- [ ] Ferramenta `quanto_falta` [RF22] · P
- [ ] Ferramenta `consultar_alimento` (sem registrar) [RF24] · P
- [ ] Ferramentas `corrigir_item` e `apagar_item` (corrige sem duplicar) [RF12] · M
- [ ] Mudar o tipo ou a data de uma refeição ("não foi almoço, foi janta") · P
- [ ] "Apagar meus dados": apagamento real com confirmação [RF26] · P
- [ ] Simulador: fingir data e hora [RF33] · M
- [ ] Fuso de Brasília em todos os cálculos de "hoje" [RN04] · P
- [ ] Marco: um dia simulado completo bate com o painel · P

## Fase 6 — Foto e áudio

- [ ] Criar conta na Groq e gerar a API key · P
- [ ] `audio/base.py` (interface `Transcritor`) + `audio/groq.py` · M
- [ ] Áudio → texto → mesmo fluxo de texto; mostrar a transcrição no painel [RF03] · P
- [ ] Converter formatos de áudio, se preciso (WhatsApp usa `.ogg`/opus) · P
- [ ] Rota de visão: foto (+ legenda) → modelo de visão → `registrar_refeicao` [RF02] · M
- [ ] Resposta mostrando o que foi identificado, para o usuário conferir · P
- [ ] Redimensionar imagens grandes antes de enviar (menos tokens, resposta mais rápida) · P
- [ ] Marco: áudio "jantei duas fatias de pizza" e foto de prato registrados certo · P

## Fase 7 — Calibragem

- [ ] Formato de cenário de teste (YAML: mensagens do usuário + o que deve estar gravado no fim) [RF34] · M
- [ ] Executor de cenários com relatório (passou/falhou, custo, tempo) · G
- [ ] Escrever ~30 cenários cobrindo os exemplos dos requisitos e casos difíceis · G
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

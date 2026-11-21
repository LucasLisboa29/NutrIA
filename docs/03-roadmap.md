# Roadmap — NutrIA

> Organiza o desenvolvimento em fases e marcos. Os prazos são **estimativas em semanas
> de dedicação parcial** (projeto pessoal, sem data fixa).
> Status: **validado** (etapa 3 de 4) em 2026-11-21.

## Decisões técnicas (fechadas na etapa 2)

### Transcrição de áudio → **Groq (Whisper large-v3-turbo)**
- **Rápido:** está entre os serviços de transcrição mais rápidos disponíveis. Um áudio de
  WhatsApp de ~20s volta em menos de 1s.
- **Preciso:** é o modelo Whisper da OpenAI, que vai bem em português.
- **Barato:** custa centavos de dólar por *hora* de áudio (confirmar o preço atual ao
  criar a conta). Tem plano gratuito com limite, suficiente para os testes.
- **Plano B:** OpenAI `gpt-4o-mini-transcribe`, ou Whisper local (grátis, mas lento num
  PC comum).
- Fica atrás de uma interface `Transcritor`, então trocar de serviço é trocar só um arquivo.

### Modelos de IA → **vários modelos, cada um no seu papel, e nada preso ao Claude**

O núcleo do bot fala com uma interface `ProvedorIA`. O Claude é a primeira implementação.
Se aparecer uma IA melhor, você cria outro adaptador e escolhe qual usar no arquivo de
configuração.

Também na configuração, cada **tipo de tarefa** ("rota") tem seu próprio modelo:

| Rota | Modelo inicial (candidato) | Por quê |
|------|---------------------------|---------|
| Mensagens do dia a dia (registrar, corrigir, consultar) | **Claude Haiku 5.5** (`claude-haiku-5-5`) | O mais rápido e barato da linha: US$ 0,10 / 1M tokens de entrada e US$ 0,50 / 1M de saída |
| Foto do prato e conversas difíceis | **Claude Sonnet 5.5** (`claude-sonnet-5-5`) | Mais inteligente, especialmente com imagem: US$ 2 / US$ 10 por 1M |
| Referência de qualidade (só nos testes) | **Claude Opus 5.5** (`claude-opus-5-5`) | O mais capaz (US$ 4 / US$ 20). Serve para comparar: "o Haiku está errando onde o Opus acerta?" |

> ⚠️ Essa tabela é um **ponto de partida, não uma decisão final**. Na Fase 7 a gente mede
> no simulador (velocidade, custo e acerto) e decide com números. Às vezes um modelo mais
> forte com *esforço baixo* sai melhor que um fraco, e o painel vai mostrar isso.

### Como deixar o bot rápido sem ficar burro

A demora numa aplicação com IA vem de algumas fontes, e cada uma tem um remédio:

1. **Modelo certo para cada tarefa:** a tabela acima.
2. **Esforço de raciocínio (`effort`) configurável:** nos modelos Claude atuais dá para
   ajustar quanto o modelo "pensa". Mensagens simples usam `low`, e casos difíceis um
   nível maior.
3. **Cache de prompt:** o prompt do sistema e as ferramentas são iguais em toda mensagem.
   Com cache, a API não reprocessa essa parte, e a resposta chega mais rápido e mais barata.
4. **A IA só decide, o código calcula:** buscar na TACO e somar macros é feito em Python
   (milissegundos), não pela IA.
5. **Poucas idas e voltas:** a IA chama várias ferramentas de uma vez (ex.: registrar 3
   alimentos numa chamada só), em vez de uma por vez.
6. **Percepção de velocidade:** no WhatsApp dá para mostrar "digitando..." enquanto o bot
   processa.
7. **Medir sempre:** o painel de depuração mostra o tempo de cada etapa (transcrição, IA,
   banco), para a gente saber onde está a demora antes de otimizar.

### Outras decisões
- **Front do simulador:** HTML + JavaScript simples, servido pelo próprio FastAPI, sem
  framework, para você focar no bot e não no front.
- **Banco:** SQLite + SQLAlchemy (migra para Postgres sem reescrever).
- **Versionamento:** Git desde o primeiro dia.

## Visão geral das fases

| Fase | Objetivo | Período estimado | Status |
|------|----------|------------------|--------|
| 0 — Fundação | Projeto Python organizado, rodando, com Git | semana 1 | Não iniciado |
| 1 — Simulador | Chat estilo WhatsApp conversando com um bot "eco" | semanas 1–2 | Não iniciado |
| 2 — Base nutricional | TACO + porções caseiras + cálculo de macros | semanas 2–3 | Não iniciado |
| 3 — Agente v1 (texto) | IA registrando refeições por texto + painel de depuração | semanas 3–5 | Não iniciado |
| 4 — Perfil e metas | Primeiro contato, aceite LGPD, perfil, cálculo de metas | semanas 5–6 | Não iniciado |
| 5 — Consultas e correções | Resumos, "quanto falta", corrigir e apagar | semanas 6–7 | Não iniciado |
| 6 — Foto e áudio | Entrada por imagem e por voz | semanas 7–8 | Não iniciado |
| 7 — Calibragem | Cenários de teste, ajustes de conversa, velocidade e custo | semanas 8–10 | Não iniciado |
| 8 — WhatsApp | Subir no WhatsApp Cloud API com número de teste | semanas 10–11 | Não iniciado |

## Detalhamento por fase

### Fase 0 — Fundação
- **Entregas:** estrutura de pastas; ambiente virtual Python; FastAPI rodando com uma rota
  `/health`; `.env` para as chaves (fora do Git); SQLite configurado; repositório Git.
- **Marco:** `http://localhost:8000/health` responde "ok".

### Fase 1 — Simulador
- **Entregas:** tela de chat estilo WhatsApp; troca de "número de telefone" (vários
  usuários de teste); envio de texto, foto e áudio (o bot ainda só ecoa); **camada de
  canal** (`AdaptadorSimulador`) já no formato que o WhatsApp vai usar depois; mensagens
  salvas no banco.
- **Marco:** você conversa com o bot eco em 2 usuários diferentes e cada um tem seu
  histórico.

### Fase 2 — Base nutricional
- **Entregas:** importação da Tabela TACO para o banco; busca de alimento por nome
  (com tolerância a variações: "feijão carioca" ≈ "feijão"); tabela de porções caseiras
  (concha, colher, fatia, unidade, prato); função que recebe "alimento + porção" e
  devolve gramas, kcal e macros; testes automatizados (pytest).
- **Marco:** `calcular("arroz", "2 colheres de servir")` retorna valores corretos sem
  usar IA.

### Fase 3 — Agente v1 (texto)
- **Entregas:** interface `ProvedorIA` + adaptador Claude; prompt do sistema em arquivo
  editável; ferramentas `registrar_refeicao` e `atualizar_item`; estimativa de porção e
  marcação de *estimado*; memória das últimas mensagens; **painel de depuração** (o que a
  IA entendeu, ferramentas chamadas, dados gravados, tokens, custo e tempo de cada etapa);
  visualização do banco por usuário.
- **Marco:** "almocei arroz, feijão e um bife" grava 3 itens corretos, e o painel mostra
  quanto custou e quanto demorou.

### Fase 4 — Perfil e metas
- **Entregas:** fluxo de primeiro contato conversado (apresentação + aceite LGPD);
  ferramenta `atualizar_perfil`; cálculo de metas (Mifflin-St Jeor + atividade +
  objetivo, com o piso de segurança da RN05); histórico de peso.
- **Marco:** um usuário novo, só conversando, termina com perfil e meta diária calculada.

### Fase 5 — Consultas e correções
- **Entregas:** ferramentas `consultar_resumo` (dia e semana), `quanto_falta`,
  `consultar_alimento`, `corrigir_item` e `apagar_item`; "apagar meus dados"; simulação de
  data/hora no simulador.
- **Marco:** um dia inteiro simulado (café, almoço, lanche, janta, uma correção) bate
  com a soma conferida no painel.

### Fase 6 — Foto e áudio
- **Entregas:** interface `Transcritor` + adaptador Groq; áudio → texto → mesmo fluxo;
  foto → rota de visão (Sonnet 5.5) → mesmas ferramentas de registro; resposta mostrando
  o que foi identificado para o usuário conferir.
- **Marco:** um áudio "jantei duas fatias de pizza" e uma foto de prato são registrados
  corretamente.

### Fase 7 — Calibragem
- **Entregas:** **cenários de teste** (conversas salvas que são reexecutadas e comparadas);
  comparação de modelos e níveis de esforço por rota (velocidade × custo × acerto); ajuste
  do prompt e das regras de quando perguntar; otimizações de velocidade (cache de prompt,
  esforço, chamadas paralelas).
- **Marco:** um conjunto de ~30 conversas de teste passando, com tempo médio de resposta
  e custo por refeição dentro de metas que vamos definir com os números em mãos.

### Fase 8 — WhatsApp
- **Entregas:** conta Meta for Developers + número de teste do WhatsApp Cloud API;
  `AdaptadorWhatsApp` (webhook de entrada + envio de resposta + download de mídia);
  deploy num servidor com HTTPS; indicador "digitando..."; aviso de privacidade.
- **Marco:** você conversa com o NutrIA pelo seu WhatsApp, com o mesmo comportamento do
  simulador.

## Dependências

- **Fase 1 depende da 0** (precisa do servidor rodando).
- **Fase 3 depende da 1 e da 2** (o agente precisa do canal para conversar e da base
  para calcular).
- **Fases 4, 5 e 6 dependem da 3**, mas são independentes entre si e podem ser feitas em
  qualquer ordem.
- **Fase 7 depende das 3–6** (calibrar exige as funcionalidades prontas). Medir custo e
  tempo, porém, começa já na Fase 3.
- **Fase 8 depende da 7** e de: conta na Meta, servidor com HTTPS e um número de
  telefone que não esteja em uso no WhatsApp comum.
- **Contas externas necessárias:** Anthropic (API key; Fase 3) e Groq (API key; Fase 6).

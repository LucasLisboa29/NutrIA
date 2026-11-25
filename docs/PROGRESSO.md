# Progresso — NutrIA

> Arquivo "onde paramos". Lido no início e atualizado no fim de cada sessão.
> Detalhe das tarefas: [04-quebra-de-tarefas.md](04-quebra-de-tarefas.md).

## Agora

- **Fase atual:** Fase 6.5, Fotos de verdade (Etapas 1 e 2 concluídas)
- **Próximo passo:** Etapa 3: rodar as 11 fotos de `Treinamento NutrIA/` no app real e medir
  (itens certos, erro de kcal ≤ 25%, zero trocas graves, ≤ 2 chamadas, ≤ 10 s, ≤ US$ 0,002).
- **A conferir pelo Lucas:** gravar um áudio de verdade pelo microfone do simulador.
- **Material de calibragem:** fotos e análise em `Treinamento NutrIA/` (fora do Git, fotos
  pessoais). Apagar a pasta quando a calibragem das fotos terminar (pedido do Lucas).
- **Bloqueios:** nenhum.

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
| 6 — Foto e áudio | ✅ Concluído |
| 6.5 — Fotos de verdade | 🟡 Etapas 1 e 2 de 3 concluídas |
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
| 2026-11-24 | Áudio transcrito antes (Groq Whisper, `language=pt` e vocabulário de comidas) e tratado como texto | Um só caminho de conversa; a transcrição fica gravada na mensagem |
| 2026-11-24 | Sem conversão de áudio | O Whisper aceita webm (navegador) e ogg/opus (WhatsApp) |
| 2026-11-24 | Fotos reduzidas para no máximo 1568 px, JPEG 85, com rotação EXIF aplicada | Menos tokens e menos tempo, sem perder qualidade para a IA |
| 2026-11-24 | Rota `visao` com Haiku 5.5 (medium) em vez de Sonnet | Medido na mesma foto: Sonnet medium 9,5 s / US$ 0,036; Haiku 2,9 s / US$ 0,0004; mesmos alimentos. Revisar com fotos reais |
| 2026-11-24 | `por_foto=true` força itens estimados e confiança no máximo média | Porção vista na foto é palpite (RF02) |
| 2026-11-24 | Foto não é reenviada no histórico (vira "[foto] legenda") e não é analisada antes do aceite | Custo por mensagem; LGPD |
| 2026-11-24 | Tomate-cereja como alimento derivado + sinônimos "salada verde", "bife grelhado" | A busca escolhia "tomate, purê" (300 g) e a IA gastava 2 chamadas corrigindo |
| 2026-11-24 | A foto é a funcionalidade principal; fase 6.5 de calibragem com fotos reais antes da Fase 7 | Decisão do Lucas: a maioria dos usuários vai registrar por foto |
| 2026-11-24 | Não depender só da TACO nem da IA: base em camadas (usuário → TACO → Base NutrIA → Open Food Facts → IA com fila de revisão) | Pedido do Lucas; a base cresce com o uso e a IA estima cada vez menos |
| 2026-11-24 | TBCA (USP) fora por enquanto | Consulta livre, mas uso em software exige licença paga |
| 2026-11-24 | Novo tipo de alimento "receita": ingredientes da TACO + rendimento | Pratos prontos com número rastreável até a TACO, sem número "de cabeça" |
| 2026-11-24 | Busca aproximada exige que toda palavra importante da consulta esteja no nome | "rosquinha" virava "feijão rosinha" e "torta de morango" virava "morango cru" |
| 2026-11-24 | Doces de doceria por camadas (morango + creme + massa) | Escolha do Lucas (método 1) |
| 2026-11-24 | Foto: registrar só o que é claramente do usuário; o resto, perguntar sem gravar | Decisão do Lucas (suco e prato da namorada na foto 1) |
| 2026-11-24 | Foto: item que não dá para identificar não é registrado; o bot pergunta. Gordura/ossos/restos não contam | Na simulação, gordura da carne virou "banana frita" |
| 2026-11-24 | Prato meio comido: perguntar antes de registrar (exceção à RN01) | O que aparece é o que sobrou, não o que foi comido |
| 2026-11-24 | Tipo "ao longo do dia" (`avulso`) e não falar de horário para bebidas e beliscos | Lucas: pessoas comuns não têm hábitos metódicos |
| 2026-11-24 | Medidas e alimentos do usuário (camada 1) com prioridade sobre as genéricas | Pedido do Lucas ("minha caneca"); reconhecer o recipiente pela foto não é confiável, então ele ensina uma vez |
| 2026-11-24 | Fila de revisão anônima (sem `usuario_id`) | Para cadastrar não importa quem pediu; apagar dados (LGPD) não mexe nela |
| 2026-11-24 | Open Food Facts pela API nova (search.openfoodfacts.org), com cache e timeout de 5 s | A antiga (cgi/search.pl) devolvia 503; internet fora do ar não pode travar o registro |
| 2026-11-24 | Produto do OFF de outro país = confiança baixa e perde para o rótulo lido na foto | Cobertura brasileira pequena; o Monster Ultra achado era o australiano |
| 2026-11-24 | Embalagem só vira porção se for individual (≤ 600 g/ml) | "1 lata de Toddy" virava 1 kg (4.000 kcal) |
| 2026-11-24 | Testes com OFF desligado (`OPENFOODFACTS_ATIVO=false`) e API falsa | Testes não podem depender da internet (um teste achou "sushi" no OFF real) |

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

### 2026-11-24 — Sessão 2 (cont.): Fase 6, foto e áudio
- Áudio: interface `Transcritor` (`app/audio/base.py`) + `TranscritorGroq`; o áudio é
  transcrito, gravado como texto na mensagem e segue o fluxo normal. Custo da Groq na
  telemetria (mínimo de 10 s cobrado).
- Foto: `app/ia/imagens.py` reduz a imagem; `MensagemUsuario` ganhou `imagens`; a rota
  `visao` é usada quando há foto; ferramenta com `por_foto`.
- Painel mostra a transcrição e o tamanho da imagem (original → enviada); chat mostra o
  texto do áudio no balão.
- 95 testes passando (transcritor falso + IA falsa).
- Marco com serviços reais: áudio gerado pela voz do Windows ("Jantei duas fatias de
  pizza...") → 4,7 s, US$ 0,0016; foto de um prato desenhado → 6,1 s, US$ 0,0009 (Haiku).
- Comparação de modelos na foto levou à troca Sonnet → Haiku na rota `visao` (ver Decisões).

### 2026-11-24 — Sessão 2 (cont.): Fase 6.5, calibragem com fotos reais (Etapa 1)
- Lucas trouxe 11 fotos reais (pasta `Treinamento NutrIA/`, fora do Git). Análise simulada
  sem gastar API: identificação pelo Claude Code, números pelo código real do app.
- Achados graves: busca trocando alimentos ("rosquinha" → feijão rosinha), pratos virando
  um ingrediente (lasanha = só a massa, 82 kcal), prato meio comido registrando o que sobrou,
  identificação errada (gordura vista como banana frita).
- Etapa 1 feita: busca segura, tipo "receita" + 10 receitas da Base NutrIA, prato por peso,
  caneca e outras medidas, tipo "ao longo do dia", prompt de foto com as decisões do Lucas.
- Resultado na simulação: itens com número da IA caíram de 6 para 1; lasanha 255 → 610 kcal,
  rosquinhas 136 (feijão) → 305 (rosca doce), torta 51 → 306 kcal.
- 117 testes passando.

### 2026-11-24 — Sessão 2 (cont.): Fase 6.5, Etapa 2 (base própria e aprendizado)
- Base de alimentos em camadas no código: usuário → TACO + Base NutrIA → Open Food Facts →
  estimativa da IA (que entra na fila de revisão).
- Memória do usuário (`app/nucleo/memoria.py`): ferramentas `ensinar_medida` e
  `ensinar_alimento` (rótulo ou receita dele); medidas, alimentos e itens frequentes vão no
  `<contexto>`.
- Fila de revisão (`app/nucleo/revisao.py`) com aba "Revisão" no simulador (marcar como
  cadastrado/ignorado).
- Open Food Facts (`app/nutricao/openfoodfacts.py`) com cache, preferência por produto do
  Brasil e trava de "embalagem individual".
- 131 testes. Teste com a IA real: "minha caneca tem 350 ml" → guardado; "uma caneca de
  achocolatado" → 350 ml (290 kcal), como "ao longo do dia".
- Observado: com a busca mais rígida, nomes longos ("achocolatado em pó preparado com
  leite") não são achados e a IA tenta de novo (1 chamada a mais). Medir na Etapa 3.
- Os testes ficaram mais lentos (~50 s): cada teste reimporta os 611 alimentos. Otimizar
  depois (carregar a base uma vez por rodada).

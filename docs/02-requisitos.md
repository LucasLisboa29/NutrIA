# Requisitos / Funcionalidades — NutrIA

> O que o projeto precisa ter. Prioridade no padrão MoSCoW
> (Must = obrigatório, Should = importante, Could = desejável).
> Status: **validado** (etapa 2 de 4) em 2026-11-21. Decisões em aberto foram fechadas
> no [roadmap](03-roadmap.md).

## Como o bot pensa (visão geral)

Toda mensagem passa pelo mesmo caminho, não importa o canal (simulador ou WhatsApp):

```
Mensagem (texto / foto / áudio)
   │
   ├─ áudio → transcrição (speech-to-text) → texto
   ├─ foto  → Claude com visão
   ▼
Agente (Claude + ferramentas)
   │  entende a intenção: registrar refeição? corrigir? perguntar algo? atualizar perfil?
   │  chama FERRAMENTAS do sistema, por exemplo:
   │    registrar_refeicao, corrigir_item, consultar_resumo, atualizar_perfil
   ▼
Núcleo (código Python)
   │  procura o alimento na TACO, converte porção → gramas, calcula calorias e macros
   │  grava no banco
   ▼
Resposta natural para o usuário
```

A ideia é dividir o trabalho: **a IA decide o que fazer e conversa**, e **o código
calcula e grava**. Assim os números são confiáveis e a conversa continua livre.

## Requisitos funcionais

### Conversa e entrada

| ID | Funcionalidade | Descrição | Prioridade |
|----|----------------|-----------|------------|
| RF01 | Conversa em linguagem natural | Entende mensagens informais, com gírias, erros de digitação e várias informações juntas ("tomei café com 2 pães e de almoço foi um PF") | Must |
| RF02 | Entrada por foto | Identifica os alimentos de uma foto e estima as porções; aceita legenda junto ("esse foi meu almoço") | Must |
| RF03 | Entrada por áudio | Transcreve a mensagem de voz e trata como texto | Must |
| RF04 | Memória de contexto | Lembra das últimas mensagens da conversa ("e mais um copo daquele suco" se refere ao suco citado antes) | Must |
| RF05 | Perguntas naturais quando faltar informação | Pergunta o que for relevante, no tom de uma conversa, sem formulário e sem limite fixo. O comportamento é configurável | Must |
| RF06 | Respostas curtas e amigáveis | Respostas no estilo de mensagem de WhatsApp (curtas, com emoji moderado e sem textão) | Should |

### Registro de refeições

| ID | Funcionalidade | Descrição | Prioridade |
|----|----------------|-----------|------------|
| RF07 | Registrar refeição | Grava os alimentos com quantidade em gramas, calorias, proteína, carboidrato e gordura | Must |
| RF08 | Estimativa de porção | Sem quantidade informada, usa uma porção padrão realista e marca o item como *estimado* | Must |
| RF09 | Porções caseiras | Converte medidas caseiras em gramas ("1 concha", "2 colheres de sopa", "1 fatia", "um prato cheio") | Must |
| RF10 | Tipo e horário da refeição | Deduz se é café, almoço, lanche, jantar ou ceia pelo texto ou pelo horário; aceita refeições passadas ("ontem à noite comi pizza") | Must |
| RF11 | Atualizar com respostas | Quando o usuário responde a uma pergunta ("era grande"), atualiza o item já gravado | Must |
| RF12 | Correções | "Na verdade foram 2 ovos", "apaga o suco", "não foi almoço, foi janta" | Must |
| RF13 | Pratos compostos | Decompõe pratos ("PF", "strogonoff", "X-tudo") em ingredientes típicos, ou usa um valor de prato pronto | Should |
| RF14 | Alimento não encontrado | Se não houver correspondência na TACO, usa a estimativa da IA, marcada como *baixa confiança*, e registra para revisão | Should |
| RF15 | Bebidas e água | Registra bebidas (com calorias) e consumo de água | Could |

### Perfil e metas

| ID | Funcionalidade | Descrição | Prioridade |
|----|----------------|-----------|------------|
| RF16 | Primeiro contato (onboarding) | Apresenta o bot, pede o aceite de uso dos dados (LGPD) e coleta o perfil de forma conversada, sem obrigar a responder tudo de uma vez | Must |
| RF17 | Perfil | Nome, sexo, idade, peso, altura, nível de atividade e objetivo (perder, manter ou ganhar peso) | Must |
| RF18 | Cálculo de metas | Calcula o gasto calórico (fórmula de Mifflin-St Jeor × nível de atividade) e a meta diária de calorias e macros conforme o objetivo | Must |
| RF19 | Atualizar perfil em conversa | "Tô pesando 78 agora", "quero focar em ganhar massa" | Must |
| RF20 | Histórico de peso | Guarda cada atualização de peso para mostrar a evolução | Should |

### Resumos e consultas

| ID | Funcionalidade | Descrição | Prioridade |
|----|----------------|-----------|------------|
| RF21 | Resumo do dia | "Quanto comi hoje?": total de calorias e macros, comparado com a meta | Must |
| RF22 | Quanto falta | "Quanto falta de proteína?", "posso comer um doce?" | Must |
| RF23 | Resumo semanal | Média da semana, dias dentro e fora da meta | Should |
| RF24 | Consultar alimento | "Quantas calorias tem uma banana?" (sem registrar) | Should |
| RF25 | Dicas simples | Sugestões gerais para bater a meta ("faltam 40g de proteína: um iogurte e 2 ovos resolvem") sem orientação clínica | Could |

### Dados e privacidade

| ID | Funcionalidade | Descrição | Prioridade |
|----|----------------|-----------|------------|
| RF26 | Apagar meus dados | O usuário pode pedir para apagar tudo ("apaga meus dados") | Must |
| RF27 | Exportar meus dados | Envia o histórico do usuário em um arquivo | Could |

### Simulador (plataforma de teste)

| ID | Funcionalidade | Descrição | Prioridade |
|----|----------------|-----------|------------|
| RF28 | Chat estilo WhatsApp | Tela web local para mandar texto, foto e áudio (gravar ou enviar arquivo) | Must |
| RF29 | Vários usuários de teste | Simula números de telefone diferentes, cada um com perfil e histórico separados | Must |
| RF30 | Painel de depuração | Ao lado do chat, mostra o que a IA entendeu, quais ferramentas chamou, o que foi gravado, os tokens usados e o custo de cada mensagem | Must |
| RF31 | Visualizar o banco | Ver as refeições e totais gravados de cada usuário de teste | Should |
| RF32 | Resetar usuário | Apagar o histórico de um usuário de teste para recomeçar | Must |
| RF33 | Simular data e hora | Fingir que é outro horário ou dia (para testar "almoço", resumos semanais etc.) | Should |
| RF34 | Cenários de teste | Salvar conversas de exemplo e reexecutar depois de mudar o prompt, para ver se algo piorou | Should |
| RF35 | Editar o comportamento sem reiniciar | Prompt e regras em arquivos que podem ser recarregados durante os testes | Should |

## Requisitos não-funcionais

- **Desempenho:** resposta em até ~5s para texto e ~10s para foto/áudio (tempo aceitável
  no WhatsApp).
- **Custo:** medir o custo por mensagem desde o início (RF30). Meta inicial: poucos
  centavos por refeição registrada.
- **Confiabilidade dos números:** calorias e macros sempre calculados pelo código a
  partir da base nutricional, nunca escritos "de cabeça" pela IA (exceto RF14, marcado).
- **Segurança e privacidade (LGPD):** chaves de API em `.env` (fora do código); telefone
  não aparece em logs; aceite registrado com data; apagamento real dos dados.
- **Configurabilidade:** personalidade, tom, quando perguntar e porções padrão ficam em
  arquivos de configuração, separados da lógica.
- **Portabilidade de canal:** o núcleo não conhece o canal. Simulador e WhatsApp são
  adaptadores que convertem mensagens de entrada e saída.
- **Limites do WhatsApp respeitados no simulador:** texto até 4096 caracteres, imagens,
  áudio e botões/listas simples.
- **Plataforma:** roda localmente no Windows (desenvolvimento); depois em um servidor
  Linux/nuvem com HTTPS (exigido pelo webhook do WhatsApp).

## Regras de negócio

- **RN01 – Nunca travar o registro:** toda refeição informada é gravada imediatamente,
  mesmo incompleta. Perguntas servem para refinar, não para bloquear.
- **RN02 – Estimado é visível:** itens com porção estimada ou baixa confiança são
  marcados no banco e podem ser indicados na resposta (ex.: "~150g").
- **RN03 – Perguntas com bom senso:** o bot pergunta quando a informação muda bastante o
  resultado (ex.: tamanho de um bife) e evita perguntar o óbvio (ex.: "1 banana").
  Os critérios exatos ficam na configuração e são calibrados nos testes.
- **RN04 – Fuso horário:** dias e refeições são contados no horário de Brasília
  (configurável por usuário no futuro).
- **RN05 – Meta mínima segura:** a meta calórica nunca fica abaixo de um piso seguro
  (ex.: 1200 kcal para mulheres e 1500 kcal para homens), mesmo com objetivo de perder peso.
- **RN06 – Sem orientação clínica:** o bot não diagnostica, não prescreve e recomenda
  procurar um profissional diante de condições de saúde.
- **RN07 – Aceite antes de gravar:** dados só são guardados depois do aceite de uso (LGPD).
- **RN08 – Assunto fora do escopo:** se o usuário falar de outra coisa, o bot responde com
  simpatia e volta ao tema de alimentação, sem virar um chat genérico.

## Exemplos de conversa (referência de comportamento)

**1. Informação incompleta, sem travar**
> 👤 almocei arroz feijão e um bife
> 🤖 Anotado seu almoço! 🍽️ Arroz (~150g), feijão (~140g) e bife (~120g): ~620 kcal.
> O bife era daqueles grandes ou normal?
> 👤 grande
> 🤖 Ajustei para ~180g. Almoço ficou em ~740 kcal. Hoje você está em 1.320 de 2.000 kcal.

**2. Usuário não responde (e tudo bem)**
> 👤 almocei arroz feijão e um bife
> 🤖 (registra e pergunta do bife)
> 👤 quanto comi hoje?
> 🤖 (responde o resumo usando a estimativa; o almoço já estava gravado)

**3. Correção**
> 👤 no café foram 2 ovos, não 1
> 🤖 Corrigido ✅ Café da manhã agora em ~390 kcal.

**4. Foto**
> 👤 [foto de um prato] janta
> 🤖 Vi arroz, frango grelhado, salada e batata doce. Registrei ~560 kcal. Confere?

## Critérios de aceite (funcionalidades-chave)

- **Registro por texto (RF07/RF08):** Dado um usuário com perfil, quando ele manda
  "almocei arroz, feijão e um bife", então uma refeição *almoço* é gravada com 3 itens,
  gramas preenchidas (estimadas), calorias e macros vindos da TACO, e a resposta mostra o
  total.
- **Sem travar (RN01):** Dado que o bot fez uma pergunta, quando o usuário manda outro
  assunto, então a refeição anterior continua gravada com a estimativa.
- **Correção (RF12):** Dado um café com "1 ovo", quando o usuário diz "foram 2 ovos",
  então o item é atualizado (não duplicado) e os totais do dia mudam.
- **Áudio (RF03):** Dado um áudio dizendo "jantei uma pizza, duas fatias", então o
  resultado é o mesmo de enviar esse texto.
- **Foto (RF02):** Dado uma foto de prato comum, então os alimentos principais são
  identificados e gravados como *estimados*.
- **Metas (RF18):** Dado o perfil completo, então a meta diária é calculada e respeita o
  piso da RN05.
- **Resumo (RF21):** "Quanto comi hoje?" retorna a soma correta das refeições do dia
  (conferível no painel RF31).
- **Painel (RF30):** Cada mensagem no simulador mostra as ferramentas chamadas, os dados
  gravados, os tokens e o custo.

## Decisões técnicas em aberto (para a etapa de roadmap/arquitetura)

- **Transcrição de áudio:** Whisper via OpenAI (pago, simples), Groq (barato e rápido) ou
  Whisper local (grátis, exige mais do computador).
- **Modelo Claude:** usar um modelo mais forte para fotos e conversas difíceis e um mais
  barato para mensagens simples, ou um só para tudo no começo.
- **Front do simulador:** HTML/JS simples servido pelo próprio FastAPI (recomendado) ou
  um framework (React).

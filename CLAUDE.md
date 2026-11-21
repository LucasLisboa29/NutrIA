# NutrIA — instruções para o Claude

Bot "nutricionista no WhatsApp". O usuário conversa de forma natural (texto, foto ou
áudio) e o sistema registra as refeições com calorias e macros. Durante o
desenvolvimento, tudo é testado num **simulador web local**. O WhatsApp entra só no fim.

## Ao começar QUALQUER sessão

1. Leia `docs/PROGRESSO.md`: fase atual, o que foi feito por último e o próximo passo.
2. Se precisar de contexto, consulte os documentos de planejamento (já validados):
   - `docs/01-visao-e-escopo.md`: o porquê e os limites
   - `docs/02-requisitos.md`: requisitos (RFxx), regras de negócio (RNxx), exemplos de conversa
   - `docs/03-roadmap.md`: as 9 fases, decisões técnicas e dependências
   - `docs/04-quebra-de-tarefas.md`: checklist de tarefas por fase
3. Trabalhe na fase indicada no PROGRESSO. Não pule fases sem o Lucas pedir.

## Ao terminar uma sessão (ou um bloco de trabalho)

- Marque `[x]` nas tarefas concluídas em `docs/04-quebra-de-tarefas.md`.
- Atualize `docs/PROGRESSO.md`: status da fase, uma entrada no diário da sessão e o
  próximo passo concreto.
- Registre decisões novas na seção "Decisões" do PROGRESSO (com data e motivo).

## Princípios de arquitetura (não quebrar)

- **A IA interpreta, o código calcula.** kcal e macros vêm de `app/nutricao/` + Tabela
  TACO, nunca de valores escritos pela IA (exceção: RF14, marcado como baixa confiança).
- **Nunca travar o registro (RN01).** Grava na hora com estimativa e refina com as
  respostas do usuário.
- **Conversa fluida.** Sem limite fixo de perguntas. O comportamento fica em
  `config/prompt_sistema.md` e é calibrado nos testes. Não engessar no código.
- **Núcleo independente do canal.** `app/canais/` converte simulador/WhatsApp ↔
  `MensagemEntrada`/`MensagemSaida`. O núcleo não sabe de onde veio a mensagem.
- **Não ficar preso a um provedor.** IA atrás de `ProvedorIA` (`app/ia/`), áudio atrás de
  `Transcritor` (`app/audio/`). Modelo e esforço por rota em `config/modelos.yaml`.
- **Velocidade importa.** Medir tempo, tokens e custo de cada etapa (`app/telemetria.py`)
  e otimizar com base nos números.
- **LGPD.** Aceite antes de gravar, telefone fora dos logs, apagamento real dos dados.

## Stack

Python 3.12 · FastAPI · SQLAlchemy + SQLite · front do simulador em HTML/JS puro ·
Claude via SDK oficial `anthropic` · Groq (Whisper) para áudio · pytest.

## Como rodar (quando a Fase 0 estiver pronta)

```powershell
.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
```

## Sobre o Lucas (como trabalhar com ele)

- Estudante de Ciência da Computação. Conversar **em português**.
- Quer **aprender** com o projeto: explicar conceitos novos de forma simples (ele não
  conhecia a LGPD, por exemplo). Evitar jargão sem explicação.
- Gosta de validar por etapas antes de seguir.
- Chaves de API ficam só no `.env` (nunca no código ou no Git).

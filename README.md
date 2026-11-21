# NutrIA 🥗

Um "nutricionista no WhatsApp": você conta o que comeu do seu jeito (por texto, foto ou
áudio) e o bot registra as calorias e os macros, acompanha suas metas e responde
perguntas como "quanto comi hoje?".

> 🚧 Em desenvolvimento. Veja onde o projeto está em [docs/PROGRESSO.md](docs/PROGRESSO.md).

## Documentação

| Documento | Conteúdo |
|-----------|----------|
| [Progresso](docs/PROGRESSO.md) | Onde paramos, decisões e diário de sessões |
| [Visão e Escopo](docs/01-visao-e-escopo.md) | Objetivo, público, o que entra e o que não entra |
| [Requisitos](docs/02-requisitos.md) | Funcionalidades, regras de negócio e exemplos de conversa |
| [Roadmap](docs/03-roadmap.md) | Fases, decisões técnicas e dependências |
| [Quebra de Tarefas](docs/04-quebra-de-tarefas.md) | Checklist por fase |

## Estrutura

```
app/          backend (FastAPI)
  canais/     simulador e WhatsApp → formato único de mensagem
  nucleo/     orquestrador, ferramentas do bot, cálculo de metas
  ia/         interface ProvedorIA + adaptador Claude + roteador de modelos
  audio/      interface Transcritor + adaptador Groq
  nutricao/   Tabela TACO, porções caseiras, cálculo de macros
  banco/      modelos e sessão do banco de dados
simulador/    tela de chat estilo WhatsApp (HTML/JS)
config/       prompt do bot, modelos por rota, porções padrão
dados/        Tabela TACO e scripts de importação
cenarios/     conversas de teste para calibragem
tests/        testes automatizados (pytest)
docs/         planejamento e progresso
```

## Como rodar (a partir da Fase 0)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env   # e preencha as chaves
uvicorn app.main:app --reload
```

O simulador fica em `http://localhost:8000` (a partir da Fase 1).

# Visão e Escopo — NutrIA

> Documento de alinhamento inicial. Define o "porquê" e os limites do projeto.
> Status: **validado** (etapa 1 de 4), com os ajustes do Lucas em 2026-11-21.

## Objetivo

Criar um "nutricionista no WhatsApp": um bot que entende o que o usuário comeu, escrito
de forma natural (ou mandado em foto), grava cada refeição de forma estruturada, com
calorias e macros, e acompanha o usuário em relação às metas dele.

## Problema / Oportunidade

Os apps de dieta exigem que o usuário pesquise cada alimento e informe a gramagem
exata. Isso dá trabalho, e por isso a maioria das pessoas desiste em poucos dias.
O WhatsApp já é aberto várias vezes ao dia. Mandar "almocei arroz, feijão e um bife"
é tão fácil quanto mandar mensagem para um amigo.

## Público-alvo

- **No início: pessoas comuns** que querem controlar a alimentação (emagrecer, ganhar
  massa ou só comer melhor) sem a burocracia de um app de dieta.
- Públicos mais específicos (academias, pacientes de nutricionista) ficam para depois.

## Proposta de valor

- **Zero atrito**: o usuário escreve como fala, sem formulário e sem gramagem obrigatória.
- **Conversa fluida, não engessada**: se falta uma informação, o bot estima uma porção
  padrão e marca o item como *estimado*. Ele pode perguntar o que achar relevante, do jeito
  que uma pessoa perguntaria, mas o registro nunca fica travado esperando resposta.
  Não há um limite fixo de perguntas: o comportamento vem da configuração do bot (prompt
  e regras) e vai ser **ajustado com base nos testes no simulador**.
- **Texto, foto ou áudio**: o usuário manda do jeito que preferir.
- **Números confiáveis**: a IA *interpreta* o texto, mas calorias e macros vêm de uma
  tabela nutricional real (TACO), não de um palpite da IA.
- **No canal que o usuário já usa**: o WhatsApp.

## Escopo (dentro) — MVP

1. **Simulador de chat local** (web, com cara de WhatsApp) para desenvolver e testar sem
   custo de WhatsApp.
2. **Camada de canal** desacoplada: o mesmo núcleo do bot atende o simulador agora e o
   WhatsApp depois.
3. **Registro de refeições por texto livre**: extrai alimentos, quantidades (ou estima),
   tipo de refeição e horário, e grava com calorias e macros.
4. **Foto do prato**: a IA identifica os alimentos e estima as porções a partir da imagem.
5. **Áudio**: o usuário manda mensagem de voz, o sistema transcreve e trata como texto.
6. **Perguntas de esclarecimento naturais**: "o bife era pequeno, médio ou grande?".
   O registro fica salvo com a estimativa e é atualizado se o usuário responder.
   A forma e a frequência das perguntas são calibradas nos testes.
7. **Correções em linguagem natural**: "na verdade foram 2 ovos", "apaga o suco".
8. **Perfil e metas**: peso, altura, idade, sexo, nível de atividade e objetivo. O bot
   calcula a meta diária de calorias e macros.
9. **Resumos e consultas**: "quanto comi hoje?", "quanto falta de proteína?", resumo
   diário e semanal.

## Fora de escopo (por enquanto)

- Integração real com o WhatsApp (fica para a fase final, depois do MVP validado).
- Montar planos alimentares e cardápios personalizados.
- Mensagens ativas/lembretes ("já almoçou?"), porque no WhatsApp elas exigem templates pagos.
- Pagamentos e assinaturas.
- Painel para nutricionistas humanos acompanharem pacientes.
- Diagnóstico ou orientação clínica (diabetes, alergias etc.).

## Premissas

- **Stack**: Python + FastAPI no backend; SQLite no desenvolvimento (com migração fácil
  para Postgres).
- **IA**: Claude (Anthropic) via API, usando *tool use* para extrair dados estruturados
  e visão para fotos. É preciso uma API key da Anthropic.
- **Áudio**: o Claude não recebe áudio direto, então é preciso um serviço de transcrição
  (*speech-to-text*). Exemplos: Whisper (OpenAI ou rodando local) e Groq. A escolha
  fica para a etapa de requisitos/arquitetura.
- **Comportamento da conversa** fica em arquivos de configuração (prompt do sistema e
  regras), fáceis de editar entre um teste e outro sem mexer no código.
- **Base nutricional**: Tabela TACO (alimentos brasileiros), complementada por uma tabela
  própria de **porções caseiras** (concha, colher de sopa, fatia, unidade → gramas).
- O WhatsApp entra depois, via **WhatsApp Cloud API** (oficial da Meta).
- Projeto pessoal/acadêmico do Lucas. No início, sem equipe e sem prazo comercial.

## Riscos

| Risco | Impacto | Mitigação |
|-------|---------|-----------|
| IA "inventa" calorias ou alimentos | Alto | IA só interpreta; números vêm da TACO; itens sem correspondência ficam marcados para revisão |
| Estimativa de porção muito errada | Médio | Porções padrão realistas; marcar como *estimado*; perguntar só quando o impacto for grande |
| Bot pergunta demais (ou de menos) e a conversa fica chata ou imprecisa | Médio | Comportamento configurável; calibrar com conversas de teste no simulador; nunca bloquear o registro |
| Transcrição de áudio errada (sotaque, barulho, nome de comida) | Médio | Mostrar o que foi entendido; permitir correção; testar com áudios reais |
| Foto com estimativa imprecisa | Médio | Mostrar o que foi entendido e permitir correção fácil |
| Custo da API de IA por mensagem | Médio | Modelo menor para tarefas simples; cache de prompt; medir custo por conversa no simulador |
| Questões legais/éticas (orientação de saúde) | Médio | Aviso de que não substitui um profissional; não dar orientação clínica |
| LGPD (Lei Geral de Proteção de Dados; dados de saúde são "sensíveis") | Médio | Consentimento no primeiro uso, opção de apagar dados, não expor telefone em logs |
| Diferenças de comportamento entre o simulador e o WhatsApp | Baixo | Simulador respeita limites do WhatsApp (texto, imagens, botões simples) |

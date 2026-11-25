# Cenários de teste (Fase 7, RF34)

Conversas de exemplo que rodam com a **IA de verdade**, para ver se o bot continua se
comportando bem depois de mudar o prompt, o modelo ou o código. Diferente do `pytest`
(IA falsa, grátis), aqui cada mensagem custa um pouco (Haiku: ~US$ 0,001).

```powershell
python -m cenarios.executar --listar          # lista e valida o formato (grátis)
python -m cenarios.executar                   # roda tudo
python -m cenarios.executar correcao foto     # só os que têm esses trechos no nome ou nas tags
python -m cenarios.executar --repetir 3       # a IA varia: rodar 3x mostra se é estável
python -m cenarios.executar --modelo claude-sonnet-5-5 --esforco medium
```

O relatório sai em `cenarios/relatorios/` (`.md` para ler, `.json` com tudo). Roda num
banco temporário: o `nutria.db` não é tocado e o servidor não precisa estar ligado.

## Formato

Cada `.yaml` desta pasta tem uma lista `cenarios:`. Um cenário:

```yaml
- nome: bife_grande                  # único, sem espaços
  descricao: o "grande" ajusta o bife sem duplicar
  tags: [texto, correcao]            # para filtrar
  agora: "12:40"                     # hora simulada (Brasília). Também: "ontem 20:00",
                                     # "2026-11-25 12:40". Padrão: 12:40 de hoje.
  usuario:                           # como o usuário começa (tudo opcional)
    aceite: true                     # padrão true; false = primeiro contato
    perfil: {sexo: masculino, idade: 30, peso_kg: 80, altura_cm: 175,
             nivel_atividade: moderado, objetivo: manter}
    medidas: [{unidade: caneca, gramas: 350}]
  conversa:
    - usuario: almocei arroz feijão e um bife
      # foto: fotos/prato1.jpg       # opcional, relativo a cenarios/ (fotos ficam fora do Git)
      # agora: "13:10"               # opcional; sem isso, cada mensagem vem 2 min depois
      espera:                        # conferido nesta mensagem (tudo opcional)
        ferramentas: [registrar_refeicao]      # tem que ter chamado
        sem_ferramentas: [apagar_item]         # não pode ter chamado ("*" = nenhuma)
        max_perguntas: 1                       # frases terminadas em "?"
        max_chamadas_ia: 2
        max_linhas: 4
        resposta_contem: [bife]                # sem acento e sem maiúscula
        resposta_contem_algum: [nutricionista, médico]
        resposta_nao_contem: ["**"]
    - usuario: grande
  final:                             # conferido no banco, no fim da conversa
    refeicoes:                       # a quantidade tem que bater; na ordem do horário
      - tipo: almoco                 # ou lista: [lanche_da_tarde, avulso]
        dia: hoje                    # hoje | ontem
        itens: 3                     # número exato ou faixa [2, 4]
        kcal: [450, 900]             # faixa [mín, máx]
        contem: [arroz, feijao, bife]
        nao_contem: [suco]
        item:
          bife: {gramas: [150, 250]}
    total_kcal: [450, 900]
    sem_estimativa_ia: true          # nenhum item com número "da cabeça" da IA
    perfil: {idade: 30, altura_cm: [174, 176]}
    medidas: {caneca: 350}
    aceite: true
    usuario_existe: true             # false depois de "apagar meus dados"
```

## Como escrever um bom cenário

- **Conferir princípios, não frases.** A IA nunca responde igual duas vezes. Confira o
  que importa (gravou? sem duplicar? perguntou demais?) e use faixas largas nas kcal.
- **Faixas honestas.** A faixa é "um nutricionista acharia razoável", não o número que
  saiu da última rodada.
- **Foto:** a foto dá contexto e a estimativa busca a realidade (ver o prompt). Nos
  cenários de foto, confira que gravou na hora, que a legenda venceu a foto e que nenhum
  alimento foi trocado; kcal só com faixa bem larga.

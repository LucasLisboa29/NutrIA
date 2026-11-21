"""Tabelas do banco de dados.

Cada classe aqui vira uma tabela. Elas vão sendo adicionadas fase a fase:
- Fase 1: usuarios, mensagens
- Fase 2: alimentos, porcoes
- Fase 3: refeicoes, itens_refeicao
- Fase 4: perfis, historico_peso
"""

from app.banco.sessao import Base  # noqa: F401

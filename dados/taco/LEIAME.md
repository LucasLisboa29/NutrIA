# Tabela TACO

**Fonte:** NEPA/UNICAMP. *Tabela Brasileira de Composição de Alimentos (TACO)*, 4ª edição
revisada e ampliada. Campinas: NEPA-UNICAMP, 2011. A reprodução é permitida desde que
citada a fonte.

**Arquivos:** os CSVs foram obtidos do projeto
[raulfdm/taco-api](https://github.com/raulfdm/taco-api) (licença MIT), que converteu a
planilha original da Unicamp e fez esta limpeza:

- `NA` (não aplicável) e `*` (amostra em reavaliação) viraram célula vazia;
- `Tr` (traço, quantidade desprezível) virou `0`.

| Arquivo | Conteúdo |
|---|---|
| `food.csv` | id, categoria e nome dos 597 alimentos |
| `nutrients.csv` | nutrientes por 100 g (usamos kcal, proteína, carboidrato, lipídeos, fibra e sódio) |
| `categories.csv` | as 15 categorias |

A importação para o banco está em `app/nutricao/importar_taco.py`. Complementos e
correções nossos (marcados com origem `derivado` ou `manual`) ficam em
`dados/alimentos_extras.yaml`, nunca nestes CSVs.

## Outras fontes (camadas da base de alimentos)

1. **Alimentos e medidas do usuário**: o que cada pessoa ensina ao bot (tabelas
   `medidas_usuario` e `alimentos_usuario`).
2. **TACO** (esta pasta) + **Base NutrIA** (`dados/alimentos_extras.yaml`: receitas montadas
   com ingredientes da TACO, derivados e correções).
3. **Open Food Facts** (produtos de marca), consultado pela internet e guardado em cache
   (`produtos_off`). Dados © Open Food Facts contributors, licença
   [ODbL](https://opendatacommons.org/licenses/odbl/1-0/): é obrigatório citar a fonte.
   Itens dessa origem aparecem com "dados: Open Food Facts (ODbL)" na explicação.
4. **Estimativa da IA**: último recurso, marcada como confiança baixa e enviada para a fila
   de revisão (`revisao_alimentos`) para virar cadastro.

A TBCA (USP) ficou de fora: a consulta é livre, mas o uso dentro de um software exige
licença paga.

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

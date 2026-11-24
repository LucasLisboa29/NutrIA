"""Importa a Tabela TACO (CSV em `dados/taco/`) para a tabela `alimentos`.

Roda sozinho ao ligar o servidor, se a tabela estiver vazia. Para reimportar à força
(depois de mexer nos dados):

    python -m app.nutricao.importar_taco

Os CSVs vieram do projeto github.com/raulfdm/taco-api (MIT), que já limpou a planilha
original: "NA" e "*" viraram vazio, e "Tr" (traço, quantidade desprezível) virou 0.
"""

import csv
from pathlib import Path

import yaml
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.banco.modelos import Alimento
from app.config import RAIZ
from app.nutricao.texto import normalizar

PASTA_TACO = RAIZ / "dados" / "taco"
ARQUIVO_EXTRAS = RAIZ / "dados" / "alimentos_extras.yaml"

# Nome da coluna no CSV -> nome do campo na nossa tabela.
COLUNAS = {
    "kcal": "kcal",
    "protein": "proteina",
    "carbohydrates": "carboidrato",
    "lipids": "gordura",
    "dietaryFiber": "fibra",
    "sodium": "sodio",
}
NUTRIENTES = list(COLUNAS.values())


def garantir_base(db: Session) -> None:
    """Importa só se a tabela estiver vazia (chamado ao iniciar o app)."""
    if db.scalar(select(func.count(Alimento.id))) == 0:
        importar(db)


def importar(db: Session) -> int:
    """Apaga e recria todos os alimentos. Devolve quantos foram gravados."""
    db.execute(delete(Alimento))
    extras = yaml.safe_load(Path(ARQUIVO_EXTRAS).read_text(encoding="utf-8")) or {}
    alimentos = _ler_taco()
    por_nome = {a.nome: a for a in alimentos}
    _aplicar_correcoes(por_nome, extras.get("correcoes", []))
    alimentos += _ler_novos(por_nome, extras.get("novos", []))
    db.add_all(alimentos)
    db.commit()
    return len(alimentos)


def _ler_csv(nome: str) -> list[dict]:
    with open(PASTA_TACO / nome, encoding="utf-8", newline="") as arquivo:
        return list(csv.DictReader(arquivo))


def _numero(valor: str) -> float | None:
    valor = (valor or "").strip()
    return float(valor) if valor else None


def _ler_taco() -> list[Alimento]:
    categorias = {linha["id"]: linha["name"].strip() for linha in _ler_csv("categories.csv")}
    nutrientes = {linha["foodId"]: linha for linha in _ler_csv("nutrients.csv")}

    alimentos = []
    for linha in _ler_csv("food.csv"):
        # Alguns nomes da planilha original têm espaços sobrando nas pontas.
        nome = " ".join(linha["name"].split())
        valores = nutrientes[linha["id"]]
        alimentos.append(
            Alimento(
                id=int(linha["id"]),
                nome=nome,
                nome_busca=normalizar(nome),
                categoria=categorias[linha["categoryId"]],
                origem="taco",
                **{campo: _numero(valores[coluna]) for coluna, campo in COLUNAS.items()},
            )
        )
    return alimentos


def _aplicar_correcoes(por_nome: dict[str, Alimento], correcoes: list[dict]) -> None:
    """Preenche valores que a TACO deixou em branco (marcados como "manual")."""
    for correcao in correcoes:
        alimento = por_nome[correcao["nome"]]
        for campo in NUTRIENTES:
            if campo in correcao:
                setattr(alimento, campo, correcao[campo])
        alimento.origem = "manual"


def _ler_novos(por_nome: dict[str, Alimento], novos: list[dict]) -> list[Alimento]:
    alimentos = []
    for item in novos:
        if item["origem"] == "derivado":
            base = por_nome[item["base"]]
            valores = {
                campo: None if getattr(base, campo) is None else round(getattr(base, campo) * item["fator"], 2)
                for campo in NUTRIENTES
            }
        else:
            valores = {campo: item.get(campo) for campo in NUTRIENTES}
        alimentos.append(
            Alimento(
                id=item["id"],
                nome=item["nome"],
                nome_busca=normalizar(item["nome"]),
                categoria=item["categoria"],
                origem=item["origem"],
                **valores,
            )
        )
    return alimentos


if __name__ == "__main__":
    from app.banco.sessao import SessaoLocal, criar_tabelas

    criar_tabelas()
    with SessaoLocal() as sessao:
        print(f"{importar(sessao)} alimentos importados.")

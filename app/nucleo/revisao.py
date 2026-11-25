"""Fila de revisão: o que a base não tinha e precisou de estimativa da IA.

É assim que a base cresce com o uso: cada item aqui é uma tarefa de cadastro (virar
receita na Base NutrIA, sinônimo ou alimento novo). Ordenada por `vezes`, mostra o que
os usuários mais procuram e ainda não temos.
"""

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.banco.modelos import RevisaoAlimento
from app.nutricao.texto import normalizar
from app.tempo import agora


def registrar(db: Session, termo: str, estimativa: dict | None) -> None:
    """Soma +1 no item (ou cria). Quem chama faz o commit."""
    chave = normalizar(termo)[:120]
    if not chave:
        return
    item = db.scalar(select(RevisaoAlimento).where(RevisaoAlimento.termo == chave))
    if item is None:
        item = RevisaoAlimento(termo=chave, exemplo=termo[:120], vezes=0)
        db.add(item)
    item.vezes += 1
    item.ultimo_em = agora()
    if estimativa:
        item.ultima_estimativa = json.dumps(estimativa, ensure_ascii=False)
    if item.status == "cadastrado":
        item.status = "pendente"  # cadastramos, mas a busca ainda não acha: revisar de novo


def pendentes(db: Session, limite: int = 50) -> list[RevisaoAlimento]:
    return list(
        db.scalars(
            select(RevisaoAlimento)
            .where(RevisaoAlimento.status == "pendente")
            .order_by(RevisaoAlimento.vezes.desc(), RevisaoAlimento.ultimo_em.desc())
            .limit(limite)
        )
    )

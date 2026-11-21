"""Ponto de entrada do NutrIA.

Rodar com:  uvicorn app.main:app --reload
Documentação automática das rotas:  http://localhost:8000/docs
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.banco.sessao import criar_tabelas, get_db


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI) -> AsyncIterator[None]:
    """Roda uma vez ao ligar o servidor (antes do yield) e uma vez ao desligar (depois)."""
    criar_tabelas()
    yield


app = FastAPI(
    title="NutrIA",
    description="Bot nutricionista: registra refeições a partir de conversa natural.",
    version="0.1.0",
    lifespan=ciclo_de_vida,
)


@app.get("/health")
def health(db: Session = Depends(get_db)) -> dict:
    """Verificação de saúde: confirma que o servidor está no ar e o banco responde."""
    db.execute(text("SELECT 1"))
    return {"status": "ok", "banco": "ok"}

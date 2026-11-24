"""Ponto de entrada do NutrIA.

Rodar com:  uvicorn app.main:app --reload
Simulador de chat:  http://localhost:8000/
Documentação automática das rotas:  http://localhost:8000/docs
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.banco.sessao import SessaoLocal, criar_tabelas, get_db
from app.canais import simulador
from app.config import RAIZ
from app.ia import roteador
from app.nutricao import importar_taco


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI) -> AsyncIterator[None]:
    """Roda uma vez ao ligar o servidor (antes do yield) e uma vez ao desligar (depois)."""
    criar_tabelas()
    with SessaoLocal() as db:
        importar_taco.garantir_base(db)  # carrega a TACO na 1ª vez
    if roteador.ia_configurada():
        # Carrega o SDK da IA agora, e não na 1ª mensagem (que ficaria uns segundos mais lenta).
        roteador.provedor(roteador.rota("dia_a_dia").provedor)
    yield


app = FastAPI(
    title="NutrIA",
    description="Bot nutricionista: registra refeições a partir de conversa natural.",
    version="0.1.0",
    lifespan=ciclo_de_vida,
)

# Rotas da API do simulador (/simulador/mensagem, /simulador/historico/...).
app.include_router(simulador.router)


@app.get("/health")
def health(db: Session = Depends(get_db)) -> dict:
    """Verificação de saúde: confirma que o servidor está no ar e o banco responde."""
    db.execute(text("SELECT 1"))
    return {"status": "ok", "banco": "ok"}


@app.get("/", include_in_schema=False)
def inicio() -> RedirectResponse:
    return RedirectResponse("/simulador/")


# A tela do simulador (HTML/CSS/JS). Fica por último: as rotas da API acima têm
# prioridade, e o que sobrar em /simulador/... é procurado como arquivo na pasta.
app.mount("/simulador", StaticFiles(directory=RAIZ / "simulador", html=True), name="tela")

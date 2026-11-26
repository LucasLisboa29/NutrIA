"""Ponto de entrada do NutrIA.

Rodar com:  uvicorn app.main:app --reload
Simulador de chat:  http://localhost:8000/
Documentação automática das rotas:  http://localhost:8000/docs
"""

import base64
import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request, Response
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.banco.sessao import SessaoLocal, criar_tabelas, get_db
from app.canais import simulador
from app.config import RAIZ, settings
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

@app.middleware("http")
async def exigir_senha(request: Request, chamar_proxima):
    """Senha de acesso quando o NutrIA está num servidor público (SENHA_ACESSO no ambiente).

    Usa a autenticação "Basic" do HTTP: o próprio navegador pede usuário e senha uma vez e
    reenvia nas próximas requisições. Sem isto, qualquer um com o link usaria o bot (e o
    crédito da API) e veria os dados. No PC (sem SENHA_ACESSO) nada muda.
    """
    senha = settings.senha_acesso
    if not senha or request.url.path == "/health":  # /health fica aberto para o provedor checar
        return await chamar_proxima(request)
    cabecalho = request.headers.get("authorization", "")
    if cabecalho.lower().startswith("basic "):
        try:
            _, _, enviada = base64.b64decode(cabecalho[6:]).decode("utf-8").partition(":")
        except (ValueError, UnicodeDecodeError):
            enviada = ""
        if secrets.compare_digest(enviada.encode(), senha.encode()):  # comparação sem vazar tempo
            return await chamar_proxima(request)
    return Response(status_code=401, headers={"WWW-Authenticate": 'Basic realm="NutrIA", charset="UTF-8"'})


@app.middleware("http")
async def sem_cache_na_tela(request: Request, chamar_proxima):
    """A tela do simulador sempre confere se há versão nova (senão o celular fica com o JS
    antigo depois de uma atualização)."""
    resposta = await chamar_proxima(request)
    if request.url.path.startswith("/simulador/") and request.url.path.endswith(("/", ".html", ".js", ".css")):
        resposta.headers["Cache-Control"] = "no-cache"
    return resposta


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

"""Preparação comum dos testes.

Os testes usam um banco e uma pasta de uploads temporários, para nunca mexer no
`nutria.db` de verdade. As variáveis de ambiente precisam ser definidas antes de
importar o app, porque as configurações são lidas na importação.
"""

import os
import tempfile
from pathlib import Path

_PASTA_TESTE = Path(tempfile.mkdtemp(prefix="nutria_teste_"))
os.environ["DATABASE_URL"] = f"sqlite:///{_PASTA_TESTE / 'teste.db'}"
os.environ["PASTA_UPLOADS"] = str(_PASTA_TESTE / "uploads")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.banco.sessao import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture
def cliente():
    """Um cliente HTTP com o banco zerado a cada teste."""
    with TestClient(app) as cliente:
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        yield cliente

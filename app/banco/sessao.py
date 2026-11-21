"""Conexão com o banco de dados (SQLAlchemy).

- `engine`: a conexão em si (SQLite no desenvolvimento, Postgres em produção).
- `SessaoLocal`: fábrica de sessões. Uma sessão é uma "conversa" com o banco, em que
  você lê, grava e no fim confirma (commit).
- `Base`: classe-mãe de todas as tabelas (ver `modelos.py`).
- `get_db`: entrega uma sessão para cada requisição do FastAPI e fecha no final.
"""

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

# O SQLite, por padrão, só aceita a conexão na thread que a criou. O FastAPI atende
# requisições em threads diferentes, então essa trava é desligada (só no SQLite).
_connect_args = (
    {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
)

engine = create_engine(settings.database_url, connect_args=_connect_args)

SessaoLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    """Toda tabela do NutrIA herda desta classe."""


def criar_tabelas() -> None:
    """Cria no banco as tabelas que ainda não existem (chamado ao iniciar o app)."""
    from app.banco import modelos  # noqa: F401  (registra as tabelas na Base)

    Base.metadata.create_all(bind=engine)


def get_db() -> Iterator[Session]:
    """Dependência do FastAPI: abre uma sessão por requisição e garante o fechamento."""
    sessao = SessaoLocal()
    try:
        yield sessao
    finally:
        sessao.close()

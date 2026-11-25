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
# Os testes nunca chamam a IA de verdade (custa dinheiro e depende da internet).
# Quem precisa de IA usa a fixture `ia_falsa`, que responde com um roteiro.
os.environ["ANTHROPIC_API_KEY"] = ""
os.environ["GROQ_API_KEY"] = ""  # idem para a transcrição de áudio (fixture `transcritor_falso`)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.banco.sessao import Base, SessaoLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.nutricao.importar_taco import garantir_base  # noqa: E402


@pytest.fixture
def cliente():
    """Um cliente HTTP com o banco zerado a cada teste (a base TACO é recarregada)."""
    with TestClient(app) as cliente:
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        with SessaoLocal() as sessao:
            garantir_base(sessao)
        yield cliente


@pytest.fixture
def db():
    """Uma sessão de banco com a base nutricional carregada."""
    Base.metadata.create_all(bind=engine)
    with SessaoLocal() as sessao:
        garantir_base(sessao)
        yield sessao


@pytest.fixture
def ia_falsa():
    """Troca a IA de verdade por uma de mentira, roteirizada pelo teste."""
    from app.ia import roteador
    from tests.ia_falsa import IAFalsa

    falsa = IAFalsa()
    roteador.registrar_provedor("claude", falsa)
    yield falsa
    roteador._provedores.pop("claude", None)


def aceitar_termo(telefone: str) -> None:
    """Cria o usuário já com o termo aceito, para testes que não são sobre o primeiro contato."""
    from app.nucleo import historico, perfil

    with SessaoLocal() as sessao:
        usuario = historico.obter_ou_criar_usuario(sessao, telefone)
        perfil.registrar_aceite(sessao, usuario, "simulador")
        sessao.commit()


@pytest.fixture
def transcritor_falso():
    """Troca a Groq por um transcritor de mentira: devolve o texto que o teste mandar."""
    from app.audio.base import Transcricao
    from app.ia import roteador

    class TranscritorFalso:
        texto = ""
        recebidos: list = []

        def transcrever(self, conteudo, mime, nome_arquivo):
            self.recebidos.append((len(conteudo), mime))
            return Transcricao(texto=self.texto, duracao_s=4.0, modelo="whisper-falso")

    falso = TranscritorFalso()
    roteador.registrar_transcritor("groq", falso)
    yield falso
    roteador._transcritores.pop("groq", None)

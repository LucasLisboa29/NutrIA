from fastapi.testclient import TestClient

from app.main import app


def test_health_responde_ok():
    # O "with" executa o ciclo de vida do app (cria as tabelas), como no servidor real.
    with TestClient(app) as cliente:
        resposta = cliente.get("/health")

    assert resposta.status_code == 200
    assert resposta.json() == {"status": "ok", "banco": "ok"}

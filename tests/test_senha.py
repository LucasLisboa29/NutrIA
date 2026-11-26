"""Senha de acesso para quando o NutrIA está num servidor público."""

import pytest

from app.config import settings


@pytest.fixture
def com_senha(monkeypatch):
    monkeypatch.setattr(settings, "senha_acesso", "segredo-de-teste")


def test_sem_senha_configurada_tudo_abre(cliente):
    assert cliente.get("/simulador/usuarios").status_code == 200


def test_com_senha_pede_login(cliente, com_senha):
    resposta = cliente.get("/simulador/usuarios")
    assert resposta.status_code == 401
    assert resposta.headers["www-authenticate"].startswith("Basic")
    assert cliente.get("/simulador/usuarios", auth=("lucas", "errada")).status_code == 401


def test_com_senha_certa_entra(cliente, com_senha):
    assert cliente.get("/simulador/usuarios", auth=("qualquer", "segredo-de-teste")).status_code == 200
    assert cliente.get("/simulador/", auth=("qualquer", "segredo-de-teste")).status_code == 200


def test_health_fica_aberto_para_o_provedor(cliente, com_senha):
    assert cliente.get("/health").status_code == 200


def test_tela_do_simulador_sem_cache(cliente):
    # Sem isto o celular continua com o app.js antigo depois de publicar uma versão nova.
    assert cliente.get("/simulador/app.js").headers["cache-control"] == "no-cache"

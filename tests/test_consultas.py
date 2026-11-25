"""Testes da Fase 5: resumos, consultas, correções, apagar dados e relógio simulado."""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app.banco.modelos import Mensagem, Refeicao, Usuario
from app.nucleo import ferramentas
from tests.conftest import aceitar_termo

ANA = "5534999990001"
SEGUNDA = datetime(2026, 11, 23)  # uma segunda-feira


@pytest.fixture(autouse=True)
def ana_com_perfil(cliente, ia_falsa):
    """Ana já aceitou o termo e tem meta de 1507 kcal (mesmo perfil do teste de metas)."""
    ferramentas._PEDIDOS_APAGAR.clear()
    aceitar_termo(ANA)
    ia_falsa.roteiro = [
        ("atualizar_perfil", {"sexo": "feminino", "idade": 30, "peso_kg": 65, "altura_cm": 165,
                              "nivel_atividade": "leve", "objetivo": "perder"}),
        "ok",
    ]
    enviar(cliente, "meu perfil", SEGUNDA.replace(hour=7))


def enviar(cliente, texto, quando: datetime | None = None):
    dados = {"telefone": ANA, "texto": texto}
    if quando:
        dados["agora_simulado"] = quando.strftime("%Y-%m-%dT%H:%M")
    resposta = cliente.post("/simulador/mensagem", data=dados)
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


def registrar(cliente, ia_falsa, tipo, itens, quando):
    ia_falsa.roteiro = [("registrar_refeicao", {"tipo": tipo, "itens": itens}), "Anotado!"]
    return enviar(cliente, f"comi no {tipo}", quando)


def resultado_da_ferramenta(json, indice=0):
    return json["depuracao"]["ferramentas"][indice]["resultado"]


ARROZ = {"descricao": "arroz", "alimento": "arroz"}  # 150 g, 192 kcal
OVOS = {"descricao": "2 ovos", "alimento": "ovo", "quantidade": 2}  # 100 g, 146 kcal
SUCO = {"descricao": "suco", "alimento": "suco de laranja"}  # 200 g


# ---------- Relógio simulado (RF33) ----------


def test_relogio_simulado_vale_para_mensagens_e_refeicoes(cliente, ia_falsa):
    quando = datetime(2026, 11, 20, 12, 30)
    registrar(cliente, ia_falsa, "almoco", [ARROZ], quando)

    banco = cliente.get(f"/simulador/banco/{ANA}").json()
    datas = [d["data"] for d in banco["dias"]]
    assert "20/11/2026" in datas
    ultima = cliente.get(f"/simulador/historico/{ANA}").json()[-1]
    assert ultima["horario"].startswith("2026-11-20T15:30")  # 12:30 em Brasília = 15:30 UTC
    # E o contexto da IA naquela mensagem dizia que era sexta.
    assert "sexta, 20/11/2026 12:30" in ia_falsa.pedidos[-2]["mensagens"][-1].contexto


# ---------- Resumos e "quanto falta" (RF21, RF22, RF23) ----------


def test_marco_dia_simulado_completo_bate_com_o_painel(cliente, ia_falsa):
    registrar(cliente, ia_falsa, "cafe_da_manha", [OVOS], SEGUNDA.replace(hour=8))
    registrar(cliente, ia_falsa, "almoco", [ARROZ], SEGUNDA.replace(hour=12, minute=30))
    registrar(cliente, ia_falsa, "jantar", [ARROZ, OVOS], SEGUNDA.replace(hour=20))

    ia_falsa.roteiro = [("consultar_resumo", {"periodo": "dia"}), "Você está em 676 de 1507!"]
    resumo = resultado_da_ferramenta(enviar(cliente, "quanto comi hoje?", SEGUNDA.replace(hour=21)))

    painel = next(d for d in cliente.get(f"/simulador/banco/{ANA}").json()["dias"] if d["data"] == "23/11/2026")
    assert resumo["total"]["kcal"] == painel["totais"]["kcal"] == 2 * 192 + 2 * 146
    assert [r["tipo"] for r in resumo["refeicoes"]] == ["Café da manhã", "Almoço", "Jantar"]
    assert resumo["meta"]["kcal"] == 1507
    assert resumo["falta"]["kcal"] == 1507 - 676
    assert resumo["percentual_kcal"] == 45


def test_resumo_da_semana(cliente, ia_falsa):
    # Terça: perto da meta (dentro). Quarta: bem abaixo. Os outros dias: sem registro.
    terca, quarta = SEGUNDA + timedelta(days=1), SEGUNDA + timedelta(days=2)
    pf = {"descricao": "PF", "alimento": "pf", "quantidade": 2.4}  # ~1510 kcal
    registrar(cliente, ia_falsa, "almoco", [pf], terca.replace(hour=12))
    registrar(cliente, ia_falsa, "almoco", [ARROZ], quarta.replace(hour=12))

    ia_falsa.roteiro = [("consultar_resumo", {"periodo": "semana"}), "Semana boa!"]
    semana = resultado_da_ferramenta(enviar(cliente, "como foi minha semana?", quarta.replace(hour=21)))

    assert semana["periodo"] == "19/11 a 25/11"
    assert semana["dias_com_registro"] == 2
    assert semana["dias_dentro_da_meta"] == 1 and semana["dias_abaixo_da_meta"] == 1
    terca_resumo = next(d for d in semana["dias"] if d["data"] == "24/11")
    assert semana["media_kcal"] == round((terca_resumo["kcal"] + 192) / 2)


def test_consultar_alimento_nao_registra(cliente, ia_falsa, db):
    ia_falsa.roteiro = [("consultar_alimento", {"alimento": "banana", "quantidade": 1}), "~62 kcal"]
    resultado = resultado_da_ferramenta(enviar(cliente, "quantas calorias tem uma banana?"))

    assert resultado["registrado"] is False and resultado["total"]["kcal"] > 0
    assert db.scalars(select(Refeicao)).all() == []


# ---------- Correções (RF12) ----------


def test_apagar_item_e_refeicao_vazia_some(cliente, ia_falsa):
    json = registrar(cliente, ia_falsa, "cafe_da_manha", [OVOS, SUCO], SEGUNDA.replace(hour=8))
    ovo_id, suco_id = (i["item_id"] for i in resultado_da_ferramenta(json)["itens_registrados"])

    ia_falsa.roteiro = [("apagar_item", {"item_id": suco_id}), "Tirei o suco."]
    resultado = resultado_da_ferramenta(enviar(cliente, "apaga o suco", SEGUNDA.replace(hour=9)))
    assert resultado["refeicao_apagada"] is False
    assert resultado["total_da_refeicao"]["kcal"] == 146

    ia_falsa.roteiro = [("apagar_item", {"item_id": ovo_id}), "Tirei os ovos."]
    resultado = resultado_da_ferramenta(enviar(cliente, "apaga os ovos também", SEGUNDA.replace(hour=9)))
    assert resultado["refeicao_apagada"] is True
    assert cliente.get(f"/simulador/banco/{ANA}").json()["dias"] == []


def test_nao_foi_almoco_foi_janta_e_foi_ontem(cliente, ia_falsa):
    json = registrar(cliente, ia_falsa, "almoco", [ARROZ], SEGUNDA.replace(hour=12))
    refeicao_id = resultado_da_ferramenta(json)["refeicao_id"]

    ia_falsa.roteiro = [
        ("alterar_refeicao", {"refeicao_id": refeicao_id, "tipo": "jantar", "quando": "2026-11-22 20:00"}),
        "Corrigido!",
    ]
    resultado = resultado_da_ferramenta(enviar(cliente, "não foi almoço, foi a janta de ontem", SEGUNDA.replace(hour=13)))
    assert resultado["depois"] == {"tipo": "jantar", "quando": "22/11 20:00"}


# ---------- Apagar meus dados (RF26) ----------


def test_apagar_dados_exige_confirmacao_numa_mensagem_nova(cliente, ia_falsa, db):
    registrar(cliente, ia_falsa, "almoco", [ARROZ], SEGUNDA.replace(hour=12))

    # A IA tenta pedir e confirmar na MESMA mensagem: o código não deixa.
    ia_falsa.roteiro = [
        ("apagar_meus_dados", {"confirmado": False}),
        ("apagar_meus_dados", {"confirmado": True}),
        "Tem certeza? É para sempre.",
    ]
    json = enviar(cliente, "apaga tudo", SEGUNDA.replace(hour=13))
    assert resultado_da_ferramenta(json, 1)["apagado"] is False
    assert db.scalar(select(Usuario).where(Usuario.telefone == ANA)) is not None

    # Confirmação na mensagem seguinte: aí sim apaga.
    ia_falsa.roteiro = [("apagar_meus_dados", {"confirmado": True})]
    json = enviar(cliente, "sim, pode apagar", SEGUNDA.replace(hour=13, minute=1))
    assert "apaguei *tudo*" in json["resposta"]["texto"]
    assert json["depuracao"]["usuario_apagado"] is True

    db.expire_all()
    assert db.scalar(select(Usuario).where(Usuario.telefone == ANA)) is None
    assert db.scalars(select(Mensagem)).all() == []  # nem a despedida foi gravada
    assert db.scalars(select(Refeicao)).all() == []


def test_pedido_de_apagar_expira(cliente, ia_falsa, db):
    ia_falsa.roteiro = [("apagar_meus_dados", {"confirmado": False}), "Confirma?"]
    enviar(cliente, "apaga tudo", SEGUNDA.replace(hour=13))

    ia_falsa.roteiro = [("apagar_meus_dados", {"confirmado": True}), "Confirma de novo?"]
    json = enviar(cliente, "sim", SEGUNDA.replace(hour=13, minute=11))  # 11 min depois
    assert resultado_da_ferramenta(json)["apagado"] is False
    assert db.scalar(select(Usuario).where(Usuario.telefone == ANA)) is not None


def test_depois_de_apagar_recomeca_do_zero(cliente, ia_falsa):
    ia_falsa.roteiro = [("apagar_meus_dados", {"confirmado": False}), "Confirma?"]
    enviar(cliente, "apaga tudo", SEGUNDA.replace(hour=13))
    ia_falsa.roteiro = [("apagar_meus_dados", {"confirmado": True})]
    enviar(cliente, "sim", SEGUNDA.replace(hour=13, minute=1))

    json = enviar(cliente, "oi", SEGUNDA.replace(hour=14))
    assert "concorda" in json["resposta"]["texto"]  # boas-vindas com o termo de novo


def test_contexto_avisa_a_ia_do_pedido_de_apagar_pendente(cliente, ia_falsa):
    ia_falsa.roteiro = [("apagar_meus_dados", {"confirmado": False}), "Confirma?"]
    enviar(cliente, "apaga tudo", SEGUNDA.replace(hour=13))

    ia_falsa.roteiro = ["Ok, não apago."]
    enviar(cliente, "deixa pra lá", SEGUNDA.replace(hour=13, minute=1))
    assert "aguardando confirmação" in ia_falsa.pedidos[-1]["mensagens"][-1].contexto


def test_pediu_perfil_reconhece_pedidos_so_em_perguntas():
    from app.nucleo.registros import pediu_perfil

    assert pediu_perfil("Anotado! Me conta sua idade e seu peso atual?")
    assert pediu_perfil("Registrei. Pra conta do gasto calórico, uso a fórmula feminina ou masculina?")
    assert not pediu_perfil("Anotado! O bife era grande?")
    # Falar do peso sem perguntar não conta como pedido.
    assert not pediu_perfil("Anotei seu peso de 80 kg. 💪")

"""Testes da Fase 4: primeiro contato, aceite LGPD, perfil conversado e meta."""

from sqlalchemy import select

from app.banco.modelos import Consentimento, HistoricoPeso, Refeicao
from tests.conftest import aceitar_termo

ANA = "5534999990001"


def enviar(cliente, texto, telefone=ANA):
    resposta = cliente.post("/simulador/mensagem", data={"telefone": telefone, "texto": texto})
    assert resposta.status_code == 200
    return resposta.json()


def nomes_das_ferramentas(pedido):
    return [f.nome for f in pedido["ferramentas"]]


# ---------- Primeiro contato e aceite (RF16, RN07) ----------


def test_boas_vindas_sao_fixas_e_nao_gastam_ia(cliente, ia_falsa):
    json = enviar(cliente, "almocei arroz e feijão")  # mesmo contando uma refeição

    assert "concorda" in json["resposta"]["texto"]
    assert ia_falsa.pedidos == []  # nenhuma chamada à IA
    assert json["depuracao"]["modo"] == "primeiro_contato"


def test_antes_do_aceite_a_ia_so_tem_a_ferramenta_de_aceite(cliente, ia_falsa):
    enviar(cliente, "oi")
    ia_falsa.roteiro = ["Preciso do seu sim antes de anotar 🙂"]
    enviar(cliente, "comi um pão")

    pedido = ia_falsa.pedidos[0]
    assert nomes_das_ferramentas(pedido) == ["registrar_aceite"]
    assert "NÃO aceitou" in pedido["mensagens"][-1].contexto
    assert "termo de uso" in pedido["sistema"]


def test_aceite_fica_registrado_com_data_e_versao(cliente, ia_falsa, db):
    enviar(cliente, "oi")
    ia_falsa.roteiro = [("registrar_aceite", {}), "Bem-vinda! Como posso te chamar?"]
    json = enviar(cliente, "sim")

    assert json["depuracao"]["ferramentas"][0]["resultado"]["aceite"] == "registrado"
    (consentimento,) = db.scalars(select(Consentimento)).all()
    assert consentimento.versao_termo == "1" and consentimento.aceito_em is not None
    # A partir daqui, a IA recebe as ferramentas normais.
    ia_falsa.roteiro = ["Oi!"]
    enviar(cliente, "oi de novo")
    assert "registrar_refeicao" in nomes_das_ferramentas(ia_falsa.pedidos[-1])


def test_sem_aceite_o_codigo_recusa_gravar_mesmo_se_a_ia_tentar(cliente, ia_falsa, db):
    enviar(cliente, "oi")
    # Uma IA "desobediente" que tenta registrar sem ter a ferramenta.
    ia_falsa.roteiro = [
        ("registrar_refeicao", {"tipo": "almoco", "itens": [{"descricao": "pão", "alimento": "pão"}]}),
        "ok",
    ]
    json = enviar(cliente, "comi um pão")

    assert json["depuracao"]["ferramentas"][0]["erro"] is True
    assert db.scalars(select(Refeicao)).all() == []


# ---------- Perfil e meta (RF17–RF20) ----------


def test_marco_perfil_e_meta_so_conversando(cliente, ia_falsa):
    aceitar_termo(ANA)

    ia_falsa.roteiro = [
        ("atualizar_perfil", {"nome": "Ana", "objetivo": "perder", "sexo": None, "idade": None}),
        "Prazer, Ana! Quantos anos você tem?",
    ]
    primeira = enviar(cliente, "sou a Ana e quero emagrecer")
    resultado = primeira["depuracao"]["ferramentas"][0]["resultado"]
    assert resultado["meta_diaria"] is None
    assert "idade" in resultado["faltando_para_a_meta"]

    ia_falsa.roteiro = [
        ("atualizar_perfil", {"idade": 30, "sexo": "feminino", "peso_kg": 65, "altura_cm": 1.65}),
        "Anotado! Você faz exercício?",
    ]
    enviar(cliente, "30 anos, mulher, 65 kg e 1,65")

    ia_falsa.roteiro = [("atualizar_perfil", {"nivel_atividade": "leve"}), "Sua meta é ~1.507 kcal!"]
    terceira = enviar(cliente, "caminho 2x por semana")
    meta = terceira["depuracao"]["ferramentas"][0]["resultado"]["meta_diaria"]
    assert meta["kcal"] == 1507  # o mesmo número do teste de metas, agora vindo da conversa

    banco = cliente.get(f"/simulador/banco/{ANA}").json()
    assert banco["perfil"]["altura_cm"] == 165  # 1,65 m convertido para cm
    assert banco["meta"]["kcal"] == 1507

    # Na mensagem seguinte, a IA vê a meta no contexto.
    ia_falsa.roteiro = ["Oi!"]
    enviar(cliente, "oi")
    assert "Meta diária: 1507 kcal" in ia_falsa.pedidos[-1]["mensagens"][-1].contexto


def test_cada_peso_informado_vai_para_o_historico(cliente, ia_falsa, db):
    aceitar_termo(ANA)
    for peso in (80, 78.5):
        ia_falsa.roteiro = [("atualizar_perfil", {"peso_kg": peso}), "Anotado!"]
        enviar(cliente, f"tô pesando {peso}")

    assert [p.peso_kg for p in db.scalars(select(HistoricoPeso))] == [80, 78.5]
    assert cliente.get(f"/simulador/banco/{ANA}").json()["perfil"]["peso_kg"] == 78.5


def test_dado_absurdo_volta_como_erro_para_a_ia(cliente, ia_falsa):
    aceitar_termo(ANA)
    ia_falsa.roteiro = [("atualizar_perfil", {"peso_kg": 650}), "Acho que digitou errado 🙂"]
    json = enviar(cliente, "peso 650")

    ferramenta = json["depuracao"]["ferramentas"][0]
    assert ferramenta["erro"] is True and "peso" in ferramenta["resultado"]["erro"]


def test_resetar_apaga_perfil_pesos_e_aceite(cliente, ia_falsa, db):
    aceitar_termo(ANA)
    ia_falsa.roteiro = [("atualizar_perfil", {"peso_kg": 70, "nome": "Ana"}), "ok"]
    enviar(cliente, "sou a Ana, 70 kg")

    cliente.delete(f"/simulador/usuarios/{ANA}")
    db.expire_all()
    assert db.scalars(select(Consentimento)).all() == []
    assert db.scalars(select(HistoricoPeso)).all() == []
    assert cliente.get(f"/simulador/banco/{ANA}").json()["perfil"] == {}

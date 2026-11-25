"""Testes da Etapa 2 das fotos: memória do usuário, fila de revisão e Open Food Facts.
Tudo com IA falsa e Open Food Facts falso (sem internet)."""

import httpx
import pytest
from sqlalchemy import select

from app.banco.modelos import AlimentoUsuario, MedidaUsuario, RevisaoAlimento
from app.config import settings
from app.nutricao import openfoodfacts
from tests.conftest import aceitar_termo

ANA = "5534999990001"
BRUNO = "5534999990002"


@pytest.fixture(autouse=True)
def usuarios(cliente):
    aceitar_termo(ANA)
    aceitar_termo(BRUNO)


def enviar(cliente, texto, telefone=ANA):
    resposta = cliente.post("/simulador/mensagem", data={"telefone": telefone, "texto": texto})
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


def registrar(cliente, ia_falsa, itens, telefone=ANA, tipo="avulso"):
    ia_falsa.roteiro = [("registrar_refeicao", {"tipo": tipo, "itens": itens}), "Anotado!"]
    return enviar(cliente, "comi", telefone)["depuracao"]["ferramentas"][0]["resultado"]


CANECA = {"descricao": "caneca de achocolatado", "alimento": "achocolatado", "quantidade": 1, "unidade": "caneca"}


# ---------- Medidas do usuário (foto 7) ----------


def test_medida_ensinada_vale_so_para_quem_ensinou(cliente, ia_falsa):
    ia_falsa.roteiro = [("ensinar_medida", {"nome": "caneca", "gramas": 350}), "Guardei!"]
    enviar(cliente, "minha caneca tem uns 350 ml")

    da_ana = registrar(cliente, ia_falsa, [CANECA])["itens_registrados"][0]
    do_bruno = registrar(cliente, ia_falsa, [CANECA], telefone=BRUNO)["itens_registrados"][0]
    assert da_ana["gramas"] == 350  # medida dela
    assert do_bruno["gramas"] == 300  # caneca genérica


def test_medida_ensinada_aparece_no_contexto(cliente, ia_falsa):
    ia_falsa.roteiro = [("ensinar_medida", {"nome": "Caneca", "gramas": 350}), "Guardei!"]
    enviar(cliente, "minha caneca tem 350 ml")
    ia_falsa.roteiro = ["Oi!"]
    enviar(cliente, "oi")
    assert "Medidas do usuário: caneca = 350 g/ml" in ia_falsa.pedidos[-1]["mensagens"][-1].contexto


# ---------- Alimentos do usuário ----------


def test_alimento_pelo_rotulo(cliente, ia_falsa):
    ia_falsa.roteiro = [
        ("ensinar_alimento", {"nome": "whey da Ana", "porcao_g": 30, "kcal": 120, "proteina": 24,
                              "carboidrato": 3, "gordura": 1.5}),
        "Guardei!",
    ]
    enviar(cliente, "meu whey tem 120 kcal e 24 g de proteína em 30 g")

    item = registrar(cliente, ia_falsa, [{"descricao": "2 scoops", "alimento": "whey da Ana", "quantidade": 2}])[
        "itens_registrados"][0]
    assert (item["gramas"], item["kcal"], item["proteina"]) == (60, 240, 48)


def test_alimento_pela_receita_do_usuario(cliente, ia_falsa):
    ia_falsa.roteiro = [
        ("ensinar_alimento", {"nome": "meu shake", "ingredientes": [
            {"alimento": "leite", "quantidade": 300, "unidade": "ml"},
            {"alimento": "banana", "quantidade": 1, "unidade": "unidade"},
        ]}),
        "Guardei!",
    ]
    resultado = enviar(cliente, "meu shake é 300 ml de leite com 1 banana")["depuracao"]["ferramentas"][0]["resultado"]
    assert resultado["porcao_g"] == 370  # 300 g de leite + 70 g de banana
    item = registrar(cliente, ia_falsa, [{"descricao": "shake", "alimento": "meu shake"}])["itens_registrados"][0]
    assert item["gramas"] == 370 and item["kcal"] == resultado["por_porcao"]["kcal"]


def test_itens_frequentes_vao_para_o_contexto(cliente, ia_falsa):
    for _ in range(3):
        registrar(cliente, ia_falsa, [CANECA])
    ia_falsa.roteiro = ["Oi!"]
    enviar(cliente, "oi")
    assert "Leite, de vaca, achocolatado, 1 caneca (3x)" in ia_falsa.pedidos[-1]["mensagens"][-1].contexto


def test_apagar_meus_dados_apaga_o_que_foi_ensinado(cliente, ia_falsa, db):
    ia_falsa.roteiro = [("ensinar_medida", {"nome": "caneca", "gramas": 350}), "ok"]
    enviar(cliente, "caneca 350")
    ia_falsa.roteiro = [("apagar_meus_dados", {"confirmado": False}), "Confirma?"]
    enviar(cliente, "apaga tudo")
    ia_falsa.roteiro = [("apagar_meus_dados", {"confirmado": True})]
    enviar(cliente, "sim")
    db.expire_all()
    assert db.scalars(select(MedidaUsuario)).all() == []
    assert db.scalars(select(AlimentoUsuario)).all() == []


# ---------- Fila de revisão ----------


SUSHI = {"descricao": "sushi", "alimento": "sushi",
         "estimativa_ia": {"gramas": 200, "kcal": 300, "proteina": 12, "carboidrato": 50, "gordura": 4}}


def test_estimativa_da_ia_vai_para_a_fila_de_revisao(cliente, ia_falsa):
    registrar(cliente, ia_falsa, [SUSHI])
    registrar(cliente, ia_falsa, [SUSHI], telefone=BRUNO)

    (item,) = cliente.get("/simulador/revisao").json()
    assert (item["termo"], item["vezes"]) == ("sushi", 2)
    assert item["ultima_estimativa"]["kcal"] == 300

    cliente.post(f"/simulador/revisao/{item['id']}", data={"status": "cadastrado"})
    assert cliente.get("/simulador/revisao").json() == []


def test_alimento_nao_encontrado_sem_estimativa_tambem_entra_na_fila(cliente, ia_falsa):
    resultado = registrar(cliente, ia_falsa, [{"descricao": "x", "alimento": "temaki"}])
    assert resultado["registrado"] is False
    assert [i["termo"] for i in cliente.get("/simulador/revisao").json()] == ["temaki"]


def test_fila_e_anonima_e_sobrevive_ao_apagar_dados(cliente, ia_falsa, db):
    registrar(cliente, ia_falsa, [SUSHI])
    cliente.delete(f"/simulador/usuarios/{ANA}")
    db.expire_all()
    assert len(db.scalars(select(RevisaoAlimento)).all()) == 1  # não tem dado de quem pediu


# ---------- Open Food Facts (falso) ----------


def produto_falso(nome="Monster Energy Ultra Peachy Keen", kcal=1.0, brasil=True, quantidade="473 ml"):
    return {
        "code": "789000000001", "product_name": nome, "brands": ["Monster Energy"], "quantity": quantidade,
        "nutriments": {"energy-kcal_100g": kcal, "proteins_100g": 0, "carbohydrates_100g": 0.5, "fat_100g": 0},
        "countries_tags": ["en:brazil"] if brasil else ["en:australia"],
    }


@pytest.fixture
def off_falso(monkeypatch):
    """Liga o Open Food Facts, mas com a API trocada por uma lista roteirizada."""
    chamadas = []
    resposta = {"hits": []}

    def consultar(termo):
        chamadas.append(termo)
        if isinstance(resposta["hits"], Exception):
            raise resposta["hits"]
        return resposta["hits"]

    monkeypatch.setattr(settings, "openfoodfacts_ativo", True)
    monkeypatch.setattr(openfoodfacts, "_consultar_api", consultar)
    return {"chamadas": chamadas, "resposta": resposta}


MONSTER = {"descricao": "lata de Monster", "alimento": "Monster Energy Ultra Peachy Keen",
           "quantidade": 1, "unidade": "lata"}


def test_produto_de_marca_vem_do_open_food_facts(cliente, ia_falsa, off_falso):
    off_falso["resposta"]["hits"] = [produto_falso()]
    item = registrar(cliente, ia_falsa, [MONSTER])["itens_registrados"][0]
    assert item["gramas"] == 473  # 1 lata = conteúdo da embalagem
    assert item["kcal"] == 5 and item["confianca"] == "media"

    registrar(cliente, ia_falsa, [MONSTER])
    assert len(off_falso["chamadas"]) == 1  # a 2ª vez veio do cache, sem internet


def test_rotulo_lido_na_foto_vence_produto_de_outro_pais(cliente, ia_falsa, off_falso):
    off_falso["resposta"]["hits"] = [produto_falso(kcal=11.8, brasil=False)]
    rotulo = {"gramas": 473, "kcal": 10, "proteina": 0, "carboidrato": 2, "gordura": 0}
    item = registrar(cliente, ia_falsa, [{**MONSTER, "estimativa_ia": rotulo}])["itens_registrados"][0]
    assert item["kcal"] == 10  # o rótulo da foto, não o Monster australiano


def test_internet_fora_do_ar_nao_trava_o_registro(cliente, ia_falsa, off_falso):
    off_falso["resposta"]["hits"] = httpx.ConnectError("sem internet")
    rotulo = {"gramas": 473, "kcal": 10, "proteina": 0, "carboidrato": 2, "gordura": 0}
    item = registrar(cliente, ia_falsa, [{**MONSTER, "estimativa_ia": rotulo}])["itens_registrados"][0]
    assert item["kcal"] == 10


def test_produto_parecido_mas_diferente_nao_e_aceito(cliente, ia_falsa, off_falso):
    off_falso["resposta"]["hits"] = [produto_falso(nome="Monster Energy Original")]
    resultado = registrar(cliente, ia_falsa, [MONSTER])
    assert resultado["registrado"] is False  # "ultra peachy keen" não está no nome achado


def test_quantidade_da_embalagem():
    assert openfoodfacts._quantidade_em_gramas("473 ml") == 473
    assert openfoodfacts._quantidade_em_gramas("1,5 L") == 1500
    assert openfoodfacts._quantidade_em_gramas("6 x 330 ml") == 330
    assert openfoodfacts._quantidade_em_gramas("sem info") is None

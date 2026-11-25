"""Testes da Fase 6: áudio (transcrição) e foto (visão), com IA e transcritor falsos."""

import io

import pytest
from PIL import Image

from app.ia import imagens, roteador
from app.ia.base import MensagemUsuario
from tests.conftest import aceitar_termo

ANA = "5534999990001"


def foto_png(largura=4000, altura=3000) -> bytes:
    """Uma "foto" grande de mentira (do tamanho de uma foto de celular)."""
    saida = io.BytesIO()
    Image.new("RGB", (largura, altura), (200, 160, 90)).save(saida, format="PNG")
    return saida.getvalue()


def enviar(cliente, texto="", arquivo=None):
    arquivos = {"arquivo": arquivo} if arquivo else None
    resposta = cliente.post("/simulador/mensagem", data={"telefone": ANA, "texto": texto}, files=arquivos)
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


AUDIO = ("gravacao.webm", b"bytes-de-audio", "audio/webm;codecs=opus")
PIZZA = (
    "registrar_refeicao",
    {"tipo": "jantar", "itens": [{"descricao": "duas fatias de pizza", "alimento": "pizza", "quantidade": 2, "unidade": "fatia"}]},
)


@pytest.fixture(autouse=True)
def ana_aceitou(cliente):
    aceitar_termo(ANA)


# ---------- Áudio (RF03) ----------


def test_marco_audio_vira_texto_e_registra(cliente, ia_falsa, transcritor_falso):
    transcritor_falso.texto = "Jantei duas fatias de pizza"
    ia_falsa.roteiro = [PIZZA, "Anotado!"]

    json = enviar(cliente, arquivo=AUDIO)

    # A IA recebeu o texto transcrito, como se fosse uma mensagem escrita.
    assert ia_falsa.pedidos[0]["mensagens"][-1].texto == "Jantei duas fatias de pizza"
    assert json["depuracao"]["transcricao"] == "Jantei duas fatias de pizza"
    assert json["depuracao"]["ferramentas"][0]["resultado"]["total_da_refeicao"]["kcal"] == 585
    # A transcrição fica gravada na mensagem (o chat e o histórico mostram o que foi dito).
    entrada = cliente.get(f"/simulador/historico/{ANA}").json()[-2]
    assert entrada["tipo_midia"] == "audio" and entrada["texto"] == "Jantei duas fatias de pizza"
    # O custo inclui a transcrição (mínimo de 10 s cobrado pela Groq).
    etapas = [e["etapa"] for e in json["depuracao"]["etapas"]]
    assert etapas[0] == "transcricao"
    assert json["depuracao"]["custo_usd"] > json["depuracao"]["etapas"][1]["custo_usd"]


def test_audio_sem_groq_configurada_avisa_sem_chamar_a_ia(cliente, ia_falsa):
    json = enviar(cliente, arquivo=AUDIO)
    assert "Ainda não consigo ouvir áudios" in json["resposta"]["texto"]
    assert ia_falsa.pedidos == []


def test_audio_sem_fala_pede_para_gravar_de_novo(cliente, ia_falsa, transcritor_falso):
    transcritor_falso.texto = ""
    json = enviar(cliente, arquivo=AUDIO)
    assert "Não entendi" in json["resposta"]["texto"]
    assert ia_falsa.pedidos == []


# ---------- Foto (RF02) ----------


def test_marco_foto_usa_rota_de_visao_e_imagem_reduzida(cliente, ia_falsa):
    ia_falsa.roteiro = [
        ("registrar_refeicao", {
            "tipo": "jantar",
            "por_foto": True,
            "itens": [
                {"descricao": "arroz", "alimento": "arroz", "quantidade": 120, "unidade": "g"},
                {"descricao": "frango", "alimento": "frango", "quantidade": 1, "unidade": "file"},
            ],
        }),
        "Vi arroz e frango. Confere?",
    ]
    json = enviar(cliente, "janta", ("prato.png", foto_png(), "image/png"))

    pedido = ia_falsa.pedidos[0]
    assert pedido["modelo"] == roteador.rota("visao").modelo  # a rota "visao" de modelos.yaml
    assert json["depuracao"]["rota"] == "visao"
    (imagem,) = pedido["mensagens"][-1].imagens
    assert imagem.mime == "image/jpeg"
    with Image.open(io.BytesIO(imagem.dados)) as enviada:
        assert max(enviada.size) == 1568  # 4000×3000 reduzida
    assert json["depuracao"]["imagem"]["original"].startswith("4000×3000")

    # Itens vistos na foto são sempre estimados, mesmo informados em gramas (RF02).
    itens = json["depuracao"]["ferramentas"][0]["resultado"]["itens_registrados"]
    assert all(i["estimado"] for i in itens)
    assert itens[0]["confianca"] == "media"  # "120 g" sozinho seria "alta"


def test_foto_antes_do_aceite_nao_e_analisada(cliente, ia_falsa):
    outro = "5534999990009"
    cliente.post("/simulador/mensagem", data={"telefone": outro, "texto": "oi"})  # boas-vindas
    ia_falsa.roteiro = ["Preciso do seu sim antes 🙂"]
    cliente.post(
        "/simulador/mensagem",
        data={"telefone": outro, "texto": ""},
        files={"arquivo": ("prato.png", foto_png(400, 300), "image/png")},
    )
    mensagem = ia_falsa.pedidos[0]["mensagens"][-1]
    assert mensagem.imagens == []
    assert "mandou uma foto" in mensagem.texto


def test_foto_antiga_nao_e_reenviada_no_historico(cliente, ia_falsa):
    ia_falsa.roteiro = ["Que prato bonito!"]
    enviar(cliente, "olha", ("prato.png", foto_png(400, 300), "image/png"))
    ia_falsa.roteiro = ["Oi!"]
    enviar(cliente, "oi")

    anteriores = [m for m in ia_falsa.pedidos[-1]["mensagens"][:-1] if isinstance(m, MensagemUsuario)]
    assert all(m.imagens == [] for m in anteriores)
    assert "[foto] olha" in anteriores[0].texto


# ---------- Redução da imagem ----------


def test_imagem_pequena_nao_e_aumentada():
    preparada = imagens.preparar(foto_png(800, 600))
    assert (preparada.largura, preparada.altura) == (800, 600)


def test_imagem_em_pe_mantem_a_proporcao():
    preparada = imagens.preparar(foto_png(3024, 4032))
    assert (preparada.largura, preparada.altura) == (1176, 1568)
    assert imagens.tokens_estimados(1176, 1568) == 2459

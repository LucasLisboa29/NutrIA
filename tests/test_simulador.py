from app.config import settings

ANA = "5534999990001"
BRUNO = "5534999990002"


def enviar(cliente, telefone, texto="", arquivo=None):
    arquivos = {"arquivo": arquivo} if arquivo else None
    return cliente.post(
        "/simulador/mensagem", data={"telefone": telefone, "texto": texto}, files=arquivos
    )


def test_primeira_mensagem_recebe_boas_vindas_com_o_termo(cliente):
    texto = enviar(cliente, ANA, "oi").json()["resposta"]["texto"]
    assert "NutrIA" in texto and "concorda" in texto


def test_sem_chave_de_ia_o_bot_avisa_e_ecoa(cliente):
    enviar(cliente, ANA, "oi")  # a 1ª mensagem recebe as boas-vindas
    resposta = enviar(cliente, ANA, "almocei arroz e feijão")

    assert resposta.status_code == 200
    # Sem chave da Anthropic (como nos testes), o bot avisa e repete a mensagem.
    texto = resposta.json()["resposta"]["texto"]
    assert "IA ainda não está configurada" in texto
    assert "Você disse: *almocei arroz e feijão*" in texto


def test_marco_dois_usuarios_com_historicos_separados(cliente):
    enviar(cliente, ANA, "oi, sou a Ana")
    enviar(cliente, BRUNO, "oi, sou o Bruno")
    enviar(cliente, ANA, "comi uma maçã")

    historico_ana = cliente.get(f"/simulador/historico/{ANA}").json()
    historico_bruno = cliente.get(f"/simulador/historico/{BRUNO}").json()

    # Cada mensagem gera 2 registros: a do usuário e a resposta do bot.
    assert [m["texto"] for m in historico_ana if m["direcao"] == "entrada"] == [
        "oi, sou a Ana",
        "comi uma maçã",
    ]
    assert len(historico_ana) == 4
    assert [m["texto"] for m in historico_bruno if m["direcao"] == "entrada"] == [
        "oi, sou o Bruno"
    ]
    usuarios = {u["telefone"]: u["total_mensagens"] for u in cliente.get("/simulador/usuarios").json()}
    assert usuarios == {ANA: 4, BRUNO: 2}


def test_foto_com_legenda_fica_gravada_e_pode_ser_vista(cliente):
    foto = ("prato.jpg", b"bytes-de-uma-foto", "image/jpeg")
    resposta = enviar(cliente, ANA, "meu almoço", foto)

    assert resposta.status_code == 200
    entrada = cliente.get(f"/simulador/historico/{ANA}").json()[0]
    assert entrada["tipo_midia"] == "imagem"
    assert entrada["texto"] == "meu almoço"
    midia = cliente.get(entrada["url_midia"])
    assert midia.status_code == 200
    assert midia.content == b"bytes-de-uma-foto"


def test_audio_gravado_no_navegador_e_aceito(cliente):
    audio = ("gravacao.webm", b"bytes-de-audio", "audio/webm;codecs=opus")
    enviar(cliente, ANA, "oi")  # a 1ª mensagem recebe as boas-vindas
    resposta = enviar(cliente, ANA, arquivo=audio)

    # Áudio só é entendido na Fase 6; por enquanto o bot pede texto, sem travar.
    assert "só entendo mensagens de texto" in resposta.json()["resposta"]["texto"]


def test_resetar_apaga_mensagens_e_arquivos(cliente):
    enviar(cliente, ANA, "foto", ("prato.png", b"png", "image/png"))
    enviar(cliente, BRUNO, "oi")
    assert any(settings.pasta_uploads.iterdir())

    assert cliente.delete(f"/simulador/usuarios/{ANA}").json() == {"apagado": True}

    assert cliente.get(f"/simulador/historico/{ANA}").json() == []
    assert len(cliente.get(f"/simulador/historico/{BRUNO}").json()) == 2
    assert not (settings.pasta_uploads / "1").exists()


def test_mensagem_vazia_e_recusada(cliente):
    assert enviar(cliente, ANA, "   ").status_code == 400


def test_telefone_invalido_e_recusado(cliente):
    assert enviar(cliente, "123", "oi").status_code == 422


def test_arquivo_que_nao_e_foto_nem_audio_e_recusado(cliente):
    pdf = ("cardapio.pdf", b"%PDF", "application/pdf")
    assert enviar(cliente, ANA, "olha", pdf).status_code == 415


def test_tela_do_simulador_e_servida(cliente):
    resposta = cliente.get("/")
    assert resposta.status_code == 200
    assert "NutrIA" in resposta.text

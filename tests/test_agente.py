"""Testes do agente (Fase 3) com a IA falsa: o laço de ferramentas, o registro no banco,
as correções e a telemetria. Nenhum teste aqui chama a API de verdade."""

from datetime import timedelta

from sqlalchemy import select

from app.banco.modelos import ItemRefeicao, Refeicao
from app.ia import roteador
from app.ia.base import ErroIA, MensagemUsuario, ResultadoFerramenta, ResultadosFerramentas, Uso
from app.ia.claude import _converter_mensagens
from app.nucleo.orquestrador import RESPOSTA_ERRO
from app.tempo import agora, para_local

ANA = "5534999990001"
BRUNO = "5534999990002"

ALMOCO = (
    "registrar_refeicao",
    {
        "tipo": "almoco",
        "itens": [
            {"descricao": "arroz", "alimento": "arroz", "quantidade": None, "unidade": None},
            {"descricao": "feijão", "alimento": "feijão"},
            {"descricao": "um bife", "alimento": "bife", "quantidade": 1, "unidade": "bife"},
        ],
    },
)


def enviar(cliente, texto, telefone=ANA):
    resposta = cliente.post("/simulador/mensagem", data={"telefone": telefone, "texto": texto})
    assert resposta.status_code == 200
    return resposta.json()


def itens_do_banco(cliente, telefone=ANA):
    return [i for d in cliente.get(f"/simulador/banco/{telefone}").json()["dias"]
            for r in d["refeicoes"] for i in r["itens"]]


# ---------- Marco da fase ----------


def test_marco_almoco_com_tres_itens(cliente, ia_falsa):
    ia_falsa.roteiro = [ALMOCO, "Anotado seu almoço! 🍽️"]

    json = enviar(cliente, "almocei arroz, feijão e um bife")

    assert json["resposta"]["texto"] == "Anotado seu almoço! 🍽️"
    itens = itens_do_banco(cliente)
    assert [i["alimento_nome"] for i in itens] == [
        "Arroz, tipo 1, cozido",
        "Feijão, carioca, cozido",
        "Carne, bovina, contra-filé, sem gordura, grelhado",
    ]
    assert [i["estimado"] for i in itens] == [True, True, False]
    assert itens[0]["kcal"] == 192  # 150 g de arroz × 128 kcal/100 g, pela TACO

    # O painel recebe o que a IA pediu, o que o código devolveu, tokens e custo.
    dep = json["depuracao"]
    assert dep["chamadas_ia"] == 2
    assert dep["ferramentas"][0]["nome"] == "registrar_refeicao"
    assert dep["ferramentas"][0]["resultado"]["total_da_refeicao"]["kcal"] == 192 + 106 + 194
    assert dep["tokens"]["entrada"] == 2000 and dep["tokens"]["cache_leitura"] == 6000
    assert dep["custo_usd"] > 0


def test_resultado_da_ferramenta_volta_para_a_ia(cliente, ia_falsa):
    ia_falsa.roteiro = [ALMOCO, "ok"]
    enviar(cliente, "almocei arroz, feijão e um bife")

    segunda_chamada = ia_falsa.pedidos[1]["mensagens"]
    assert isinstance(segunda_chamada[-1], ResultadosFerramentas)
    assert '"registrado":true' in segunda_chamada[-1].resultados[0].conteudo


# ---------- Correções e contexto ----------


def test_resposta_a_pergunta_atualiza_sem_duplicar(cliente, ia_falsa):
    ia_falsa.roteiro = [ALMOCO, "O bife era grande ou normal?"]
    enviar(cliente, "almocei arroz, feijão e um bife")
    bife_id = itens_do_banco(cliente)[2]["id"]

    # Os modelos costumam mandar null nos campos que não mudaram: isso não pode apagar nada.
    ia_falsa.roteiro = [
        ("atualizar_item", {"item_id": bife_id, "tamanho": "grande", "quantidade": None, "unidade": None}),
        "Ajustei!",
    ]
    json = enviar(cliente, "grande")

    itens = itens_do_banco(cliente)
    assert len(itens) == 3
    assert itens[2]["gramas"] == 140  # 1 bife (100 g) × grande (1,4)
    resultado = json["depuracao"]["ferramentas"][0]["resultado"]
    assert resultado["antes"]["gramas"] == 100 and resultado["depois"]["gramas"] == 140


def test_contexto_tem_os_ids_e_o_historico_vai_junto(cliente, ia_falsa):
    ia_falsa.roteiro = [ALMOCO, "O bife era grande?"]
    enviar(cliente, "almocei arroz, feijão e um bife")
    ia_falsa.roteiro = ["Beleza!"]
    enviar(cliente, "normal")

    mensagens = ia_falsa.pedidos[-1]["mensagens"]
    # Histórico (RF04): a mensagem anterior e a resposta do bot.
    assert mensagens[0].texto == "almocei arroz, feijão e um bife"
    assert mensagens[1].texto == "O bife era grande?"
    # Contexto: a IA sabe que horas são e os ids para corrigir.
    atual = mensagens[-1]
    assert isinstance(atual, MensagemUsuario) and atual.texto == "normal"
    assert "item_id" in atual.contexto and "Almoço" in atual.contexto


def test_nao_mexe_em_item_de_outro_usuario(cliente, ia_falsa):
    ia_falsa.roteiro = [ALMOCO, "ok"]
    enviar(cliente, "almocei arroz, feijão e um bife", telefone=BRUNO)
    item_do_bruno = itens_do_banco(cliente, BRUNO)[0]["id"]

    ia_falsa.roteiro = [("atualizar_item", {"item_id": item_do_bruno, "quantidade": 5}), "Não achei."]
    json = enviar(cliente, "foram 5")

    assert json["depuracao"]["ferramentas"][0]["erro"] is True
    assert itens_do_banco(cliente, BRUNO)[0]["gramas"] == 150  # intacto


# ---------- Casos especiais do registro ----------


def test_alimento_fora_da_tabela_usa_estimativa_da_ia(cliente, ia_falsa):
    ia_falsa.roteiro = [
        ("registrar_refeicao", {"tipo": "jantar", "itens": [{"descricao": "sushi", "alimento": "sushi"}]}),
        ("registrar_refeicao", {
            "tipo": "jantar",
            "itens": [{
                "descricao": "sushi", "alimento": "sushi",
                "estimativa_ia": {"gramas": 200, "kcal": 300, "proteina": 12, "carboidrato": 50, "gordura": 4},
            }],
        }),
        "Anotado!",
    ]
    json = enviar(cliente, "jantei 10 peças de sushi")

    primeira = json["depuracao"]["ferramentas"][0]["resultado"]
    assert primeira["registrado"] is False and primeira["nao_encontrados"] == ["sushi"]
    (item,) = itens_do_banco(cliente)
    assert (item["origem"], item["confianca"], item["kcal"]) == ("ia", "baixa", 300)


def test_prato_composto_vira_varios_itens(cliente, ia_falsa):
    ia_falsa.roteiro = [
        ("registrar_refeicao", {"tipo": "almoco", "itens": [{"descricao": "um PF", "alimento": "pf"}]}),
        "Anotado!",
    ]
    enviar(cliente, "almocei um PF")
    assert len(itens_do_banco(cliente)) == 6


def test_refeicao_de_ontem_fica_no_dia_certo(cliente, ia_falsa):
    ontem = para_local(agora() - timedelta(days=1)).replace(hour=20, minute=0)
    ia_falsa.roteiro = [
        ("registrar_refeicao", {
            "tipo": "jantar",
            "quando": ontem.strftime("%Y-%m-%d %H:%M"),
            "itens": [{"descricao": "pizza", "alimento": "pizza", "quantidade": 2, "unidade": "fatia"}],
        }),
        "Anotado!",
    ]
    enviar(cliente, "ontem à noite comi 2 fatias de pizza")

    (dia,) = cliente.get(f"/simulador/banco/{ANA}").json()["dias"]
    assert dia["data"] == ontem.strftime("%d/%m/%Y")
    assert dia["refeicoes"][0]["hora"] == "20:00"
    # Na próxima mensagem, a pizza de ontem não aparece nos registros de hoje.
    ia_falsa.roteiro = ["Oi!"]
    enviar(cliente, "oi")
    contexto = ia_falsa.pedidos[-1]["mensagens"][-1].contexto
    assert "Pizza" not in contexto and "Registros de hoje: nenhum." in contexto


def test_refeicao_no_futuro_e_recusada(cliente, ia_falsa):
    amanha = para_local(agora() + timedelta(days=1))
    ia_falsa.roteiro = [
        ("registrar_refeicao", {"tipo": "almoco", "quando": amanha.strftime("%Y-%m-%d %H:%M"),
                                "itens": [{"descricao": "arroz", "alimento": "arroz"}]}),
        "Isso ainda não aconteceu 😉",
    ]
    json = enviar(cliente, "amanhã vou almoçar arroz")
    assert json["depuracao"]["ferramentas"][0]["erro"] is True
    assert itens_do_banco(cliente) == []


# ---------- Falhas ----------


def test_falha_da_ia_nao_derruba_e_mantem_o_que_ja_gravou(cliente, ia_falsa):
    ia_falsa.roteiro = [ALMOCO, ErroIA("internet caiu")]
    json = enviar(cliente, "almocei arroz, feijão e um bife")

    assert json["resposta"]["texto"] == RESPOSTA_ERRO
    assert json["depuracao"]["erro"] == "internet caiu"
    assert len(itens_do_banco(cliente)) == 3  # RN01: o registro já feito continua lá


def test_ia_em_laco_infinito_e_interrompida(cliente, ia_falsa):
    ia_falsa.roteiro = [("atualizar_item", {"item_id": 999})] * 6
    json = enviar(cliente, "oi")
    assert json["resposta"]["texto"] == RESPOSTA_ERRO
    assert "6 passos" in json["depuracao"]["aviso"]


def test_resetar_apaga_tambem_as_refeicoes(cliente, ia_falsa, db):
    ia_falsa.roteiro = [ALMOCO, "ok"]
    enviar(cliente, "almocei arroz, feijão e um bife")
    cliente.delete(f"/simulador/usuarios/{ANA}")
    db.expire_all()
    assert db.scalars(select(Refeicao)).all() == []
    assert db.scalars(select(ItemRefeicao)).all() == []


# ---------- Peças isoladas ----------


def test_custo_pelos_precos_do_yaml():
    uso = Uso(entrada=1_000_000, saida=1_000_000, cache_leitura=1_000_000, cache_escrita=0)
    # Haiku 5.5: US$ 0,10 entrada + 0,50 saída + 0,01 cache (10% da entrada)
    assert roteador.custo_usd("claude-haiku-5-5", uso) == 0.61


def test_adaptador_claude_converte_para_o_formato_da_api():
    convertidas = _converter_mensagens([
        MensagemUsuario(texto="oi"),
        MensagemUsuario(texto="almocei arroz", contexto="<contexto>...</contexto>"),
        ResultadosFerramentas([ResultadoFerramenta("abc", '{"ok":1}', erro=True)]),
    ])
    # Mensagens seguidas do mesmo papel viram uma só.
    assert len(convertidas) == 1 and convertidas[0]["role"] == "user"
    blocos = convertidas[0]["content"]
    assert [b["type"] for b in blocos] == ["text", "text", "text", "tool_result"]
    assert blocos[-1] == {"type": "tool_result", "tool_use_id": "abc", "content": '{"ok":1}', "is_error": True}

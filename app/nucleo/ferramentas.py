"""Ferramentas que a IA pode pedir para o código executar (tool use).

Cada ferramenta tem duas partes:
- a **definição** (nome, descrição e JSON Schema dos argumentos), que vai para a IA;
- a **execução**, uma função Python que faz o trabalho de verdade e devolve um dict.

A IA decide *quando* chamar e *com quais argumentos*. Os números (gramas, kcal, macros)
saem sempre do módulo de nutrição; a IA só informa o que e quanto foi comido.
"""

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.banco.modelos import ItemRefeicao, Refeicao, Usuario
from app.ia.base import Ferramenta
from app.nutricao import calculo, porcoes, taco
from app.nutricao.calculo import ItemCalculado
from app.nucleo import perfil as perfis
from app.nucleo import registros
from app.tempo import agora, fuso_local, para_local


@dataclass
class Contexto:
    """O que toda ferramenta recebe: a sessão do banco e quem está conversando."""

    db: Session
    usuario: Usuario
    canal: str = "simulador"
    mensagem_id: int = 0  # id da mensagem do usuário que está sendo respondida
    usuario_apagado: bool = False  # vira True depois de apagar_meus_dados


class ErroFerramenta(ValueError):
    """Erro de uso (argumento ruim). Volta para a IA, que pode corrigir e tentar de novo."""


# ---------- Definições (o que a IA vê) ----------

_ITEM = {
    "type": "object",
    "properties": {
        "descricao": {
            "type": "string",
            "description": "Como o usuário falou, ex.: 'um bife grande', '2 conchas de feijão'.",
        },
        "alimento": {
            "type": "string",
            "description": (
                "Nome simples e comum do alimento ou prato, para busca na tabela "
                "nutricional. Ex.: 'arroz', 'arroz integral', 'feijão preto', 'bife', "
                "'pão francês', 'pf', 'x-tudo', 'pizza'. Sem quantidade aqui."
            ),
        },
        "quantidade": {
            "type": ["number", "null"],
            "description": "Quantidade informada pelo usuário (ex.: 2). null se ele não disse.",
        },
        "unidade": {
            "type": ["string", "null"],
            "description": (
                "Medida informada: g, ml, unidade, fatia, concha, colher de sopa, colher "
                "de servir, escumadeira, copo, xícara, lata, prato, pedaço, bife... "
                "null se ele não disse."
            ),
        },
        "tamanho": {
            "type": ["string", "null"],
            "enum": ["pequeno", "medio", "grande", "cheio", "raso", None],
            "description": "Só se o usuário indicou o tamanho.",
        },
        "estimativa_ia": {
            "type": ["object", "null"],
            "description": (
                "SOMENTE para alimentos que provavelmente não estão numa tabela brasileira "
                "básica (pratos japoneses, marcas, receitas regionais raras) ou quando a "
                "ferramenta avisou que não encontrou o alimento. Sua estimativa para a "
                "porção consumida. Fica marcada como baixa confiança."
            ),
            "properties": {
                "gramas": {"type": "number"},
                "kcal": {"type": "number"},
                "proteina": {"type": "number"},
                "carboidrato": {"type": "number"},
                "gordura": {"type": "number"},
            },
            "required": ["gramas", "kcal", "proteina", "carboidrato", "gordura"],
        },
    },
    "required": ["descricao", "alimento"],
}

DEFINICOES = [
    Ferramenta(
        nome="registrar_refeicao",
        descricao=(
            "Grava uma refeição que o usuário comeu, com um ou mais itens, e devolve "
            "gramas, calorias e macros calculados pela tabela TACO, além do total do dia. "
            "Use sempre que o usuário contar algo que comeu ou bebeu, mesmo sem "
            "quantidade (o sistema estima a porção). Registre tudo numa chamada só. "
            "Para acrescentar itens a uma refeição já gravada, informe refeicao_id."
        ),
        parametros={
            "type": "object",
            "properties": {
                "tipo": {
                    "type": "string",
                    "enum": list(registros.TIPOS),
                    "description": "Deduza pelo texto ou, se não for dito, pelo horário.",
                },
                "quando": {
                    "type": ["string", "null"],
                    "description": (
                        "Data e hora (Brasília) em que comeu, formato 'AAAA-MM-DD HH:MM'. "
                        "null se foi agora ou há pouco."
                    ),
                },
                "refeicao_id": {
                    "type": ["integer", "null"],
                    "description": "Só para acrescentar itens a uma refeição já registrada.",
                },
                "itens": {"type": "array", "items": _ITEM, "minItems": 1},
            },
            "required": ["tipo", "itens"],
        },
    ),
    Ferramenta(
        nome="atualizar_item",
        descricao=(
            "Atualiza um item já registrado quando o usuário dá mais detalhes "
            "(ex.: respondeu 'era grande', 'foram 2 conchas', 'era peito de frango'). "
            "Recalcula os valores. Use o item_id que aparece no contexto ou no resultado "
            "do registro. Envie só os campos que mudaram."
        ),
        parametros={
            "type": "object",
            "properties": {
                "item_id": {"type": "integer"},
                "alimento": {"type": ["string", "null"], "description": "Novo alimento, se mudou."},
                "quantidade": {"type": ["number", "null"]},
                "unidade": {"type": ["string", "null"]},
                "tamanho": {
                    "type": ["string", "null"],
                    "enum": ["pequeno", "medio", "grande", "cheio", "raso", None],
                },
            },
            "required": ["item_id"],
        },
    ),
    Ferramenta(
        nome="atualizar_perfil",
        descricao=(
            "Salva dados do perfil que o usuário contou na conversa (aceita só parte "
            "deles; envie apenas o que ele disse). Devolve o perfil, a meta diária "
            "calculada (quando o perfil está completo) e o que ainda falta. Use também "
            "quando ele atualizar algo ('tô pesando 78', 'quero ganhar massa')."
        ),
        parametros={
            "type": "object",
            "properties": {
                "nome": {"type": ["string", "null"], "description": "Primeiro nome ou apelido."},
                "sexo": {
                    "type": ["string", "null"],
                    "enum": [*perfis.SEXOS, None],
                    "description": "Usado só na fórmula de gasto calórico.",
                },
                "idade": {"type": ["integer", "null"]},
                "peso_kg": {"type": ["number", "null"]},
                "altura_cm": {"type": ["number", "null"], "description": "Em centímetros (1,65 m = 165)."},
                "nivel_atividade": {
                    "type": ["string", "null"],
                    "enum": [*perfis.NIVEIS, None],
                    "description": (
                        "sedentario (quase sem exercício), leve (1-3x/semana), moderado "
                        "(3-5x/semana), intenso (6-7x/semana), muito_intenso (treino "
                        "pesado diário ou trabalho físico)."
                    ),
                },
                "objetivo": {
                    "type": ["string", "null"],
                    "enum": [*perfis.OBJETIVOS, None],
                    "description": "perder, manter ou ganhar peso.",
                },
            },
        },
    ),
]

DEFINICOES += [
    Ferramenta(
        nome="consultar_resumo",
        descricao=(
            "Resumo do que o usuário comeu: 'dia' (refeições com item_id, total, meta e "
            "quanto falta de cada nutriente) ou 'semana' (7 dias até a data: total de cada "
            "dia, média e dias dentro/acima/abaixo da meta). Use para 'quanto comi hoje?', "
            "'quanto falta de proteína?', 'posso comer um doce?', 'como foi minha semana?' "
            "e para achar itens de outros dias antes de corrigir."
        ),
        parametros={
            "type": "object",
            "properties": {
                "periodo": {"type": "string", "enum": ["dia", "semana"]},
                "data": {
                    "type": ["string", "null"],
                    "description": "AAAA-MM-DD (o dia, ou o último dia da semana). null = hoje.",
                },
            },
            "required": ["periodo"],
        },
    ),
    Ferramenta(
        nome="consultar_alimento",
        descricao=(
            "Calcula calorias e macros de um alimento ou prato SEM registrar. Use para "
            "perguntas como 'quantas calorias tem uma banana?' ou 'vale mais a pena X ou Y?'."
        ),
        parametros={
            "type": "object",
            "properties": {
                "alimento": {"type": "string"},
                "quantidade": {"type": ["number", "null"]},
                "unidade": {"type": ["string", "null"]},
                "tamanho": {
                    "type": ["string", "null"],
                    "enum": ["pequeno", "medio", "grande", "cheio", "raso", None],
                },
            },
            "required": ["alimento"],
        },
    ),
    Ferramenta(
        nome="apagar_item",
        descricao=(
            "Remove um item registrado por engano ('apaga o suco', 'não comi a sobremesa'). "
            "Se a refeição ficar vazia, ela também some. Para mudar quantidade ou alimento, "
            "use atualizar_item em vez de apagar e registrar de novo."
        ),
        parametros={
            "type": "object",
            "properties": {"item_id": {"type": "integer"}},
            "required": ["item_id"],
        },
    ),
    Ferramenta(
        nome="alterar_refeicao",
        descricao=(
            "Muda o tipo ou a data/hora de uma refeição inteira ('não foi almoço, foi "
            "janta', 'isso foi ontem')."
        ),
        parametros={
            "type": "object",
            "properties": {
                "refeicao_id": {"type": "integer"},
                "tipo": {"type": ["string", "null"], "enum": [*registros.TIPOS, None]},
                "quando": {"type": ["string", "null"], "description": "AAAA-MM-DD HH:MM (Brasília)."},
            },
            "required": ["refeicao_id"],
        },
    ),
    Ferramenta(
        nome="apagar_meus_dados",
        descricao=(
            "Apaga DE VERDADE todos os dados do usuário (refeições, perfil, pesos, "
            "conversas e aceite). Funciona em duas etapas: chame quando o usuário pedir; o "
            "sistema devolve o aviso para você pedir a confirmação. Só depois que ele "
            "confirmar, numa NOVA mensagem, chame de novo com confirmado=true."
        ),
        parametros={
            "type": "object",
            "properties": {"confirmado": {"type": "boolean"}},
            "required": ["confirmado"],
        },
    ),
]

# Antes do aceite dos termos (LGPD), a IA só tem esta ferramenta.
DEFINICOES_ONBOARDING = [
    Ferramenta(
        nome="registrar_aceite",
        descricao=(
            "Registra que o usuário aceitou o termo de uso apresentado nas boas-vindas. "
            "Chame SOMENTE quando ele concordar de forma clara. Nunca chame se ele "
            "estiver em dúvida, perguntando algo ou recusando."
        ),
        parametros={"type": "object", "properties": {}},
    ),
]
DEFINICOES_ONBOARDING.append(next(f for f in DEFINICOES if f.nome == "apagar_meus_dados"))


# ---------- Execução ----------


def executar(ctx: Contexto, nome: str, argumentos: dict) -> dict:
    funcoes = {
        "registrar_refeicao": registrar_refeicao,
        "atualizar_item": atualizar_item,
        "atualizar_perfil": atualizar_perfil,
        "registrar_aceite": registrar_aceite,
        "consultar_resumo": consultar_resumo,
        "consultar_alimento": consultar_alimento,
        "apagar_item": apagar_item,
        "alterar_refeicao": alterar_refeicao,
        "apagar_meus_dados": apagar_meus_dados,
    }
    if nome not in funcoes:
        raise ErroFerramenta(f"Ferramenta desconhecida: {nome}")
    # RN07 garantida pelo código, não só pelo prompt: sem aceite, nada de dado pessoal.
    if nome not in ("registrar_aceite", "apagar_meus_dados") and not perfis.tem_aceite(ctx.usuario):
        raise ErroFerramenta("O usuário ainda não aceitou o termo de uso: nada pode ser gravado.")
    return funcoes[nome](ctx, argumentos)


def registrar_refeicao(ctx: Contexto, args: dict) -> dict:
    refeicao = _obter_ou_criar_refeicao(ctx, args)

    novos: list[ItemRefeicao] = []
    nao_encontrados: list[str] = []
    for item in args.get("itens") or []:
        calculados = _calcular_item(ctx.db, item)
        if calculados is None:
            nao_encontrados.append(item.get("alimento", ""))
            continue
        for calculado in calculados:
            novos.append(_novo_item(item, calculado))

    if not novos and not refeicao.itens:
        ctx.db.rollback()
        return {
            "registrado": False,
            "nao_encontrados": nao_encontrados,
            "instrucao": "Nenhum item encontrado na tabela. Chame de novo com nomes mais "
            "simples ou com estimativa_ia.",
        }

    refeicao.itens.extend(novos)
    ctx.db.commit()

    resultado = {
        "registrado": True,
        "refeicao_id": refeicao.id,
        "tipo": refeicao.tipo,
        "quando": f"{para_local(refeicao.data_hora):%d/%m %H:%M}",
        "itens_registrados": [_resumo_item(i) for i in novos],
        "total_da_refeicao": registros.totais(refeicao.itens),
        "total_do_dia": registros.totais_do_dia(ctx.db, ctx.usuario, para_local(refeicao.data_hora).date()),
    }
    if nao_encontrados:
        resultado["nao_encontrados"] = nao_encontrados
        resultado["instrucao"] = (
            "Estes itens NÃO foram gravados. Chame registrar_refeicao de novo só com "
            f"eles, com refeicao_id={refeicao.id}, usando um nome mais simples ou estimativa_ia."
        )
    return resultado


def atualizar_item(ctx: Contexto, args: dict) -> dict:
    item = _item_do_usuario(ctx, args.get("item_id"))
    antes = _resumo_item(item)
    # Campo ausente ou null = "não mudou" (os modelos costumam mandar null em tudo).
    def mudou_ou_atual(campo: str, atual):
        return args.get(campo) if args.get(campo) is not None else atual

    novo = {
        "alimento": mudou_ou_atual("alimento", item.alimento_nome),
        "quantidade": mudou_ou_atual("quantidade", item.quantidade),
        "unidade": mudou_ou_atual("unidade", item.unidade),
        "tamanho": mudou_ou_atual("tamanho", item.tamanho),
    }

    if item.alimento_id is None and not args.get("alimento"):
        raise ErroFerramenta(
            "Este item foi estimado pela IA (não está na tabela). Para mudar a quantidade, "
            "chame registrar_refeicao com uma nova estimativa_ia e explique ao usuário."
        )
    alimento = (
        taco.melhor(ctx.db, novo["alimento"])
        if args.get("alimento")
        else taco.por_nome_exato(ctx.db, item.alimento_nome)
    )
    calculado = calculo.calcular(ctx.db, alimento, novo["quantidade"], novo["unidade"], novo["tamanho"])

    item.quantidade, item.unidade, item.tamanho = novo["quantidade"], novo["unidade"], novo["tamanho"]
    _copiar_valores(item, calculado)
    ctx.db.commit()

    return {
        "atualizado": True,
        "antes": antes,
        "depois": _resumo_item(item),
        "total_da_refeicao": registros.totais(item.refeicao.itens),
        "total_do_dia": registros.totais_do_dia(
            ctx.db, ctx.usuario, para_local(item.refeicao.data_hora).date()
        ),
    }


def atualizar_perfil(ctx: Contexto, args: dict) -> dict:
    try:
        mudou = perfis.atualizar(ctx.db, ctx.usuario, args)
    except perfis.DadoInvalido as erro:
        raise ErroFerramenta(str(erro)) from erro
    ctx.db.commit()

    resultado = {"atualizado": mudou, "perfil": perfis.como_dict(ctx.usuario.perfil)}
    meta = perfis.meta(ctx.usuario.perfil)
    if isinstance(meta, perfis.metas.Meta):
        resultado["meta_diaria"] = meta.como_dict()
    else:
        resultado["meta_diaria"] = None
        resultado["faltando_para_a_meta"] = meta.faltando
        if meta.motivo:
            resultado["motivo_sem_meta"] = meta.motivo
    return resultado


def registrar_aceite(ctx: Contexto, args: dict) -> dict:
    if perfis.tem_aceite(ctx.usuario):
        return {"aceite": "já registrado"}
    consentimento = perfis.registrar_aceite(ctx.db, ctx.usuario, ctx.canal)
    ctx.db.commit()
    return {"aceite": "registrado", "versao_termo": consentimento.versao_termo}


def consultar_resumo(ctx: Contexto, args: dict) -> dict:
    dia = _data(args.get("data")) or registros.hoje()
    if args.get("periodo") == "semana":
        return registros.resumo_semana(ctx.db, ctx.usuario, dia)
    return registros.resumo_dia(ctx.db, ctx.usuario, dia)


def consultar_alimento(ctx: Contexto, args: dict) -> dict:
    """Mesma conta do registro, mas nada é gravado (RF24)."""
    calculados = _calcular_item(ctx.db, {**args, "estimativa_ia": None})
    if calculados is None:
        return {"encontrado": False, "alimento": args.get("alimento"),
                "instrucao": "Não está na tabela. Se responder, deixe claro que é uma estimativa sua."}
    return {
        "encontrado": True,
        "registrado": False,
        "itens": [
            {"alimento": c.alimento, "gramas": c.gramas, "kcal": c.kcal, "proteina": c.proteina,
             "carboidrato": c.carboidrato, "gordura": c.gordura, "estimado": c.estimado,
             "explicacao": c.explicacao}
            for c in calculados
        ],
        "total": {campo: round(sum(getattr(c, campo) for c in calculados), 1)
                  for campo in ("kcal", "proteina", "carboidrato", "gordura")},
    }


def apagar_item(ctx: Contexto, args: dict) -> dict:
    item = _item_do_usuario(ctx, args.get("item_id"))
    refeicao = item.refeicao
    apagado = _resumo_item(item)
    refeicao.itens.remove(item)  # o cascade "delete-orphan" apaga do banco
    refeicao_apagada = not refeicao.itens
    dia = para_local(refeicao.data_hora).date()
    if refeicao_apagada:
        ctx.db.delete(refeicao)
    ctx.db.commit()
    resultado = {"apagado": apagado, "refeicao_apagada": refeicao_apagada,
                 "total_do_dia": registros.totais_do_dia(ctx.db, ctx.usuario, dia)}
    if not refeicao_apagada:
        resultado["total_da_refeicao"] = registros.totais(refeicao.itens)
    return resultado


def alterar_refeicao(ctx: Contexto, args: dict) -> dict:
    refeicao = ctx.db.get(Refeicao, args.get("refeicao_id"))
    if refeicao is None or refeicao.usuario_id != ctx.usuario.id:
        raise ErroFerramenta("refeicao_id não encontrado para este usuário.")
    antes = {"tipo": refeicao.tipo, "quando": f"{para_local(refeicao.data_hora):%d/%m %H:%M}"}
    if args.get("tipo"):
        if args["tipo"] not in registros.TIPOS:
            raise ErroFerramenta(f"tipo inválido. Use um de {list(registros.TIPOS)}.")
        refeicao.tipo = args["tipo"]
    if args.get("quando"):
        refeicao.data_hora = _quando(args["quando"])
    ctx.db.commit()
    return {"alterado": True, "antes": antes,
            "depois": {"tipo": refeicao.tipo, "quando": f"{para_local(refeicao.data_hora):%d/%m %H:%M}"}}


# Pedidos de apagar aguardando confirmação: usuario_id -> (id da mensagem do pedido, validade).
# Ficam só na memória: se o servidor reiniciar, o pedido expira (o usuário pede de novo).
_PEDIDOS_APAGAR: dict[int, tuple[int, datetime]] = {}
VALIDADE_PEDIDO = timedelta(minutes=10)


def pedido_de_apagar_pendente(usuario_id: int) -> bool:
    pedido = _PEDIDOS_APAGAR.get(usuario_id)
    return pedido is not None and agora() <= pedido[1]


def apagar_meus_dados(ctx: Contexto, args: dict) -> dict:
    """RF26, em duas etapas garantidas pelo código (ação destrutiva e irreversível)."""
    pedido = _PEDIDOS_APAGAR.get(ctx.usuario.id)
    confirmacao_valida = (
        args.get("confirmado") is True
        and pedido is not None
        and pedido[0] != ctx.mensagem_id  # a confirmação veio numa mensagem NOVA do usuário
        and agora() <= pedido[1]
    )
    if not confirmacao_valida:
        _PEDIDOS_APAGAR[ctx.usuario.id] = (ctx.mensagem_id, agora() + VALIDADE_PEDIDO)
        return {
            "apagado": False,
            "aguardando_confirmacao": True,
            "instrucao": (
                "Explique que isso apaga PARA SEMPRE refeições, perfil, pesos e conversas, "
                "e pergunte se ele confirma. Só chame de novo com confirmado=true se ele "
                "confirmar na próxima mensagem (vale por 10 minutos)."
            ),
        }

    _PEDIDOS_APAGAR.pop(ctx.usuario.id, None)
    from app.nucleo import historico  # import aqui evita import circular

    historico.apagar_usuario(ctx.db, ctx.usuario)
    ctx.usuario_apagado = True
    return {"apagado": True}


# ---------- Ajudantes ----------


def _obter_ou_criar_refeicao(ctx: Contexto, args: dict) -> Refeicao:
    if args.get("refeicao_id"):
        refeicao = ctx.db.get(Refeicao, args["refeicao_id"])
        if refeicao is None or refeicao.usuario_id != ctx.usuario.id:
            raise ErroFerramenta("refeicao_id não encontrado para este usuário.")
        return refeicao

    tipo = args.get("tipo")
    if tipo not in registros.TIPOS:
        raise ErroFerramenta(f"tipo inválido: {tipo!r}. Use um de {list(registros.TIPOS)}.")
    refeicao = Refeicao(usuario_id=ctx.usuario.id, tipo=tipo, data_hora=_quando(args.get("quando")))
    ctx.db.add(refeicao)
    ctx.db.flush()  # gera o id
    return refeicao


def _item_do_usuario(ctx: Contexto, item_id) -> ItemRefeicao:
    item = ctx.db.get(ItemRefeicao, item_id)
    if item is None or item.refeicao.usuario_id != ctx.usuario.id:
        raise ErroFerramenta("item_id não encontrado para este usuário.")
    return item


def _data(texto: str | None):
    if not texto:
        return None
    try:
        return datetime.strptime(texto.strip()[:10], "%Y-%m-%d").date()
    except ValueError as erro:
        raise ErroFerramenta("data deve estar no formato AAAA-MM-DD.") from erro


def _quando(texto: str | None) -> datetime:
    if not texto:
        return agora()
    try:
        local = datetime.strptime(texto.strip()[:16], "%Y-%m-%d %H:%M")
    except ValueError as erro:
        raise ErroFerramenta("quando deve estar no formato 'AAAA-MM-DD HH:MM'.") from erro
    # O SQLite guarda só a hora "de parede", sem fuso: por isso tudo vai em UTC.
    momento = local.replace(tzinfo=fuso_local()).astimezone(UTC)
    if momento > agora():
        raise ErroFerramenta("quando está no futuro; refeições registradas já aconteceram.")
    return momento


def _calcular_item(db: Session, item: dict) -> list[ItemCalculado] | None:
    """Um item vira 1 ItemCalculado (ou vários, se for prato composto). None = não achou."""
    termo = (item.get("alimento") or "").strip()
    quantidade, unidade, tamanho = item.get("quantidade"), item.get("unidade"), item.get("tamanho")

    prato = calculo.calcular_prato(db, termo, quantidade, tamanho)
    if prato is not None:
        return prato
    try:
        return [calculo.calcular(db, termo, quantidade, unidade, tamanho)]
    except taco.AlimentoNaoEncontrado:
        estimativa = item.get("estimativa_ia")
        if not estimativa:
            return None
        # RF14: não está na tabela; usa o número da IA, marcado como baixa confiança.
        return [
            ItemCalculado(
                alimento_id=0,
                alimento=termo,
                origem="ia",
                gramas=round(float(estimativa["gramas"]), 1),
                kcal=round(float(estimativa["kcal"])),
                proteina=round(float(estimativa["proteina"]), 1),
                carboidrato=round(float(estimativa["carboidrato"]), 1),
                gordura=round(float(estimativa["gordura"]), 1),
                fibra=0.0,
                estimado=True,
                confianca=porcoes.BAIXA,
                explicacao="não está na tabela: estimativa da IA (revisar)",
            )
        ]


def _novo_item(item: dict, calculado: ItemCalculado) -> ItemRefeicao:
    novo = ItemRefeicao(
        descricao=(item.get("descricao") or item.get("alimento") or "")[:120],
        quantidade=item.get("quantidade"),
        unidade=item.get("unidade"),
        tamanho=item.get("tamanho"),
    )
    _copiar_valores(novo, calculado)
    return novo


def _copiar_valores(item: ItemRefeicao, calculado: ItemCalculado) -> None:
    item.alimento_id = calculado.alimento_id or None
    item.alimento_nome = calculado.alimento
    for campo in ("gramas", "kcal", "proteina", "carboidrato", "gordura", "fibra"):
        setattr(item, campo, getattr(calculado, campo))
    item.estimado = calculado.estimado
    item.confianca = calculado.confianca
    item.origem = calculado.origem
    item.explicacao = calculado.explicacao


def _resumo_item(item: ItemRefeicao) -> dict:
    return {
        "item_id": item.id,
        "descricao": item.descricao,
        "alimento": item.alimento_nome,
        "gramas": item.gramas,
        "kcal": item.kcal,
        "proteina": item.proteina,
        "carboidrato": item.carboidrato,
        "gordura": item.gordura,
        "estimado": item.estimado,
        "confianca": item.confianca,
    }


def como_texto(resultado: dict) -> str:
    """Resultado em JSON compacto, que é o formato que volta para a IA."""
    return json.dumps(resultado, ensure_ascii=False, separators=(",", ":"))

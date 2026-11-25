"""Ferramentas que a IA pode pedir para o código executar (tool use).

Cada ferramenta tem duas partes:
- a **definição** (nome, descrição e JSON Schema dos argumentos), que vai para a IA;
- a **execução**, uma função Python que faz o trabalho de verdade e devolve um dict.

A IA decide *quando* chamar e *com quais argumentos*. Os números (gramas, kcal, macros)
saem sempre do módulo de nutrição; a IA só informa o que e quanto foi comido.
"""

import json
from dataclasses import dataclass
from datetime import UTC, datetime

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


# ---------- Execução ----------


def executar(ctx: Contexto, nome: str, argumentos: dict) -> dict:
    funcoes = {
        "registrar_refeicao": registrar_refeicao,
        "atualizar_item": atualizar_item,
        "atualizar_perfil": atualizar_perfil,
        "registrar_aceite": registrar_aceite,
    }
    if nome not in funcoes:
        raise ErroFerramenta(f"Ferramenta desconhecida: {nome}")
    # RN07 garantida pelo código, não só pelo prompt: sem aceite, nada de dado pessoal.
    if nome != "registrar_aceite" and not perfis.tem_aceite(ctx.usuario):
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
    item = ctx.db.get(ItemRefeicao, args.get("item_id"))
    if item is None or item.refeicao.usuario_id != ctx.usuario.id:
        raise ErroFerramenta("item_id não encontrado para este usuário.")

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

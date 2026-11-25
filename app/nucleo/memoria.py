"""O que o NutrIA aprende sobre cada usuário (camada 1 da base de alimentos).

- **Medidas dele**: "minha caneca tem 350 ml". Depois disso, "1 caneca" vale 350 ml
  para ele, em vez da média de 300 ml.
- **Alimentos dele**: o rótulo do whey que ele toma, a receita do shake dele.
- **Itens frequentes**: o que ele mais registra. Vai no contexto para a IA reconhecer
  o hábito ("é a sua caneca de sempre?") sem precisar adivinhar.

Reconhecer "a mesma caneca" pela foto não é confiável. O que funciona é a pessoa
ensinar uma vez e o bot usar e confirmar.
"""

from datetime import timedelta

from rapidfuzz import fuzz
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.banco.modelos import AlimentoUsuario, ItemRefeicao, MedidaUsuario, Refeicao, Usuario
from app.nutricao import calculo, porcoes
from app.nutricao.calculo import ItemCalculado
from app.nutricao.taco import _cobre_a_consulta
from app.nutricao.texto import normalizar, singularizar
from app.tempo import agora

MACROS = ("kcal", "proteina", "carboidrato", "gordura", "fibra")


class DadoInvalido(ValueError):
    pass


# ---------- Medidas ----------


def medidas(usuario: Usuario) -> dict[str, float]:
    return {m.unidade: m.gramas for m in usuario.medidas}


def ensinar_medida(db: Session, usuario: Usuario, nome: str, gramas: float, descricao: str = "") -> MedidaUsuario:
    gramas = float(gramas)
    if not 1 <= gramas <= 3000:
        raise DadoInvalido("A medida deve ficar entre 1 e 3000 g/ml.")
    unidade = porcoes.normalizar_unidade(nome)
    if not unidade:
        raise DadoInvalido("Diga o nome da medida (ex.: caneca, pote, copo do trabalho).")
    existente = next((m for m in usuario.medidas if m.unidade == unidade), None)
    if existente:
        existente.gramas, existente.descricao = gramas, descricao or existente.descricao
        return existente
    medida = MedidaUsuario(usuario_id=usuario.id, unidade=unidade, gramas=gramas, descricao=descricao)
    usuario.medidas.append(medida)
    db.flush()
    return medida


# ---------- Alimentos ----------


def ensinar_alimento(db: Session, usuario: Usuario, args: dict) -> AlimentoUsuario:
    """Por rótulo (valores de uma porção) ou por receita (ingredientes da base)."""
    nome = (args.get("nome") or "").strip()
    if not nome:
        raise DadoInvalido("Diga o nome do alimento.")

    if args.get("ingredientes"):
        itens = [
            calculo.calcular(db, i["alimento"], i.get("quantidade"), i.get("unidade"),
                             medidas_usuario=medidas(usuario))
            for i in args["ingredientes"]
        ]
        porcao_g = sum(i.gramas for i in itens)
        totais = {campo: sum(getattr(i, campo) for i in itens) for campo in MACROS}
    else:
        porcao_g = float(args.get("porcao_g") or 0)
        if porcao_g <= 0 or args.get("kcal") is None:
            raise DadoInvalido("Informe porcao_g e pelo menos kcal da porção (do rótulo).")
        totais = {campo: float(args.get(campo) or 0) for campo in MACROS}

    if porcao_g <= 0:
        raise DadoInvalido("A porção precisa ter peso maior que zero.")
    por_100g = {campo: round(valor * 100 / porcao_g, 2) for campo, valor in totais.items()}

    nome_busca = normalizar(nome)
    existente = next((a for a in usuario.alimentos_proprios if a.nome_busca == nome_busca), None)
    alimento = existente or AlimentoUsuario(usuario_id=usuario.id, nome=nome, nome_busca=nome_busca)
    alimento.porcao_g = round(porcao_g, 1)
    for campo, valor in por_100g.items():
        setattr(alimento, campo, valor)
    if existente is None:
        usuario.alimentos_proprios.append(alimento)
    db.flush()
    return alimento


def buscar_alimento(usuario: Usuario, termo: str) -> AlimentoUsuario | None:
    consulta = normalizar(termo)
    melhor, melhor_nota = None, 0.0
    for alimento in usuario.alimentos_proprios:
        if consulta in (alimento.nome_busca, singularizar(alimento.nome_busca)) or singularizar(consulta) == alimento.nome_busca:
            return alimento
        nota = fuzz.token_set_ratio(consulta, alimento.nome_busca)
        if nota >= 90 and _cobre_a_consulta(consulta, alimento.nome_busca.split()) and nota > melhor_nota:
            melhor, melhor_nota = alimento, nota
    return melhor


def calcular_alimento(alimento: AlimentoUsuario, quantidade, unidade, tamanho, medidas_usuario) -> ItemCalculado:
    """Gramas de um alimento ensinado: g/ml direto, medida dele, ou a porção dele."""
    regras = porcoes.carregar_yaml("porcoes.yaml")
    unidade_norm = porcoes.normalizar_unidade(unidade, regras) if unidade else None
    fator, _ = porcoes._fator_tamanho(tamanho, regras)
    qtd = quantidade or 1
    if unidade_norm in porcoes._PESO_VOLUME:
        gramas = qtd * regras["medidas"][unidade_norm]
        explicacao = f"{qtd:g} {unidade_norm}"
    elif unidade_norm and unidade_norm in medidas_usuario:
        gramas = qtd * medidas_usuario[unidade_norm] * fator
        explicacao = f"{qtd:g} × {unidade_norm} (sua medida: {medidas_usuario[unidade_norm]:g} g)"
    else:
        gramas = qtd * alimento.porcao_g * fator
        explicacao = f"{qtd:g} × sua porção ({alimento.porcao_g:g} g)"
    valores = {campo: getattr(alimento, campo) for campo in MACROS}
    return calculo.de_valores(
        alimento.nome, "usuario", valores, gramas,
        estimado=quantidade is None, confianca=porcoes.MEDIA,
        explicacao=f"alimento que você ensinou: {explicacao} = {gramas:g} g",
    )


# ---------- Frequentes ----------


def itens_frequentes(db: Session, usuario: Usuario, dias: int = 30, minimo: int = 3, limite: int = 5) -> list[dict]:
    """O que a pessoa mais registrou nos últimos dias (alimento + medida mais comum)."""
    desde = agora() - timedelta(days=dias)
    consulta = (
        select(ItemRefeicao.alimento_nome, ItemRefeicao.quantidade, ItemRefeicao.unidade, func.count())
        .join(Refeicao)
        .where(Refeicao.usuario_id == usuario.id, Refeicao.data_hora >= desde)
        .group_by(ItemRefeicao.alimento_nome, ItemRefeicao.quantidade, ItemRefeicao.unidade)
        .order_by(func.count().desc())
    )
    frequentes = []
    for nome, quantidade, unidade, vezes in db.execute(consulta):
        if vezes < minimo:
            break
        medida = f"{quantidade:g} {unidade}" if quantidade and unidade else "porção padrão"
        frequentes.append({"alimento": nome, "medida": medida, "vezes": vezes})
        if len(frequentes) == limite:
            break
    return frequentes

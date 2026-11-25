"""Gramas -> calorias e macros. É aqui que "o código calcula" (princípio do projeto).

A IA (Fase 3) só diz *o quê* e *quanto* a pessoa comeu: "arroz, 2, colher de servir".
Os números saem daqui, da base TACO, sempre do mesmo jeito: valor por 100 g × gramas / 100.
"""

from dataclasses import asdict, dataclass

from sqlalchemy.orm import Session

from app.banco.modelos import Alimento
from app.config import carregar_yaml
from app.nutricao import porcoes, taco
from app.nutricao.texto import normalizar, singularizar


@dataclass
class ItemCalculado:
    alimento_id: int
    alimento: str  # nome na base
    origem: str  # "taco", "derivado" ou "manual"
    gramas: float
    kcal: float
    proteina: float
    carboidrato: float
    gordura: float
    fibra: float
    estimado: bool
    confianca: str  # "alta", "media" ou "baixa"
    explicacao: str

    def como_dict(self) -> dict:
        return asdict(self)


def calcular(
    db: Session,
    alimento: str | Alimento,
    quantidade: float | None = None,
    unidade: str | None = None,
    tamanho: str | None = None,
) -> ItemCalculado:
    """Ex.: calcular(db, "arroz", 2, "colher de servir").

    Levanta taco.AlimentoNaoEncontrado se o nome não bater com nada (a Fase 3 trata
    esse caso com a estimativa da IA, RF14).
    """
    if isinstance(alimento, str):
        alimento = taco.melhor(db, alimento)
    porcao = porcoes.para_gramas(alimento, quantidade, unidade, tamanho)
    return _montar(alimento, porcao.gramas, porcao.estimado, porcao.confianca, porcao.explicacao)


def nutrientes(alimento: Alimento, gramas: float) -> dict[str, float]:
    """Regra de três: o valor da tabela é por 100 g."""

    def valor(por_100g: float | None, casas: int) -> float:
        return round((por_100g or 0) * gramas / 100, casas)

    return {
        "kcal": valor(alimento.kcal, 0),
        "proteina": valor(alimento.proteina, 1),
        "carboidrato": valor(alimento.carboidrato, 1),
        "gordura": valor(alimento.gordura, 1),
        "fibra": valor(alimento.fibra, 1),
    }


# ---------- Pratos compostos (RF13) ----------


def buscar_prato(termo: str) -> tuple[str, dict] | None:
    """Procura em `config/pratos.yaml` pelo nome ou apelido do prato."""
    consulta = normalizar(termo)
    for nome, prato in carregar_yaml("pratos.yaml").items():
        nomes = {normalizar(nome)} | {normalizar(a) for a in prato.get("apelidos", [])}
        if consulta in nomes or singularizar(consulta) in nomes:
            return nome, prato
    return None


def calcular_prato(
    db: Session,
    termo: str,
    quantidade: float | None = None,
    tamanho: str | None = None,
    unidade: str | None = None,
) -> list[ItemCalculado] | None:
    """Decompõe um prato ("PF", "x-tudo") nos ingredientes típicos.

    Devolve um item por ingrediente, para cada um poder ser corrigido depois
    ("sem batata frita"). Devolve None se o termo não for um prato conhecido.

    A quantidade é em porções ("1 pedaço", "2 PFs"), exceto quando vem em peso ou
    volume: "600 g de carbonara" escala o prato para pesar 600 g no total.
    """
    achado = buscar_prato(termo)
    if achado is None:
        return None
    nome_prato, prato = achado

    regras = carregar_yaml("porcoes.yaml")
    fator_tamanho, _ = porcoes._fator_tamanho(tamanho, regras)
    unidade_norm = porcoes.normalizar_unidade(unidade, regras) if unidade else None
    if quantidade and unidade_norm in porcoes._PESO_VOLUME:
        peso_porcao = sum(i["gramas"] for i in prato["ingredientes"])
        gramas_pedidas = quantidade * regras["medidas"][unidade_norm]
        multiplicador = gramas_pedidas / peso_porcao * fator_tamanho
    else:
        multiplicador = (quantidade or 1) * fator_tamanho

    itens = []
    for ingrediente in prato["ingredientes"]:
        alimento = taco.por_nome_exato(db, ingrediente["alimento"])
        if alimento is None:
            raise taco.AlimentoNaoEncontrado(ingrediente["alimento"])
        gramas = ingrediente["gramas"] * multiplicador
        explicacao = f"parte de {nome_prato}: {ingrediente['gramas']:g} g × {multiplicador:g} = {gramas:g} g"
        # Prato decomposto é sempre uma estimativa: cada lugar monta de um jeito (RN02).
        itens.append(_montar(alimento, gramas, True, porcoes.BAIXA, explicacao))
    return itens


def _montar(alimento: Alimento, gramas: float, estimado: bool, confianca: str, explicacao: str) -> ItemCalculado:
    if alimento.kcal is None:
        # A base não tem as calorias deste alimento: o total sairia 0 sem ninguém perceber.
        confianca = porcoes.BAIXA
        explicacao += " (atenção: sem valor de kcal na base)"
    return ItemCalculado(
        alimento_id=alimento.id,
        alimento=alimento.nome,
        origem=alimento.origem,
        gramas=round(gramas, 1),
        estimado=estimado,
        # Valores digitados à mão (não TACO) nunca passam de confiança média.
        confianca=porcoes.MEDIA if alimento.origem == "manual" and confianca == porcoes.ALTA else confianca,
        explicacao=explicacao,
        **nutrientes(alimento, gramas),
    )

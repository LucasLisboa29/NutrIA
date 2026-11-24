"""Converte medidas caseiras em gramas (RF08, RF09).

Regras em `config/porcoes.yaml`. A ideia central do RN01 aparece aqui: nunca falhar.
Se a medida for desconhecida, usamos a porção padrão e marcamos como estimado, em vez de
travar o registro.
"""

from dataclasses import dataclass
from fnmatch import fnmatchcase

from app.banco.modelos import Alimento
from app.config import carregar_yaml
from app.nutricao.texto import normalizar, sem_acento, singularizar

# Confiança da quantidade, do mais para o menos preciso.
ALTA = "alta"  # peso ou volume informado (g, ml)
MEDIA = "media"  # medida caseira conhecida (concha, fatia)
BAIXA = "baixa"  # chute: porção padrão ou medida desconhecida

_PESO_VOLUME = {"g", "kg", "ml", "l"}


@dataclass
class Porcao:
    gramas: float
    estimado: bool  # True quando o usuário não deu quantidade (RF08, RN02)
    confianca: str
    explicacao: str  # ex.: "2 × concha (140 g) = 280 g"


def para_gramas(
    alimento: Alimento,
    quantidade: float | None = None,
    unidade: str | None = None,
    tamanho: str | None = None,
) -> Porcao:
    regras = carregar_yaml("porcoes.yaml")
    especificas = _medidas_do_alimento(alimento, regras)
    padrao = especificas.get("padrao", regras["padrao_geral"])
    fator, nome_tamanho = _fator_tamanho(tamanho, regras)
    sufixo = f" × {nome_tamanho} ({fator:g})" if nome_tamanho else ""

    # Nada informado: "comi arroz".
    if quantidade is None and not unidade:
        gramas = padrao * fator
        return Porcao(gramas, True, BAIXA, f"porção padrão ({padrao:g} g){sufixo} = {gramas:g} g")

    quantidade = 1 if quantidade is None else quantidade
    unidade_norm = normalizar_unidade(unidade or "unidade", regras)

    if unidade_norm in especificas:
        por_medida, confianca = especificas[unidade_norm], MEDIA
    elif unidade_norm in regras["medidas"]:
        por_medida = regras["medidas"][unidade_norm]
        confianca = ALTA if unidade_norm in _PESO_VOLUME else MEDIA
    else:
        # Medida que não conhecemos ("1 marmita"): usa a porção padrão, sem travar.
        gramas = quantidade * padrao * fator
        return Porcao(
            gramas,
            True,
            BAIXA,
            f"medida {unidade!r} desconhecida: {quantidade:g} × porção padrão ({padrao:g} g){sufixo} = {gramas:g} g",
        )

    gramas = quantidade * por_medida * fator
    return Porcao(
        gramas,
        False,
        confianca,
        f"{quantidade:g} × {unidade_norm} ({por_medida:g} g){sufixo} = {gramas:g} g",
    )


def normalizar_unidade(unidade: str, regras: dict | None = None) -> str:
    """'Colheres de Sopa' -> 'colher de sopa'; 'cs' -> 'colher de sopa'."""
    regras = regras or carregar_yaml("porcoes.yaml")
    texto = normalizar(unidade)
    conhecidas = set(regras["medidas"]) | {
        medida for especificas in regras["alimentos"].values() for medida in especificas
    }
    for forma in (texto, singularizar(texto)):
        if forma in conhecidas:
            return forma
        for oficial, apelidos in regras["apelidos_unidade"].items():
            if forma in {normalizar(a) for a in apelidos}:
                return oficial
    return singularizar(texto)


def _medidas_do_alimento(alimento: Alimento, regras: dict) -> dict:
    nome = sem_acento(alimento.nome)
    for padrao_nome, medidas in regras["alimentos"].items():
        if fnmatchcase(nome, sem_acento(padrao_nome)):
            return medidas
    return {}


def _fator_tamanho(tamanho: str | None, regras: dict) -> tuple[float, str | None]:
    if not tamanho:
        return 1.0, None
    texto = normalizar(tamanho)
    for forma in (texto, singularizar(texto)):
        # "grande", "grandes"; "cheia" -> "cheio"; "media" -> "medio"
        for candidato in (forma, forma[:-1] + "o" if forma.endswith("a") else forma):
            if candidato in regras["tamanhos"]:
                return float(regras["tamanhos"][candidato]), candidato
    return 1.0, None  # tamanho desconhecido: ignora, sem travar

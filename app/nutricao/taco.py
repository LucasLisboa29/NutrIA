"""Busca de alimentos por nome, tolerante a como as pessoas escrevem.

Ordem da busca:
1. **Sinônimo** (`config/sinonimos.yaml`): "pão de sal" -> "Pão, trigo, francês".
   É a escolha que nós definimos como padrão; confiança máxima.
2. **Busca aproximada** (fuzzy) com a biblioteca RapidFuzz: compara o texto com todos os
   nomes da base e dá uma nota de 0 a 100 de parecença. Tolera erro de digitação,
   palavras fora de ordem e palavras a mais ("feijao preto cozido" ~ "Feijão, preto, cozido").

Devolve uma lista de candidatos ordenados. Na Fase 3, a IA recebe essa lista e escolhe;
aqui, o primeiro da lista é o palpite do código.
"""

from dataclasses import dataclass

from rapidfuzz import fuzz
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.banco.modelos import Alimento
from app.config import carregar_yaml
from app.nutricao.texto import normalizar, singularizar

NOTA_MINIMA = 75  # abaixo disso, consideramos "não encontrado" (RF14)

# Palavras de preparo: quem diz só "batata" quase nunca comeu batata crua.
_CRU = {"cru", "crua", "crus", "cruas"}


@dataclass
class Candidato:
    alimento: Alimento
    nota: float  # 0 a 100
    via: str  # "sinonimo" ou "aproximada"


class AlimentoNaoEncontrado(LookupError):
    def __init__(self, termo: str):
        super().__init__(f"Alimento não encontrado na base: {termo!r}")
        self.termo = termo


def buscar(db: Session, termo: str, limite: int = 5) -> list[Candidato]:
    consulta = normalizar(termo)
    if not consulta:
        return []

    candidatos: list[Candidato] = []
    alimento_sinonimo = _por_sinonimo(db, consulta)
    if alimento_sinonimo is not None:
        candidatos.append(Candidato(alimento_sinonimo, 100.0, "sinonimo"))

    for alimento, nota in _aproximada(db, consulta):
        if len(candidatos) >= limite:
            break
        if alimento_sinonimo is None or alimento.id != alimento_sinonimo.id:
            candidatos.append(Candidato(alimento, nota, "aproximada"))
    return candidatos


def melhor(db: Session, termo: str) -> Alimento:
    """O palpite do código para um termo. Levanta AlimentoNaoEncontrado se não achar."""
    candidatos = buscar(db, termo, limite=1)
    if not candidatos:
        raise AlimentoNaoEncontrado(termo)
    return candidatos[0].alimento


def por_nome_exato(db: Session, nome: str) -> Alimento | None:
    return db.scalar(select(Alimento).where(Alimento.nome == nome))


def _por_sinonimo(db: Session, consulta: str) -> Alimento | None:
    sinonimos = {normalizar(chave): valor for chave, valor in carregar_yaml("sinonimos.yaml").items()}
    for forma in (consulta, singularizar(consulta)):
        if forma in sinonimos:
            return por_nome_exato(db, sinonimos[forma])
    return None


def _aproximada(db: Session, consulta: str) -> list[tuple[Alimento, float]]:
    palavras = set(consulta.split()) | set(singularizar(consulta).split())
    pede_cru = bool(palavras & _CRU)

    uma_palavra = len(consulta.split()) == 1

    notas = []
    for alimento in db.scalars(select(Alimento)):
        nome = alimento.nome_busca
        palavras_nome = nome.split()
        # token_set_ratio ignora ordem e palavras extras do nome mais longo:
        # "feijao preto" x "feijao preto cozido" = 100.
        nota = max(
            fuzz.token_set_ratio(consulta, nome),
            fuzz.token_set_ratio(singularizar(consulta), nome),
        )
        if uma_palavra:
            # Erro de digitação numa palavra só ("cuzcuz" ~ "cuscuz"): compara palavra a palavra.
            nota = max(nota, 0.95 * max(fuzz.ratio(consulta, p) for p in palavras_nome))
        if nota < NOTA_MINIMA:
            continue
        if not _cobre_a_consulta(consulta, palavras_nome):
            # Parecido no texto, mas é outro alimento ("rosquinha" x "feijão rosinha",
            # "torta de morango" x "morango cru"): melhor "não encontrado" que um erro.
            continue
        # Desempates, para o palpite ficar mais "humano":
        if palavras_nome[0] in palavras:
            nota += 3  # o alimento principal é o que a pessoa disse ("pera" > "laranja pera")
        if not pede_cru and set(palavras_nome) & _CRU and alimento.categoria != "Frutas e derivados":
            nota -= 6  # prefere o preparado ao cru (fruta crua é o normal, não penaliza)
        nota -= len(nome) / 100  # entre empatados, o nome mais simples
        notas.append((alimento, nota))

    # Ordena pela nota completa; só depois limita a 99 (100 é reservado ao sinônimo).
    notas.sort(key=lambda par: par[1], reverse=True)
    return [(alimento, round(min(nota, 99.0), 1)) for alimento, nota in notas]


# Palavras que não definem o alimento ("suco DE uva", "pão COM manteiga").
_PALAVRAS_VAZIAS = {"de", "da", "do", "das", "dos", "com", "e", "a", "o", "em", "no", "na", "ao", "um", "uma"}


def _cobre_a_consulta(consulta: str, palavras_nome: list[str]) -> bool:
    """Toda palavra importante do que a pessoa disse precisa estar no nome do alimento.

    É a trava contra o pior erro da busca aproximada: escolher um alimento *parecido no
    texto* mas diferente na comida. Regras:
    - cada palavra da consulta precisa bater (quase igual, nota >= 90) com alguma palavra
      do nome: "peito de frango grelhado" cobre "Frango, peito, sem pele, grelhado";
    - exceção para erro de digitação na palavra principal: a 1ª palavra da consulta pode
      ser só parecida (>= 80) com a 1ª palavra do nome ("cuzcuz" ~ "Cuscuz, paulista").
    Assim "rosquinha" não vira "Feijão, rosinha" (a palavra principal do nome é "feijão")
    e "torta de morango" não vira "Morango, cru" (não existe "torta" no nome).
    """
    nome = set(palavras_nome) | {singularizar(p) for p in palavras_nome}
    importantes = [p for p in consulta.split() if p not in _PALAVRAS_VAZIAS]
    for indice, palavra in enumerate(importantes):
        formas = {palavra, singularizar(palavra)}
        if formas & nome or any(fuzz.ratio(f, p) >= 90 for f in formas for p in nome):
            continue
        if indice == 0 and any(fuzz.ratio(f, palavras_nome[0]) >= 80 for f in formas):
            continue
        return False
    return True

"""Produtos de marca via Open Food Facts (camada 4 da base).

O Open Food Facts é uma base aberta e colaborativa de produtos de mercado (rótulo,
código de barras). Licença ODbL: os dados podem ser usados desde que a fonte seja
citada ("© Open Food Facts contributors").

Cuidados:
- só é consultado quando TACO, Base NutrIA e alimentos do usuário não acharam nada;
- tempo limite curto: se a internet falhar, segue para a estimativa da IA (RN01);
- toda busca fica em cache no banco (`buscas_off`, `produtos_off`): o mesmo produto não
  é procurado duas vezes;
- nada pessoal é enviado: só o nome do produto, e o app se identifica de forma genérica;
- a cobertura de produtos brasileiros é pequena e há versões de outros países com
  fórmula diferente (o Monster Ultra achado era o australiano). Por isso produto de fora
  do Brasil fica com confiança baixa, e o rótulo lido na foto tem preferência sobre ele.
"""

import re

import httpx
from rapidfuzz import fuzz
from sqlalchemy.orm import Session

from app.banco.modelos import BuscaOFF, ProdutoOFF
from app.config import settings
from app.nutricao import calculo, porcoes
from app.nutricao.calculo import ItemCalculado
from app.nutricao.taco import _cobre_a_consulta
from app.nutricao.texto import normalizar

# API de busca nova ("search-a-licious"). A antiga (cgi/search.pl) vivia devolvendo 503.
URL_BUSCA = "https://search.openfoodfacts.org/search"
IDENTIFICACAO = "NutrIA/0.1 (projeto de estudo)"  # a API pede um User-Agent próprio
CAMPOS = "code,product_name,product_name_pt,brands,quantity,nutriments,countries_tags"
FONTE = "Open Food Facts (ODbL)"
EMBALAGEM_INDIVIDUAL_MAX = 600  # g ou ml
EMBALAGENS = {"lata", "unidade", "garrafa", "long neck", "pacote", "embalagem", "caixinha", "pote", "sache", "barra"}


def buscar(db: Session, termo: str) -> ProdutoOFF | None:
    if not settings.openfoodfacts_ativo:
        return None
    chave = normalizar(termo)[:120]
    cache = db.get(BuscaOFF, chave)
    if cache is not None:
        return db.get(ProdutoOFF, cache.codigo) if cache.codigo else None

    try:
        produtos = _consultar_api(termo)
    except httpx.HTTPError:
        return None  # falha de rede não vai para o cache: na próxima tenta de novo

    produto = _escolher(chave, produtos)
    if produto is not None and db.get(ProdutoOFF, produto.codigo) is None:
        db.add(produto)
    db.add(BuscaOFF(termo=chave, codigo=produto.codigo if produto else None))
    db.flush()
    return db.get(ProdutoOFF, produto.codigo) if produto else None


def calcular(produto: ProdutoOFF, quantidade, unidade, tamanho, medidas_usuario) -> ItemCalculado:
    unidade_norm = porcoes.normalizar_unidade(unidade) if unidade else None
    # A embalagem só vira porção quando é individual (lata, garrafinha, barra): "1 lata"
    # de Toddy em pó (1 kg) não é uma porção de 1 kg.
    individual = produto.quantidade_g is not None and produto.quantidade_g <= EMBALAGEM_INDIVIDUAL_MAX
    if individual and (unidade_norm in EMBALAGENS or (unidade_norm is None and quantidade)):
        gramas = (quantidade or 1) * produto.quantidade_g
        porcao_desc = f"{quantidade or 1:g} × embalagem ({produto.quantidade_g:g} g/ml)"
        estimado, confianca = False, porcoes.MEDIA
    else:
        porcao = porcoes.para_gramas(produto, quantidade, unidade, tamanho, medidas_usuario,
                                     padrao_g=produto.quantidade_g if individual else None)
        gramas, porcao_desc = porcao.gramas, porcao.explicacao
        estimado, confianca = porcao.estimado, porcao.confianca
    nome = f"{produto.nome} ({produto.marca})" if produto.marca else produto.nome
    valores = {c: getattr(produto, c) for c in ("kcal", "proteina", "carboidrato", "gordura", "fibra")}
    if not produto.do_brasil:
        confianca = porcoes.BAIXA  # versão de outro país pode ter outra fórmula
    explicacao = f"{porcao_desc}; dados: {FONTE}" + ("" if produto.do_brasil else ", produto de outro país")
    return calculo.de_valores(
        nome[:120], "openfoodfacts", valores, gramas, estimado,
        porcoes.MEDIA if confianca == porcoes.ALTA else confianca,
        explicacao,
    )


def _consultar_api(termo: str) -> list[dict]:
    resposta = httpx.get(
        URL_BUSCA,
        params={"q": termo, "page_size": 15, "fields": CAMPOS},
        headers={"User-Agent": IDENTIFICACAO},
        timeout=5.0,
    )
    resposta.raise_for_status()
    return resposta.json().get("hits", [])


def _escolher(consulta: str, produtos: list[dict]) -> ProdutoOFF | None:
    """O produto mais parecido que tenha as calorias informadas."""
    melhor, melhor_nota = None, 0.0
    for p in produtos:
        nutrientes = p.get("nutriments") or {}
        kcal = nutrientes.get("energy-kcal_100g")
        if kcal is None and nutrientes.get("energy_100g") is not None:
            kcal = float(nutrientes["energy_100g"]) / 4.184  # veio em kJ
        nome = (p.get("product_name_pt") or p.get("product_name") or "").strip()
        if kcal is None or not nome or not p.get("code"):
            continue
        marcas = p.get("brands") or ""
        marcas = ", ".join(marcas) if isinstance(marcas, list) else str(marcas)
        texto = normalizar(f"{nome} {marcas}")
        if not _cobre_a_consulta(consulta, texto.split()):
            continue  # mesma trava da busca na TACO: toda palavra importante tem que estar lá
        nota = fuzz.token_set_ratio(consulta, texto)
        do_brasil = "en:brazil" in (p.get("countries_tags") or [])
        if do_brasil:
            nota += 5  # preferência por produto vendido no Brasil
        if nota > melhor_nota:
            melhor_nota = nota
            melhor = ProdutoOFF(
                codigo=str(p["code"])[:32],
                nome=nome[:160],
                marca=marcas.split(",")[0].split(":")[-1].strip()[:120],
                do_brasil=do_brasil,
                quantidade_g=_quantidade_em_gramas(p.get("quantity") or ""),
                kcal=round(float(kcal), 2),
                proteina=_num(nutrientes.get("proteins_100g")),
                carboidrato=_num(nutrientes.get("carbohydrates_100g")),
                gordura=_num(nutrientes.get("fat_100g")),
                fibra=_num(nutrientes.get("fiber_100g")),
            )
    return melhor if melhor_nota >= 70 else None


def _quantidade_em_gramas(texto: str) -> float | None:
    """'473 ml' -> 473; '1,5 L' -> 1500; '6 x 330 ml' -> 330 (uma unidade)."""
    achado = re.search(r"(\d+(?:[.,]\d+)?)\s*(kg|g|ml|cl|l)\b", texto.lower())
    if not achado:
        return None
    valor = float(achado.group(1).replace(",", "."))
    return valor * {"kg": 1000, "g": 1, "ml": 1, "cl": 10, "l": 1000}[achado.group(2)]


def _num(valor) -> float:
    try:
        return round(float(valor), 2)
    except (TypeError, ValueError):
        return 0.0

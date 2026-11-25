"""Testes da base nutricional (Fase 2): busca, porções e cálculo, tudo sem IA."""

from fnmatch import fnmatchcase

import pytest
from sqlalchemy import func, select

from app.banco.modelos import Alimento
from app.config import carregar_yaml
from app.nutricao import calculo, porcoes, taco
from app.nutricao.texto import normalizar, sem_acento, singularizar

# ---------- Marco da fase ----------


def test_marco_arroz_duas_colheres_de_servir(db):
    item = calculo.calcular(db, "arroz", 2, "colher de servir")

    # Arroz tipo 1 cozido na TACO: 128 kcal, 2,5 g prot, 28,1 g carb, 0,2 g gord por 100 g.
    assert item.alimento == "Arroz, tipo 1, cozido"
    assert item.gramas == 90
    assert item.kcal == 115  # 128 × 90 / 100 = 115,2
    assert item.carboidrato == 25.3
    assert item.estimado is False
    assert item.confianca == "media"


# ---------- Importação ----------


def test_importacao_tem_taco_e_extras(db):
    from app.nutricao.importar_taco import ARQUIVO_EXTRAS
    import yaml

    extras = yaml.safe_load(ARQUIVO_EXTRAS.read_text(encoding="utf-8"))["novos"]
    assert db.scalar(select(func.count(Alimento.id))) == 597 + len(extras)  # TACO + Base NutrIA
    feijao = taco.por_nome_exato(db, "Feijão, carioca, cozido")
    assert (feijao.kcal, feijao.proteina, feijao.origem) == (76, 4.8, "taco")
    macarrao = taco.por_nome_exato(db, "Macarrão, trigo, cozido")
    assert macarrao.origem == "derivado"
    assert macarrao.kcal == pytest.approx(371 * 0.42, abs=0.01)


def test_leite_em_branco_na_taco_foi_corrigido(db):
    leite = calculo.calcular(db, "leite", 1, "copo")
    assert leite.origem == "manual"
    assert leite.kcal == 122  # 61 kcal/100 ml × 200 ml


def test_alimento_sem_kcal_na_base_avisa(db):
    item = calculo.calcular(db, taco.por_nome_exato(db, "Coco, verde, cru"), 100, "g")
    assert item.confianca == "baixa"
    assert "sem valor de kcal" in item.explicacao


# ---------- Texto ----------


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [("colheres", "colher"), ("pães", "pao"), ("porções", "porcao"), ("fatias", "fatia"),
     ("pastéis", "pastel"), ("arroz", "arroz"), ("ovos", "ovo")],
)
def test_singularizar(entrada, esperado):
    assert singularizar(normalizar(entrada)) == esperado


# ---------- Busca ----------


@pytest.mark.parametrize(
    ("termo", "esperado"),
    [
        ("arroz", "Arroz, tipo 1, cozido"),
        ("Pão de Sal", "Pão, trigo, francês"),
        ("pães franceses", "Pão, trigo, francês"),
        ("aipim", "Mandioca, cozida"),
        ("ovos", "Ovo, de galinha, inteiro, cozido/10minutos"),
        ("feijão preto", "Feijão, preto, cozido"),
        ("queijo parmesão", "Queijo, parmesão"),  # pela busca aproximada
        ("cuzcuz", "Cuscuz, paulista"),  # erro de digitação
        ("abacaxi", "Abacaxi, cru"),  # fruta crua é o normal
        ("pera", "Pêra, Park, crua"),  # não "Laranja, pêra"
        ("feijão preto cru", "Feijão, preto, cru"),  # pediu cru, leva cru
    ],
)
def test_busca_tolerante(db, termo, esperado):
    assert taco.melhor(db, termo).nome == esperado


def test_busca_prefere_preparado_ao_cru(db):
    assert "cru" not in taco.melhor(db, "frango assado").nome


def test_alimento_inexistente(db):
    assert taco.buscar(db, "sushi") == []
    with pytest.raises(taco.AlimentoNaoEncontrado):
        calculo.calcular(db, "sushi", 1, "unidade")


# ---------- Porções ----------


def test_peso_em_gramas_tem_confianca_alta(db):
    item = calculo.calcular(db, "frango", 150, "g")
    assert (item.gramas, item.confianca, item.estimado) == (150, "alta", False)


def test_apelido_e_plural_de_medida(db):
    assert porcoes.normalizar_unidade("Colheres de Sopa") == "colher de sopa"
    assert porcoes.normalizar_unidade("cs") == "colher de sopa"
    assert calculo.calcular(db, "feijão", 2, "conchas").gramas == 280


def test_tamanho_multiplica_a_medida(db):
    assert calculo.calcular(db, "feijão", 1, "concha", "grande").gramas == 196  # 140 × 1,4
    assert calculo.calcular(db, "arroz", 1, "prato", "cheio").gramas == 325  # 250 × 1,3


def test_sem_quantidade_usa_porcao_padrao_e_marca_estimado(db):
    item = calculo.calcular(db, "arroz")
    assert (item.gramas, item.estimado, item.confianca) == (150, True, "baixa")


def test_quantidade_sem_unidade_conta_unidades(db):
    assert calculo.calcular(db, "ovo", 2).gramas == 100  # 2 × 50 g


def test_medida_desconhecida_nao_trava(db):
    item = calculo.calcular(db, "arroz", 1, "bacia")
    assert (item.gramas, item.estimado) == (150, True)
    assert "desconhecida" in item.explicacao


def test_medida_generica_quando_alimento_nao_tem_especifica(db):
    # Abacate não tem medidas próprias: "colher de sopa" usa a genérica (15 g).
    assert calculo.calcular(db, "abacate", 2, "colher de sopa").gramas == 30


# ---------- Pratos compostos ----------


def test_prato_feito_vira_itens(db):
    itens = calculo.calcular_prato(db, "PF")
    nomes = [i.alimento for i in itens]
    assert "Arroz, tipo 1, cozido" in nomes and "Feijão, carioca, cozido" in nomes
    assert all(i.estimado for i in itens)
    # Faixa de sanidade. Hoje dá ~630 kcal; PF de restaurante tende a ter mais óleo
    # (a calibrar na Fase 7).
    assert 500 < sum(i.kcal for i in itens) < 1000


def test_prato_em_dobro(db):
    um = calculo.calcular_prato(db, "x-tudo")
    dois = calculo.calcular_prato(db, "xis tudo", quantidade=2)
    assert sum(i.gramas for i in dois) == 2 * sum(i.gramas for i in um)


def test_termo_que_nao_e_prato(db):
    assert calculo.calcular_prato(db, "arroz") is None


# ---------- Configuração coerente com a base ----------
# Protege contra erro de digitação nos YAML: um nome errado lá quebraria o bot em silêncio.


def test_todo_sinonimo_aponta_para_alimento_existente(db):
    nomes = set(db.scalars(select(Alimento.nome)))
    faltando = {k: v for k, v in carregar_yaml("sinonimos.yaml").items() if v not in nomes}
    assert faltando == {}


def test_todo_ingrediente_de_prato_existe(db):
    nomes = set(db.scalars(select(Alimento.nome)))
    faltando = [
        ing["alimento"]
        for prato in carregar_yaml("pratos.yaml").values()
        for ing in prato["ingredientes"]
        if ing["alimento"] not in nomes
    ]
    assert faltando == []


def test_toda_regra_de_porcao_vale_para_algum_alimento(db):
    nomes = [sem_acento(n) for n in db.scalars(select(Alimento.nome))]
    sem_uso = [
        regra
        for regra in carregar_yaml("porcoes.yaml")["alimentos"]
        if not any(fnmatchcase(n, sem_acento(regra)) for n in nomes)
    ]
    assert sem_uso == []

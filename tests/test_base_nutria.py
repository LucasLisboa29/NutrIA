"""Testes da Etapa 1 das fotos: busca segura, receitas da Base NutrIA, pratos por peso e
medidas novas. Os casos vêm das fotos reais analisadas (pasta de calibragem)."""

import pytest

from app.nucleo import ferramentas, registros
from app.nutricao import calculo, taco


# ---------- Busca segura (fotos 9 e 10) ----------


@pytest.mark.parametrize(
    ("termo", "proibido"),
    [
        ("rosquinha", "Feijão, rosinha, cozido"),  # foto 9: virava feijão
        ("torta de morango", "Morango, cru"),  # foto 10: virava só morango
        ("banana frita", "Banana, prata, crua"),
    ],
)
def test_busca_nao_troca_por_alimento_parecido_no_texto(db, termo, proibido):
    assert proibido not in [c.alimento.nome for c in taco.buscar(db, termo)]


@pytest.mark.parametrize(
    ("termo", "esperado"),
    [
        ("peito de frango grelhado", "Frango, peito, sem pele, grelhado"),  # palavras fora de ordem
        ("cuzcuz", "Cuscuz, paulista"),  # erro de digitação continua aceito
        ("carne grelhada", "Carne, bovina, maminha, grelhada"),
    ],
)
def test_busca_segura_continua_achando_o_certo(db, termo, esperado):
    assert taco.melhor(db, termo).nome == esperado


# ---------- Receitas da Base NutrIA ----------


def test_receita_e_calculada_a_partir_dos_ingredientes_da_taco(db):
    molho = taco.por_nome_exato(db, "Molho branco (bechamel)")
    leite = taco.por_nome_exato(db, "Leite, de vaca, integral")
    manteiga = taco.por_nome_exato(db, "Manteiga, com sal")
    farinha = taco.por_nome_exato(db, "Farinha, de trigo")
    esperado = (leite.kcal * 500 + manteiga.kcal * 30 + farinha.kcal * 30) / 100 / 520 * 100
    assert molho.origem == "receita"
    assert molho.kcal == pytest.approx(esperado, abs=0.01)


def test_receita_pode_usar_outra_receita_como_ingrediente(db):
    # Macarrão ao molho branco usa o "Molho branco (bechamel)", que também é receita.
    assert taco.por_nome_exato(db, "Macarrão, ao molho branco").kcal > 0


@pytest.mark.parametrize(
    ("termo", "esperado"),
    [
        ("bacon", "Toucinho, frito"),
        ("lasanha", "Lasanha, à bolonhesa"),
        ("massa de lasanha", "Lasanha, massa fresca, cozida"),
        ("carbonara", "Macarrão, à carbonara"),
        ("pizza de frango com catupiry", "Pizza, frango com catupiry"),
        ("rosca doce", "Rosca doce (pão doce)"),
        ("molho branco", "Molho branco (bechamel)"),
    ],
)
def test_sinonimos_novos(db, termo, esperado):
    assert taco.melhor(db, termo).nome == esperado


# ---------- Porções (fotos 1, 4, 6, 7 e 8) ----------


def test_lasanha_um_pedaco_e_um_pedaco_de_verdade(db):
    item = calculo.calcular(db, "lasanha", 1, "pedaço")
    assert item.gramas == 250  # antes: só a massa, 50 g
    assert 400 < item.kcal < 480


def test_carbonara_pelo_peso_que_o_usuario_disse(db):
    item = calculo.calcular(db, "carbonara", 600, "g")
    assert item.gramas == 600 and item.kcal == pytest.approx(1376, abs=2)


def test_caneca_e_uma_medida_conhecida(db):
    item = calculo.calcular(db, "achocolatado", 1, "caneca")
    assert (item.gramas, item.confianca) == (300, "media")


def test_colher_de_carne_moida_tem_medida_propria(db):
    assert calculo.calcular(db, "carne moída", 4, "colher de sopa").gramas == 100  # não 60


def test_prato_composto_pelo_peso_total(db):
    itens = calculo.calcular_prato(db, "pf", 300, unidade="g")
    assert sum(i.gramas for i in itens) == pytest.approx(300, abs=1)


def test_prato_composto_em_porcoes_continua_igual(db):
    itens = calculo.calcular_prato(db, "pf", 2)
    assert sum(i.gramas for i in itens) == 2 * 460


# ---------- Ao longo do dia (foto 3) ----------


def test_tipo_ao_longo_do_dia_existe_para_bebidas_e_beliscos():
    assert registros.TIPOS["avulso"] == "Ao longo do dia"
    definicao = next(f for f in ferramentas.DEFINICOES if f.nome == "registrar_refeicao")
    assert "avulso" in definicao.parametros["properties"]["tipo"]["enum"]

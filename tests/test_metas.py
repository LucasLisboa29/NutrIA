"""Testes do cálculo de metas (Fase 4). Contas conferidas à mão."""

import pytest

from app.nucleo import metas
from app.nucleo.metas import Meta, SemMeta


def test_mulher_perder_peso():
    meta = metas.calcular("feminino", 30, 65, 165, "leve", "perder")
    # TMB = 650 + 1031,25 - 150 - 161 = 1370,25; × 1,375 = 1884,1; −20% = 1507,3
    assert isinstance(meta, Meta)
    assert (meta.tmb, meta.gasto_total, meta.kcal) == (1370, 1884, 1507)
    assert meta.proteina_g == 117  # 1,8 g × 65 kg
    assert meta.piso_aplicado is False


def test_homem_ganhar_peso():
    meta = metas.calcular("masculino", 25, 80, 180, "intenso", "ganhar")
    # TMB = 800 + 1125 - 125 + 5 = 1805; × 1,725 = 3113,6; +10% = 3425
    assert (meta.tmb, meta.kcal) == (1805, 3425)


def test_macros_somam_as_calorias_da_meta():
    meta = metas.calcular("feminino", 40, 70, 160, "moderado", "manter")
    total = meta.proteina_g * 4 + meta.carboidrato_g * 4 + meta.gordura_g * 9
    assert total == pytest.approx(meta.kcal, abs=10)  # diferença só de arredondamento


def test_piso_de_seguranca_rn05():
    # TMB = 450 + 937,5 - 300 - 161 = 926,5; × 1,2 = 1111,8; −20% = 889 -> piso de 1200
    meta = metas.calcular("feminino", 60, 45, 150, "sedentario", "perder")
    assert meta.kcal == 1200
    assert meta.piso_aplicado is True
    assert "piso" in meta.explicacao


def test_piso_masculino_e_1500():
    meta = metas.calcular("masculino", 70, 50, 155, "sedentario", "perder")
    assert meta.kcal == 1500


def test_dados_incompletos_dizem_o_que_falta():
    resultado = metas.calcular("feminino", None, 65, None, "leve", "perder")
    assert isinstance(resultado, SemMeta)
    assert resultado.faltando == ["idade", "altura_cm"]


def test_menor_de_idade_nao_recebe_meta():
    resultado = metas.calcular("masculino", 15, 60, 170, "moderado", "perder")
    assert isinstance(resultado, SemMeta)
    assert "nutricionista" in resultado.motivo

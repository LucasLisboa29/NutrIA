"""Cálculo da meta diária de calorias e macros (RF18, RN05).

Passo a passo:
1. **TMB** (taxa metabólica basal): quanto o corpo gasta em repouso total, pela fórmula
   de Mifflin-St Jeor, a mais usada hoje para adultos:
       homem:  10 × peso(kg) + 6,25 × altura(cm) − 5 × idade + 5
       mulher: 10 × peso(kg) + 6,25 × altura(cm) − 5 × idade − 161
2. **GET** (gasto energético total) = TMB × fator de atividade (sedentário 1,2 ... 1,9).
3. **Meta** = GET ajustado pelo objetivo (−20% para perder, +10% para ganhar), nunca
   abaixo do piso de segurança (RN05).
4. **Macros**: proteína por kg de peso, gordura como % das calorias, carboidrato o resto.
   Proteína e carboidrato têm 4 kcal por grama; gordura tem 9.

Os parâmetros ficam em `config/metas.yaml`. Aqui só tem conta, sem IA.
"""

from dataclasses import asdict, dataclass

from app.config import carregar_yaml

CAMPOS_NECESSARIOS = ("sexo", "idade", "peso_kg", "altura_cm", "nivel_atividade", "objetivo")


@dataclass
class Meta:
    kcal: int
    proteina_g: int
    carboidrato_g: int
    gordura_g: int
    tmb: int
    gasto_total: int
    piso_aplicado: bool
    explicacao: str

    def como_dict(self) -> dict:
        return asdict(self)


@dataclass
class SemMeta:
    """Quando ainda não dá para calcular: o que falta ou por quê."""

    faltando: list[str]
    motivo: str = ""

    def como_dict(self) -> dict:
        return asdict(self)


def calcular(
    sexo: str | None,
    idade: int | None,
    peso_kg: float | None,
    altura_cm: float | None,
    nivel_atividade: str | None,
    objetivo: str | None,
) -> Meta | SemMeta:
    dados = dict(sexo=sexo, idade=idade, peso_kg=peso_kg, altura_cm=altura_cm,
                 nivel_atividade=nivel_atividade, objetivo=objetivo)
    faltando = [campo for campo in CAMPOS_NECESSARIOS if dados[campo] in (None, "")]
    if faltando:
        return SemMeta(faltando=faltando)

    config = carregar_yaml("metas.yaml")
    if idade < config["idade_minima"]:
        return SemMeta(
            faltando=[],
            motivo=f"Menor de {config['idade_minima']} anos: a fórmula é para adultos. "
            "O ideal é ter acompanhamento de um nutricionista.",
        )

    ajuste_sexo = 5 if sexo == "masculino" else -161
    tmb = 10 * peso_kg + 6.25 * altura_cm - 5 * idade + ajuste_sexo
    fator = config["fatores_atividade"][nivel_atividade]
    gasto = tmb * fator
    ajuste = config["ajuste_objetivo"][objetivo]
    kcal = gasto * (1 + ajuste)

    piso = config["piso_kcal"][sexo]
    piso_aplicado = kcal < piso
    kcal = max(kcal, piso)

    proteina = config["proteina_g_por_kg"][objetivo] * peso_kg
    gordura = kcal * config["gordura_fracao_kcal"] / 9
    carboidrato = max(kcal - proteina * 4 - gordura * 9, 0) / 4

    explicacao = (
        f"TMB {tmb:.0f} kcal (Mifflin-St Jeor) × {fator} ({nivel_atividade}) = gasto de "
        f"{gasto:.0f} kcal; objetivo {objetivo} ({ajuste:+.0%}) = {gasto * (1 + ajuste):.0f} kcal"
    )
    if piso_aplicado:
        explicacao += f"; abaixo do piso de segurança, ajustado para {piso} kcal"

    return Meta(
        kcal=round(kcal),
        proteina_g=round(proteina),
        carboidrato_g=round(carboidrato),
        gordura_g=round(gordura),
        tmb=round(tmb),
        gasto_total=round(gasto),
        piso_aplicado=piso_aplicado,
        explicacao=explicacao,
    )

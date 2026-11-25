"""Consultas sobre as refeições gravadas: o que o usuário comeu hoje, totais etc.

Usado para montar o contexto que vai para a IA a cada mensagem, para a aba "Banco" do
simulador e, na Fase 5, para os resumos.
"""

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.banco.modelos import ItemRefeicao, Refeicao, Usuario
from app.tempo import DIAS_DA_SEMANA, agora, fuso_local, para_local

TIPOS = {
    "cafe_da_manha": "Café da manhã",
    "lanche_da_manha": "Lanche da manhã",
    "almoco": "Almoço",
    "lanche_da_tarde": "Lanche da tarde",
    "jantar": "Jantar",
    "ceia": "Ceia",
}
MACROS = ("kcal", "proteina", "carboidrato", "gordura", "fibra")


def refeicoes_do_dia(db: Session, usuario: Usuario, dia: date) -> list[Refeicao]:
    """Refeições de um dia no horário de Brasília (RN04)."""
    # Meia-noite em Brasília, convertida para UTC (o banco guarda tudo em UTC).
    inicio = datetime.combine(dia, datetime.min.time(), tzinfo=fuso_local()).astimezone(UTC)
    fim = inicio + timedelta(days=1)
    return list(
        db.scalars(
            select(Refeicao)
            .where(Refeicao.usuario_id == usuario.id)
            .where(Refeicao.data_hora >= inicio, Refeicao.data_hora < fim)
            .order_by(Refeicao.data_hora)
        )
    )


def totais(itens: list[ItemRefeicao]) -> dict[str, float]:
    return {campo: round(sum(getattr(i, campo) for i in itens), 1) for campo in MACROS}


def totais_do_dia(db: Session, usuario: Usuario, dia: date) -> dict[str, float]:
    return totais([i for r in refeicoes_do_dia(db, usuario, dia) for i in r.itens])


def hoje() -> date:
    return para_local(agora()).date()


def texto_contexto_minimo() -> str:
    """Contexto antes do aceite: só data e hora (nenhum dado pessoal)."""
    momento = para_local(agora())
    return "\n".join(
        [
            "<contexto>",
            f"Agora: {DIAS_DA_SEMANA[momento.weekday()]}, {momento:%d/%m/%Y %H:%M} (horário de Brasília).",
            "O usuário ainda NÃO aceitou o termo de uso.",
            "</contexto>",
        ]
    )


def _linhas_perfil(usuario: Usuario) -> list[str]:
    from app.nucleo import metas, perfil  # import aqui evita import circular

    dados = perfil.como_dict(usuario.perfil)
    preenchidos = {k: v for k, v in dados.items() if v is not None}
    linhas = [
        "Perfil: " + (", ".join(f"{k}={v}" for k, v in preenchidos.items()) if preenchidos else "vazio")
    ]
    meta = perfil.meta(usuario.perfil)
    if isinstance(meta, metas.Meta):
        linhas.append(
            f"Meta diária: {meta.kcal} kcal | proteína {meta.proteina_g} g | "
            f"carboidrato {meta.carboidrato_g} g | gordura {meta.gordura_g} g"
        )
    elif meta.motivo:
        linhas.append(f"Sem meta: {meta.motivo}")
    else:
        linhas.append("Sem meta ainda. Falta no perfil: " + ", ".join(meta.faltando))
    return linhas


def texto_contexto(db: Session, usuario: Usuario) -> str:
    """O "bilhete" que vai junto de cada mensagem do usuário para a IA.

    A IA não tem relógio nem acesso ao banco. Sem isto, ela não saberia que horas são
    (para deduzir "almoço") nem os números dos itens que pode corrigir.
    """
    momento = para_local(agora())
    linhas = [
        "<contexto>",
        f"Agora: {DIAS_DA_SEMANA[momento.weekday()]}, {momento:%d/%m/%Y %H:%M} (horário de Brasília).",
        *_linhas_perfil(usuario),
    ]
    refeicoes = refeicoes_do_dia(db, usuario, momento.date())
    if not refeicoes:
        linhas.append("Registros de hoje: nenhum.")
    else:
        linhas.append("Registros de hoje:")
        for refeicao in refeicoes:
            t = totais(refeicao.itens)
            linhas.append(
                f"- {TIPOS.get(refeicao.tipo, refeicao.tipo)} (refeicao_id {refeicao.id}) "
                f"às {para_local(refeicao.data_hora):%H:%M}: {t['kcal']:.0f} kcal"
            )
            for item in refeicao.itens:
                marca = " (estimado)" if item.estimado else ""
                linhas.append(
                    f"  - item_id {item.id}: {item.alimento_nome}, {item.gramas:.0f} g, "
                    f"{item.kcal:.0f} kcal{marca}"
                )
        t = totais([i for r in refeicoes for i in r.itens])
        linhas.append(
            f"Total de hoje: {t['kcal']:.0f} kcal | proteína {t['proteina']:.0f} g | "
            f"carboidrato {t['carboidrato']:.0f} g | gordura {t['gordura']:.0f} g"
        )
    linhas.append("</contexto>")
    return "\n".join(linhas)

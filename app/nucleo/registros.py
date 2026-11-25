"""Consultas sobre as refeições gravadas: o que o usuário comeu hoje, totais etc.

Usado para montar o contexto que vai para a IA a cada mensagem, para a aba "Banco" do
simulador e, na Fase 5, para os resumos.
"""

import re
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.banco.modelos import ItemRefeicao, Mensagem, Refeicao, Usuario
from app.tempo import DIAS_DA_SEMANA, agora, fuso_local, para_local

TIPOS = {
    "cafe_da_manha": "Café da manhã",
    "lanche_da_manha": "Lanche da manhã",
    "almoco": "Almoço",
    "lanche_da_tarde": "Lanche da tarde",
    "jantar": "Jantar",
    "ceia": "Ceia",
    # Bebida, café, fruta ou belisco fora das refeições: nem tudo é "refeição", e o bot
    # é para pessoas comuns, que nem sempre têm horários metódicos.
    "avulso": "Ao longo do dia",
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


# Palavras que indicam que o bot pediu um dado do perfil (para não pedir de novo em seguida).
_PEDIU_PERFIL = re.compile(
    r"idade|anos voc|quantos anos|peso|pesa|altura|mede|f[oó]rmula|homem ou mulher|mulher ou homem|"
    r"exercita|treina|atividade f[ií]sica|objetivo|perder, manter|seu nome|te chamar",
    re.IGNORECASE,
)


def pediu_perfil(texto: str) -> bool:
    """A resposta tem uma pergunta sobre o perfil? Olha só as frases que terminam em "?"."""
    perguntas = re.findall(r"[^.!?\n]*\?", texto or "")
    return any(_PEDIU_PERFIL.search(p) for p in perguntas)


def _linhas_perfil(db: Session, usuario: Usuario) -> list[str]:
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
        # Ritmo dos pedidos (para o usuário não cansar): o código decide QUANDO pode pedir,
        # a IA decide COMO. O prompt sozinho não segurava: o Haiku pedia 2 dados por vez e
        # repetia o mesmo pedido na mensagem seguinte (visto nos cenários da Fase 7).
        ultima = db.scalar(
            select(Mensagem.texto)
            .where(Mensagem.usuario_id == usuario.id, Mensagem.direcao == "saida")
            .order_by(Mensagem.id.desc())
            .limit(1)
        )
        if pediu_perfil(ultima or ""):
            linhas.append("Pedido de perfil: NÃO peça dado do perfil nesta resposta (você pediu na anterior).")
        else:
            linhas.append(
                f"Pedido de perfil: se a resposta não tiver outra pergunta, pode pedir só um dado: {meta.faltando[0]}."
            )
    return linhas


def _linhas_memoria(db: Session, usuario: Usuario) -> list[str]:
    """O que o bot aprendeu sobre a pessoa (camada 1): medidas, alimentos e hábitos."""
    from app.nucleo import memoria  # import aqui evita import circular

    linhas = []
    if usuario.medidas:
        linhas.append("Medidas do usuário: " + "; ".join(f"{m.unidade} = {m.gramas:g} g/ml" for m in usuario.medidas))
    if usuario.alimentos_proprios:
        linhas.append("Alimentos do usuário: " + "; ".join(
            f"{a.nome} (porção {a.porcao_g:g} g)" for a in usuario.alimentos_proprios))
    frequentes = memoria.itens_frequentes(db, usuario)
    if frequentes:
        linhas.append("Itens frequentes (30 dias): " + "; ".join(
            f"{f['alimento']}, {f['medida']} ({f['vezes']}x)" for f in frequentes))
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
        *_linhas_perfil(db, usuario),
        *_linhas_memoria(db, usuario),
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
        meta = _meta_do_usuario(usuario)
        if meta:
            # A conta do "quanto falta" sai pronta: sem isto, a IA subtraía de cabeça.
            falta = {k: meta[k] - t[k] for k in ("kcal", "proteina", "carboidrato", "gordura")}
            linhas.append(
                "Falta hoje para a meta (negativo = passou): "
                f"{falta['kcal']:.0f} kcal | proteína {falta['proteina']:.0f} g | "
                f"carboidrato {falta['carboidrato']:.0f} g | gordura {falta['gordura']:.0f} g"
            )
    linhas.append("</contexto>")
    return "\n".join(linhas)


# ---------- Resumos (RF21, RF22, RF23) ----------

MARGEM_META = 0.10  # dentro da meta = até 10% acima ou abaixo


def _meta_do_usuario(usuario: Usuario) -> dict | None:
    from app.nucleo import metas, perfil

    meta = perfil.meta(usuario.perfil)
    if not isinstance(meta, metas.Meta):
        return None
    return {"kcal": meta.kcal, "proteina": meta.proteina_g, "carboidrato": meta.carboidrato_g, "gordura": meta.gordura_g}


def resumo_dia(db: Session, usuario: Usuario, dia: date) -> dict:
    """Tudo o que foi comido num dia, comparado com a meta, e quanto falta."""
    refeicoes = refeicoes_do_dia(db, usuario, dia)
    total = totais([i for r in refeicoes for i in r.itens])
    resumo = {
        "data": f"{dia:%d/%m/%Y}",
        "dia_da_semana": DIAS_DA_SEMANA[dia.weekday()],
        "refeicoes": [
            {
                "refeicao_id": r.id,
                "tipo": TIPOS.get(r.tipo, r.tipo),
                "hora": f"{para_local(r.data_hora):%H:%M}",
                "kcal": totais(r.itens)["kcal"],
                "itens": [
                    {"item_id": i.id, "alimento": i.alimento_nome, "gramas": i.gramas,
                     "kcal": i.kcal, "estimado": i.estimado}
                    for i in r.itens
                ],
            }
            for r in refeicoes
        ],
        "total": total,
    }
    meta = _meta_do_usuario(usuario)
    resumo["meta"] = meta
    if meta:
        # Quanto falta (RF22): negativo quer dizer que passou da meta.
        resumo["falta"] = {campo: round(meta[campo] - total[campo], 1) for campo in meta}
        resumo["percentual_kcal"] = round(100 * total["kcal"] / meta["kcal"])
    return resumo


def resumo_semana(db: Session, usuario: Usuario, ultimo_dia: date) -> dict:
    """Os 7 dias até `ultimo_dia`: total de cada dia, média e situação perante a meta."""
    meta = _meta_do_usuario(usuario)
    dias = []
    for deslocamento in range(6, -1, -1):
        dia = ultimo_dia - timedelta(days=deslocamento)
        total = totais_do_dia(db, usuario, dia)
        registro = {"data": f"{dia:%d/%m}", "dia_da_semana": DIAS_DA_SEMANA[dia.weekday()],
                    "kcal": total["kcal"], "proteina": total["proteina"]}
        if meta and total["kcal"] > 0:
            diferenca = (total["kcal"] - meta["kcal"]) / meta["kcal"]
            registro["situacao"] = (
                "dentro" if abs(diferenca) <= MARGEM_META else ("acima" if diferenca > 0 else "abaixo")
            )
        dias.append(registro)

    com_registro = [d for d in dias if d["kcal"] > 0]
    resumo = {
        "periodo": f"{dias[0]['data']} a {dias[-1]['data']}",
        "dias": dias,
        "dias_com_registro": len(com_registro),
        "media_kcal": round(sum(d["kcal"] for d in com_registro) / len(com_registro)) if com_registro else 0,
        "media_proteina": round(sum(d["proteina"] for d in com_registro) / len(com_registro)) if com_registro else 0,
        "meta": meta,
        "observacao": "A média considera só os dias com algum registro.",
    }
    if meta:
        for situacao in ("dentro", "acima", "abaixo"):
            resumo[f"dias_{situacao}_da_meta"] = sum(1 for d in dias if d.get("situacao") == situacao)
    return resumo

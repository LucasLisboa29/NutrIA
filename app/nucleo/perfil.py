"""Perfil do usuário, aceite dos termos (LGPD) e histórico de peso.

Sobre a LGPD (Lei Geral de Proteção de Dados): informações de saúde, como peso e o que
a pessoa come, são "dados pessoais sensíveis". Para guardá-las, a lei exige um
consentimento claro e específico. Por isso, antes do aceite, o bot não grava refeição,
peso nem perfil (RN07). O aceite fica registrado com data e versão do termo.
"""

from sqlalchemy.orm import Session

from app.banco.modelos import Consentimento, HistoricoPeso, Perfil, Usuario
from app.config import carregar_yaml
from app.nucleo import metas
from app.tempo import agora, como_utc

SEXOS = ("feminino", "masculino")
NIVEIS = ("sedentario", "leve", "moderado", "intenso", "muito_intenso")
OBJETIVOS = ("perder", "manter", "ganhar")


class DadoInvalido(ValueError):
    pass


# ---------- Aceite (LGPD) ----------


def versao_termo() -> str:
    return str(carregar_yaml("onboarding.yaml")["versao_termo"])


def tem_aceite(usuario: Usuario) -> bool:
    """Aceitou a versão atual do termo? Se o termo mudar de versão, pede de novo."""
    return any(c.versao_termo == versao_termo() for c in usuario.consentimentos)


def registrar_aceite(db: Session, usuario: Usuario, canal: str) -> Consentimento:
    consentimento = Consentimento(usuario_id=usuario.id, versao_termo=versao_termo(), canal=canal)
    usuario.consentimentos.append(consentimento)
    db.flush()
    return consentimento


# ---------- Perfil ----------


def obter(db: Session, usuario: Usuario) -> Perfil:
    if usuario.perfil is None:
        usuario.perfil = Perfil(usuario_id=usuario.id)
        db.flush()
    return usuario.perfil


def idade_atual(perfil: Perfil) -> int | None:
    """A idade informada + os anos que passaram desde então."""
    if perfil.idade is None:
        return None
    if perfil.idade_informada_em is None:
        return perfil.idade
    anos = (agora() - como_utc(perfil.idade_informada_em)).days // 365
    return perfil.idade + anos


def meta(perfil: Perfil | None) -> metas.Meta | metas.SemMeta:
    if perfil is None:
        return metas.SemMeta(faltando=list(metas.CAMPOS_NECESSARIOS))
    return metas.calcular(
        perfil.sexo, idade_atual(perfil), perfil.peso_kg, perfil.altura_cm,
        perfil.nivel_atividade, perfil.objetivo,
    )


def atualizar(db: Session, usuario: Usuario, dados: dict) -> list[str]:
    """Atualiza só os campos informados (aceita dados parciais, RF19). Devolve o que mudou."""
    perfil = obter(db, usuario)
    mudou = []

    if dados.get("nome"):
        perfil.nome = str(dados["nome"]).strip()[:60]
        mudou.append("nome")
    if dados.get("sexo"):
        if dados["sexo"] not in SEXOS:
            raise DadoInvalido(f"sexo deve ser um de {SEXOS}.")
        perfil.sexo = dados["sexo"]
        mudou.append("sexo")
    if dados.get("idade") is not None:
        idade = int(dados["idade"])
        if not 10 <= idade <= 110:
            raise DadoInvalido("idade fora do intervalo esperado (10 a 110 anos).")
        perfil.idade, perfil.idade_informada_em = idade, agora()
        mudou.append("idade")
    if dados.get("altura_cm") is not None:
        altura = float(dados["altura_cm"])
        if altura < 3:  # veio em metros (1,65): converte
            altura *= 100
        if not 100 <= altura <= 250:
            raise DadoInvalido("altura fora do intervalo esperado (100 a 250 cm).")
        perfil.altura_cm = round(altura, 1)
        mudou.append("altura_cm")
    if dados.get("peso_kg") is not None:
        peso = float(dados["peso_kg"])
        if not 25 <= peso <= 350:
            raise DadoInvalido("peso fora do intervalo esperado (25 a 350 kg).")
        perfil.peso_kg = round(peso, 1)
        usuario.pesos.append(HistoricoPeso(usuario_id=usuario.id, peso_kg=perfil.peso_kg))  # RF20
        mudou.append("peso_kg")
    if dados.get("nivel_atividade"):
        if dados["nivel_atividade"] not in NIVEIS:
            raise DadoInvalido(f"nivel_atividade deve ser um de {NIVEIS}.")
        perfil.nivel_atividade = dados["nivel_atividade"]
        mudou.append("nivel_atividade")
    if dados.get("objetivo"):
        if dados["objetivo"] not in OBJETIVOS:
            raise DadoInvalido(f"objetivo deve ser um de {OBJETIVOS}.")
        perfil.objetivo = dados["objetivo"]
        mudou.append("objetivo")

    perfil.atualizado_em = agora()
    db.flush()
    return mudou


def como_dict(perfil: Perfil | None) -> dict:
    if perfil is None:
        return {}
    return {
        "nome": perfil.nome,
        "sexo": perfil.sexo,
        "idade": idade_atual(perfil),
        "peso_kg": perfil.peso_kg,
        "altura_cm": perfil.altura_cm,
        "nivel_atividade": perfil.nivel_atividade,
        "objetivo": perfil.objetivo,
    }

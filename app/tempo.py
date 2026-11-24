"""Funções de data e hora usadas no app todo.

Regra: o banco guarda tudo em UTC (horário universal). A conversão para o horário de
Brasília acontece só na hora de mostrar ou de calcular "hoje" (RN04, Fase 5).
"""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from app.config import settings

DIAS_DA_SEMANA = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]


def fuso_local() -> ZoneInfo:
    return ZoneInfo(settings.timezone)


def para_local(momento: datetime) -> datetime:
    """UTC do banco -> horário de Brasília, para mostrar e para saber o que é "hoje"."""
    return como_utc(momento).astimezone(fuso_local())


def agora() -> datetime:
    """Data e hora atuais em UTC, com fuso marcado."""
    return datetime.now(UTC)


def como_utc(momento: datetime) -> datetime:
    """O SQLite devolve datas sem fuso. Esta função marca de volta como UTC."""
    if momento.tzinfo is None:
        return momento.replace(tzinfo=UTC)
    return momento.astimezone(UTC)

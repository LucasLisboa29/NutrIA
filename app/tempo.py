"""Funções de data e hora usadas no app todo.

Regra: o banco guarda tudo em UTC (horário universal). A conversão para o horário de
Brasília acontece só na hora de mostrar ou de calcular "hoje" (RN04, Fase 5).
"""

from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from app.config import settings

DIAS_DA_SEMANA = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]

# Relógio simulado (RF33): uma diferença em relação ao relógio real. Fica numa
# ContextVar, uma variável que vale só para a requisição atual, para que um teste
# "fingindo" ser outro dia não afete as mensagens de outros usuários ao mesmo tempo.
_deslocamento: ContextVar[timedelta] = ContextVar("deslocamento_do_relogio", default=timedelta(0))


@contextmanager
def relogio_simulado(momento_local: datetime | None):
    """Durante o `with`, `agora()` finge que é `momento_local` (horário de Brasília)."""
    if momento_local is None:
        yield
        return
    if momento_local.tzinfo is None:
        momento_local = momento_local.replace(tzinfo=fuso_local())
    token = _deslocamento.set(momento_local.astimezone(UTC) - datetime.now(UTC))
    try:
        yield
    finally:
        _deslocamento.reset(token)


def fuso_local() -> ZoneInfo:
    return ZoneInfo(settings.timezone)


def para_local(momento: datetime) -> datetime:
    """UTC do banco -> horário de Brasília, para mostrar e para saber o que é "hoje"."""
    return como_utc(momento).astimezone(fuso_local())


def agora() -> datetime:
    """Data e hora atuais em UTC, com fuso marcado (ou a simulada, no simulador)."""
    return datetime.now(UTC) + _deslocamento.get()


def como_utc(momento: datetime) -> datetime:
    """O SQLite devolve datas sem fuso. Esta função marca de volta como UTC."""
    if momento.tzinfo is None:
        return momento.replace(tzinfo=UTC)
    return momento.astimezone(UTC)

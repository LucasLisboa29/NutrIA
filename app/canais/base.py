"""Camada de canal: o formato comum das mensagens.

O núcleo do NutrIA só conhece `MensagemEntrada` e `MensagemSaida`. Cada canal (o
simulador agora, o WhatsApp na Fase 8) tem um *adaptador* que converte o formato dele
para esses dois tipos e de volta. Por isso, trocar o simulador pelo WhatsApp não muda
nada no núcleo: muda só o adaptador.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol

from app.tempo import agora


class TipoMidia(StrEnum):
    IMAGEM = "imagem"
    AUDIO = "audio"


@dataclass
class Midia:
    """Um arquivo anexado. Como no WhatsApp, é no máximo um por mensagem."""

    tipo: TipoMidia
    conteudo: bytes
    mime: str  # ex.: "image/jpeg", "audio/ogg"
    nome_arquivo: str = ""


@dataclass
class MensagemEntrada:
    """O que o usuário mandou, já num formato que não depende do canal."""

    canal: str  # "simulador" ou "whatsapp"
    remetente: str  # telefone do usuário, só dígitos (ex.: "5534999990000")
    texto: str = ""  # texto da mensagem ou legenda da foto
    midia: Midia | None = None
    horario: datetime = field(default_factory=agora)


@dataclass
class MensagemSaida:
    """O que o bot vai responder."""

    destinatario: str
    texto: str
    horario: datetime = field(default_factory=agora)


class Adaptador(Protocol):
    """O que todo canal precisa oferecer ao núcleo."""

    canal: str

    def responder(self, saida: MensagemSaida) -> Any:
        """Entrega a resposta pelo canal.

        No simulador, a resposta volta no corpo da requisição HTTP. No WhatsApp, vai
        ser uma chamada à API da Meta.
        """
        ...

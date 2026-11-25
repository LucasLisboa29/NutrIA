"""Interface `Transcritor`: transforma áudio em texto (RF03).

Mesma ideia do `ProvedorIA`: o núcleo só conhece esta interface. Hoje o adaptador é a
Groq (Whisper); trocar por outro serviço é escrever outro adaptador.

Depois de transcrito, o áudio segue exatamente o mesmo caminho de uma mensagem de
texto. Assim o bot não precisa de uma "inteligência" separada para áudio.
"""

from dataclasses import dataclass
from typing import Protocol


@dataclass
class Transcricao:
    texto: str
    duracao_s: float  # duração do áudio, usada para calcular o custo
    modelo: str


class ErroTranscricao(RuntimeError):
    pass


class Transcritor(Protocol):
    def transcrever(self, conteudo: bytes, mime: str, nome_arquivo: str) -> Transcricao: ...

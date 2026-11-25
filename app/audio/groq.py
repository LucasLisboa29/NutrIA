"""Adaptador de transcrição da Groq (modelo Whisper), com o SDK oficial `groq`.

O Whisper aceita direto os formatos que usamos: webm/opus (gravação do navegador) e
ogg/opus (áudio do WhatsApp). Por isso não precisamos converter nada.
"""

import mimetypes

import groq

from app.audio.base import ErroTranscricao, Transcricao
from app.config import carregar_yaml

# Palavras que costumam aparecer: ajudam o Whisper a acertar a grafia de comidas.
VOCABULARIO = (
    "Conversa sobre alimentação no Brasil: arroz, feijão, farofa, cuscuz, tapioca, "
    "pão de queijo, açaí, coxinha, pastel, strogonoff, PF, marmita, whey, iogurte."
)


class TranscritorGroq:
    def __init__(self, api_key: str):
        self.cliente = groq.Groq(api_key=api_key, max_retries=2, timeout=30.0)

    def transcrever(self, conteudo: bytes, mime: str, nome_arquivo: str) -> Transcricao:
        modelo = carregar_yaml("modelos.yaml")["transcricao"]["modelo"]
        nome = nome_arquivo or f"audio{mimetypes.guess_extension(mime.split(';')[0]) or '.webm'}"
        try:
            resposta = self.cliente.audio.transcriptions.create(
                file=(nome, conteudo),
                model=modelo,
                language="pt",  # avisar o idioma deixa mais rápido e mais preciso
                prompt=VOCABULARIO,
                response_format="verbose_json",  # inclui a duração do áudio
                temperature=0.0,
            )
        except groq.AuthenticationError as erro:
            raise ErroTranscricao("Chave da Groq inválida (confira GROQ_API_KEY no .env).") from erro
        except groq.APIStatusError as erro:
            raise ErroTranscricao(f"A Groq respondeu {erro.status_code}: {erro.message}") from erro
        except groq.APIConnectionError as erro:
            raise ErroTranscricao("Sem conexão com a Groq.") from erro

        duracao = float(getattr(resposta, "duration", 0) or 0)
        return Transcricao(texto=(resposta.text or "").strip(), duracao_s=duracao, modelo=modelo)

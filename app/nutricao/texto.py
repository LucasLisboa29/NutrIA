"""Limpeza de texto para comparar nomes de alimentos e de medidas.

O usuário escreve "Pão Francês", "pao frances" ou "pães franceses", e tudo isso precisa
virar a mesma coisa. Por isso, antes de comparar, todo texto passa por aqui.
"""

import re
import unicodedata

# Palavras que terminam em "s" mas não estão no plural.
_SEM_PLURAL = {"pires", "lapis", "gas", "mais", "tres", "arroz", "cuscuz", "atras", "xis"}


def sem_acento(texto: str) -> str:
    """'Pão Francês' -> 'pao frances' (minúsculo e sem acentos)."""
    decomposto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in decomposto if not unicodedata.combining(c)).lower().strip()


def normalizar(texto: str) -> str:
    """Sem acento, minúsculo, sem pontuação e com espaços simples.

    'Arroz, tipo 1, cozido' -> 'arroz tipo 1 cozido'
    """
    texto = sem_acento(texto)
    texto = re.sub(r"[^a-z0-9]+", " ", texto)
    return " ".join(texto.split())


def singularizar_palavra(palavra: str) -> str:
    """Regras simples do português, suficientes para medidas e alimentos comuns."""
    if palavra in _SEM_PLURAL or len(palavra) <= 3:
        return palavra
    for fim, troca in (("oes", "ao"), ("aes", "ao"), ("eis", "el"), ("ns", "m")):
        if palavra.endswith(fim):
            return palavra[: -len(fim)] + troca
    if palavra.endswith(("res", "zes")):
        return palavra[:-2]  # colheres -> colher
    if palavra.endswith("s"):
        return palavra[:-1]
    return palavra


def singularizar(texto: str) -> str:
    """'colheres de sopa' -> 'colher de sopa'; 'paes franceses' -> 'pao frances'."""
    return " ".join(singularizar_palavra(p) for p in texto.split())

"""Configurações do NutrIA.

Lê as variáveis do arquivo `.env` (que fica fora do Git) e dos arquivos em `config/`.
Qualquer parte do app importa `settings` daqui, em vez de ler o .env sozinha.
"""

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict

# Pasta raiz do projeto (NutrIA/), calculada a partir deste arquivo.
RAIZ = Path(__file__).resolve().parent.parent
PASTA_CONFIG = RAIZ / "config"


class Settings(BaseSettings):
    """Variáveis de ambiente. O nome do campo é o nome da variável no .env."""

    model_config = SettingsConfigDict(
        env_file=RAIZ / ".env",
        env_file_encoding="utf-8",
        extra="ignore",  # ignora variáveis do .env que não estão listadas aqui
    )

    anthropic_api_key: str = ""  # necessária a partir da Fase 3
    groq_api_key: str = ""  # necessária a partir da Fase 6
    database_url: str = f"sqlite:///{RAIZ / 'nutria.db'}"
    timezone: str = "America/Sao_Paulo"
    # Onde ficam as fotos e áudios recebidos (fora do Git, ver .gitignore).
    pasta_uploads: Path = RAIZ / "uploads"
    # Consultar o Open Food Facts (internet) para produtos de marca. Os testes desligam.
    openfoodfacts_ativo: bool = True


@lru_cache
def get_settings() -> Settings:
    """Devolve sempre a mesma instância (o .env é lido uma vez só)."""
    return Settings()


settings = get_settings()


def carregar_yaml(nome: str) -> dict:
    """Lê um arquivo de `config/`, por exemplo carregar_yaml("modelos.yaml").

    É lido a cada chamada, de propósito: assim dá para editar o arquivo com o servidor
    rodando e ver o efeito no próximo teste (RF35).
    """
    with open(PASTA_CONFIG / nome, encoding="utf-8") as arquivo:
        return yaml.safe_load(arquivo) or {}

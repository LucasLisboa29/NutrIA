"""Mede tempo, tokens e custo de cada etapa do processamento de uma mensagem.

"Velocidade importa" é um princípio do projeto, e não dá para otimizar o que não se
mede. Cada mensagem gera um relatório que aparece no painel de depuração (RF30).
"""

import time
from contextlib import contextmanager
from dataclasses import dataclass, field

from app.ia.base import Uso


@dataclass
class Telemetria:
    etapas: list[dict] = field(default_factory=list)
    inicio: float = field(default_factory=time.perf_counter)

    @contextmanager
    def etapa(self, nome: str, **dados):
        """Uso: `with telemetria.etapa("ia", modelo=...) as registro: ...`"""
        registro = {"etapa": nome, **dados}
        comeco = time.perf_counter()
        try:
            yield registro
        finally:
            registro["ms"] = round((time.perf_counter() - comeco) * 1000, 1)
            self.etapas.append(registro)

    def resumo(self) -> dict:
        chamadas_ia = [e for e in self.etapas if e["etapa"] == "ia"]
        tokens = Uso()
        for e in chamadas_ia:
            uso = e.get("uso") or {}
            tokens.entrada += uso.get("entrada", 0)
            tokens.saida += uso.get("saida", 0)
            tokens.cache_leitura += uso.get("cache_leitura", 0)
            tokens.cache_escrita += uso.get("cache_escrita", 0)
        return {
            "tempo_total_ms": round((time.perf_counter() - self.inicio) * 1000, 1),
            "tempo_ia_ms": round(sum(e["ms"] for e in chamadas_ia), 1),
            "chamadas_ia": len(chamadas_ia),
            "tokens": tokens.__dict__,
            "custo_usd": round(sum(e.get("custo_usd", 0) for e in chamadas_ia), 6),
            "etapas": self.etapas,
        }

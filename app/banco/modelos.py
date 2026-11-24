"""Tabelas do banco de dados.

Cada classe aqui vira uma tabela. Elas vão sendo adicionadas fase a fase:
- Fase 1: usuarios, mensagens
- Fase 2: alimentos, porcoes
- Fase 3: refeicoes, itens_refeicao
- Fase 4: perfis, historico_peso
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.banco.sessao import Base
from app.tempo import agora


class Usuario(Base):
    """Uma pessoa que conversa com o bot, identificada pelo telefone."""

    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    telefone: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)

    # "cascade" faz o SQLAlchemy apagar as mensagens junto com o usuário.
    mensagens: Mapped[list["Mensagem"]] = relationship(
        back_populates="usuario",
        cascade="all, delete-orphan",
        order_by="Mensagem.id",
    )


class Mensagem(Base):
    """Uma mensagem da conversa, nos dois sentidos."""

    __tablename__ = "mensagens"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), index=True
    )
    direcao: Mapped[str] = mapped_column(String(8))  # "entrada" (usuário → bot) ou "saida"
    canal: Mapped[str] = mapped_column(String(16))
    texto: Mapped[str] = mapped_column(Text, default="")
    tipo_midia: Mapped[str | None] = mapped_column(String(16))  # "imagem", "audio" ou nada
    mime_midia: Mapped[str | None] = mapped_column(String(64))
    caminho_midia: Mapped[str | None] = mapped_column(String(255))  # relativo a uploads/
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)

    usuario: Mapped[Usuario] = relationship(back_populates="mensagens")

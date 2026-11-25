"""Tabelas do banco de dados.

Cada classe aqui vira uma tabela. Elas vão sendo adicionadas fase a fase:
- Fase 1: usuarios, mensagens
- Fase 2: alimentos, porcoes
- Fase 3: refeicoes, itens_refeicao
- Fase 4: perfis, historico_peso

Sobre apagar: o SQLite não aplica "ON DELETE CASCADE" sozinho, então quem apaga em
cascata é o SQLAlchemy (o `cascade="all, delete-orphan"` nos relacionamentos).
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
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
    refeicoes: Mapped[list["Refeicao"]] = relationship(
        back_populates="usuario",
        cascade="all, delete-orphan",
        order_by="Refeicao.data_hora",
    )
    perfil: Mapped["Perfil | None"] = relationship(
        back_populates="usuario", cascade="all, delete-orphan", uselist=False
    )
    pesos: Mapped[list["HistoricoPeso"]] = relationship(
        cascade="all, delete-orphan", order_by="HistoricoPeso.registrado_em"
    )
    consentimentos: Mapped[list["Consentimento"]] = relationship(
        cascade="all, delete-orphan", order_by="Consentimento.aceito_em"
    )
    medidas: Mapped[list["MedidaUsuario"]] = relationship(cascade="all, delete-orphan")
    alimentos_proprios: Mapped[list["AlimentoUsuario"]] = relationship(cascade="all, delete-orphan")


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


class Alimento(Base):
    """Um alimento da base nutricional. Todos os valores são por 100 g.

    `origem` diz de onde veio o número:
    - "taco": Tabela TACO 4ª edição (NEPA/Unicamp), a fonte principal;
    - "derivado": calculado a partir de um alimento da TACO (ex.: macarrão cozido);
    - "manual": valor de referência digitado por nós, para o que a TACO não tem.
    """

    __tablename__ = "alimentos"

    id: Mapped[int] = mapped_column(primary_key=True)  # na TACO, é o número oficial
    nome: Mapped[str] = mapped_column(String(120), unique=True)
    nome_busca: Mapped[str] = mapped_column(String(120), index=True)  # sem acento, minúsculo
    categoria: Mapped[str] = mapped_column(String(60))
    origem: Mapped[str] = mapped_column(String(16), default="taco")
    kcal: Mapped[float | None] = mapped_column(Float)
    proteina: Mapped[float | None] = mapped_column(Float)  # g
    carboidrato: Mapped[float | None] = mapped_column(Float)  # g
    gordura: Mapped[float | None] = mapped_column(Float)  # g (lipídeos)
    fibra: Mapped[float | None] = mapped_column(Float)  # g
    sodio: Mapped[float | None] = mapped_column(Float)  # mg


class Refeicao(Base):
    """Uma refeição: café da manhã, almoço etc., com a data e hora em que foi comida."""

    __tablename__ = "refeicoes"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), index=True
    )
    # cafe_da_manha, lanche_da_manha, almoco, lanche_da_tarde, jantar ou ceia
    tipo: Mapped[str] = mapped_column(String(20))
    data_hora: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)  # UTC
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)

    usuario: Mapped[Usuario] = relationship(back_populates="refeicoes")
    itens: Mapped[list["ItemRefeicao"]] = relationship(
        back_populates="refeicao",
        cascade="all, delete-orphan",
        order_by="ItemRefeicao.id",
    )


class ItemRefeicao(Base):
    """Um alimento dentro de uma refeição, com a quantidade e os valores já calculados.

    Os valores ficam gravados (e não recalculados na hora de mostrar) para que uma
    mudança futura na base TACO não altere o que o usuário já comeu.
    """

    __tablename__ = "itens_refeicao"

    id: Mapped[int] = mapped_column(primary_key=True)
    refeicao_id: Mapped[int] = mapped_column(
        ForeignKey("refeicoes.id", ondelete="CASCADE"), index=True
    )
    descricao: Mapped[str] = mapped_column(String(120))  # como o usuário falou ("um bife")
    alimento_id: Mapped[int | None] = mapped_column(ForeignKey("alimentos.id"))  # None = estimativa da IA
    alimento_nome: Mapped[str] = mapped_column(String(120))
    quantidade: Mapped[float | None] = mapped_column(Float)
    unidade: Mapped[str | None] = mapped_column(String(40))
    tamanho: Mapped[str | None] = mapped_column(String(20))
    gramas: Mapped[float] = mapped_column(Float)
    kcal: Mapped[float] = mapped_column(Float)
    proteina: Mapped[float] = mapped_column(Float)
    carboidrato: Mapped[float] = mapped_column(Float)
    gordura: Mapped[float] = mapped_column(Float)
    fibra: Mapped[float] = mapped_column(Float)
    estimado: Mapped[bool] = mapped_column(Boolean, default=False)  # RN02
    confianca: Mapped[str] = mapped_column(String(8))  # alta, media ou baixa
    origem: Mapped[str] = mapped_column(String(16))  # taco, derivado, manual ou ia (RF14)
    explicacao: Mapped[str] = mapped_column(Text, default="")
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=agora, onupdate=agora
    )

    refeicao: Mapped[Refeicao] = relationship(back_populates="itens")


class Consentimento(Base):
    """Registro do aceite dos termos de uso (LGPD, RN07).

    Fica numa tabela própria, com data e versão do termo, para provar *quando* e *com
    qual texto* a pessoa concordou. Se o termo mudar, a versão muda e dá para pedir de novo.
    """

    __tablename__ = "consentimentos"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), index=True)
    versao_termo: Mapped[str] = mapped_column(String(20))
    canal: Mapped[str] = mapped_column(String(16))
    aceito_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)


class Perfil(Base):
    """Dados para calcular a meta (RF17). Tudo opcional: a coleta é aos poucos, conversando."""

    __tablename__ = "perfis"

    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), primary_key=True)
    nome: Mapped[str | None] = mapped_column(String(60))
    sexo: Mapped[str | None] = mapped_column(String(10))  # "feminino" ou "masculino" (para a fórmula)
    idade: Mapped[int | None] = mapped_column(Integer)
    idade_informada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    peso_kg: Mapped[float | None] = mapped_column(Float)  # o mais recente (histórico em historico_peso)
    altura_cm: Mapped[float | None] = mapped_column(Float)
    nivel_atividade: Mapped[str | None] = mapped_column(String(16))
    objetivo: Mapped[str | None] = mapped_column(String(10))  # perder, manter ou ganhar
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora, onupdate=agora)

    usuario: Mapped[Usuario] = relationship(back_populates="perfil")


class HistoricoPeso(Base):
    """Cada peso informado, para mostrar a evolução (RF20)."""

    __tablename__ = "historico_peso"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), index=True)
    peso_kg: Mapped[float] = mapped_column(Float)
    registrado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)


# ---------- Etapa 2 das fotos: base própria e aprendizado ----------


class MedidaUsuario(Base):
    """Uma medida que o usuário ensinou: "minha caneca tem 350 ml" (camada 1 da base).

    Vale só para ele e tem prioridade sobre as medidas genéricas de `porcoes.yaml`.
    """

    __tablename__ = "medidas_usuario"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), index=True)
    unidade: Mapped[str] = mapped_column(String(40))  # já normalizada: "caneca", "pote do trabalho"
    gramas: Mapped[float] = mapped_column(Float)  # ou ml (1 ml ~ 1 g)
    descricao: Mapped[str] = mapped_column(String(120), default="")
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)


class AlimentoUsuario(Base):
    """Um alimento que o usuário ensinou (rótulo de um produto, receita dele).

    Valores por 100 g, como na TACO. `porcao_g` é a porção que ele costuma comer.
    """

    __tablename__ = "alimentos_usuario"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), index=True)
    nome: Mapped[str] = mapped_column(String(120))
    nome_busca: Mapped[str] = mapped_column(String(120), index=True)
    porcao_g: Mapped[float] = mapped_column(Float)
    kcal: Mapped[float] = mapped_column(Float)
    proteina: Mapped[float] = mapped_column(Float)
    carboidrato: Mapped[float] = mapped_column(Float)
    gordura: Mapped[float] = mapped_column(Float)
    fibra: Mapped[float] = mapped_column(Float, default=0)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)


class RevisaoAlimento(Base):
    """Fila de revisão: alimentos que a base não tinha e a IA precisou estimar.

    Cada linha é uma tarefa de cadastro para a Base NutrIA; `vezes` diz o que é mais
    pedido. Não guarda QUEM pediu (é anônima): para cadastrar um alimento isso não
    importa, e assim apagar os dados de um usuário (LGPD) não mexe aqui.
    """

    __tablename__ = "revisao_alimentos"

    id: Mapped[int] = mapped_column(primary_key=True)
    termo: Mapped[str] = mapped_column(String(120), unique=True)  # normalizado
    exemplo: Mapped[str] = mapped_column(String(120))  # como a IA escreveu
    vezes: Mapped[int] = mapped_column(Integer, default=1)
    ultima_estimativa: Mapped[str] = mapped_column(Text, default="")  # JSON por porção
    status: Mapped[str] = mapped_column(String(12), default="pendente")  # pendente, cadastrado, ignorado
    primeiro_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)
    ultimo_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)


class ProdutoOFF(Base):
    """Produto de marca vindo do Open Food Facts (cache local). Valores por 100 g.

    Dados © Open Food Facts contributors, licença ODbL (precisa citar a fonte).
    """

    __tablename__ = "produtos_off"

    codigo: Mapped[str] = mapped_column(String(32), primary_key=True)  # código de barras
    nome: Mapped[str] = mapped_column(String(160))
    marca: Mapped[str] = mapped_column(String(120), default="")
    quantidade_g: Mapped[float | None] = mapped_column(Float)  # conteúdo da embalagem (473 ml)
    kcal: Mapped[float] = mapped_column(Float)
    proteina: Mapped[float] = mapped_column(Float)
    carboidrato: Mapped[float] = mapped_column(Float)
    gordura: Mapped[float] = mapped_column(Float)
    fibra: Mapped[float] = mapped_column(Float, default=0)
    do_brasil: Mapped[bool] = mapped_column(Boolean, default=False)  # vendido no Brasil?
    buscado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)


class BuscaOFF(Base):
    """Cache das buscas no Open Food Facts: termo -> produto (ou nada encontrado)."""

    __tablename__ = "buscas_off"

    termo: Mapped[str] = mapped_column(String(120), primary_key=True)
    codigo: Mapped[str | None] = mapped_column(String(32))  # None = procurou e não achou
    buscado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)

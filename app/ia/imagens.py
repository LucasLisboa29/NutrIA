"""Preparo de fotos antes de mandar para a IA de visão (Fase 6).

Uma foto de celular tem ~12 megapixels (4032 × 3024). A IA cobra a imagem em tokens,
proporcional à área (~1 token a cada 750 pixels), e acima de ~1568 px no lado maior
ela já reduz a imagem por conta própria. Mandar a foto inteira só deixa o pedido mais
lento e caro, sem ganhar qualidade. Por isso reduzimos antes, aqui.
"""

import io
from dataclasses import dataclass

from PIL import Image, ImageOps

LADO_MAXIMO = 1568  # pixels no lado maior
QUALIDADE_JPEG = 85


@dataclass
class ImagemPreparada:
    dados: bytes
    mime: str
    largura: int
    altura: int
    tamanho_original: str  # para o painel de depuração, ex.: "4032×3024, 2,1 MB"
    tamanho_final: str


def preparar(conteudo: bytes) -> ImagemPreparada:
    with Image.open(io.BytesIO(conteudo)) as original:
        original_desc = f"{original.width}×{original.height}, {_kb(len(conteudo))}"
        # Fotos de celular guardam a rotação num campo EXIF; aplica para não ir "deitada".
        imagem = ImageOps.exif_transpose(original).convert("RGB")
        imagem.thumbnail((LADO_MAXIMO, LADO_MAXIMO))  # reduz mantendo a proporção
        saida = io.BytesIO()
        imagem.save(saida, format="JPEG", quality=QUALIDADE_JPEG, optimize=True)

    dados = saida.getvalue()
    return ImagemPreparada(
        dados=dados,
        mime="image/jpeg",
        largura=imagem.width,
        altura=imagem.height,
        tamanho_original=original_desc,
        tamanho_final=f"{imagem.width}×{imagem.height}, {_kb(len(dados))}",
    )


def tokens_estimados(largura: int, altura: int) -> int:
    return round(largura * altura / 750)


def _kb(tamanho: int) -> str:
    return f"{tamanho / 1024 / 1024:.1f} MB" if tamanho > 1024 * 1024 else f"{tamanho / 1024:.0f} KB"

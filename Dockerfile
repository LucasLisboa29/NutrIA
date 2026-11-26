# Imagem do NutrIA para rodar num servidor (Railway, Render, Fly...).
# Um Dockerfile descreve, passo a passo, o "computador" onde o app vai rodar: assim ele
# funciona igual em qualquer provedor, sem depender do que está instalado lá.

FROM python:3.12-slim

# Python sem buffer (logs aparecem na hora) e sem criar arquivos .pyc
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    # Banco e mídias numa pasta só (/data). No provedor, monte um VOLUME nessa pasta:
    # sem volume, tudo some a cada nova versão publicada.
    DATABASE_URL=sqlite:////data/nutria.db \
    PASTA_UPLOADS=/data/uploads

WORKDIR /app

# Dependências primeiro: o Docker reaproveita esta etapa enquanto o requirements não mudar
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app
COPY config ./config
COPY dados ./dados
COPY simulador ./simulador

RUN mkdir -p /data/uploads

# O provedor diz em qual porta escutar pela variável PORT. Um processo só (--workers 1):
# o pedido de "apagar meus dados" fica na memória entre duas mensagens.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1 --proxy-headers --forwarded-allow-ips='*'"]

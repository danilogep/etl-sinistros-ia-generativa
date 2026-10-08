FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MPLBACKEND=Agg

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src

# A chave vem do ambiente (-e GOOGLE_API_KEY=... ou env_file), nunca da imagem.
ENTRYPOINT ["python", "-m"]
CMD ["src.pipeline"]

# C:\Users\Alessandro\Downloads\gpt-de-favela-api\Dockerfile

# --- Estágio 1: Build (Construção) ---
FROM python:3.10-slim-buster as builder

WORKDIR /app

COPY --chown=root:root requirements.txt ./

RUN set -ex && \
    pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# --- Estágio 2: Runtime (Execução) ---
FROM python:3.10-slim-buster

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
COPY --from=builder /usr/local/bin/uvicorn /usr/local/bin/uvicorn

COPY . .

EXPOSE 8080 # Exponha a porta 8080, que é a padrão do Cloud Run

# Comando para iniciar a aplicação Uvicorn.
# Uvicorn vai usar a variável de ambiente $PORT automaticamente se ela existir.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0"] # LINHA ALTERADA: Removemos a porta explícita aqui.
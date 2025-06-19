# Estágio 1: Construir as dependências
FROM python:3.10-slim-buster as builder

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir --user -r requirements.txt

# Estágio 2: Imagem final de produção
FROM python:3.10-slim-buster

WORKDIR /app

# Copia as dependências instaladas do estágio anterior
COPY --from=builder /root/.local /root/.local

# Copia o código da aplicação
COPY . .

# Garante que o diretório de pacotes Python esteja no PATH
ENV PATH="/root/.local/bin:${PATH}"

# Expõe a porta que o Cloud Run usará
EXPOSE 8080

# Comando para iniciar a aplicação.
# Uvicorn usará automaticamente a variável $PORT do Cloud Run.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0"]
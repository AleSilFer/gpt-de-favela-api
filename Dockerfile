# C:\Users\Alessandro\Downloads\gpt-de-favela-api\Dockerfile

# --- Estágio 1: Build (Construção) ---
# Usamos uma imagem base oficial do Python para garantir um ambiente consistente.
FROM python:3.10-slim-buster as builder

WORKDIR /app
COPY requirements.txt ./
# Usamos --user para evitar warnings de permissão durante o build.
RUN pip install --no-cache-dir --user -r requirements.txt

# --- Estágio 2: Imagem final de produção ---
# Usamos a mesma imagem base para a execução.
FROM python:3.10-slim-buster

WORKDIR /app

# Copia apenas as dependências instaladas do estágio anterior
COPY --from=builder /root/.local /root/.local

# Copia o código da aplicação
COPY . .

# Garante que o diretório de pacotes Python esteja no PATH do sistema
ENV PATH="/root/.local/bin:${PATH}"

# Expõe a porta 8080, que o Cloud Run usará.
EXPOSE 8080

# Comando para iniciar a aplicação.
# Uvicorn usará automaticamente a variável de ambiente $PORT fornecida pelo Cloud Run.
# Esta é a forma mais robusta para ambientes de nuvem.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0"]
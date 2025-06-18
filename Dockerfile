# C:\Users\Alessandro\Downloads\gpt-de-favela-api\Dockerfile

# --- Estágio 1: Build (Construção) ---
# Usamos uma imagem base oficial do Python.
FROM python:3.10-slim-buster as builder

# Define o diretório de trabalho dentro do contêiner.
WORKDIR /app

# Copia o arquivo de requisitos para o diretório de trabalho.
COPY requirements.txt ./

# Instala as dependências Python usando pip.
RUN pip install --no-cache-dir -r requirements.txt


# --- Estágio 2: Runtime (Execução) ---
# Usamos a mesma imagem base para a execução.
FROM python:3.10-slim-buster

WORKDIR /app

# Copia as dependências instaladas do estágio anterior.
COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages

# Copia o código da nossa API SIMPLES para dentro do container.
# ATENÇÃO: Mudança aqui!
COPY main_simples.py .

# Expõe a porta que o Cloud Run espera.
EXPOSE 8080

# Comando para iniciar a aplicação Uvicorn.
# ATENÇÃO: Mudança aqui! Apontamos para o 'main_simples:app' e usamos a variável PORT.
CMD ["uvicorn", "main_simples:app", "--host", "0.0.0.0", "--port", "${PORT:-8080}"]
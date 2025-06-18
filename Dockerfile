# C:\Users\Alessandro\Downloads\gpt-de-favela-api\Dockerfile

# --- Estágio 1: Build (Construção) ---
# Usamos uma imagem base oficial do Python para garantir um ambiente consistente.
FROM python:3.10-slim-buster as builder

# Define o diretório de trabalho dentro do contêiner.
WORKDIR /app

# Copia o arquivo de requisitos para o diretório de trabalho.
COPY requirements.txt ./

# Instala as dependências Python usando pip.
RUN pip install --no-cache-dir -r requirements.txt


# --- Estágio 2: Runtime (Execução) ---
# Usamos a mesma imagem base para a execução, para manter a imagem final pequena.
FROM python:3.10-slim-buster

WORKDIR /app

# Copia as dependências instaladas do estágio anterior.
COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages

# Copia TODOS os arquivos da nossa aplicação (.py, .json) para dentro do container.
# ATENÇÃO: Mudança aqui! Voltamos a usar "COPY . .".
COPY . .

# Expõe a porta que o Cloud Run espera.
EXPOSE 8080

# Comando para iniciar a aplicação Uvicorn
# ATENÇÃO: Mudança aqui! Voltamos a apontar para 'main:app'.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "${PORT:-8080}"]
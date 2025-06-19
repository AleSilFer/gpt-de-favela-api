# Estágio 1: Build
FROM python:3.10-slim-buster as builder
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir --user -r requirements.txt

# Estágio 2: Imagem final
FROM python:3.10-slim-buster
WORKDIR /app
COPY --from=builder /root/.local /root/.local
COPY . .
ENV PATH="/root/.local/bin:${PATH}"
EXPOSE 8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
# C:\Users\Alessandro\Downloads\gpt-de-favela-api\main.py
# VERSÃO DE TESTE - SEM DEPENDÊNCIAS DO GOOGLE
from fastapi import FastAPI

app = FastAPI(title="API de Teste de Deploy")


@app.get("/")
def read_root():
    return {"message": "SUCESSO! A API mínima está no ar!"}


@app.get("/health")
def health_check():
    return {"status": "ok"}

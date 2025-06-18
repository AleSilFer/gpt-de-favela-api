# C:\Users\Alessandro\Downloads\gpt-de-favela-api\main_simples.py
from fastapi import FastAPI

# Cria a instância da aplicação FastAPI.
app = FastAPI(title="API de Teste Simples")


@app.get("/")
def read_root():
    """Este é o endpoint raiz. Se você acessar a URL da API, ele responderá."""
    return {"message": "API Simples está VIVA no Cloud Run!"}


@app.get("/health")
def health_check():
    """Este é um endpoint de 'saúde' para verificar se a API está respondendo."""
    return {"status": "ok"}

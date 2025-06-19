from fastapi import FastAPI, HTTPException, Query, Path, Body, Response, status
from pydantic import BaseModel, Field
from typing import List, Optional
import os
import googlemaps
import requests
from google.cloud import secretmanager
from google.api_core import exceptions

# --- Configurações Iniciais ---
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "gpt-favela")
gmaps_client = None
sptrans_api_key = None
sptrans_session = requests.Session()
secret_manager_client = None


# --- Bloco de Inicialização da Aplicação ---
def startup_event():
    """Função que roda quando a API inicia para configurar os clientes."""
    global gmaps_client, sptrans_api_key, secret_manager_client

    print("INFO: Iniciando a configuração da API...")

    # Tenta inicializar o cliente do Secret Manager primeiro
    try:
        secret_manager_client = secretmanager.SecretManagerServiceClient()
        print("INFO: Cliente do Secret Manager inicializado.")
    except Exception as e:
        print(
            f"ERRO CRÍTICO: Não foi possível inicializar o cliente do Secret Manager. Erro: {e}"
        )
        return  # Para a execução se não conseguir inicializar o cliente de segredos

    # Carrega a chave do Google Maps do Secret Manager e inicializa o cliente
    maps_api_key_value = get_secret_value("google-maps-api-key")
    if maps_api_key_value:
        gmaps_client = googlemaps.Client(key=maps_api_key_value)
        print("INFO: Cliente Google Maps inicializado com sucesso.")
    else:
        print(
            "AVISO: Cliente Google Maps não inicializado, chave não encontrada no Secret Manager."
        )

    # Carrega a chave da SPTrans do Secret Manager
    sptrans_api_key = get_secret_value("sptrans-olho-vivo-api-key")
    if sptrans_api_key:
        print("INFO: Chave da API da SPTrans carregada. Tentando autenticar...")
        if not autenticar_sptrans():
            print("AVISO: Autenticação inicial com a SPTrans falhou.")
    else:
        print("AVISO: Chave da SPTrans não encontrada no Secret Manager.")


def get_secret_value(secret_id: str) -> Optional[str]:
    """Busca o valor de um segredo. Retorna None se não encontrar."""
    if not secret_manager_client:
        return None

    print(f"INFO: Buscando segredo '{secret_id}'...")
    name = f"projects/{PROJECT_ID}/secrets/{secret_id}/versions/latest"
    try:
        response = secret_manager_client.access_secret_version(name=name)
        return response.payload.data.decode("UTF-8")
    except exceptions.NotFound:
        print(f"AVISO: Segredo '{secret_id}' não encontrado.")
        return None
    except Exception as e:
        print(f"ERRO: Falha ao buscar segredo '{secret_id}': {e}")
        return None


def autenticar_sptrans():
    if not sptrans_api_key:
        return False

    auth_url = f"http://api.olhovivo.sptrans.com.br/v2.1/Login/Autenticar?token={sptrans_api_key}"
    try:
        response = sptrans_session.post(auth_url)
        response.raise_for_status()
        if response.text.lower() == "true":
            print("INFO: Autenticação com a SPTrans bem-sucedida.")
            return True
        return False
    except Exception as e:
        print(f"ERRO: Exceção ao autenticar com a SPTrans: {e}")
        return False


# --- Configuração do FastAPI ---
app = FastAPI(
    title="API GPT de Favela - v2.0",
    description="API com Geolocalização, Transporte Público e Gerenciamento de Segredos.",
    version="2.0.0",
)


@app.on_event("startup")
async def on_startup():
    startup_event()


# --- Modelos Pydantic ---
class SecretPayload(BaseModel):
    value: str = Field(..., description="O valor do segredo a ser criado/atualizado.")


# --- Endpoints ---
@app.get("/")
def read_root():
    return {"message": "API GPT de Favela v2.0"}


@app.post("/secrets/{secret_id}", status_code=status.HTTP_201_CREATED)
def create_secret(secret_id: str, payload: SecretPayload):
    """Cria um novo segredo ou adiciona uma nova versão a um segredo existente."""
    if not secret_manager_client:
        raise HTTPException(
            status_code=503,
            detail="Serviço indisponível: cliente do Secret Manager não inicializado.",
        )

    parent = f"projects/{PROJECT_ID}"
    secret_path = f"{parent}/secrets/{secret_id}"
    try:
        secret_manager_client.create_secret(
            request={
                "parent": parent,
                "secret_id": secret_id,
                "secret": {"replication": {"automatic": {}}},
            }
        )
    except exceptions.AlreadyExists:
        pass  # Segredo já existe, o que é ok.

    payload_bytes = payload.value.encode("UTF-8")
    secret_manager_client.add_secret_version(
        request={"parent": secret_path, "payload": {"data": payload_bytes}}
    )
    return {"name": secret_path, "status": "version_added"}


# ... Adicione outros endpoints aqui (Geolocalização, SPTrans, etc.)

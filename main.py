from fastapi import FastAPI, HTTPException, Query, Path, Body, Response, status
from pydantic import BaseModel, Field
from typing import List, Optional
import os
import googlemaps
import requests
from google.cloud import secretmanager
from google.api_core import exceptions

# --- Configurações Iniciais ---
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT_ID", "gpt-favela")
gmaps_client = None
sptrans_session = requests.Session()
secret_manager_client = secretmanager.SecretManagerServiceClient()


# --- Bloco de Inicialização (Funções Reutilizáveis) ---
def get_secret_value(secret_id: str) -> Optional[str]:
    """Busca o valor de um segredo. Retorna None se não encontrar."""
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


# --- Configuração do FastAPI ---
app = FastAPI(
    title="API GPT de Favela - V1.3 (Secret Admin)",
    description="API para geolocalização, transporte e agora gerenciamento de segredos.",
    version="1.3.0",
)


@app.on_event("startup")
async def on_startup():
    global gmaps_client
    maps_api_key = get_secret_value("google-maps-api-key")
    if maps_api_key:
        gmaps_client = googlemaps.Client(key=maps_api_key)
        print("INFO: Cliente Google Maps inicializado.")
    else:
        print("AVISO: Cliente Google Maps não inicializado, chave não encontrada.")


# --- Modelos Pydantic ---
class SecretPayload(BaseModel):
    value: str = Field(..., description="O valor do segredo a ser criado/atualizado.")


class SecretResponse(BaseModel):
    name: str
    value: str


# --- Endpoints da API ---
@app.get("/")
def read_root():
    return {"message": "Bem-vindo à API de Automação do GPT de Favela!"}


# --- Grupo de Endpoints: Secret Manager ---


@app.post(
    "/secrets/{secret_id}",
    status_code=status.HTTP_201_CREATED,
    response_model=SecretResponse,
)
def create_secret(secret_id: str, payload: SecretPayload):
    """Cria um novo segredo ou adiciona uma nova versão a um segredo existente."""
    parent = f"projects/{PROJECT_ID}"
    secret_path = f"{parent}/secrets/{secret_id}"

    try:
        # Tenta criar o segredo. Se já existir, ele vai dar um erro 'AlreadyExists'.
        secret_manager_client.create_secret(
            request={
                "parent": parent,
                "secret_id": secret_id,
                "secret": {"replication": {"automatic": {}}},
            }
        )
        print(f"INFO: Segredo '{secret_id}' criado.")
    except exceptions.AlreadyExists:
        print(f"INFO: Segredo '{secret_id}' já existe. Adicionando nova versão.")
        pass  # O segredo já existe, o que é ok.
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Erro inesperado ao criar o segredo: {e}"
        )

    # Adiciona o valor como uma nova versão do segredo
    try:
        payload_bytes = payload.value.encode("UTF-8")
        response = secret_manager_client.add_secret_version(
            request={"parent": secret_path, "payload": {"data": payload_bytes}}
        )
        print(f"INFO: Nova versão adicionada para o segredo '{secret_id}'.")
        return SecretResponse(name=response.name, value=payload.value)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Erro ao adicionar versão ao segredo: {e}"
        )


@app.get("/secrets/{secret_id}", response_model=SecretResponse)
def read_secret(secret_id: str):
    """Lê o valor mais recente de um segredo."""
    value = get_secret_value(secret_id)
    if value is None:
        raise HTTPException(
            status_code=404, detail=f"Segredo '{secret_id}' não encontrado."
        )
    return SecretResponse(
        name=f"projects/{PROJECT_ID}/secrets/{secret_id}", value=value
    )


@app.delete("/secrets/{secret_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_secret(secret_id: str):
    """Deleta um segredo e todas as suas versões."""
    name = f"projects/{PROJECT_ID}/secrets/{secret_id}"
    try:
        secret_manager_client.delete_secret(request={"name": name})
        print(f"INFO: Segredo '{secret_id}' deletado com sucesso.")
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except exceptions.NotFound:
        raise HTTPException(
            status_code=404,
            detail=f"Segredo '{secret_id}' não encontrado para deletar.",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao deletar segredo: {e}")


# --- Outros endpoints (Geolocalização, SPTrans) podem ser adicionados aqui ---

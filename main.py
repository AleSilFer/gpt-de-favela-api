from fastapi import FastAPI, HTTPException, Query, Path, Body, Response, status
from pydantic import BaseModel, Field
from typing import List, Optional
import os
import googlemaps
import requests
from google.cloud import secretmanager
from google.api_core import exceptions

# --- Configurações Iniciais ---
PROJECT_ID = "gpt-favela"

# --- Clientes Globais ---
gmaps_client = None
sptrans_api_key = None
sptrans_session = requests.Session()
# Cliente do Secret Manager é inicializado aqui. Ele usará as credenciais do ambiente Cloud Run.
secret_manager_client = secretmanager.SecretManagerServiceClient()


# --- Funções de Inicialização (Startup) ---
def get_secret_value(secret_id: str) -> Optional[str]:
    """Busca a versão mais recente de um segredo, usando o cliente global."""
    if not secret_manager_client:
        print(
            f"ERRO: Cliente do Secret Manager não inicializado ao tentar buscar '{secret_id}'."
        )
        return None

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
        return response.text.lower() == "true"
    except Exception as e:
        print(f"ERRO ao autenticar com a SPTrans: {e}")
        return False


# --- Configuração do FastAPI ---
app = FastAPI(
    title="API GPT de Favela - v2.0 (Secret Admin)",
    description="API com Geolocalização, Transporte e Gerenciamento de Segredos.",
    version="2.0.0",
)


@app.on_event("startup")
async def startup_event():
    """Função que roda uma vez quando a API é iniciada para configurar os clientes."""
    global gmaps_client, sptrans_api_key
    print("INFO: Iniciando configuração da API...")

    # Montar segredos como volumes é o método preferido, mas como estamos adicionando
    # gerenciamento de segredos, precisamos do cliente Secret Manager ativo.

    maps_api_key_value = get_secret_value("google-maps-api-key")
    if maps_api_key_value:
        gmaps_client = googlemaps.Client(key=maps_api_key_value)
        print("INFO: Cliente Google Maps inicializado.")

    sptrans_api_key = get_secret_value("sptrans-olho-vivo-api-key")
    if sptrans_api_key:
        autenticar_sptrans()
    else:
        print("AVISO: Chave da SPTrans não encontrada no Secret Manager.")
    print("--- API PRONTA ---")


# --- Modelos Pydantic ---
class SecretPayload(BaseModel):
    value: str = Field(..., description="O valor do segredo a ser criado.")


class SecretResponse(BaseModel):
    name: str
    value: Optional[str] = None


class AddressGeocodeResponse(BaseModel):
    original_address: str
    formatted_address: str
    latitude: float
    longitude: float


class LinhaSPTrans(BaseModel):
    cl: int = Field(alias="CodigoLinha")
    lc: bool = Field(alias="Circular")
    lt: str = Field(alias="Letreiro")
    sl: int = Field(alias="Sentido")
    tp: str = Field(alias="DenominacaoTPTS")
    ts: str = Field(alias="DenominacaoTSTP")

    class Config:
        populate_by_name = True


class PosicaoVeiculo(BaseModel):
    p: str
    a: bool
    ta: str
    py: float
    px: float


class PosicaoLinha(BaseModel):
    hr: str
    vs: List[PosicaoVeiculo]


# --- Endpoints da API ---
@app.get("/")
def read_root():
    return {"message": "API GPT de Favela v2.0"}


# --- Grupo de Endpoints: Secret Manager ---


@app.post(
    "/secrets/{secret_id}",
    status_code=status.HTTP_201_CREATED,
    tags=["Secret Management"],
)
def create_or_update_secret(secret_id: str, payload: SecretPayload, response: Response):
    """Cria um novo segredo ou adiciona uma nova versão a um segredo existente."""
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
        print(f"INFO: Segredo '{secret_id}' criado.")
        response.status_code = status.HTTP_201_CREATED
    except exceptions.AlreadyExists:
        print(f"INFO: Segredo '{secret_id}' já existe. Adicionando nova versão.")
        response.status_code = status.HTTP_200_OK
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Erro inesperado ao criar o segredo: {str(e)}"
        )

    payload_bytes = payload.value.encode("UTF-8")
    version_response = secret_manager_client.add_secret_version(
        request={"parent": secret_path, "payload": {"data": payload_bytes}}
    )
    return {"name": version_response.name, "status": "version_added"}


@app.get(
    "/secrets/{secret_id}", response_model=SecretResponse, tags=["Secret Management"]
)
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


@app.delete(
    "/secrets/{secret_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Secret Management"],
)
def delete_secret(secret_id: str):
    """Deleta um segredo e todas as suas versões."""
    name = f"projects/{PROJECT_ID}/secrets/{secret_id}"
    try:
        secret_manager_client.delete_secret(request={"name": name})
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except exceptions.NotFound:
        raise HTTPException(
            status_code=404,
            detail=f"Segredo '{secret_id}' não encontrado para deletar.",
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Erro ao deletar segredo: {str(e)}"
        )


# --- Grupo de Endpoints: Geolocalização ---
@app.get(
    "/geocode/address",
    response_model=List[AddressGeocodeResponse],
    tags=["Geolocation"],
)
def geocode_address(
    address: str = Query(..., description="Endereço a ser geocodificado.")
):
    if gmaps_client is None:
        raise HTTPException(
            status_code=503, detail="Serviço do Google Maps indisponível."
        )
    try:
        geocode_result = gmaps_client.geocode(address)
        if not geocode_result:
            raise HTTPException(status_code=404, detail="Endereço não encontrado.")
        return [
            AddressGeocodeResponse(
                original_address=address,
                formatted_address=res["formatted_address"],
                latitude=res["geometry"]["location"]["lat"],
                longitude=res["geometry"]["location"]["lng"],
            )
            for res in geocode_result
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro interno: {str(e)}")


# --- Grupo de Endpoints: SPTrans ---
@app.get("/sptrans/linhas", response_model=List[LinhaSPTrans], tags=["SPTrans"])
def buscar_linhas(
    termo_busca: str = Query(
        ..., description="Termo para buscar a linha (ex: '8000' ou 'Lapa')."
    )
):
    if not autenticar_sptrans():
        raise HTTPException(status_code=503, detail="Serviço SPTrans indisponível.")
    try:
        url_busca = f"http://api.olhovivo.sptrans.com.br/v2.1/Linha/Buscar?termosBusca={termo_busca}"
        response = sptrans_session.get(url_busca)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Erro ao processar a busca de linha: {str(e)}"
        )


@app.get(
    "/sptrans/posicao/{codigo_linha}", response_model=PosicaoLinha, tags=["SPTrans"]
)
def buscar_posicao_linha(
    codigo_linha: int = Path(..., description="Código da linha (ex: 31690).")
):
    if not autenticar_sptrans():
        raise HTTPException(status_code=503, detail="Serviço SPTrans indisponível.")
    try:
        url_busca = f"http://api.olhovivo.sptrans.com.br/v2.1/Posicao/Linha?codigoLinha={codigo_linha}"
        response = sptrans_session.get(url_busca)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Erro ao buscar posição da linha: {str(e)}"
        )

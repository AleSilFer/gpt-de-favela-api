# C:\Users\Alessandro\Downloads\gpt-de-favela-api\main.py
from fastapi import FastAPI, HTTPException, Query, Depends
from pydantic import BaseModel, Field
from typing import List
import os
import googlemaps
from google.cloud import secretmanager
from functools import lru_cache

# --- Configuração do Projeto ---
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "gpt-favela")

# --- LÓGICA DE INICIALIZAÇÃO "PREGUIÇOSA" ---


# @lru_cache() garante que a função só roda uma vez.
# O resultado (o cliente) fica guardado em cache para as próximas chamadas.
@lru_cache()
def get_secret_manager_client():
    """Inicializa e retorna um cliente do Secret Manager, mas apenas quando for necessário."""
    print("INFO: Primeira chamada. Inicializando cliente do Secret Manager...")
    try:
        # No Cloud Run, ele usará as credenciais do ambiente automaticamente.
        client = secretmanager.SecretManagerServiceClient()
        print("INFO: Cliente do Secret Manager inicializado com sucesso.")
        return client
    except Exception as e:
        print(
            f"ERRO CRÍTICO: Falha ao inicializar o cliente do Secret Manager. Erro: {e}"
        )
        return None


def access_secret_version(secret_id: str) -> str:
    """Busca um segredo específico usando o cliente inicializado."""
    client = get_secret_manager_client()
    if client is None:
        raise RuntimeError("Cliente do Secret Manager não pôde ser inicializado.")

    name = f"projects/{PROJECT_ID}/secrets/{secret_id}/versions/latest"
    print(f"INFO: Acessando o segredo '{secret_id}'...")
    try:
        response = client.access_secret_version(name=name)
        secret_value = response.payload.data.decode("UTF-8")
        if not secret_value:
            raise ValueError(f"O valor do segredo '{secret_id}' está vazio.")
        print(f"INFO: Segredo '{secret_id}' acessado com sucesso.")
        return secret_value
    except Exception as e:
        print(
            f"ERRO CRÍTICO: Não foi possível acessar o valor do segredo '{secret_id}'. Causa: {e}"
        )
        raise


@lru_cache()
def get_gmaps_client():
    """Inicializa e retorna o cliente do Google Maps, mas apenas quando necessário."""
    print("INFO: Primeira chamada. Inicializando cliente Google Maps...")
    try:
        api_key = access_secret_version("google-maps-api-key")
        gmaps = googlemaps.Client(key=api_key)
        print("INFO: Cliente Google Maps inicializado com sucesso.")
        return gmaps
    except Exception as e:
        print(f"ERRO CRÍTICO: Falha ao inicializar o cliente Google Maps. Erro: {e}")
        return None


# --- Configuração do FastAPI ---
# A API agora inicia instantaneamente, sem bloqueios.
app = FastAPI(
    title="API GPT de Favela - V5 (Lazy Init)",
    description="API para geolocalização com inicialização preguiçosa de clientes.",
    version="0.5.0",
)


# --- Modelos Pydantic (sem alterações) ---
class AddressGeocodeResponse(BaseModel):
    original_address: str
    formatted_address: str
    latitude: float
    longitude: float
    place_id: str
    types: List[str]
    partial_match: bool = False


# --- Endpoints da API ---
@app.get("/")
def read_root():
    """Endpoint raiz que retorna uma mensagem de boas-vindas."""
    return {"message": "Bem-vindo à API de Geolocalização do GPT de Favela! V5"}


@app.get("/health")
def health_check():
    """Endpoint de saúde para verificar se a API está online."""
    return {"status": "ok", "api_version": app.version}


@app.get("/geocode/address", response_model=List[AddressGeocodeResponse])
def geocode_address(
    address: str = Query(..., description="Endereço a ser geocodificado."),
    gmaps_client: googlemaps.Client = Depends(get_gmaps_client),
):
    """Converte um endereço textual em coordenadas geográficas."""
    if gmaps_client is None:
        raise HTTPException(
            status_code=503,
            detail="Serviço do Google Maps indisponível devido a erro na inicialização.",
        )
    try:
        geocode_result = gmaps_client.geocode(address)
        if not geocode_result:
            raise HTTPException(
                status_code=404,
                detail="Endereço não encontrado ou inválido pela Google Geocoding API.",
            )
        results = [
            AddressGeocodeResponse(
                original_address=address,
                formatted_address=res["formatted_address"],
                latitude=res["geometry"]["location"]["lat"],
                longitude=res["geometry"]["location"]["lng"],
                place_id=res["place_id"],
                types=res["types"],
                partial_match=res.get("partial_match", False),
            )
            for res in geocode_result
        ]
        return results
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Erro interno ao geocodificar o endereço: {e}"
        )

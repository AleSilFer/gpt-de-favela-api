# C:\Users\Alessandro\Downloads\gpt-de-favela-api\main.py
# --- Importações Necessárias ---
from fastapi import FastAPI, HTTPException, Query, Depends
from pydantic import BaseModel, Field
from typing import List
import os
import googlemaps
from google.cloud import secretmanager
from functools import lru_cache

# --- Configuração do Google Cloud Project ---
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "gpt-favela")

# --- LÓGICA DE INICIALIZAÇÃO "PREGUIÇOSA" (LAZY INITIALIZATION) ---


# Usamos lru_cache para garantir que a função seja executada apenas uma vez
# e o resultado (o cliente) seja reutilizado em chamadas futuras.
@lru_cache()
def get_secret_manager_client():
    """
    Inicializa e retorna um cliente do Secret Manager.
    Esta função só será executada na primeira vez que for chamada.
    """
    print("INFO: Primeira chamada. Inicializando cliente do Secret Manager...")
    try:
        client = secretmanager.SecretManagerServiceClient()
        print("INFO: Cliente do Secret Manager inicializado com sucesso.")
        return client
    except Exception as e:
        print(
            f"ERRO CRÍTICO: Falha ao inicializar o cliente do Secret Manager. Erro: {e}"
        )
        # Retorna None para que possamos tratar o erro nos endpoints.
        return None


@lru_cache()
def get_maps_api_key() -> str:
    """
    Busca a chave da API do Google Maps do Secret Manager.
    Usa o cliente inicializado pela função acima.
    """
    print(
        "INFO: Primeira chamada. Buscando chave da API do Google Maps no Secret Manager..."
    )
    client = get_secret_manager_client()
    if client is None:
        raise RuntimeError("Cliente do Secret Manager não pôde ser inicializado.")

    secret_id = "google-maps-api-key"
    name = f"projects/{PROJECT_ID}/secrets/{secret_id}/versions/latest"
    try:
        response = client.access_secret_version(name=name)
        key = response.payload.data.decode("UTF-8")
        if not key:
            raise ValueError("O valor do segredo 'google-maps-api-key' está vazio.")
        print("INFO: Chave da API do Google Maps obtida com sucesso.")
        return key
    except Exception as e:
        print(
            f"ERRO CRÍTICO: Não foi possível acessar o segredo '{secret_id}'. Causa: {e}"
        )
        raise RuntimeError(f"Falha ao carregar o segredo '{secret_id}'.")


@lru_cache()
def get_gmaps_client():
    """
    Inicializa e retorna o cliente do Google Maps.
    Esta função depende da chave obtida pela função anterior.
    """
    print("INFO: Primeira chamada. Inicializando cliente Google Maps...")
    try:
        api_key = get_maps_api_key()
        gmaps = googlemaps.Client(key=api_key)
        print("INFO: Cliente Google Maps inicializado com sucesso.")
        return gmaps
    except Exception as e:
        print(f"ERRO CRÍTICO: Falha ao inicializar o cliente Google Maps. Erro: {e}")
        # Retorna None para que possamos tratar o erro nos endpoints.
        return None


# --- Configuração do FastAPI ---
# A API agora inicia instantaneamente, pois não há bloqueio de I/O na inicialização.
app = FastAPI(
    title="API GPT de Favela - V3 (Lazy Init)",
    description="API para geolocalização e transporte público com inicialização preguiçosa de clientes.",
    version="0.3.0",
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
    return {"message": "Bem-vindo à API de Geolocalização do GPT de Favela! V3"}


@app.get("/health")
def health_check():
    """Endpoint de saúde para verificar se a API está online e respondendo."""
    return {"status": "ok", "api_version": app.version}


# O 'Depends' injeta o cliente gmaps na função quando o endpoint é chamado.
@app.get("/geocode/address", response_model=List[AddressGeocodeResponse])
def geocode_address(
    address: str = Query(..., description="Endereço a ser geocodificado."),
    gmaps_client: googlemaps.Client = Depends(get_gmaps_client),
):
    """
    Converte um endereço textual em coordenadas geográficas (latitude e longitude).
    """
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

        results = []
        for res in geocode_result:
            location = res["geometry"]["location"]
            results.append(
                AddressGeocodeResponse(
                    original_address=address,
                    formatted_address=res["formatted_address"],
                    latitude=location["lat"],
                    longitude=location["lng"],
                    place_id=res["place_id"],
                    types=res["types"],
                    partial_match=res.get("partial_match", False),
                )
            )
        return results
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Erro interno ao geocodificar o endereço: {e}"
        )

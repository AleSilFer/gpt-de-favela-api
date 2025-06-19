from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List
import os
import googlemaps
from google.cloud import secretmanager
from google.oauth2 import service_account

# --- Configurações Iniciais ---
PROJECT_ID = "gpt-favela"
CREDENTIALS_FILE = "credentials.json"  # O nome do arquivo que esperamos encontrar.
gmaps_client = None

# --- Bloco de Inicialização ---
try:
    print(f"INFO: Tentando carregar credenciais do arquivo: {CREDENTIALS_FILE}")
    # O Python procura este arquivo na mesma pasta onde o main.py está.
    # No Docker, será em /app/credentials.json
    credentials = service_account.Credentials.from_service_account_file(
        CREDENTIALS_FILE
    )
    sm_client = secretmanager.SecretManagerServiceClient(credentials=credentials)
    print("INFO: Cliente do Secret Manager inicializado com SUCESSO via arquivo.")

    # Função para acessar outros segredos
    def access_secret(secret_id: str) -> str:
        name = f"projects/{PROJECT_ID}/secrets/{secret_id}/versions/latest"
        response = sm_client.access_secret_version(name=name)
        return response.payload.data.decode("UTF-8")

    # Carrega a chave do Google Maps e inicializa o cliente
    print("INFO: Buscando a chave da API do Google Maps...")
    maps_api_key = access_secret("google-maps-api-key")
    gmaps_client = googlemaps.Client(key=maps_api_key)
    print("INFO: API Pronta para uso!")

except FileNotFoundError:
    print(f"AVISO: O arquivo de credenciais '{CREDENTIALS_FILE}' não foi encontrado.")
    print("AVISO: A API iniciará, mas os endpoints que dependem do Google falharão.")
    # A aplicação continua, mas gmaps_client permanecerá None
    pass
except Exception as e:
    print(f"ERRO CRÍTICO na inicialização: {e}")
    # Em caso de outro erro, a aplicação continua, mas gmaps_client permanecerá None
    pass


# --- Configuração do FastAPI ---
app = FastAPI(title="API GPT de Favela - V7 (Final)", version="0.7.0")


class AddressGeocodeResponse(BaseModel):
    original_address: str
    formatted_address: str
    latitude: float
    longitude: float


@app.get("/")
def read_root():
    return {"message": "API GPT de Favela V7"}


@app.get("/geocode/address", response_model=List[AddressGeocodeResponse])
def geocode_address(
    address: str = Query(..., description="Endereço a ser geocodificado.")
):
    if gmaps_client is None:
        raise HTTPException(
            status_code=503,
            detail="Serviço indisponível: cliente do Google Maps não foi inicializado corretamente.",
        )
    try:
        geocode_result = gmaps_client.geocode(address)
        if not geocode_result:
            raise HTTPException(status_code=404, detail="Endereço não encontrado.")

        results = []
        for result in geocode_result:
            results.append(
                AddressGeocodeResponse(
                    original_address=address,
                    formatted_address=result["formatted_address"],
                    latitude=result["geometry"]["location"]["lat"],
                    longitude=result["geometry"]["location"]["lng"],
                )
            )
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro interno: {str(e)}")

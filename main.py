# C:\Users\Alessandro\Downloads\gpt-de-favela-api\main.py
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List
import os
import googlemaps
from google.cloud import secretmanager
from google.oauth2 import service_account

# --- Configurações Iniciais ---
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "gpt-favela")

# A API vai procurar o arquivo de credenciais que o CI/CD colocou no container
CREDENTIALS_FILE_PATH = "/app/credentials.json" 

# --- Inicialização ---
try:
    print(f"INFO: Tentando carregar credenciais de: {CREDENTIALS_FILE_PATH}")
    credentials = service_account.Credentials.from_service_account_file(CREDENTIALS_FILE_PATH)
    secret_manager_client = secretmanager.SecretManagerServiceClient(credentials=credentials)
    
    def access_secret_version(secret_id: str) -> str:
        name = f"projects/{PROJECT_ID}/secrets/{secret_id}/versions/latest"
        response = secret_manager_client.access_secret_version(name=name)
        return response.payload.data.decode("UTF-8")

    print("INFO: Buscando a chave da API do Google Maps...")
    maps_api_key = access_secret_version("google-maps-api-key")
    gmaps = googlemaps.Client(key=maps_api_key)
    print("INFO: API Pronta!")

except Exception as e:
    print(f"FATAL: APLICAÇÃO FALHOU AO INICIAR. Erro: {e}")
    gmaps = None

# --- Configuração do FastAPI ---
app = FastAPI(title="API GPT de Favela - V6 (JSON Injetado)", version="0.6.0")

# --- Modelos e Endpoints (sem alterações)...
class AddressGeocodeResponse(BaseModel):
    original_address: str; formatted_address: str; latitude: float; longitude: float; place_id: str; types: List[str]; partial_match: bool = False

@app.get("/")
def read_root():
    return {"message": "Bem-vindo à API de Geolocalização do GPT de Favela! V6"}

@app.get("/geocode/address", response_model=List[AddressGeocodeResponse])
def geocode_address(address: str = Query(..., description="Endereço a ser geocodificado.")):
    if gmaps is None:
        raise HTTPException(status_code=503, detail="Serviço do Google Maps indisponível.")
    try:
        geocode_result = gmaps.geocode(address)
        if not geocode_result:
            raise HTTPException(status_code=404, detail="Endereço não encontrado.")
        results = [AddressGeocodeResponse(original_address=address, formatted_address=res['formatted_address'], latitude=res['geometry']['location']['lat'], longitude=res['geometry']['location']['lng'], place_id=res['place_id'], types=res['types'], partial_match=res.get('partial_match', False)) for res in geocode_result]
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro interno: {e}")
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List
import os
import googlemaps

# O caminho onde o Cloud Run irá "entregar" nosso segredo como um arquivo
API_KEY_FILE_PATH = "/secrets/Maps_api_key"
gmaps_client = None

# Bloco de inicialização que roda quando a API liga
try:
    print(f"INFO: Tentando ler a chave da API do arquivo: {API_KEY_FILE_PATH}")
    with open(API_KEY_FILE_PATH, "r") as f:
        api_key = f.read().strip()

    if api_key:
        gmaps_client = googlemaps.Client(key=api_key)
        print("INFO: Cliente do Google Maps inicializado com sucesso!")
        print("INFO: API Pronta para uso!")
    else:
        print(
            "ERRO CRÍTICO: O arquivo de segredo da chave de API foi encontrado, mas está vazio."
        )

except FileNotFoundError:
    # Este aviso aparecerá no seu teste local, o que é esperado.
    print(f"AVISO: O arquivo de segredo '{API_KEY_FILE_PATH}' não foi encontrado.")
    print(
        "AVISO: Isso é normal em ambiente local. Na nuvem (Cloud Run), o arquivo deve existir."
    )
except Exception as e:
    print(f"ERRO CRÍTICO na inicialização: {e}")


# --- Configuração do FastAPI ---
app = FastAPI(title="API GPT de Favela - V9 (Secret via Volume)", version="0.9.0")


class AddressGeocodeResponse(BaseModel):
    original_address: str
    formatted_address: str
    latitude: float
    longitude: float


@app.get("/")
def read_root():
    return {"message": "Bem-vindo à API de Geolocalização do GPT de Favela! V9"}


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

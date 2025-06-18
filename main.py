# C:\Users\Alessandro\Downloads\gpt-de-favela-api\main.py
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List
import os
import googlemaps
from google.cloud import secretmanager
from google.oauth2 import service_account

# --- Configurações Iniciais ---
PROJECT_ID = "gpt-favela"


def create_credentials_from_secret():
    """Busca o conteúdo do JSON de credenciais do Secret Manager e o salva em um arquivo temporário."""
    try:
        # Primeiro, inicializa um cliente SEM credenciais específicas para buscar o super segredo.
        # Ele usará as credenciais do ambiente Cloud Run (que têm permissão para ler segredos).
        print(
            "INFO: Inicializando cliente SM para buscar o 'super segredo' de credenciais."
        )
        initial_client = secretmanager.SecretManagerServiceClient()

        secret_id = "gcp-sa-credentials-json"  # O nome do nosso novo segredo
        name = f"projects/{PROJECT_ID}/secrets/{secret_id}/versions/latest"

        print(f"INFO: Buscando o conteúdo do segredo: {name}")
        response = initial_client.access_secret_version(name=name)
        credentials_json_content = response.payload.data.decode("UTF-8")

        # Define um caminho para o arquivo de credenciais dentro do contêiner (em uma pasta que permite escrita)
        temp_credentials_path = "/tmp/credentials.json"

        print(f"INFO: Escrevendo o conteúdo das credenciais em {temp_credentials_path}")
        with open(temp_credentials_path, "w") as f:
            f.write(credentials_json_content)

        # Retorna o caminho para o arquivo de credenciais recém-criado
        return temp_credentials_path

    except Exception as e:
        print(
            f"ERRO CRÍTICO ao buscar ou criar o arquivo de credenciais a partir do Secret Manager: {e}"
        )
        raise RuntimeError("Falha no bootstrap de credenciais.")


# --- Bloco de Inicialização Principal ---
try:
    print("\n--- INICIANDO API GPT DE FAVELA (MODO ROBUSTO) ---")

    # 1. Cria o arquivo de credenciais a partir do Secret Manager
    credentials_path = create_credentials_from_secret()

    # 2. Cria credenciais a partir do arquivo que acabamos de criar
    print(f"INFO: Carregando credenciais a partir de {credentials_path}")
    credentials = service_account.Credentials.from_service_account_file(
        credentials_path
    )

    # 3. Inicializa o cliente do Secret Manager USANDO as credenciais do arquivo
    print("INFO: Inicializando cliente SM final com as credenciais do arquivo.")
    secret_manager_client = secretmanager.SecretManagerServiceClient(
        credentials=credentials
    )
    print("INFO: Cliente SM final inicializado com sucesso.")

    # 4. Função para acessar outros segredos usando o cliente já autenticado
    def access_secret_version(secret_id: str) -> str:
        name = f"projects/{PROJECT_ID}/secrets/{secret_id}/versions/latest"
        response = secret_manager_client.access_secret_version(name=name)
        return response.payload.data.decode("UTF-8")

    # 5. Busca a chave da API do Google Maps
    print("INFO: Buscando a chave da API do Google Maps...")
    maps_api_key = access_secret_version("google-maps-api-key")
    print("INFO: Chave da API do Google Maps obtida com sucesso.")

    # 6. Inicializa o cliente do Google Maps
    gmaps = googlemaps.Client(key=maps_api_key)
    print("INFO: Cliente Google Maps 'gmaps' inicializado e pronto para uso.")
    print("--- API PRONTA PARA RECEBER REQUISIÇÕES ---\n")

except Exception as startup_error:
    print(f"\nFATAL: APLICAÇÃO FALHOU AO INICIAR. Erro: {startup_error}\n")
    gmaps = None

# --- Configuração do FastAPI ---
app = FastAPI(title="API GPT de Favela - V4 (Robusto)", version="0.4.0")


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
    return {"message": "Bem-vindo à API de Geolocalização do GPT de Favela! V4"}


@app.get("/geocode/address", response_model=List[AddressGeocodeResponse])
def geocode_address(
    address: str = Query(..., description="Endereço a ser geocodificado.")
):
    if gmaps is None:
        raise HTTPException(
            status_code=503,
            detail="Serviço do Google Maps indisponível devido a erro na inicialização.",
        )
    try:
        geocode_result = gmaps.geocode(address)
        if not geocode_result:
            raise HTTPException(status_code=404, detail="Endereço não encontrado.")
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
        raise HTTPException(status_code=500, detail=f"Erro interno: {e}")

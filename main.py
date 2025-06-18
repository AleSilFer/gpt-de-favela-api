# C:\Users\Alessandro\Downloads\gpt-de-favela-api\main.py
# --- Importações Necessárias ---
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Optional
import os
import googlemaps
from google.cloud import secretmanager
from google.oauth2 import service_account

# --- Configurações Iniciais e Constantes ---
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT_ID", "gpt-favela")
CREDENTIALS_FILE_PATH = os.path.join(os.path.dirname(__file__), "credentials.json")

# --- Funções de Inicialização ---


def get_secret_manager_client():
    """Inicializa e retorna um cliente do Secret Manager."""
    print("INFO: Verificando método de autenticação...")
    if os.path.exists(CREDENTIALS_FILE_PATH):
        print(
            f"INFO: Arquivo '{CREDENTIALS_FILE_PATH}' encontrado. Usando credenciais de conta de serviço."
        )
        try:
            credentials = service_account.Credentials.from_service_account_file(
                CREDENTIALS_FILE_PATH
            )
            client = secretmanager.SecretManagerServiceClient(credentials=credentials)
            print(
                "INFO: Cliente do Secret Manager inicializado com SUCESSO via arquivo JSON."
            )
            return client
        except Exception as e:
            print(f"ERRO CRÍTICO: Falha ao carregar credenciais do arquivo JSON: {e}")
            raise RuntimeError("Não foi possível carregar as credenciais do arquivo.")
    else:
        print(
            "AVISO: Arquivo 'credentials.json' não encontrado. Tentando credenciais padrão do ambiente (ADC)..."
        )
        try:
            client = secretmanager.SecretManagerServiceClient()
            print(
                "INFO: Cliente do Secret Manager inicializado com SUCESSO via credenciais padrão do ambiente."
            )
            return client
        except Exception as e:
            print(
                f"ERRO CRÍTICO: Falha ao usar credenciais padrão do ambiente (ADC): {e}"
            )
            raise RuntimeError("Nenhum método de autenticação válido foi encontrado.")


def access_secret_version(client, secret_id: str, version_id: str = "latest") -> str:
    """Acessa um segredo usando um cliente já inicializado."""
    name = f"projects/{PROJECT_ID}/secrets/{secret_id}/versions/{version_id}"
    print(f"INFO: Acessando o segredo '{secret_id}'...")
    try:
        response = client.access_secret_version(name=name)
        secret_value = response.payload.data.decode("UTF-8")
        if not secret_value:
            raise ValueError("O valor do segredo retornado está vazio.")
        print(f"INFO: Segredo '{secret_id}' acessado com sucesso.")
        return secret_value
    except Exception as e:
        print(
            f"ERRO CRÍTICO: Não foi possível acessar o valor do segredo '{secret_id}'. Causa: {e}"
        )
        raise


# --- Bloco de Inicialização Principal da Aplicação ---
try:
    print("\n--- INICIANDO API GPT DE FAVELA ---")
    sm_client = get_secret_manager_client()
    maps_api_key = access_secret_version(sm_client, "google-maps-api-key")
    gmaps = googlemaps.Client(key=maps_api_key)
    print("INFO: Cliente Google Maps 'gmaps' inicializado e pronto para uso.")
    print("--- API PRONTA PARA RECEBER REQUISIÇÕES ---\n")
except Exception as startup_error:
    print(f"\nFATAL: APLICAÇÃO FALHOU AO INICIAR. Erro: {startup_error}\n")
    gmaps = None

# --- Configuração do FastAPI ---
app = FastAPI(
    title="API GPT de Favela - V2",
    description="API para geolocalização e transporte público. Tentativa de correção de inicialização.",
    version="0.2.0",
)


# --- Modelos Pydantic ---
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
    return {"message": "Bem-vindo à API de Geolocalização do GPT de Favela!"}


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
            status_code=500, detail=f"Erro interno ao geocodificar o endereço: {str(e)}"
        )

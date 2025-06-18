# C:\Users\Alessandro\Downloads\gpt-de-favela-api\main.py

# --- Importações Necessárias ---
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Dict, Union
import os
import googlemaps # Biblioteca para interagir com a Google Maps API
from google.cloud import secretmanager # Biblioteca para interagir com o Google Secret Manager
from google.oauth2 import service_account # Importa para carregar chaves de serviço (para teste local)


# --- Configuração do Google Cloud Project ---
# ID do seu projeto Google Cloud.
# JÁ PERSONALIZADO com a sua ID: 'gpt-favela'
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT_ID", "gpt-favela")

# --- Inicialização do Cliente do Secret Manager ---
# ATENÇÃO: ESTE MÉTODO DE CARREGAR 'credentials.json' É APENAS PARA DESENVOLVIMENTO LOCAL
# QUANDO AS CREDENCIAIS PADRÃO (ADC) ESTÃO COM PROBLEMAS.
# Para produção no Cloud Run, as credenciais serão gerenciadas automaticamente pelo GCP.
# Certifique-se de que 'credentials.json' está na raiz do seu projeto local
# e que está no .gitignore para NÃO ser enviado para o GitHub.
CREDENTIALS_FILE_PATH = os.path.join(os.path.dirname(__file__), "credentials.json")

secret_manager_client = None # Inicializa como None para garantir escopo

try:
    if os.path.exists(CREDENTIALS_FILE_PATH):
        print("INFO: Tentando carregar credenciais de service_account do arquivo local.")
        credentials = service_account.Credentials.from_service_account_file(
            CREDENTIALS_FILE_PATH,
            scopes=["https://www.googleapis.com/auth/cloud-platform"] # Escopo necessário para Secret Manager
        )
        secret_manager_client = secretmanager.SecretManagerServiceClient(credentials=credentials)
        print("INFO: SecretManagerServiceClient inicializado com sucesso usando arquivo local.")
    else:
        print("AVISO: 'credentials.json' não encontrado. Tentando credenciais padrão (ADC).")
        # Se 'credentials.json' não estiver presente, tenta o método padrão do Google Cloud SDK (ADC)
        secret_manager_client = secretmanager.SecretManagerServiceClient()
        print("INFO: SecretManagerServiceClient inicializado com sucesso no modo padrão (ADC).")

except Exception as e:
    print(f"ERRO CRÍTICO: Não foi possível inicializar SecretManagerServiceClient. Erro: {e}")
    # Se a inicialização do cliente falhar, a aplicação não pode prosseguir.
    raise RuntimeError(f"Falha ao inicializar o cliente Secret Manager: {e}. Verifique as credenciais e permissões.")


# --- Função para Acessar Segredos ---
def access_secret_version(secret_id: str, version_id: str = "latest") -> str:
    """
    Função para acessar a versão mais recente de um segredo no Google Secret Manager.

    Args:
        secret_id (str): O ID do segredo (o nome que você deu no Secret Manager, ex: 'google-maps-api-key').
        version_id (str): A versão do segredo a ser acessada (padrão é 'latest').

    Returns:
        str: O valor decodificado do segredo.

    Raises:
        RuntimeError: Se houver um erro ao acessar o segredo, geralmente por PROJECT_ID incorreta,
                      segredo não encontrado ou falta de permissão.
    """
    # Constrói o nome completo do recurso do segredo no formato do Google Cloud.
    name = f"projects/{PROJECT_ID}/secrets/{secret_id}/versions/{version_id}"
    try:
        response = secret_manager_client.access_secret_version(name=name)
        return response.payload.data.decode("UTF-8")
    except Exception as e:
        # Em caso de erro, imprime mensagens úteis para depuração e levanta um erro.
        print(f"ERRO CRÍTICO: Não foi possível acessar o segredo '{secret_id}'.")
        print(f"  - Verifique se a PROJECT_ID no 'main.py' está correta e corresponde ao seu projeto GCP ('{PROJECT_ID}').")
        print(f"  - Verifique se o segredo '{secret_id}' existe no Secret Manager do seu projeto.")
        print(f"  - Verifique se a conta de serviço (ou suas credenciais locais) tem a permissão 'Secret Manager Secret Accessor' para este segredo.")
        raise RuntimeError(f"Falha ao carregar o segredo '{secret_id}'. Detalhes: {e}")

# --- Carrega a Chave da Google Maps API ---
# A API precisa da chave ANTES de ser inicializada.
try:
    Maps_API_KEY = access_secret_version("google-maps-api-key")
    print("DEBUG: Chave do Google Maps API carregada com sucesso do Secret Manager.") # NOVA MENSAGEM
except RuntimeError:
    print("A aplicação não pode iniciar sem a chave da Google Maps API. Saindo.")
    exit(1) # Força a saída do programa se a chave não puder ser carregada.

# --- Inicialização do Cliente Google Maps ---
# Agora que temos a chave, podemos inicializar o cliente Google Maps.
gmaps = googlemaps.Client(key=Maps_API_KEY)
print("DEBUG: Cliente Google Maps 'gmaps' inicializado com sucesso.") # NOVA MENSAGEM

# --- Configuração do FastAPI ---
# Cria a instância principal da sua aplicação FastAPI.
app = FastAPI(
    title="API GPT de Favela - Geolocalização (Secret Manager)",
    description="API para explorar funcionalidades de geolocalização com Google Maps, usando Google Secret Manager para chaves.",
    version="0.1.1", # Versão da sua API
)

# --- Modelos Pydantic para Validação de Dados ---
# Estes modelos definem a estrutura dos dados que sua API espera receber e enviar.
# Eles são automaticamente usados para validação e documentação.

class AddressGeocodeResponse(BaseModel):
    """Modelo para a resposta da geocodificação de endereço (endereço -> lat/lng)."""
    original_address: str = Field(..., description="O endereço original que foi solicitado.")
    formatted_address: str = Field(..., description="O endereço formatado pelo Google Maps.")
    latitude: float = Field(..., description="Latitude da localização encontrada.")
    longitude: float = Field(..., description="Longitude da localização encontrada.")
    place_id: str = Field(..., description="ID única do lugar no Google Maps.")
    types: List[str] = Field(..., description="Tipos de resultado da geocodificação (ex: 'street_address', 'locality').")
    partial_match: bool = Field(False, description="Indica se a geocodificação foi uma correspondência parcial.")

class LatLngGeocodeResponse(BaseModel):
    """Modelo para a resposta da geocodificação reversa de coordenadas (lat/lng -> endereço)."""
    original_latitude: float = Field(..., description="A latitude original que foi solicitada.")
    original_longitude: float = Field(..., description="A longitude original que foi solicitada.")
    formatted_address: str = Field(..., description="O endereço formatado pelo Google Maps para as coordenadas.")
    place_id: str = Field(..., description="ID única do lugar no Google Maps.")
    types: List[str] = Field(..., description="Tipos de resultado da geocodificação reversa.")

# --- Endpoints da API ---

@app.get("/")
async def read_root():
    """
    Endpoint raiz da API.
    Retorna uma mensagem de boas-vindas para indicar que a API está funcionando.
    """
    return {"message": "Bem-vindo à API de Geolocalização do GPT de Favela! Versão 0.1.1"}

@app.get("/geocode/address", response_model=List[AddressGeocodeResponse])
async def geocode_address(address: str = Query(..., description="Endereço a ser convertido em coordenadas (ex: 'Avenida Paulista, 1578, São Paulo').")):
    """
    Converte um endereço textual em coordenadas geográficas (latitude e longitude).
    Utiliza a Google Geocoding API.
    Retorna uma lista de possíveis resultados de geocodificação, pois um endereço pode ter múltiplos resultados.
    """
    try:
        # Tenta usar o cliente 'gmaps' que foi inicializado globalmente.
        geocode_result = gmaps.geocode(address)

        if not geocode_result:
            # Se a API do Google não retornar resultados, consideramos não encontrado.
            raise HTTPException(status_code=404, detail="Endereço não encontrado ou inválido pela Google Geocoding API.")

        results = []
        for res in geocode_result:
            location = res['geometry']['location']
            results.append(AddressGeocodeResponse(
                original_address=address,
                formatted_address=res['formatted_address'],
                latitude=location['lat'],
                longitude=location['lng'],
                place_id=res['place_id'],
                types=res['types'],
                partial_match=res.get('partial_match', False)
            ))
        return results

    except Exception as e:
        # Captura qualquer erro durante o processo e retorna um erro HTTP 500.
        raise HTTPException(status_code=500, detail=f"Erro interno ao geocodificar o endereço: {str(e)}")

@app.get("/geocode/latlng", response_model=List[LatLngGeocodeResponse])
async def reverse_geocode_latlng(
    latitude: float = Query(..., description="Latitude da localização (ex: -23.561356)."),
    longitude: float = Query(..., description="Longitude da localização (ex: -46.656910).")
):
    """
    Converte coordenadas geográficas (latitude e longitude) em um endereço textual.
    Utiliza a Google Reverse Geocoding API.
    Retorna uma lista de possíveis resultados de geocodificação reversa.
    """
    try:
        # Tenta usar o cliente 'gmaps' que foi inicializado globalmente.
        reverse_geocode_result = gmaps.reverse_geocode((latitude, longitude))

        if not reverse_geocode_result:
            # Se a API do Google não retornar resultados, consideramos não encontrado.
            raise HTTPException(status_code=404, detail="Coordenadas não encontradas ou inválidas pela Google Reverse Geocoding API.")

        results = []
        for res in reverse_geocode_result:
            results.append(LatLngGeocodeResponse(
                original_latitude=latitude,
                original_longitude=longitude,
                formatted_address=res['formatted_address'],
                place_id=res['place_id'],
                types=res['types']
            ))
        return results

    except Exception as e:
        # Captura qualquer erro durante o processo e retorna um erro HTTP 500.
        raise HTTPException(status_code=500, detail=f"Erro interno ao geocodificar as coordenadas: {str(e)}")

@app.get("/health")
async def health_check():
    """
    Endpoint de Health Check.
    Retorna o status da API para indicar que está online e funcionando.
    """
    return {"status": "ok", "api_version": app.version}
# C:\Users\Alessandro\Downloads\gpt-de-favela-api\main.py

# --- Importações Necessárias ---
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Dict, Union
import os
import googlemaps
from google.cloud import secretmanager
from google.oauth2 import service_account
import requests

# --- Configuração do Google Cloud Project ---
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "gpt-favela")

# --- Inicialização do Cliente do Secret Manager ---
try:
    secret_manager_client = secretmanager.SecretManagerServiceClient()
    print("INFO: Cliente do Secret Manager inicializado com sucesso.")
except Exception as e:
    print(f"ERRO CRÍTICO: Não foi possível inicializar o cliente do Secret Manager: {e}")
    secret_manager_client = None

# --- Função para Acessar Segredos ---
def access_secret_version(secret_id: str, project_id: str, version_id: str = "latest") -> str:
    """
    Acessa uma versão de um segredo no Google Secret Manager e retorna seu payload.
    """
    if not secret_manager_client:
        raise RuntimeError("O cliente do Secret Manager não está disponível.")

    name = f"projects/{project_id}/secrets/{secret_id}/versions/{version_id}"
    print(f"INFO: Acessando o segredo: {name}")
    try:
        response = secret_manager_client.access_secret_version(name=name)
        payload = response.payload.data.decode("UTF-8")
        print(f"INFO: Segredo '{secret_id}' acessado com sucesso.")
        return payload
    except Exception as e:
        print(f"ERRO CRÍTICO: Falha ao acessar o segredo '{secret_id}'. A permissão 'Secret Manager Secret Accessor' pode estar faltando. Erro: {e}")
        raise RuntimeError(f"Não foi possível acessar o segredo {secret_id}") from e

# --- Carrega as Chaves de API ---
try:
    Maps_API_KEY = access_secret_version("google-maps-api-key", project_id=PROJECT_ID)
    SPTRANS_OLHO_VIVO_API_KEY = access_secret_version("sptrans-olho-vivo-api-key", project_id=PROJECT_ID)
except RuntimeError as e:
    print(f"A aplicação não pode iniciar sem as chaves de API necessárias. Erro: {e}. Saindo.")
    exit(1) # Força a saída se não conseguir carregar as chaves

# --- Inicialização dos Clientes de API ---
gmaps = googlemaps.Client(key=Maps_API_KEY)
print("INFO: Cliente Google Maps 'gmaps' inicializado com sucesso.")

# --- Configurações e Cliente para SPTrans Olho Vivo API ---
SPTRANS_API_BASE_URL = "http://api.olhovivo.sptrans.com.br/v2.1"
sptrans_auth_token = None # Este será o próximo a ser corrigido

# --- Funções Auxiliares para SPTrans API ---
def authenticate_sptrans():
    # ATENÇÃO: A lógica de autenticação real da SPTrans será implementada em uma próxima aula.
    print("INFO: Autenticação SPTrans temporariamente simulada como bem-sucedida.")
    global sptrans_auth_token
    sptrans_auth_token = "SIMULATED_TOKEN" # Simula um token para passar das checagens
    return True

if not authenticate_sptrans():
    print("ERRO CRÍTICO: Não foi possível autenticar na API SPTrans.")

# --- Configuração do FastAPI ---
app = FastAPI(
    title="API GPT de Favela - Geolocalização e Transporte Público",
    description="API para explorar funcionalidades de geolocalização e transporte público de SP.",
    version="0.3.0",
)

# --- Modelos Pydantic para Validação de Dados ---
class AddressGeocodeResponse(BaseModel):
    original_address: str = Field(..., description="O endereço original que foi solicitado.")
    formatted_address: str = Field(..., description="O endereço formatado pelo Google Maps.")
    latitude: float = Field(..., description="Latitude da localização encontrada.")
    longitude: float = Field(..., description="Longitude da localização encontrada.")
    place_id: str = Field(..., description="ID única do lugar no Google Maps.")
    types: List[str] = Field(..., description="Tipos de resultado da geocodificação (ex: 'street_address', 'locality').")
    partial_match: bool = Field(False, description="Indica se a geocodificação foi uma correspondência parcial.")

class LatLngGeocodeResponse(BaseModel):
    original_latitude: float = Field(..., description="A latitude original que foi solicitada.")
    original_longitude: float = Field(..., description="A longitude original que foi solicitada.")
    formatted_address: str = Field(..., description="O endereço formatado pelo Google Maps para as coordenadas.")
    place_id: str = Field(..., description="ID única do lugar no Google Maps.")
    types: List[str] = Field(..., description="Tipos de resultado da geocodificação reversa.")

class SPTransLinha(BaseModel):
    cl: int = Field(..., description="Código identificador da linha.")
    lc: bool = Field(..., description="Indica se a linha opera no sentido anti-horário (circular).")
    lt: str = Field(..., description="Primeiro letreiro descritivo da linha.")
    tl: int = Field(..., description="Informação sobre o tipo de linha (0 = comum, 1 = seletivo).")
    sl: int = Field(..., description="Sentido da linha (1 = ida, 2 = volta).")
    tp: str = Field(..., description="Letreiro de segundo sentido da linha (terminal principal).")
    ts: str = Field(..., description="Letreiro de segundo sentido da linha (terminal secundário).")

class SPTransPosicaoVeiculo(BaseModel):
    p: int = Field(..., description="Prefix do veículo.")
    py: float = Field(..., description="Latitude da posição do veículo.")
    px: float = Field(..., description="Longitude da posição do veículo.")
    a: bool = Field(..., description="Indica se o veículo é acessível (PCD).")
    ta: str = Field(..., description="Horário da última atualização da posição do veículo (formato%Y-%m-%d %H:%M:%S).")
    l: bool = Field(..., description="Indica se a posição é um ponto de ônibus ou um ponto de interesse (true para ponto de ônibus).")

class SPTransPosicoesResponse(BaseModel):
    hr: str = Field(..., description="Horário da geração das informações (yyyy-MM-dd HH:mm:ss).")
    vs: List[SPTransPosicaoVeiculo] = Field(..., description="Lista de veículos na linha.")

# --- Endpoints da API ---

@app.get("/")
async def read_root():
    return {"message": "Bem-vindo à API de Geolocalização e Transporte Público do GPT de Favela!"}

@app.get("/geocode/address", response_model=List[AddressGeocodeResponse])
async def geocode_address(address: str = Query(..., description="Endereço a ser convertido em coordenadas (ex: 'Avenida Paulista, 1578, São Paulo').")):
    try:
        geocode_result = gmaps.geocode(address)
        if not geocode_result:
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
        raise HTTPException(status_code=500, detail=f"Erro interno ao geocodificar o endereço: {str(e)}")

@app.get("/geocode/latlng", response_model=List[LatLngGeocodeResponse])
async def reverse_geocode_latlng(
    latitude: float = Query(..., description="Latitude da localização (ex: -23.561356)."),
    longitude: float = Query(..., description="Longitude da localização (ex: -46.656910).")
):
    try:
        reverse_geocode_result = gmaps.reverse_geocode((latitude, longitude))
        if not reverse_geocode_result:
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
        raise HTTPException(status_code=500, detail=f"Erro interno ao geocodificar as coordenadas: {str(e)}")

@app.get("/sptrans/linhas", response_model=List[SPTransLinha])
async def get_sptrans_linhas(termo_busca: str = Query(..., description="Termo de busca para linhas de ônibus (ex: 'paulista', '8700').")):
    if not sptrans_auth_token:
        raise HTTPException(status_code=503, detail="Serviço SPTrans indisponível (autenticação falhou).")

    search_url = f"{SPTRANS_API_BASE_URL}/Linha/Buscar"
    try:
        response = requests.get(search_url, params={"termosBusca": termo_busca}, headers={"Cookie": f"apiCredentials={sptrans_auth_token}"})
        response.raise_for_status()
        linhas_data = response.json()
        return [SPTransLinha(**linha) for linha in linhas_data]
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Erro ao buscar linhas SPTrans: {str(e)}")

@app.get("/sptrans/posicoes/{codigo_linha}", response_model=SPTransPosicoesResponse)
async def get_sptrans_posicoes(codigo_linha: int = Field(..., description="Código identificador da linha (campo 'cl' da linha).")):
    if not sptrans_auth_token:
        raise HTTPException(status_code=503, detail="Serviço SPTrans indisponível (autenticação falhou).")

    posicoes_url = f"{SPTRANS_API_BASE_URL}/Posicao/Linha"
    try:
        response = requests.get(posicoes_url, params={"codigoLinha": codigo_linha}, headers={"Cookie": f"apiCredentials={sptrans_auth_token}"})
        response.raise_for_status()
        posicoes_data = response.json()
        return SPTransPosicoesResponse(**posicoes_data)
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Erro ao buscar posições SPTrans: {str(e)}")

@app.get("/health")
async def health_check():
    return {"status": "ok", "api_version": app.version}
# C:\Users\Alessandro\Downloads\gpt-de-favela-api\main.py

# --- Importações Necessárias ---
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Dict, Union
import os
import googlemaps
# from google.cloud import secretmanager # TEMPORARIAMENTE COMENTADO PARA DIAGNÓSTICO
# from google.oauth2 import service_account # TEMPORARIAMENTE COMENTADO PARA DIAGNÓSTICO
import requests

# --- Configuração do Google Cloud Project ---
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT_ID", "gpt-favela")

# --- Inicialização do Cliente do Secret Manager ---
# TEMPORARIAMENTE DESABILITADO PARA DIAGNÓSTICO
secret_manager_client = None
print("DIAGNOSTICO: Cliente Secret Manager TEMPORARIAMENTE desabilitado na inicialização.")


# --- Função para Acessar Segredos ---
# TEMPORARIAMENTE MODIFICADO PARA DIAGNÓSTICO: Não acessa o Secret Manager real
def access_secret_version(secret_id: str, version_id: str = "latest") -> str:
    print(f"DIAGNOSTICO: Retornando chave DUMMY para '{secret_id}'.")
    return "DUMMY_KEY_FOR_DIAGNOSTIC_ONLY"

# --- Carrega as Chaves de API ---
try:
    # NOVO: Usaremos chaves DUMMY para diagnóstico
    GOOGLE_MAPS_API_KEY = access_secret_version("google-maps-api-key") # Apenas para manter a estrutura de chamada
    print("DEBUG: Chave do Google Maps API carregada (DIAGNÓSTICO).")
    SPTRANS_OLHO_VIVO_API_KEY = access_secret_version("sptrans-olho-vivo-api-key") # Apenas para manter a estrutura de chamada
    print("DEBUG: Chave da SPTrans Olho Vivo API carregada (DIAGNÓSTICO).")
except RuntimeError as e:
    print(f"A aplicação não pode iniciar sem as chaves de API necessárias. Erro: {e}. Saindo.")
    exit(1)

# --- Inicialização dos Clientes de API ---
# Se a chave for DUMMY_KEY, o cliente googlemaps pode falhar em chamadas reais, mas o objetivo é iniciar o app.
gmaps = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)
print("DEBUG: Cliente Google Maps 'gmaps' inicializado com sucesso (DIAGNÓSTICO).")

# NOVO: Configurações e Cliente para SPTrans Olho Vivo API
SPTRANS_API_BASE_URL = "http://api.olhovivo.sptrans.com.br/v2.1"
sptrans_auth_token = None

# --- Funções Auxiliares para SPTrans API ---
# Temporariamente modificada para não tentar autenticar com chave real
def authenticate_sptrans():
    print("DIAGNOSTICO: Autenticação SPTrans TEMPORARIAMENTE desabilitada. Retornando True.")
    return True # Simula autenticação bem-sucedida para permitir que o app inicie.

# Autenticar a SPTrans na inicialização da API
if not authenticate_sptrans():
    print("ERRO CRÍTICO: Não foi possível autenticar na API SPTrans. A aplicação não pode continuar.")

# --- Configuração do FastAPI ---
app = FastAPI(
    title="API GPT de Favela - Geolocalização e Transporte Público (DIAGNÓSTICO)",
    description="API de diagnóstico temporária para explorar funcionalidades de geolocalização e transporte público de SP.",
    version="0.2.1-DIAGNOSTICO", # NOVO: Versão atualizada da API
)

# --- Modelos Pydantic para Validação de Dados (EXISTENTES) ---
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

# NOVO: Modelos Pydantic para SPTrans Olho Vivo (EXISTENTES)
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

# --- Endpoints da API (EXISTENTES) ---

@app.get("/")
async def read_root():
    return {"message": "Bem-vindo à API de Geolocalização e Transporte Público do GPT de Favela! Versão 0.2.1-DIAGNÓSTICO"}

@app.get("/geocode/address", response_model=List[AddressGeocodeResponse])
async def geocode_address(address: str = Query(..., description="Endereço a ser convertido em coordenadas (ex: 'Avenida Paulista, 1578, São Paulo').")):
    try:
        # Se a chave for DUMMY_KEY, esta chamada falhará na integração com a Google Maps API.
        # Mas o objetivo é ver se o app inicia.
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

# NOVO: Endpoints para SPTrans Olho Vivo API
@app.get("/sptrans/linhas", response_model=List[SPTransLinha])
async def get_sptrans_linhas(termo_busca: str = Query(..., description="Termo de busca para linhas de ônibus (ex: 'paulista', '8700').")):
    if not sptrans_auth_token:
        raise HTTPException(status_code=503, detail="Serviço SPTrans indisponível (autenticação falhou).")

    search_url = f"{SPTRANS_API_BASE_URL}/Linha/Buscar"
    try:
        # Não tentará autenticar com chave real
        response = requests.get(search_url, params={"termosBusca": termo_busca})
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
        # Não tentará autenticar com chave real
        response = requests.get(posicoes_url, params={"codigoLinha": codigo_linha})
        response.raise_for_status()
        posicoes_data = response.json()

        if 'vs' in posicoes_data:
            for veiculo in posicoes_data['vs']:
                if 'l' in veiculo and isinstance(veiculo['l'], str):
                    veiculo['l'] = veiculo['l'].lower() == 'true'
        return SPTransPosicoesResponse(**posicoes_data)
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Erro ao buscar posições SPTrans: {str(e)}")

@app.get("/health")
async def health_check():
    return {"status": "ok", "api_version": app.version}
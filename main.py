from fastapi import FastAPI, HTTPException, Query, Path
from pydantic import BaseModel, Field
from typing import List, Optional
import os
import googlemaps
import requests

# --- Configurações Iniciais ---
MAPS_API_KEY_FILE_PATH = "/secrets/google-maps/api_key"
SPTRANS_API_KEY_FILE_PATH = "/secrets/sptrans/api_key"

gmaps_client = None
sptrans_api_key = None
sptrans_session = requests.Session()

# --- Bloco de Inicialização da Aplicação ---
def startup_event():
    global gmaps_client, sptrans_api_key
    try:
        print("INFO: Lendo chave da API do Google Maps...")
        with open(MAPS_API_KEY_FILE_PATH, "r") as f:
            maps_api_key = f.read().strip()
        if maps_api_key:
            gmaps_client = googlemaps.Client(key=maps_api_key)
            print("INFO: Cliente do Google Maps inicializado com sucesso!")
    except Exception as e:
        print(f"AVISO: Não foi possível inicializar o cliente do Google Maps. Erro: {e}")

    try:
        print("INFO: Lendo chave da API da SPTrans...")
        with open(SPTRANS_API_KEY_FILE_PATH, "r") as f:
            sptrans_api_key = f.read().strip()
        if sptrans_api_key:
            print("INFO: Chave da API da SPTrans carregada. Tentando autenticar...")
            if not autenticar_sptrans():
                 print("AVISO: Autenticação inicial com a SPTrans falhou.")
    except Exception as e:
        print(f"AVISO: Não foi possível carregar a chave da SPTrans. Erro: {e}")

def autenticar_sptrans():
    if sptrans_api_key is None:
        return False
    
    auth_url = f"http://api.olhovivo.sptrans.com.br/v2.1/Login/Autenticar?token={sptrans_api_key}"
    try:
        response = sptrans_session.post(auth_url)
        if response.status_code == 200 and response.text.lower() == 'true':
            print("INFO: Autenticação com a SPTrans bem-sucedida.")
            return True
        else:
            print(f"ERRO: Falha na autenticação com a SPTrans. Status: {response.status_code}, Resposta: {response.text}")
            sptrans_session.cookies.clear()
            return False
    except Exception as e:
        print(f"ERRO: Exceção ao autenticar com a SPTrans: {e}")
        return False

# --- Configuração do FastAPI ---
app = FastAPI(
    title="API GPT de Favela - V1.1 (SPTrans Fix)",
    description="API para geolocalização e consulta de transporte público em São Paulo.",
    version="1.1.0",
)

@app.on_event("startup")
async def on_startup():
    startup_event()

# --- Modelos Pydantic ---
class AddressGeocodeResponse(BaseModel):
    original_address: str
    formatted_address: str
    latitude: float
    longitude: float

class LinhaSPTrans(BaseModel):
    cl: int = Field(alias="CodigoLinha")
    lc: bool = Field(alias="Circular")
    lt: str = Field(alias="Letreiro")
    sl: int = Field(alias="Sentido")
    tp: str = Field(alias="DenominacaoTPTS")
    ts: str = Field(alias="DenominacaoTSTP")
    
    class Config:
        populate_by_name = True

class PosicaoVeiculo(BaseModel):
    p: str
    a: bool
    ta: str
    py: float
    px: float

class PosicaoLinha(BaseModel):
    hr: str
    vs: List[PosicaoVeiculo]


# --- Endpoints da API ---
@app.get("/")
def read_root():
    return {"message": "Bem-vindo à API de Geolocalização e Transporte do GPT de Favela!"}

@app.get("/sptrans/linhas", response_model=List[LinhaSPTrans])
def buscar_linhas(termo_busca: str = Query(..., description="Termo para buscar a linha (ex: '8000' ou 'Lapa').")):
    if not sptrans_session.cookies:
        if not autenticar_sptrans():
            raise HTTPException(status_code=503, detail="Serviço SPTrans indisponível (falha na autenticação).")
    try:
        url_busca = f"http://api.olhovivo.sptrans.com.br/v2.1/Linha/Buscar?termosBusca={termo_busca}"
        response = sptrans_session.get(url_busca)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao processar a busca de linha: {str(e)}")

@app.get("/sptrans/posicao/{codigo_linha}", response_model=PosicaoLinha)
def buscar_posicao_linha(codigo_linha: int = Path(..., description="Código da linha (ex: 31690).")):
    if not sptrans_session.cookies:
        if not autenticar_sptrans():
            raise HTTPException(status_code=503, detail="Serviço SPTrans indisponível (falha na autenticação).")
    try:
        # CORREÇÃO DA URL AQUI!
        url_busca = f"http://api.olhovivo.sptrans.com.br/v2.1/Posicao/Linha?codigoLinha={codigo_linha}"
        response = sptrans_session.get(url_busca)
        response.raise_for_status()
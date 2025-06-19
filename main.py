from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Optional
import os
import googlemaps
import requests

# --- Configurações Iniciais ---
# NOVOS CAMINHOS para os segredos montados
MAPS_API_KEY_FILE_PATH = "/secrets/google-maps/api_key"
SPTRANS_API_KEY_FILE_PATH = "/secrets/sptrans/api_key"

gmaps_client = None
sptrans_api_key = None
sptrans_session = requests.Session()

# --- Bloco de Inicialização ---
try:
    print(
        f"INFO: Lendo chave da API do Google Maps do arquivo: {MAPS_API_KEY_FILE_PATH}"
    )
    with open(MAPS_API_KEY_FILE_PATH, "r") as f:
        maps_api_key = f.read().strip()
    if maps_api_key:
        gmaps_client = googlemaps.Client(key=maps_api_key)
        print("INFO: Cliente do Google Maps inicializado com sucesso!")
except Exception as e:
    print(f"AVISO: Não foi possível inicializar o cliente do Google Maps. Erro: {e}")

try:
    print(
        f"INFO: Lendo chave da API da SPTrans do arquivo: {SPTRANS_API_KEY_FILE_PATH}"
    )
    with open(SPTRANS_API_KEY_FILE_PATH, "r") as f:
        sptrans_api_key = f.read().strip()
    if sptrans_api_key:
        print("INFO: Chave da API da SPTrans carregada com sucesso!")
except Exception as e:
    print(f"AVISO: Não foi possível carregar a chave da SPTrans. Erro: {e}")


# --- Lógica da SPTrans ---
def autenticar_sptrans():
    if sptrans_api_key is None:
        print("ERRO: Chave da API SPTrans não está disponível.")
        return False

    url = f"http://api.olhovivo.sptrans.com.br/v2.1/Login/Autenticar?token={sptrans_api_key}"
    try:
        response = sptrans_session.post(url)
        if response.status_code == 200 and response.text.lower() == "true":
            print("INFO: Autenticação com a SPTrans bem-sucedida.")
            return True
        else:
            print(
                f"ERRO: Falha na autenticação com a SPTrans. Status: {response.status_code}, Resposta: {response.text}"
            )
            return False
    except Exception as e:
        print(f"ERRO: Exceção ao autenticar com a SPTrans: {e}")
        return False


# --- Configuração do FastAPI ---
app = FastAPI(
    title="API GPT de Favela - V10 (Final)",
    description="API para geolocalização e transporte público com segredos montados.",
    version="1.0.0",
)


# --- Modelos Pydantic ---
class AddressGeocodeResponse(BaseModel):
    original_address: str
    formatted_address: str
    latitude: float
    longitude: float


class LinhaSPTrans(BaseModel):
    CodigoLinha: int
    Circular: bool
    Letreiro: str
    Sentido: int
    Tipo: str
    DenominacaoTPTS: str
    DenominacaoTSTP: str
    Informacoes: Optional[str] = None


# --- Endpoints da API ---
@app.get("/")
def read_root():
    return {
        "message": "Bem-vindo à API de Geolocalização e Transporte do GPT de Favela!"
    }


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


@app.get("/sptrans/linhas", response_model=List[LinhaSPTrans])
def buscar_linhas(
    termo_busca: str = Query(
        ..., description="Termo para buscar a linha (ex: '8000' ou 'Term. Lapa')."
    )
):
    if not autenticar_sptrans():
        raise HTTPException(
            status_code=503,
            detail="Não foi possível autenticar com o serviço da SPTrans.",
        )

    try:
        url_busca = f"http://api.olhovivo.sptrans.com.br/v2.1/Linha/Buscar?termosBusca={termo_busca}"
        response = sptrans_session.get(url_busca)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Erro ao buscar linha na SPTrans: {e.response.text}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erro interno ao processar a busca de linha: {str(e)}",
        )

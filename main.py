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
# Criamos uma sessão para que os cookies de autenticação sejam mantidos entre as requisições
sptrans_session = requests.Session()


# --- Bloco de Inicialização da Aplicação ---
# Este bloco roda uma única vez quando a API liga
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
        print(
            f"AVISO: Não foi possível inicializar o cliente do Google Maps. Erro: {e}"
        )

    try:
        print("INFO: Lendo chave da API da SPTrans...")
        with open(SPTRANS_API_KEY_FILE_PATH, "r") as f:
            sptrans_api_key = f.read().strip()
        if sptrans_api_key:
            print("INFO: Chave da API da SPTrans carregada. Tentando autenticar...")
            if not autenticar_sptrans():
                print("AVISO: Autenticação inicial com a SPTrans falhou.")
        else:
            print("ERRO CRÍTICO: O arquivo de segredo da SPTrans está vazio.")
    except Exception as e:
        print(f"AVISO: Não foi possível carregar a chave da SPTrans. Erro: {e}")


def autenticar_sptrans():
    """Autentica na API da SPTrans e armazena o cookie de sessão."""
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
    title="API GPT de Favela - V10 (SPTrans)",
    description="API para geolocalização e busca de linhas e posições de ônibus em SP.",
    version="1.0.0",
)


@app.on_event("startup")
async def on_startup():
    startup_event()


# --- Modelos Pydantic Corrigidos ---
class LinhaSPTrans(BaseModel):
    cl: int = Field(alias="CodigoLinha")
    lc: bool = Field(alias="Circular")
    lt: str = Field(alias="Letreiro")
    sl: int = Field(alias="Sentido")
    tp: str = Field(alias="DenominacaoTPTS")
    ts: str = Field(alias="DenominacaoTSTP")

    class Config:
        populate_by_name = True


class Parada(BaseModel):
    cp: int = Field(alias="CodigoParada")
    np: str = Field(alias="Nome")
    ed: str = Field(alias="Endereco")
    py: float = Field(alias="Latitude")
    px: float = Field(alias="Longitude")


class PosicaoVeiculo(BaseModel):
    p: str = Field(alias="Prefixo")
    a: bool = Field(alias="Acessivel")
    ta: str = Field(alias="Hora")
    py: float = Field(alias="Latitude")
    px: float = Field(alias="Longitude")


class PosicaoLinha(BaseModel):
    hr: str = Field(alias="Horario")
    vs: List[PosicaoVeiculo] = Field(alias="Veiculos")


# --- Endpoints da API ---
@app.get("/")
def read_root():
    return {
        "message": "Bem-vindo à API de Geolocalização e Transporte do GPT de Favela!"
    }


@app.get("/sptrans/linhas", response_model=List[LinhaSPTrans])
def buscar_linhas(
    termo_busca: str = Query(
        ..., description="Termo para buscar a linha (ex: '8000' ou 'Lapa')."
    )
):
    if not autenticar_sptrans():
        raise HTTPException(
            status_code=503,
            detail="Serviço SPTrans indisponível (falha na autenticação).",
        )
    try:
        url = f"http://api.olhovivo.sptrans.com.br/v2.1/Linha/Buscar?termosBusca={termo_busca}"
        response = sptrans_session.get(url)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Erro ao processar a busca de linha: {str(e)}"
        )


@app.get("/sptrans/posicao/{codigo_linha}", response_model=PosicaoLinha)
def buscar_posicao_linha(
    codigo_linha: int = Path(..., description="Código da linha (ex: 31690).")
):
    if not autenticar_sptrans():
        raise HTTPException(
            status_code=503,
            detail="Serviço SPTrans indisponível (falha na autenticação).",
        )
    try:
        url = f"http://api.olhovivo.sptrans.com.br/v2.1/Posicao/Linha?codigoLinha={codigo_linha}"
        response = sptrans_session.get(url)
        response.raise_for_status()
        # O Pydantic irá mapear 'Horario' para 'hr' e 'Veiculos' para 'vs' automaticamente.
        return response.json()
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Erro ao buscar posição da linha: {str(e)}"
        )

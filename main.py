# C:\Users\Alessandro\Downloads\gpt-de-favela-api\main.py

# --- Importações Necessárias ---
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Dict, Union
import os
import googlemaps
from google.cloud import secretmanager
from google.oauth2 import service_account
import requests # NOVO: Importa a biblioteca requests para fazer requisições HTTP

# --- Configuração do Google Cloud Project ---
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT_ID", "gpt-favela")

# --- Inicialização do Cliente do Secret Manager ---
CREDENTIALS_FILE_PATH = os.path.join(os.path.dirname(__file__), "credentials.json")
secret_manager_client = None

try:
    if os.path.exists(CREDENTIALS_FILE_PATH):
        print("INFO: Tentando carregar credenciais de service_account do arquivo local.")
        credentials = service_account.Credentials.from_service_account_file(
            CREDENTIALS_FILE_PATH,
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        secret_manager_client = secretmanager.SecretManagerServiceClient(credentials=credentials)
        print("INFO: SecretManagerServiceClient inicializado com sucesso usando arquivo local.")
    else:
        print("AVISO: 'credentials.json' não encontrado. Tentando credenciais padrão (ADC).")
        secret_manager_client = secretmanager.SecretManagerServiceClient()
        print("INFO: SecretManagerServiceClient inicializado com sucesso no modo padrão (ADC).")

except Exception as e:
    print(f"ERRO CRÍTICO: Não foi possível inicializar SecretManagerServiceClient. Erro: {e}")
    raise RuntimeError(f"Falha ao inicializar o cliente Secret Manager: {e}. Verifique as credenciais e permissões.")

# --- Função para Acessar Segredos ---
def access_secret_version(secret_id: str, version_id: str = "latest") -> str:
    name = f"projects/{PROJECT_ID}/secrets/{secret_id}/versions/{version_id}"
    try:
        response = secret_manager_client.access_secret_version(name=name)
        return response.payload.data.decode("UTF-8")
    except Exception as e:
        print(f"ERRO CRÍTICO: Não foi possível acessar o segredo '{secret_id}'.")
        print(f"  - Verifique se a PROJECT_ID no 'main.py' está correta e corresponde ao seu projeto GCP ('{PROJECT_ID}').")
        print(f"  - Verifique se o segredo '{secret_id}' existe no Secret Manager do seu projeto.")
        print(f"  - Verifique se a conta de serviço (ou suas credenciais locais) tem a permissão 'Secret Manager Secret Accessor' para este segredo.")
        raise RuntimeError(f"Falha ao carregar o segredo '{secret_id}'. Detalhes: {e}")

# --- Carrega as Chaves de API ---
try:
    Maps_API_KEY = access_secret_version("google-maps-api-key")
    print("DEBUG: Chave do Google Maps API carregada com sucesso do Secret Manager.")
    # NOVO: Carrega a chave da API Olho Vivo
    SPTRANS_OLHO_VIVO_API_KEY = access_secret_version("sptrans-olho-vivo-api-key")
    print("DEBUG: Chave da SPTrans Olho Vivo API carregada com sucesso do Secret Manager.")
except RuntimeError as e:
    print(f"A aplicação não pode iniciar sem as chaves de API necessárias. Erro: {e}. Saindo.")
    exit(1)

# --- Inicialização dos Clientes de API ---
gmaps = googlemaps.Client(key=Maps_API_KEY)
print("DEBUG: Cliente Google Maps 'gmaps' inicializado com sucesso.")

# NOVO: Configurações e Cliente para SPTrans Olho Vivo API
SPTRANS_API_BASE_URL = "http://api.olhovivo.sptrans.com.br/v2.1"
# Variável global para armazenar o token da SPTrans
sptrans_auth_token = None

# --- Funções Auxiliares para SPTrans API ---
def authenticate_sptrans():
    global sptrans_auth_token
    auth_url = f"{SPTRANS_API_BASE_URL}/Login/Autenticar"
    headers = {"Content-Type": "application/json"} # API espera application/json
    try:
        # A API Olho Vivo geralmente aceita o token no corpo da requisição ou como querystring
        # Vamos tentar como querystring primeiro, que é mais comum em exemplos antigos.
        # Caso contrário, pode ser no corpo como JSON {"token": "SUA_CHAVE"}
        response = requests.post(auth_url, params={"token": SPTRANS_OLHO_VIVO_API_KEY})
        response.raise_for_status() # Lança exceção para erros HTTP (4xx ou 5xx)
        if response.json() is True:
            # A autenticação da SPTrans retorna TRUE para sucesso.
            # O token de sessão é então usado em requisições futuras, mantido por COOKIES.
            # requests.Session() gerencia cookies automaticamente.
            # Não há um "token" explícito para extrair no corpo da resposta
            # O próprio objeto de sessão mantém a autenticação via cookies.
            # Por isso, precisamos de um objeto session global para a SPTrans
            # Como a autenticação é gerenciada por cookies na sessão requests,
            # vamos criar um cliente global que já esteja autenticado.
            print("INFO: Autenticação SPTrans bem-sucedida! Cookies de sessão obtidos.")
            return True
        else:
            print(f"ERRO: Autenticação SPTrans falhou. Resposta: {response.text}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"ERRO: Erro de requisição na autenticação SPTrans: {e}")
        return False

# Autenticar a SPTrans na inicialização da API
# Isso é importante para que as requisições subsequentes já estejam autenticadas.
if not authenticate_sptrans():
    print("ERRO CRÍTICO: Não foi possível autenticar na API SPTrans. A aplicação não pode continuar.")
    # Não vamos sair do app, mas as funções da SPTrans falharão.
    # Em produção, você talvez queira tentar reautenticar nas requisições.

# --- Configuração do FastAPI ---
app = FastAPI(
    title="API GPT de Favela - Geolocalização e Transporte Público", # NOVO: Título atualizado
    description="API para explorar funcionalidades de geolocalização com Google Maps e transporte público de SP.", # NOVO: Descrição atualizada
    version="0.2.0", # NOVO: Versão atualizada da API
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

# NOVO: Modelos Pydantic para SPTrans Olho Vivo
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
    ta: str = Field(..., description="Horário da última atualização da posição do veículo (formato yyyy-MM-dd HH:mm:ss).")
    l: bool = Field(..., description="Indica se a posição é um ponto de ônibus ou um ponto de interesse (true para ponto de ônibus).") # Este campo na API Olho Vivo não é bool, é 'false' ou 'true' string. Se der erro, pode precisar de ajuste.

class SPTransPosicoesResponse(BaseModel):
    hr: str = Field(..., description="Horário da geração das informações (yyyy-MM-dd HH:mm:ss).")
    vs: List[SPTransPosicaoVeiculo] = Field(..., description="Lista de veículos na linha.")

# --- Endpoints da API (EXISTENTES) ---

@app.get("/")
async def read_root():
    return {"message": "Bem-vindo à API de Geolocalização e Transporte Público do GPT de Favela! Versão 0.2.0"}

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

# NOVO: Endpoints para SPTrans Olho Vivo API
@app.get("/sptrans/linhas", response_model=List[SPTransLinha])
async def get_sptrans_linhas(termo_busca: str = Query(..., description="Termo de busca para linhas de ônibus (ex: 'paulista', '8700').")):
    """
    Busca linhas de ônibus da SPTrans pelo termo informado.
    """
    if not sptrans_auth_token: # Verifica se a autenticação falhou na inicialização.
        raise HTTPException(status_code=503, detail="Serviço SPTrans indisponível (autenticação falhou).")

    search_url = f"{SPTRANS_API_BASE_URL}/Linha/Buscar"
    try:
        # A autenticação é mantida por cookies na sessão requests
        # Mas para simplificar aqui, faremos a autenticação por requisição,
        # o que é menos eficiente mas mais robusto para a estrutura atual.
        # Em produção, você teria um mecanismo para reautenticar e usar uma sessão global.
        # Por enquanto, vamos reautenticar a cada chamada para garantir o cookie.
        if not authenticate_sptrans(): # Tenta reautenticar
             raise HTTPException(status_code=503, detail="Falha na reautenticação com SPTrans.")

        response = requests.get(search_url, params={"termosBusca": termo_busca})
        response.raise_for_status()
        linhas_data = response.json()
        return [SPTransLinha(**linha) for linha in linhas_data]
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Erro ao buscar linhas SPTrans: {str(e)}")

@app.get("/sptrans/posicoes/{codigo_linha}", response_model=SPTransPosicoesResponse)
async def get_sptrans_posicoes(codigo_linha: int = Field(..., description="Código identificador da linha (campo 'cl' da linha).")):
    """
    Retorna a posição de todos os veículos de uma linha SPTrans.
    """
    if not sptrans_auth_token: # Verifica se a autenticação falhou na inicialização.
        raise HTTPException(status_code=503, detail="Serviço SPTrans indisponível (autenticação falhou).")

    posicoes_url = f"{SPTRANS_API_BASE_URL}/Posicao/Linha"
    try:
        # Reautentica para garantir o cookie de sessão.
        if not authenticate_sptrans():
            raise HTTPException(status_code=503, detail="Falha na reautenticação com SPTrans.")

        response = requests.get(posicoes_url, params={"codigoLinha": codigo_linha})
        response.raise_for_status()
        posicoes_data = response.json()
        
        # A API SPTrans retorna os veículos sob a chave 'vs' e o horário em 'hr'
        # O campo 'l' em 'vs' pode ser string "true"/"false" e não bool. Ajuste aqui.
        if 'vs' in posicoes_data:
            for veiculo in posicoes_data['vs']:
                if 'l' in veiculo and isinstance(veiculo['l'], str):
                    veiculo['l'] = veiculo['l'].lower() == 'true' # Converte "true"/"false" para bool
        
        return SPTransPosicoesResponse(**posicoes_data)
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Erro ao buscar posições SPTrans: {str(e)}")

@app.get("/health")
async def health_check():
    return {"status": "ok", "api_version": app.version}
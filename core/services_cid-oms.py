import requests
import base64
import time
from django.conf import settings

# Você deve colocar estas chaves no seu settings.py ou variáveis de ambiente
# Cadastre-se em: https://icd.who.int/icdapi/
CLIENT_ID = getattr(settings, 'WHO_API_CLIENT_ID', 'SEU_CLIENT_ID_AQUI')
CLIENT_SECRET = getattr(settings, 'WHO_API_CLIENT_SECRET', 'SEU_CLIENT_SECRET_AQUI')


class WHOConversionService:
    _token = None
    _token_expiry = 0

    @classmethod
    def _get_token(cls):
        """Obtém ou renova o token OAuth2 da OMS"""
        if cls._token and time.time() < cls._token_expiry:
            return cls._token

        token_url = 'https://icdaccessmanagement.who.int/connect/token'
        payload = {'grant_type': 'client_credentials', 'scope': 'icdapi_access'}
        auth_str = f"{CLIENT_ID}:{CLIENT_SECRET}"
        b64_auth = base64.b64encode(auth_str.encode()).decode()

        headers = {
            'Authorization': f'Basic {b64_auth}',
            'Content-Type': 'application/x-www-form-urlencoded'
        }

        try:
            response = requests.post(token_url, data=payload, headers=headers, timeout=5)
            response.raise_for_status()
            data = response.json()
            cls._token = data['access_token']
            cls._token_expiry = time.time() + data['expires_in'] - 60  # Margem de segurança
            return cls._token
        except Exception as e:
            print(f"Erro ao obter token OMS: {e}")
            return None

    @classmethod
    def converter_cid10_para_cid11(cls, cid10_codigo):
        """
        Busca o CID-10 na API da OMS e retorna o CID-11 correspondente (Code ou URI).
        """
        token = cls._get_token()
        if not token:
            return "Erro de Conexão API"

        # Endpoint de pesquisa da versão mais recente (2024-01)
        # A estratégia é pesquisar o código CID-10 como termo
        base_url = "https://id.who.int/icd/release/11/2024-01/mms/search"

        headers = {
            'Authorization': f'Bearer {token}',
            'Accept': 'application/json',
            'Accept-Language': 'en'  # A API responde melhor em inglês para mapeamento técnico, mas pode usar 'pt'
        }

        params = {
            'q': cid10_codigo,
            'useFlexisearch': 'false',  # Busca exata
            'flatResults': 'true'
        }

        try:
            response = requests.get(base_url, headers=headers, params=params, timeout=5)
            if response.status_code == 200:
                data = response.json()
                results = data.get('destinationEntities', [])

                if results:
                    # Pega o primeiro resultado (match mais provável)
                    match = results[0]
                    cid11_code = match.get('theCode', 'Sem Código')
                    title = match.get('title', '')
                    return f"{cid11_code} ({title})"
                else:
                    return "Não encontrado na base CID-11"
            else:
                return f"Erro API: {response.status_code}"
        except Exception as e:
            return f"Falha na requisição: {str(e)}"


# Wrapper para usar no models.py facilmente
def converter_cid10_para_cid11(cid10):
    return WHOConversionService.converter_cid10_para_cid11(cid10)
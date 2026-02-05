# API Sankhya

Documentacao da API do Sankhya Om para integracao via Gateway.

**IMPORTANTE:** O banco de dados e **Oracle**. Use sintaxe Oracle (ROWNUM, NVL, etc).

## Documentacao Oficial

- [Guia de Integracao](https://developer.sankhya.com.br/reference/guia-integracao)
- [Requisicoes via Gateway](https://developer.sankhya.com.br/reference/requisi%C3%A7%C3%B5es-via-gateway)
- [Mapeamento de Servicos](https://developer.sankhya.com.br/reference/mapeamento-de-servi%C3%A7o)
- [Comunidade - DbExplorerSP](https://community.sankhya.com.br/developers/conectividade/post/api---dbexplorersp-executequery-kBAx9OeMMJz0sFJ)

---

## Endpoint Base

```
https://api.sankhya.com.br
```

---

## Autenticacao

A API usa OAuth 2.0 com Client Credentials. Sao necessarias 3 credenciais:

| Credencial | Onde obter |
|------------|------------|
| `client_id` | Area do Desenvolvedor Sankhya |
| `client_secret` | Area do Desenvolvedor Sankhya |
| `X-Token` | Sankhya Om > Configuracoes Gateway |

### Endpoint de Autenticacao

```
POST https://api.sankhya.com.br/authenticate
```

### Headers

| Header | Valor |
|--------|-------|
| `X-Token` | Token do Gateway |
| `Content-Type` | application/x-www-form-urlencoded |

### Body

```
client_id={CLIENT_ID}&client_secret={CLIENT_SECRET}&grant_type=client_credentials
```

### Exemplo cURL

```bash
curl -X POST https://api.sankhya.com.br/authenticate \
  -H "X-Token: seu_x_token_aqui" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "client_id=seu_client_id&client_secret=seu_client_secret&grant_type=client_credentials"
```

### Resposta

```json
{
  "access_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
  "expires_in": 300,
  "token_type": "Bearer"
}
```

**Nota:** O token expira em 300 segundos (5 minutos).

---

## Usando o Token

Apos autenticar, use o `access_token` no header de todas as requisicoes:

```
Authorization: Bearer {access_token}
```

---

## DbExplorerSP.executeQuery

Servico para executar queries SQL no banco do Sankhya. **Apenas SELECT** e permitido.

### Endpoint

```
POST https://api.sankhya.com.br/gateway/v1/mge/service.sbr?serviceName=DbExplorerSP.executeQuery&outputType=json
```

### Headers

| Header | Valor |
|--------|-------|
| `Authorization` | Bearer {access_token} |
| `Content-Type` | application/json |

### Body

```json
{
  "serviceName": "DbExplorerSP.executeQuery",
  "requestBody": {
    "sql": "SELECT TOP 10 * FROM TGFPAR"
  }
}
```

### Exemplo cURL

```bash
curl -X POST "https://api.sankhya.com.br/gateway/v1/mge/service.sbr?serviceName=DbExplorerSP.executeQuery&outputType=json" \
  -H "Authorization: Bearer eyJhbGciOiJSUzI1NiIs..." \
  -H "Content-Type: application/json" \
  -d '{
    "serviceName": "DbExplorerSP.executeQuery",
    "requestBody": {
      "sql": "SELECT TOP 10 CODPARC, NOMEPARC FROM TGFPAR"
    }
  }'
```

### Exemplo Python

```python
import httpx

# Autenticar
auth_response = httpx.post(
    "https://api.sankhya.com.br/authenticate",
    headers={
        "X-Token": "seu_x_token",
        "Content-Type": "application/x-www-form-urlencoded"
    },
    data={
        "client_id": "seu_client_id",
        "client_secret": "seu_client_secret",
        "grant_type": "client_credentials"
    }
)
access_token = auth_response.json()["access_token"]

# Executar query
query_response = httpx.post(
    "https://api.sankhya.com.br/gateway/v1/mge/service.sbr?serviceName=DbExplorerSP.executeQuery&outputType=json",
    headers={
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    },
    json={
        "serviceName": "DbExplorerSP.executeQuery",
        "requestBody": {
            "sql": "SELECT TOP 10 CODPARC, NOMEPARC FROM TGFPAR"
        }
    }
)
print(query_response.json())
```

---

## Limites e Restricoes

| Restricao | Valor |
|-----------|-------|
| Registros por query | 5.000 max |
| Tempo de expiracao do token | 300 segundos |
| Operacoes permitidas | Apenas SELECT |

---

## Variaveis de Ambiente (.env)

```env
# Sankhya API
SANKHYA_CLIENT_ID=seu_client_id
SANKHYA_CLIENT_SECRET=seu_client_secret
SANKHYA_X_TOKEN=seu_x_token
```

---

## Modulos Disponiveis

| Modulo | Descricao |
|--------|-----------|
| `mge` | Cadastros gerais (parceiros, produtos, etc) |
| `mgecom` | Comercial (pedidos, notas) |
| `mgefin` | Financeiro |
| `mgewms` | WMS |

O endpoint segue o padrao:
```
/gateway/v1/{modulo}/service.sbr?serviceName={servico}
```

---

## Servicos Uteis

| Servico | Descricao |
|---------|-----------|
| `DbExplorerSP.executeQuery` | Executa SQL SELECT |
| `CRUDServiceProvider.loadRecords` | Carrega registros de uma entidade |
| `CRUDServiceProvider.saveRecord` | Salva registro |
| `DatasetSP.loadRecords` | Carrega dataset |

---

*Atualizado em: 2026-02-05*

# Sankhya MCP Server

MCP Server para integração com o Sankhya ERP. Permite consultar o banco de dados através do Claude Desktop.

## Ferramentas Disponíveis

| Ferramenta | Descrição |
|------------|-----------|
| `executar_query` | Executa SQL SELECT no Sankhya |
| `listar_tabelas` | Lista tabelas do banco (com filtro opcional) |
| `descrever_tabela` | Mostra campos, tipos e comentários de uma tabela |
| `buscar_chaves` | Mostra PKs e FKs de uma tabela |
| `buscar_valores_dominio` | Lista valores distintos de um campo |
| `sample_dados` | Retorna amostra de dados de uma tabela |

## Instalação

### 1. Instalar dependências

```bash
pip install mcp httpx python-dotenv
```

### 2. Configurar variáveis de ambiente

Copie o arquivo `.env.example` para `.env` e preencha:

```bash
cp .env.example .env
```

Edite o `.env` com suas credenciais:

```env
SANKHYA_BASE_URL=https://api.sankhya.com.br
SANKHYA_TOKEN=seu_token_aqui
SANKHYA_APP_KEY=sua_app_key_aqui
```

### 3. Testar o servidor

```bash
cd src/mcp
python server.py
```

## Configuração no Claude Desktop

Adicione ao arquivo `claude_desktop_config.json`:

**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "sankhya": {
      "command": "python",
      "args": ["C:/caminho/para/mmarra-data-hub-v3/src/mcp/server.py"],
      "env": {
        "SANKHYA_BASE_URL": "https://api.sankhya.com.br",
        "SANKHYA_TOKEN": "seu_token_aqui",
        "SANKHYA_APP_KEY": "sua_app_key_aqui"
      }
    }
  }
}
```

> **Nota:** Substitua `C:/caminho/para/` pelo caminho real do projeto.

## Exemplos de Uso

Após configurar, você pode pedir ao Claude:

- "Liste as tabelas que começam com TGF"
- "Descreva a tabela TGFCAB"
- "Quais são as chaves da tabela TGFITE?"
- "Mostre os valores distintos do campo TIPMOV na TGFCAB"
- "Traga uma amostra de 5 registros da TGFPAR"
- "Execute: SELECT TOP 10 CODPARC, NOMEPARC FROM TGFPAR"

## Segurança

- Apenas queries SELECT são permitidas
- O token nunca é exposto nas respostas
- Limite de 100 registros por consulta

## Troubleshooting

### Erro de conexão
Verifique se a URL base está correta e acessível.

### Erro de autenticação
Confirme se o token e app key estão corretos.

### Timeout
A API tem timeout de 60 segundos. Queries muito pesadas podem falhar.

# Dynatrace Metrics V2 API Simulator

Simulador da API de Métricas V2 do Dynatrace para testes e desenvolvimento.

## � Documentação

- **[README.md](README.md)** - Documentação principal (você está aqui)
- **[DOCKER.md](DOCKER.md)** - Guia completo de Docker e deployment
- **[EXAMPLES.md](EXAMPLES.md)** - Exemplos práticos de requisições
- **[AUTHENTICATION_SUMMARY.md](AUTHENTICATION_SUMMARY.md)** - Resumo da implementação de autenticação

## �🚀 Quick Start

### Com Docker (Recomendado)

```bash
# Clone o repositório e navegue até a pasta
cd simulator_metric_dynatrace

# Inicie o simulador
docker-compose up -d

# Teste a API
curl -H "Authorization: Api-Token test-token" \
  "http://localhost:8080/api/v2/metrics"
```

### Sem Docker

```bash
# Instale as dependências
pip install -r requirements.txt

# Inicie o servidor
python app.py

# Teste em outro terminal
curl -H "Authorization: Api-Token test-token" \
  "http://localhost:8080/api/v2/metrics"
```

## Funcionalidades

Este simulador implementa os seguintes endpoints da API Dynatrace Metrics V2:

- **GET /api/v2/metrics** - Lista todas as métricas disponíveis
- **GET /api/v2/metrics/{metricId}** - Obtém dados de pontos de uma métrica específica
- **POST /api/v2/metrics/query** - Consulta métricas (endpoint alternativo)
- **GET /health** - Verificação de saúde do serviço

## Métricas Simuladas

O simulador fornece as seguintes métricas mock:

- `builtin:host.cpu.usage` - Uso de CPU (%)
- `builtin:host.mem.usage` - Uso de memória (%)
- `builtin:service.response.time` - Tempo de resposta (μs)
- `builtin:service.request.count` - Contagem de requisições
- `builtin:host.disk.avail` - Espaço em disco disponível (bytes)

## Instalação

### Pré-requisitos

**Opção Docker:**
- Docker 20.10+
- Docker Compose 1.29+

**Opção Python:**
- Python 3.7 ou superior
- pip

### Passos de instalação

1. Navegue até o diretório do simulador:
```bash
cd simulator_metric_dynatrace
```

2. Crie um ambiente virtual (recomendado):
```bash
python3 -m venv venv
source venv/bin/activate  # No Linux/Mac
# ou
venv\Scripts\activate  # No Windows
```

3. Instale as dependências:
```bash
pip install -r requirements.txt
```

4. Configure os tokens de API (opcional):
```bash
cp .env.example .env
# Edite .env e adicione seus tokens personalizados
```

## Autenticação

O simulador implementa o mesmo mecanismo de autenticação da API oficial do Dynatrace:

- **Método**: API Token no header `Authorization`
- **Formato**: `Api-Token {seu-token}`

### Tokens padrão

Por padrão, os seguintes tokens são aceitos:
- `dt0c01.sample.token1`
- `dt0c01.sample.token2`
- `test-token`

### Configurar tokens personalizados

Você pode configurar tokens personalizados via variável de ambiente:

```bash
export DT_API_TOKENS="token1,token2,token3"
python app.py
```

Ou usando um arquivo `.env`:
```bash
DT_API_TOKENS=meu-token-customizado,outro-token
```

## Uso

### Opção 1: Executar com Docker (Recomendado)

#### Usando Make (mais fácil)

```bash
# Ver todos os comandos disponíveis
make help

# Iniciar o simulador
make up

# Ver logs
make logs

# Testar a API
make test

# Parar o simulador
make down

# Reiniciar
make restart

# Ver status
make status
```

#### Usando Docker Compose

```bash
# Iniciar o simulador
docker-compose up -d

# Ver logs
docker-compose logs -f

# Parar o simulador
docker-compose down
```

#### Usando Docker diretamente

```bash
# Build da imagem
docker build -t dynatrace-simulator .

# Executar container
docker run -d \
  --name dynatrace-simulator \
  -p 8080:8080 \
  -e DT_API_TOKENS="test-token,custom-token" \
  dynatrace-simulator

# Ver logs
docker logs -f dynatrace-simulator

# Parar container
docker stop dynatrace-simulator
docker rm dynatrace-simulator
```

#### Personalizar tokens via Docker Compose

Edite o arquivo `docker-compose.yaml` e modifique a variável `DT_API_TOKENS`:

```yaml
environment:
  - DT_API_TOKENS=meu-token-1,meu-token-2,meu-token-3
```

### Opção 2: Executar localmente (Python)

```bash
python app.py
```

O servidor será iniciado em `http://localhost:8080`

### Exemplos de uso

**Nota**: Todas as requisições requerem autenticação via API Token.

#### 1. Listar todas as métricas

```bash
curl -H "Authorization: Api-Token test-token" \
  "http://localhost:8080/api/v2/metrics"
```

#### 2. Listar métricas com filtro de texto

```bash
curl -H "Authorization: Api-Token test-token" \
  "http://localhost:8080/api/v2/metrics?text=cpu"
```

#### 3. Obter dados de pontos de uma métrica

```bash
# Exemplo com timestamps (últimas 24 horas)
FROM=$(date -d '1 day ago' +%s)000
TO=$(date +%s)000

curl -H "Authorization: Api-Token test-token" \
  "http://localhost:8080/api/v2/metrics/builtin:host.cpu.usage?from=$FROM&to=$TO&resolution=5m"
```

#### 4. Obter dados com timestamps específicos

```bash
# De 1 hora atrás até agora, com resolução de 1 minuto
curl -H "Authorization: Api-Token test-token" \
  "http://localhost:8080/api/v2/metrics/builtin:host.cpu.usage?from=1699500000000&to=1699503600000&resolution=1m"
```

#### 5. Query com POST

```bash
curl -X POST http://localhost:8080/api/v2/metrics/query \
  -H "Authorization: Api-Token test-token" \
  -H "Content-Type: application/json" \
  -d '{
    "metricSelector": "builtin:host.cpu.usage",
    "from": 1699500000000,
    "to": 1699503600000,
    "resolution": "5m"
  }'
```

#### 6. Exemplo de erro de autenticação

```bash
# Sem token - retorna 401
curl "http://localhost:8080/api/v2/metrics"

# Token inválido - retorna 401
curl -H "Authorization: Api-Token token-invalido" \
  "http://localhost:8080/api/v2/metrics"

# Formato incorreto - retorna 401
curl -H "Authorization: Bearer test-token" \
  "http://localhost:8080/api/v2/metrics"
```

## Parâmetros de Query

### GET /api/v2/metrics

- `metricSelector` (opcional): Filtro de seletor de métrica
- `text` (opcional): Filtro de busca por texto
- `fields` (opcional): Campos a serem retornados
- `pageSize` (opcional): Número de resultados por página (padrão: 500)

### GET /api/v2/metrics/{metricId}

- `from` (obrigatório): Timestamp inicial em milissegundos
- `to` (opcional): Timestamp final em milissegundos (padrão: agora)
- `resolution` (opcional): Resolução dos dados (valores: "1m", "5m", "1h", "1d")
- `entitySelector` (opcional): Filtro por entidades

## Formato de Resposta

### List Metrics Response

```json
{
  "totalCount": 5,
  "nextPageKey": null,
  "metrics": [
    {
      "metricId": "builtin:host.cpu.usage",
      "displayName": "CPU usage %",
      "description": "Percentage of CPU used",
      "unit": "Percent",
      "aggregationTypes": ["avg", "min", "max"],
      "defaultAggregation": {
        "type": "avg"
      },
      "dimensionDefinitions": [...],
      "entityType": ["HOST"]
    }
  ]
}
```

### Get Data Points Response

```json
{
  "totalCount": 1,
  "nextPageKey": null,
  "resolution": "1m",
  "result": [
    {
      "metricId": "builtin:host.cpu.usage",
      "dataPointCountRatio": 1.0,
      "dimensionCountRatio": 1.0,
      "data": [
        {
          "dimensions": [],
          "dimensionMap": {},
          "timestamps": [1699500000000, 1699500060000, ...],
          "values": [45.2, 47.8, ...]
        }
      ]
    }
  ]
}
```

## Estrutura do Projeto

```
simulator_metric_dynatrace/
├── app.py                    # Aplicação Flask principal
├── mock_data.py              # Dados mock e geração de pontos de dados
├── requirements.txt          # Dependências Python
├── Dockerfile                # Imagem Docker
├── docker-compose.yaml       # Configuração Docker Compose
├── Makefile                  # Comandos Make para facilitar uso
├── .dockerignore             # Arquivos ignorados pelo Docker
├── .gitignore                # Arquivos ignorados pelo Git
├── .env.example              # Exemplo de configuração
├── test_auth.py              # Script de teste de autenticação
├── README.md                 # Esta documentação
├── DOCKER.md                 # Guia completo Docker
├── EXAMPLES.md               # Exemplos de requisições
└── AUTHENTICATION_SUMMARY.md # Resumo da autenticação
```

## Testes

### Testar autenticação (local)

Execute o script de teste para verificar se a autenticação está funcionando corretamente:

```bash
# Com o servidor rodando em outro terminal
python test_auth.py
```

### Testar com Docker

```bash
# Inicie o container
docker-compose up -d

# Execute o teste
python test_auth.py

# Ou teste manualmente com curl
curl -H "Authorization: Api-Token test-token" \
  "http://localhost:8080/api/v2/metrics"
```

O script testará:
- ✗ Requisição sem token (deve falhar com 401)
- ✗ Requisição com formato inválido (deve falhar com 401)
- ✗ Requisição com token inválido (deve falhar com 401)
- ✓ Listar métricas com token válido
- ✓ Obter dados de pontos com token válido
- ✓ Query POST com token válido

## Desenvolvimento

### Adicionar novas métricas

Edite o arquivo `mock_data.py` e adicione novos objetos de métrica à lista `METRICS`:

```python
{
    "metricId": "custom:my.metric",
    "displayName": "My Custom Metric",
    "description": "Description of my metric",
    "unit": "Count",
    "aggregationTypes": ["avg", "sum"],
    "transformations": [],
    "defaultAggregation": {
        "type": "avg"
    },
    "dimensionDefinitions": [],
    "entityType": ["CUSTOM"]
}
```

### Modificar geração de dados

A função `get_mock_data_points()` em `mock_data.py` gera valores aleatórios. Você pode modificá-la para gerar padrões de dados específicos.

### Adicionar novos tokens de API

Edite o arquivo `.env` ou defina a variável de ambiente `DT_API_TOKENS`:

```bash
# No arquivo .env
DT_API_TOKENS=token1,token2,token3,meu-token-personalizado
```

## Integração com Grafana

Para usar este simulador com o plugin Dynatrace do Grafana:

1. Inicie o simulador: `python app.py`
2. Configure o datasource no Grafana:
   - URL: `http://localhost:8080`
   - API Token: use um dos tokens válidos (ex: `test-token`)
3. Use as métricas disponíveis para criar dashboards

**Nota**: Certifique-se de configurar corretamente o token de API no Grafana, pois todas as requisições requerem autenticação.

## Respostas de Erro

### 401 Unauthorized

Quando a autenticação falha, o simulador retorna:

```json
{
  "error": {
    "code": 401,
    "message": "Missing Authorization header. Expected format: 'Api-Token {token}'"
  }
}
```

ou

```json
{
  "error": {
    "code": 401,
    "message": "Invalid API token"
  }
}
```

## Limitações

- Os dados são gerados aleatoriamente e não refletem métricas reais
- Paginação simplificada (não implementada completamente)
- Filtros de entidades são básicos
- Autenticação simplificada (apenas validação de token, sem rate limiting ou expiração)

## Licença

Este é um projeto de simulação para desenvolvimento e testes.

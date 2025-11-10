# Exemplos de Requisições - Dynatrace API Simulator

Este arquivo contém exemplos práticos de uso da API.

## Variáveis de Ambiente

```bash
export API_URL="http://localhost:8080"
export API_TOKEN="test-token"
```

## 1. Health Check

```bash
curl "$API_URL/health"
```

**Resposta:**
```json
{
  "status": "ok",
  "message": "Dynatrace API Simulator is running"
}
```

## 2. Listar Todas as Métricas

```bash
curl -H "Authorization: Api-Token $API_TOKEN" \
  "$API_URL/api/v2/metrics"
```

## 3. Listar Métricas com Filtro de Texto

```bash
# Buscar métricas relacionadas a CPU
curl -H "Authorization: Api-Token $API_TOKEN" \
  "$API_URL/api/v2/metrics?text=cpu"

# Buscar métricas de serviço
curl -H "Authorization: Api-Token $API_TOKEN" \
  "$API_URL/api/v2/metrics?text=service"
```

## 4. Listar Métricas com Metric Selector

```bash
curl -H "Authorization: Api-Token $API_TOKEN" \
  "$API_URL/api/v2/metrics?metricSelector=builtin:host"
```

## 5. Obter Dados de Pontos (Última Hora)

```bash
# Calcular timestamps
FROM=$(date -d '1 hour ago' +%s)000
TO=$(date +%s)000

# Fazer requisição
curl -H "Authorization: Api-Token $API_TOKEN" \
  "$API_URL/api/v2/metrics/builtin:host.cpu.usage?from=$FROM&to=$TO&resolution=1m"
```

## 6. Obter Dados de Pontos (Últimas 24 horas, resolução 5 minutos)

```bash
FROM=$(date -d '1 day ago' +%s)000
TO=$(date +%s)000

curl -H "Authorization: Api-Token $API_TOKEN" \
  "$API_URL/api/v2/metrics/builtin:host.cpu.usage?from=$FROM&to=$TO&resolution=5m"
```

## 7. Obter Dados com Timestamps Específicos

```bash
# Timestamps em milissegundos
curl -H "Authorization: Api-Token $API_TOKEN" \
  "$API_URL/api/v2/metrics/builtin:service.response.time?from=1699500000000&to=1699503600000&resolution=1m"
```

## 8. Query POST - Métrica de CPU

```bash
FROM=$(date -d '1 hour ago' +%s)000
TO=$(date +%s)000

curl -X POST "$API_URL/api/v2/metrics/query" \
  -H "Authorization: Api-Token $API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "metricSelector": "builtin:host.cpu.usage",
    "from": '$FROM',
    "to": '$TO',
    "resolution": "5m"
  }'
```

## 9. Query POST - Métrica de Memória

```bash
FROM=$(date -d '6 hours ago' +%s)000
TO=$(date +%s)000

curl -X POST "$API_URL/api/v2/metrics/query" \
  -H "Authorization: Api-Token $API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "metricSelector": "builtin:host.mem.usage",
    "from": '$FROM',
    "to": '$TO',
    "resolution": "1h"
  }'
```

## 10. Múltiplas Métricas em Sequência

```bash
FROM=$(date -d '1 hour ago' +%s)000
TO=$(date +%s)000

# CPU Usage
echo "=== CPU Usage ==="
curl -s -H "Authorization: Api-Token $API_TOKEN" \
  "$API_URL/api/v2/metrics/builtin:host.cpu.usage?from=$FROM&to=$TO&resolution=5m" \
  | python -m json.tool

# Memory Usage
echo -e "\n=== Memory Usage ==="
curl -s -H "Authorization: Api-Token $API_TOKEN" \
  "$API_URL/api/v2/metrics/builtin:host.mem.usage?from=$FROM&to=$TO&resolution=5m" \
  | python -m json.tool

# Response Time
echo -e "\n=== Response Time ==="
curl -s -H "Authorization: Api-Token $API_TOKEN" \
  "$API_URL/api/v2/metrics/builtin:service.response.time?from=$FROM&to=$TO&resolution=5m" \
  | python -m json.tool
```

## Exemplos de Erros de Autenticação

### Sem Token (401 Unauthorized)

```bash
curl -v "$API_URL/api/v2/metrics"
```

**Resposta:**
```json
{
  "error": {
    "code": 401,
    "message": "Missing Authorization header. Expected format: 'Api-Token {token}'"
  }
}
```

### Formato Inválido (401 Unauthorized)

```bash
curl -v -H "Authorization: Bearer $API_TOKEN" \
  "$API_URL/api/v2/metrics"
```

**Resposta:**
```json
{
  "error": {
    "code": 401,
    "message": "Invalid Authorization header format. Expected format: 'Api-Token {token}'"
  }
}
```

### Token Inválido (401 Unauthorized)

```bash
curl -v -H "Authorization: Api-Token invalid-token-xyz" \
  "$API_URL/api/v2/metrics"
```

**Resposta:**
```json
{
  "error": {
    "code": 401,
    "message": "Invalid API token"
  }
}
```

## Script Bash Completo para Testes

```bash
#!/bin/bash

API_URL="http://localhost:8080"
API_TOKEN="test-token"

echo "======================================"
echo "Dynatrace API Simulator - Testes"
echo "======================================"

# Health check
echo -e "\n1. Health Check"
curl -s "$API_URL/health" | python -m json.tool

# List metrics
echo -e "\n2. Listar Métricas"
curl -s -H "Authorization: Api-Token $API_TOKEN" \
  "$API_URL/api/v2/metrics" | python -m json.tool

# Get data points
FROM=$(date -d '1 hour ago' +%s)000
TO=$(date +%s)000

echo -e "\n3. Obter Dados de CPU (última hora)"
curl -s -H "Authorization: Api-Token $API_TOKEN" \
  "$API_URL/api/v2/metrics/builtin:host.cpu.usage?from=$FROM&to=$TO&resolution=5m" \
  | python -m json.tool

echo -e "\n======================================"
echo "Testes concluídos!"
echo "======================================"
```

Salve como `test_requests.sh` e execute:
```bash
chmod +x test_requests.sh
./test_requests.sh
```

## Usando com Grafana

1. Configure o Data Source no Grafana:
   - **Type**: Dynatrace
   - **URL**: `http://localhost:8080` (ou `http://dynatrace-simulator:8080` se Grafana estiver em Docker)
   - **API Token**: `test-token`

2. Crie um painel e use as métricas:
   - `builtin:host.cpu.usage`
   - `builtin:host.mem.usage`
   - `builtin:service.response.time`
   - etc.

## Usando com Postman

Importe a seguinte coleção:

**Headers:**
- `Authorization`: `Api-Token test-token`
- `Content-Type`: `application/json` (para POST)

**Variáveis:**
- `base_url`: `http://localhost:8080`
- `api_token`: `test-token`

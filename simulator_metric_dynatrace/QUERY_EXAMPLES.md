# Dynatrace Metrics Query Examples

Este documento contém exemplos de queries suportadas pelo simulador.

## Endpoint: GET /api/v2/metrics/query

### Exemplo 1: Query Simples
Busca uma métrica sem filtros:

```bash
curl -H "Authorization: Api-Token test-token" \
  "http://localhost:8080/api/v2/metrics/query?metricSelector=builtin:host.cpu.usage"
```

### Exemplo 2: Query com Período de Tempo
Especifica período com `from` e `to`:

```bash
curl -H "Authorization: Api-Token test-token" \
  "http://localhost:8080/api/v2/metrics/query?metricSelector=builtin:host.cpu.usage&from=1699500000000&to=1699503600000&resolution=5m"
```

### Exemplo 3: Query com Filtro Simples
Filtra por entidade específica:

```bash
curl -H "Authorization: Api-Token test-token" \
  "http://localhost:8080/api/v2/metrics/query?metricSelector=builtin:host.cpu.usage:filter(eq(dt.entity.host,HOST-1234567890))"
```

### Exemplo 4: Query Complexa com Múltiplos Filtros
Exemplo similar ao da documentação do Dynatrace:

```bash
curl -H "Authorization: Api-Token test-token" \
  "http://localhost:8080/api/v2/metrics/query?metricSelector=builtin:apps.other.crashCount.osAndVersion:filter(and(or(in(\"dt.entity.os\",entitySelector(\"type(os),entityId(~\"OS-62028BEE737F03D4~\")\"))),or(in(\"dt.entity.device_application\",entitySelector(\"type(mobile_application),entityName.equals(~\"Mobile PF - Mobile App~\")\")))))&from=1699500000000&to=1699503600000"
```

### Exemplo 5: Query com SplitBy e Sort
Agrupa e ordena os resultados:

```bash
curl -H "Authorization: Api-Token test-token" \
  "http://localhost:8080/api/v2/metrics/query?metricSelector=builtin:apps.other.crashCount.osAndVersion:filter(and(or(in(\"dt.entity.os\",entitySelector(\"type(os)\"))),or(in(\"dt.entity.device_application\",entitySelector(\"type(mobile_application)\"))))):splitBy():sort(value(auto,descending))"
```

## Formato da Resposta

### Resposta sem SplitBy

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
          "timestamps": [1699500000000, 1699500060000, 1699500120000],
          "values": [45.2, 48.7, 52.1]
        }
      ]
    }
  ]
}
```

### Resposta com SplitBy

```json
{
  "totalCount": 1,
  "nextPageKey": null,
  "resolution": "1m",
  "result": [
    {
      "metricId": "builtin:apps.other.crashCount.osAndVersion",
      "dataPointCountRatio": 1.0,
      "dimensionCountRatio": 1.0,
      "data": [
        {
          "dimensions": ["dt.entity.device_application"],
          "dimensionMap": {
            "dt.entity.device_application": "MOBILE_APPLICATION-1234567890ABCDEF"
          },
          "timestamps": [1699500000000, 1699500060000, 1699500120000],
          "values": [5, 3, 7]
        }
      ]
    }
  ]
}
```

## Sintaxe do MetricSelector

O `metricSelector` suporta a seguinte sintaxe:

```
metricId[:transformation1][:transformation2]...
```

### Transformações Suportadas (Simuladas)

1. **filter(...)** - Filtra dados por condições
   - Exemplo: `:filter(eq(dt.entity.host,HOST-123))`
   - Exemplo complexo: `:filter(and(or(in("dt.entity.os",entitySelector(...)))))`

2. **splitBy(...)** - Agrupa dados por dimensões
   - Exemplo: `:splitBy("dt.entity.device_application")`
   - Sem parâmetros: `:splitBy()`

3. **sort(...)** - Ordena os resultados
   - Exemplo: `:sort(value(auto,descending))`
   - Exemplo: `:sort(dimension("dt.entity.host",ascending))`

## Notas de Implementação

O simulador implementa **parsing simplificado** dos filtros:
- Detecta a presença de `:filter(`, `:splitBy(` e `:sort(`
- Extrai o `metricId` base (antes do primeiro `:`)
- Adapta a resposta baseado nas transformações detectadas
- Sempre retorna dados mock (não filtra dados reais)

Para queries complexas, o simulador:
1. Extrai o `metricId` base
2. Busca a métrica correspondente no mock data
3. Gera dados aleatórios apropriados
4. Formata a resposta de acordo com as transformações detectadas

## Métricas Disponíveis

- `builtin:host.cpu.usage` - CPU usage %
- `builtin:host.mem.usage` - Memory usage %
- `builtin:service.response.time` - Response time
- `builtin:service.request.count` - Request count
- `builtin:host.disk.avail` - Available disk space
- `builtin:apps.other.crashCount.osAndVersion` - App crash count by OS and version

## Testando com curl

```bash
# Teste simples
curl -H "Authorization: Api-Token test-token" \
  "http://localhost:8080/api/v2/metrics/query?metricSelector=builtin:host.cpu.usage"

# Teste com filtro complexo
curl -H "Authorization: Api-Token test-token" \
  "http://localhost:8080/api/v2/metrics/query?metricSelector=builtin:apps.other.crashCount.osAndVersion:filter(and(or(in(\"dt.entity.device_application\",entitySelector(\"type(mobile_application)\"))))):splitBy():sort(value(auto,descending))"
```

## Testando com POST

```bash
curl -X POST \
  -H "Authorization: Api-Token test-token" \
  -H "Content-Type: application/json" \
  -d '{
    "metricSelector": "builtin:host.cpu.usage:filter(eq(dt.entity.host,HOST-123))",
    "from": 1699500000000,
    "to": 1699503600000,
    "resolution": "5m"
  }' \
  "http://localhost:8080/api/v2/metrics/query"
```

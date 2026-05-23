# Dynatrace Query Examples

Este documento contém exemplos de queries suportadas pelo simulador, tanto para o endpoint de **métricas** (`/api/v2/metrics/query`) quanto para o endpoint de **logs** (`/api/v2/logs/search`, sintaxe inspirada em **DQL** — Dynatrace Query Language).

> Em todos os exemplos o token é `test-token` (definido em `DT_API_TOKENS`). Use qualquer token configurado na variável de ambiente do container.

---

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

---

## Endpoint: GET|POST /api/v2/logs/search (DQL)

O simulador implementa um parser **DQL simplificado** que cobre os padrões mais usados em logs no Dynatrace SaaS. Os filtros suportados são:

| Sintaxe                              | Significado                                        |
| ------------------------------------ | -------------------------------------------------- |
| `palavra`                            | Filtro "contains" sobre o campo `content`          |
| `campo="valor"` ou `campo='valor'`   | Igualdade exata em qualquer campo do record        |
| `status=ERROR`                       | Atalho para filtro de severidade                   |
| Combinações (espaço entre cláusulas) | AND implícito entre todas as cláusulas             |

Parâmetros:

- `query`  — string DQL (opcional; vazio retorna todos os logs do intervalo)
- `from`   — início do intervalo (ms epoch **ou** ISO-8601). Default: `now - 2h`
- `to`     — fim do intervalo (ms epoch **ou** ISO-8601). Default: `now`
- `limit`  — máximo de registros (default 1000, máximo 10000)
- `sort`   — `asc` ou `desc` por timestamp (default `desc`)

### Exemplo 1 — DQL Simples: buscar todos os logs

```bash
curl -H "Authorization: Api-Token test-token" \
  "http://localhost:8080/api/v2/logs/search?from=1699500000000&to=1699503600000&limit=50"
```

### Exemplo 2 — DQL Simples: free-text (equivalente a `fetch logs | filter contains(content,"timeout")`)

```bash
curl -H "Authorization: Api-Token test-token" \
  "http://localhost:8080/api/v2/logs/search?query=timeout&from=1699500000000&to=1699503600000"
```

### Exemplo 3 — DQL com filtro de severidade

Equivalente DQL real:

```text
fetch logs
| filter status == "ERROR"
```

Chamada ao simulador:

```bash
curl -H "Authorization: Api-Token test-token" \
  "http://localhost:8080/api/v2/logs/search?query=status%3DERROR&from=1699500000000&to=1699503600000&limit=200"
```

### Exemplo 4 — DQL com filtro por campo

Equivalente DQL real:

```text
fetch logs
| filter host.name == "host-prod-01"
```

Chamada ao simulador:

```bash
curl -G -H "Authorization: Api-Token test-token" \
  --data-urlencode 'query=host.name="host-prod-01"' \
  --data-urlencode 'from=1699500000000' \
  --data-urlencode 'to=1699503600000' \
  "http://localhost:8080/api/v2/logs/search"
```

### Exemplo 5 — DQL com múltiplos filtros (AND implícito)

Equivalente DQL real:

```text
fetch logs
| filter host.name == "host-prod-01"
       and service.name == "api-gateway"
       and status == "ERROR"
| sort timestamp desc
| limit 100
```

Chamada ao simulador:

```bash
curl -G -H "Authorization: Api-Token test-token" \
  --data-urlencode 'query=host.name="host-prod-01" service.name="api-gateway" status=ERROR' \
  --data-urlencode 'from=1699500000000' \
  --data-urlencode 'to=1699503600000' \
  --data-urlencode 'limit=100' \
  --data-urlencode 'sort=desc' \
  "http://localhost:8080/api/v2/logs/search"
```

### Exemplo 6 — DQL Complexa: filtro composto via POST (formato Dynatrace SaaS)

Equivalente DQL real:

```text
fetch logs
| filter k8s.namespace.name == "production"
       and service.name == "billing-service"
       and contains(content, "timeout")
| sort timestamp desc
| limit 500
```

Chamada ao simulador:

```bash
curl -X POST \
  -H "Authorization: Api-Token test-token" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "k8s.namespace.name=\"production\" service.name=\"billing-service\" timeout",
    "from": "2023-11-09T00:00:00.000Z",
    "to":   "2023-11-09T01:00:00.000Z",
    "limit": 500,
    "sort": "desc"
  }' \
  "http://localhost:8080/api/v2/logs/search"
```

### Formato da Resposta (Logs)

```json
{
  "totalCount": 100,
  "sliceSize": 100,
  "sliceStart": 0,
  "results": [
    {
      "timestamp": "2023-11-09T00:42:12.724Z",
      "content": "Failed to connect to database postgres-primary: connection timeout after 4500ms",
      "status": "ERROR",
      "loglevel": "ERROR",
      "host.name": "host-prod-01",
      "dt.entity.host": "HOST-00D91658C858",
      "log.source": "/var/log/app.log",
      "service.name": "billing-service",
      "k8s.namespace.name": "production",
      "dt.source_entity": "PROCESS_GROUP_INSTANCE-00AC8E10120B"
    }
  ]
}
```

### Campos disponíveis em cada record de log

| Campo                | Descrição                                              |
| -------------------- | ------------------------------------------------------ |
| `timestamp`          | ISO-8601 em UTC                                        |
| `content`            | Linha de log                                           |
| `status` / `loglevel`| Severidade (`INFO`, `WARN`, `ERROR`, `DEBUG`, `NONE`)  |
| `host.name`          | Nome do host                                           |
| `dt.entity.host`     | ID da entidade host                                    |
| `log.source`         | Origem (arquivo ou stream)                             |
| `service.name`       | Nome do serviço                                        |
| `k8s.namespace.name` | Namespace Kubernetes                                   |
| `dt.source_entity`   | ID da process group instance                           |

### Recursos DQL suportados pelo simulador

O parser do simulador implementa um subconjunto realista da DQL, suficiente para os casos acima:

- **Pipeline**: `fetch <source> | filter ... | sort <campo> [asc|desc] | limit N`
- **Operadores de comparação**: `==`, `!=`, `<`, `<=`, `>`, `>=`
- **Operadores lógicos**: `and`, `or`, `not` (com precedência) e parênteses
- **Funções**: `contains(field, "x")`, `matchesPhrase(field, "x")`, `startsWith(field, "x")`, `endsWith(field, "x")`, `in(field, "a", "b", ...)`
- **Estágios tolerados (consumidos e ignorados)**: `fields`, `fieldsAdd`, `fieldsRemove`, `summarize`, `parse`
- **Compatibilidade legada**: queries simples sem pipeline ainda funcionam (`status=ERROR`, `host.name="x" service.name="y"`, `palavra`) — são convertidas automaticamente para `fetch logs | filter ...` com **AND** implícito entre as cláusulas.

---

## Endpoint: GET|POST /api/v2/problems (Alertas)

Simula o endpoint `/api/v2/problems` (alertas/davis problems) do Dynatrace SaaS. Suporta tanto o **`problemSelector`** (mini-DSL clássica do Dynatrace) quanto **DQL** sobre `dt.davis.problems`.

### Parâmetros

- `problemSelector` — mini-DSL OU pipeline DQL (detecção automática)
- `from`, `to` — janela de tempo (ms epoch **ou** ISO-8601). Default: últimas 24h
- `pageSize` — máximo de resultados (default 50, máx 500)
- `sort` — `<campo> <asc|desc>` (default `startTime desc`)

### Cláusulas suportadas pelo `problemSelector`

| Cláusula                              | Significado                                                |
| ------------------------------------- | ---------------------------------------------------------- |
| `status("OPEN" \| "CLOSED")`          | Filtra pelo estado do problema                             |
| `severityLevel("ERROR", ...)`         | Lista de severidades aceitas                               |
| `impactLevel("SERVICES", ...)`        | Lista de níveis de impacto                                 |
| `text("...")`                         | Substring em `title` (case-insensitive)                    |
| `entityTags("env:prod", ...)`         | Match em qualquer tag (interseção)                         |
| `managementZones("Production", ...)`  | Match em qualquer management zone                          |
| `displayIds("P-23001", ...)`          | Filtro por display ID                                      |
| `problemId("...")`                    | Filtro por problemId                                       |

Múltiplas cláusulas são combinadas com **AND** (vírgula).

### Exemplo 1 — todos os problemas das últimas 24h

```bash
curl -H "Authorization: Api-Token test-token" \
  "http://localhost:8080/api/v2/problems?pageSize=10"
```

### Exemplo 2 — apenas problemas abertos

```bash
curl -G -H "Authorization: Api-Token test-token" \
  --data-urlencode 'problemSelector=status("OPEN")' \
  "http://localhost:8080/api/v2/problems"
```

### Exemplo 3 — abertos com severidade alta

```bash
curl -G -H "Authorization: Api-Token test-token" \
  --data-urlencode 'problemSelector=status("OPEN"),severityLevel("ERROR","AVAILABILITY")' \
  "http://localhost:8080/api/v2/problems"
```

### Exemplo 4 — filtro por texto e management zone

```bash
curl -G -H "Authorization: Api-Token test-token" \
  --data-urlencode 'problemSelector=text("response time"),managementZones("Production")' \
  "http://localhost:8080/api/v2/problems"
```

### Exemplo 5 — filtro por tags + janela explícita

```bash
curl -G -H "Authorization: Api-Token test-token" \
  --data-urlencode 'problemSelector=entityTags("env:prod","team:payments")' \
  --data-urlencode 'from=2023-11-09T00:00:00.000Z' \
  --data-urlencode 'to=2023-11-10T00:00:00.000Z' \
  --data-urlencode 'pageSize=100' \
  "http://localhost:8080/api/v2/problems"
```

### Exemplo 6 — DQL simples

Equivalente DQL real:

```text
fetch dt.davis.problems
| filter event.status == "OPEN"
```

Chamada ao simulador:

```bash
curl -G -H "Authorization: Api-Token test-token" \
  --data-urlencode 'problemSelector=fetch dt.davis.problems | filter event.status == "OPEN"' \
  "http://localhost:8080/api/v2/problems"
```

### Exemplo 7 — DQL com múltiplos filtros, sort e limit

Equivalente DQL real:

```text
fetch dt.davis.problems
| filter event.status == "OPEN"
       and severityLevel == "ERROR"
       and impactLevel == "SERVICES"
| sort startTime desc
| limit 20
```

Chamada ao simulador:

```bash
curl -G -H "Authorization: Api-Token test-token" \
  --data-urlencode 'problemSelector=fetch dt.davis.problems | filter event.status == "OPEN" and severityLevel == "ERROR" and impactLevel == "SERVICES" | sort startTime desc | limit 20' \
  "http://localhost:8080/api/v2/problems"
```

### Exemplo 8 — DQL complexa com OR/contains/parênteses via POST

Equivalente DQL real:

```text
fetch dt.davis.problems
| filter (severityLevel == "ERROR" or severityLevel == "AVAILABILITY")
       and contains(title, "service")
       and host.name == "host-prod-01"
| sort startTime desc
| limit 50
```

Chamada ao simulador:

```bash
curl -X POST \
  -H "Authorization: Api-Token test-token" \
  -H "Content-Type: application/json" \
  -d '{
    "problemSelector": "fetch dt.davis.problems | filter (severityLevel == \"ERROR\" or severityLevel == \"AVAILABILITY\") and contains(title, \"service\") and host.name == \"host-prod-01\" | sort startTime desc | limit 50",
    "from": "2023-11-09T00:00:00.000Z",
    "to":   "2023-11-10T00:00:00.000Z",
    "pageSize": 50
  }' \
  "http://localhost:8080/api/v2/problems"
```

### Exemplo 9 — busca direta por displayId

```bash
curl -H "Authorization: Api-Token test-token" \
  "http://localhost:8080/api/v2/problems/P-23042"
```

### Formato da Resposta (Problems)

```json
{
  "totalCount": 1,
  "pageSize": 50,
  "nextPageKey": null,
  "problems": [
    {
      "problemId": "01699503600000000042_v2",
      "displayId": "P-23042",
      "title": "Failure rate increase on billing-service",
      "status": "OPEN",
      "severityLevel": "ERROR",
      "impactLevel": "SERVICES",
      "startTime": 1699503000000,
      "endTime": -1,
      "affectedEntities": [
        { "entityId": { "id": "SERVICE-...", "type": "SERVICE" }, "name": "billing-service" }
      ],
      "impactedEntities": [ ... ],
      "rootCauseEntity":  { "entityId": { ... }, "name": "billing-service" },
      "managementZones": [ { "id": "...", "name": "Production" } ],
      "entityTags": [
        { "context": "CONTEXTLESS", "key": "env", "value": "prod", "stringRepresentation": "env:prod" }
      ],
      "recentComments": { "totalCount": 0, "comments": [], "nextPageKey": null }
    }
  ]
}
```

`endTime == -1` indica problema ainda aberto.

### Campos disponíveis em cada record de problema (para DQL)

| Campo                    | Descrição                                                                                                      |
| ------------------------ | -------------------------------------------------------------------------------------------------------------- |
| `problemId`, `displayId` | Identificadores                                                                                                |
| `title`                  | Texto do alerta                                                                                                |
| `status`                 | `OPEN` ou `CLOSED` (alias: `event.status`)                                                                     |
| `severityLevel`          | `ERROR`, `AVAILABILITY`, `PERFORMANCE`, `RESOURCE_CONTENTION`, `CUSTOM_ALERT`, `MONITORING_UNAVAILABLE`, `INFO` |
| `impactLevel`            | `INFRASTRUCTURE`, `SERVICES`, `APPLICATION`, `ENVIRONMENT`                                                     |
| `startTime`, `endTime`   | Millis epoch (`-1` quando OPEN)                                                                                |
| `host.name`              | Host afetado (achatado para facilitar DQL)                                                                     |
| `service.name`           | Serviço afetado (achatado para facilitar DQL)                                                                  |
| `tags`                   | Lista `["env:prod", "team:payments", ...]`                                                                     |
| `event.kind`             | Sempre `DAVIS_PROBLEM`                                                                                         |

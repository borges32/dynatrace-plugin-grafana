# Integração Dynatrace Metrics V2 - Guia de Teste

## Visão Geral

O plugin Grafana foi atualizado para integrar com a API Dynatrace Metrics V2, permitindo:
- ✅ Consulta de métricas do Dynatrace
- ✅ Suporte a time range do dashboard ou customizado
- ✅ Configuração de resolução de dados
- ✅ Suporte a alertas
- ✅ Autenticação via API Token

## Arquivos Modificados

### Frontend (TypeScript/React)
1. **src/types.ts** - Novos tipos para queries e configuração
2. **src/components/ConfigEditor.tsx** - Interface de configuração do datasource
3. **src/components/QueryEditor.tsx** - Interface de criação de queries
4. **src/plugin.json** - Habilitado suporte a alertas

### Backend (Go)
1. **pkg/plugin/datasource.go** - Integração completa com API Dynatrace V2

## Como Testar

### 1. Iniciar o Simulador Dynatrace

```bash
cd ../../simulator_metric_dynatrace
docker-compose up -d

# Verificar se está rodando
curl http://localhost:8080/health
```

### 2. Build do Plugin Grafana

```bash
cd ../plugin/opensource-dynatraceplugin-datasource

# Instalar dependências frontend
npm install

# Build frontend
npm run build

# Build backend
mage -v
```

### 3. Configurar Grafana para Desenvolvimento

Edite o arquivo de configuração do Grafana (`grafana.ini` ou via docker-compose):

```ini
[plugins]
allow_loading_unsigned_plugins = opensource-dynatraceplugin-datasource

[paths]
plugins = /path/to/dynatrace-plugin-grafana/plugin/opensource-dynatraceplugin-datasource/dist
```

### 4. Iniciar Grafana

```bash
# Via Docker
docker-compose up -d

# Ou via binário local
grafana-server
```

### 5. Configurar Datasource no Grafana

1. Acesse Grafana: http://localhost:3000
2. Login: admin/admin
3. Vá em: Configuration → Data Sources → Add data source
4. Procure por "Dynatrace Plugin Datasource"
5. Configure:
   - **API URL**: `http://localhost:8080`
   - **API Token**: `test-token`
6. Clique em "Save & Test"
7. Deve exibir: "Successfully connected to Dynatrace API"

### 6. Criar Dashboard de Teste

1. Vá em: Create → Dashboard → Add new panel
2. Selecione o datasource "Dynatrace Plugin Datasource"
3. Configure a query:
   - **Metric ID**: `builtin:host.cpu.usage`
   - **Resolution**: `5 minutes`
   - **Use Dashboard Time**: ✓ (marcado)
4. Ajuste o time range para "Last 6 hours"
5. Clique em "Apply"

### 7. Testar Outras Métricas

Métricas disponíveis no simulador:
- `builtin:host.cpu.usage` - Uso de CPU (%)
- `builtin:host.mem.usage` - Uso de memória (%)
- `builtin:service.response.time` - Tempo de resposta (μs)
- `builtin:service.request.count` - Contagem de requisições
- `builtin:host.disk.avail` - Espaço em disco disponível (bytes)

### 8. Testar Time Range Customizado

1. Desmarque "Use Dashboard Time"
2. Configure:
   - **Custom From**: `1699500000000` (timestamp em ms)
   - **Custom To**: `1699503600000` (timestamp em ms)
3. Clique em "Run Query"

### 9. Testar Alertas

1. No painel, clique em "Alert" tab
2. Crie uma regra de alerta:
   - **Metric ID**: `builtin:host.cpu.usage`
   - **Condition**: `WHEN avg() OF query(A, 5m, now) IS ABOVE 80`
3. Salve a regra
4. O plugin deve funcionar com o sistema de alertas do Grafana

## Estrutura de Dados

### Query Model (Frontend → Backend)

```typescript
{
  "metricId": "builtin:host.cpu.usage",
  "useDashboardTime": true,
  "resolution": "5m",
  "customFrom": "1699500000000",  // opcional
  "customTo": "1699503600000"     // opcional
}
```

### Dynatrace API Response

```json
{
  "totalCount": 1,
  "resolution": "5m",
  "result": [
    {
      "metricId": "builtin:host.cpu.usage",
      "data": [
        {
          "timestamps": [1699500000000, 1699500300000, ...],
          "values": [45.2, 47.8, ...]
        }
      ]
    }
  ]
}
```

### Grafana Data Frame

```go
Frame{
  Fields: [
    Field{Name: "time", Type: time.Time, Values: [...]},
    Field{Name: "value", Type: float64, Values: [...]}
  ]
}
```

## Logs de Debug

### Backend (Go)
```bash
# Ver logs do plugin
tail -f /var/log/grafana/grafana.log

# Ou via Docker
docker logs -f grafana
```

### Frontend (Browser)
Abra o DevTools do navegador (F12) e veja o console.

## Troubleshooting

### Erro: "API URL is not configured"
- Verifique se você preencheu o campo "API URL" no datasource

### Erro: "API Token is not configured"
- Verifique se você preencheu o campo "API Token" no datasource

### Erro: "Error connecting to Dynatrace API"
- Verifique se o simulador está rodando: `docker ps`
- Teste manualmente: `curl http://localhost:8080/health`

### Erro: "metricId is required"
- Certifique-se de preencher o campo "Metric ID" na query

### Erro: "Dynatrace API returned status 401"
- Verifique se o token está correto
- Tokens válidos no simulador: `test-token`, `dt0c01.sample.token1`, `dt0c01.sample.token2`

### Plugin não aparece no Grafana
- Verifique `allow_loading_unsigned_plugins` no grafana.ini
- Verifique se o path dos plugins está correto
- Reinicie o Grafana

### Dados não aparecem no gráfico
- Verifique os logs do backend
- Verifique se o time range é compatível com os dados do simulador
- Teste a API diretamente: `curl -H "Authorization: Api-Token test-token" http://localhost:8080/api/v2/metrics/builtin:host.cpu.usage?from=...&to=...`

## Exemplo Completo de Teste via cURL

```bash
# 1. Testar health check
curl http://localhost:8080/health

# 2. Testar autenticação
curl -H "Authorization: Api-Token test-token" \
  http://localhost:8080/api/v2/metrics

# 3. Testar query de métrica
FROM=$(date -d '1 hour ago' +%s)000
TO=$(date +%s)000

curl -H "Authorization: Api-Token test-token" \
  "http://localhost:8080/api/v2/metrics/builtin:host.cpu.usage?from=$FROM&to=$TO&resolution=5m" \
  | jq .
```

## Próximos Passos

1. **Suporte a Relative Time**: Implementar parsing de `now-1h`, `now-6h`, etc.
2. **Caching**: Adicionar cache de métricas para melhor performance
3. **Filtros de Entidades**: Suporte a `entitySelector`
4. **Múltiplas Dimensões**: Suporte a métricas com múltiplas dimensões
5. **Template Variables**: Suporte a variáveis do Grafana

## Referências

- [Grafana Plugin Development](https://grafana.com/docs/grafana/latest/developers/plugins/)
- [Grafana Backend Plugin Guide](https://grafana.com/docs/grafana/latest/developers/plugins/backend/)
- [Dynatrace Metrics V2 API](https://www.dynatrace.com/support/help/dynatrace-api/environment-api/metric-v2/)

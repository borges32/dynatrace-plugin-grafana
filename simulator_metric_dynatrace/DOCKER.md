# Guia Docker - Dynatrace API Simulator

## 🐳 Arquivos Docker

### Dockerfile
- **Base**: Python 3.11-slim (imagem leve)
- **Porta exposta**: 8080
- **Health check**: Verifica `/health` a cada 30 segundos
- **Tamanho**: ~150MB

### docker-compose.yaml
- **Serviço**: dynatrace-simulator
- **Container**: dynatrace-api-simulator
- **Rede**: dynatrace-net (bridge)
- **Restart policy**: unless-stopped

## 🚀 Comandos Rápidos

### Com Make (Recomendado)

```bash
make up      # Inicia o simulador
make logs    # Ver logs em tempo real
make test    # Testar a API
make down    # Parar o simulador
make restart # Reiniciar
make status  # Ver status
```

### Com Docker Compose

```bash
docker-compose up -d              # Iniciar em background
docker-compose logs -f            # Ver logs
docker-compose ps                 # Ver status
docker-compose restart            # Reiniciar
docker-compose down               # Parar e remover
docker-compose down -v            # Parar e remover volumes
```

### Com Docker CLI

```bash
# Build
docker build -t dynatrace-simulator .

# Run
docker run -d \
  --name dynatrace-simulator \
  -p 8080:8080 \
  -e DT_API_TOKENS="test-token,custom-token" \
  dynatrace-simulator

# Logs
docker logs -f dynatrace-simulator

# Stop
docker stop dynatrace-simulator
docker rm dynatrace-simulator
```

## ⚙️ Configuração

### Variáveis de Ambiente

| Variável | Descrição | Padrão |
|----------|-----------|--------|
| `DT_API_TOKENS` | Tokens válidos (separados por vírgula) | `dt0c01.sample.token1,dt0c01.sample.token2,test-token` |

### Configurar no docker-compose.yaml

```yaml
services:
  dynatrace-simulator:
    environment:
      - DT_API_TOKENS=meu-token-1,meu-token-2,meu-token-3
```

### Configurar via linha de comando

```bash
docker-compose up -d \
  -e DT_API_TOKENS="token1,token2,token3"
```

### Usando arquivo .env

Crie um arquivo `.env`:
```bash
DT_API_TOKENS=production-token,staging-token,dev-token
```

E rode:
```bash
docker-compose --env-file .env up -d
```

## 🔍 Health Check

O container possui health check automático:

```yaml
healthcheck:
  test: ["CMD", "python", "-c", "import requests; requests.get('http://localhost:8080/health')"]
  interval: 30s
  timeout: 5s
  retries: 3
  start_period: 5s
```

Verificar status:
```bash
docker inspect dynatrace-api-simulator --format='{{.State.Health.Status}}'
```

## 🌐 Networking

### Acesso Local
```bash
curl http://localhost:8080/health
```

### Conectar de outro Container

```yaml
services:
  grafana:
    networks:
      - dynatrace-net
    environment:
      - DYNATRACE_URL=http://dynatrace-simulator:8080
```

### Rede Personalizada

```yaml
networks:
  dynatrace-net:
    driver: bridge
    ipam:
      config:
        - subnet: 172.25.0.0/16
```

## 📊 Monitoramento

### Ver logs em tempo real
```bash
docker-compose logs -f
```

### Ver últimas 100 linhas
```bash
docker-compose logs --tail=100
```

### Filtrar logs por serviço
```bash
docker-compose logs dynatrace-simulator
```

### Exportar logs
```bash
docker-compose logs > simulator-logs.txt
```

## 🔧 Troubleshooting

### Container não inicia

```bash
# Ver logs detalhados
docker-compose logs

# Verificar status
docker-compose ps

# Rebuild sem cache
docker-compose build --no-cache
docker-compose up -d
```

### Porta 8080 já em uso

Edite `docker-compose.yaml`:
```yaml
ports:
  - "8081:8080"  # Mapeia porta 8081 do host para 8080 do container
```

### Health check falha

```bash
# Entrar no container
docker-compose exec dynatrace-simulator /bin/bash

# Testar manualmente
curl http://localhost:8080/health
```

### Limpar tudo

```bash
# Parar e remover containers, networks e volumes
docker-compose down -v

# Remover também as imagens
docker-compose down -v --rmi all

# Limpar cache do Docker
docker system prune -a
```

## 🚀 Deploy em Produção

### Docker Compose para Produção

```yaml
version: '3.8'

services:
  dynatrace-simulator:
    image: dynatrace-simulator:latest
    container_name: dynatrace-api-simulator
    restart: always
    ports:
      - "8080:8080"
    environment:
      - DT_API_TOKENS=${DT_API_TOKENS}
    healthcheck:
      test: ["CMD", "python", "-c", "import requests; requests.get('http://localhost:8080/health')"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 5s
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
    networks:
      - dynatrace-net

networks:
  dynatrace-net:
    driver: bridge
```

### Com nginx reverse proxy

```yaml
version: '3.8'

services:
  dynatrace-simulator:
    # ... config anterior ...
    expose:
      - "8080"
    networks:
      - internal

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
    depends_on:
      - dynatrace-simulator
    networks:
      - internal

networks:
  internal:
    driver: bridge
```

## 📈 Performance

### Recursos Padrão
- **CPU**: Ilimitado (pode ser limitado)
- **Memory**: Ilimitado (pode ser limitado)

### Limitar Recursos

```yaml
services:
  dynatrace-simulator:
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 512M
        reservations:
          cpus: '0.25'
          memory: 256M
```

## 🔐 Segurança

### Usar secrets para tokens

```yaml
services:
  dynatrace-simulator:
    environment:
      - DT_API_TOKENS_FILE=/run/secrets/api_tokens
    secrets:
      - api_tokens

secrets:
  api_tokens:
    file: ./secrets/api_tokens.txt
```

### Rede isolada

```yaml
networks:
  dynatrace-net:
    driver: bridge
    internal: true  # Sem acesso à internet
```

## 📦 Registry

### Build e Push para Docker Hub

```bash
# Build com tag
docker build -t seuusuario/dynatrace-simulator:latest .
docker build -t seuusuario/dynatrace-simulator:1.0.0 .

# Push
docker push seuusuario/dynatrace-simulator:latest
docker push seuusuario/dynatrace-simulator:1.0.0
```

### Usar imagem do registry

```yaml
services:
  dynatrace-simulator:
    image: seuusuario/dynatrace-simulator:latest
```

## 🧪 Testes

### Teste completo com Docker

```bash
# Iniciar
make up

# Aguardar 3 segundos
sleep 3

# Testar
make test

# Parar
make down
```

### CI/CD Pipeline Exemplo

```bash
#!/bin/bash
set -e

echo "Building Docker image..."
docker build -t dynatrace-simulator:test .

echo "Starting container..."
docker run -d --name test-simulator -p 8080:8080 dynatrace-simulator:test

echo "Waiting for container to be ready..."
sleep 5

echo "Running tests..."
curl -f http://localhost:8080/health || exit 1

echo "Cleaning up..."
docker stop test-simulator
docker rm test-simulator

echo "Tests passed!"
```

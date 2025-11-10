.PHONY: help build up down logs test clean restart status

help: ## Mostra esta mensagem de ajuda
	@echo "Dynatrace API Simulator - Comandos disponíveis:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

build: ## Build da imagem Docker
	docker-compose build

up: ## Inicia o simulador em background
	docker-compose up -d
	@echo ""
	@echo "✓ Simulador iniciado em http://localhost:8080"
	@echo "  Use 'make logs' para ver os logs"
	@echo "  Use 'make test' para testar a API"

down: ## Para o simulador
	docker-compose down

logs: ## Mostra os logs do container
	docker-compose logs -f

test: ## Executa testes de autenticação
	@echo "Testando API..."
	@python test_auth.py || echo "Certifique-se de que o simulador está rodando (make up)"

test-curl: ## Testa a API com curl
	@echo "Testando endpoint /health..."
	@curl -s http://localhost:8080/health | python -m json.tool
	@echo ""
	@echo "Testando endpoint /api/v2/metrics com autenticação..."
	@curl -s -H "Authorization: Api-Token test-token" http://localhost:8080/api/v2/metrics | python -m json.tool

restart: ## Reinicia o simulador
	docker-compose restart
	@echo "✓ Simulador reiniciado"

status: ## Mostra status dos containers
	docker-compose ps

clean: ## Remove containers, volumes e imagens
	docker-compose down -v --rmi local
	@echo "✓ Limpeza completa realizada"

shell: ## Abre shell no container
	docker-compose exec dynatrace-simulator /bin/bash

# Comandos locais (sem Docker)
install: ## Instala dependências Python localmente
	pip install -r requirements.txt

run-local: ## Executa o simulador localmente (sem Docker)
	python app.py

# Desenvolvimento
dev: ## Inicia em modo desenvolvimento com logs
	docker-compose up

rebuild: ## Rebuild completo da imagem
	docker-compose down
	docker-compose build --no-cache
	docker-compose up -d
	@echo "✓ Rebuild completo e iniciado"

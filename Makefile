.PHONY: help install dev-install setup docker-up docker-down docker-logs db-init db-migrate db-upgrade test lint format clean run

# Default target
help:
	@echo "KR Lead Scraper - Available Commands"
	@echo "===================================="
	@echo ""
	@echo "Setup & Installation:"
	@echo "  make install        - Install production dependencies"
	@echo "  make dev-install    - Install development dependencies"
	@echo "  make setup          - Complete setup (Docker + DB + Ollama)"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-up      - Start all Docker services"
	@echo "  make docker-down    - Stop all Docker services"
	@echo "  make docker-logs    - Show Docker logs"
	@echo "  make docker-build   - Build Docker image"
	@echo ""
	@echo "Database:"
	@echo "  make db-init        - Initialize database"
	@echo "  make db-migrate     - Create new migration"
	@echo "  make db-upgrade     - Apply migrations"
	@echo "  make db-downgrade   - Rollback migration"
	@echo ""
	@echo "Development:"
	@echo "  make run            - Run API server"
	@echo "  make test           - Run tests"
	@echo "  make test-cov       - Run tests with coverage"
	@echo "  make lint           - Run linters"
	@echo "  make format         - Format code"
	@echo "  make clean          - Clean temporary files"
	@echo ""
	@echo "Ollama:"
	@echo "  make ollama-setup   - Setup Ollama models"
	@echo "  make ollama-list    - List installed models"
	@echo ""

# Installation
install:
	pip install -r requirements.txt
	playwright install chromium

dev-install: install
	pip install -e ".[dev]"
	pre-commit install

# Complete setup
setup: docker-up ollama-setup db-init
	@echo "✅ Setup completed!"

# Docker commands
docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f

docker-build:
	docker-compose build

docker-restart:
	docker-compose restart

# Database commands
db-init:
	python scripts/init_db.py

db-migrate:
	@read -p "Enter migration message: " msg; \
	alembic revision --autogenerate -m "$$msg"

db-upgrade:
	alembic upgrade head

db-downgrade:
	alembic downgrade -1

db-reset:
	alembic downgrade base
	alembic upgrade head

# Ollama commands
ollama-setup:
	chmod +x scripts/setup_ollama.sh
	./scripts/setup_ollama.sh

ollama-list:
	docker exec kr-ollama ollama list

# Development
run:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

run-prod:
	uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4

# Testing
test:
	pytest tests/ -v

test-cov:
	pytest tests/ -v --cov=app --cov-report=html --cov-report=term

test-fast:
	pytest tests/ -v -m "not slow"

# Code quality
lint:
	black --check .
	ruff check .
	mypy app --ignore-missing-imports

format:
	black .
	ruff check --fix .

pre-commit:
	pre-commit run --all-files

# Cleaning
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.coverage" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	rm -rf build/ dist/

# Scraping
scrape-pipeline:
	python scripts/scrape_complete_pipeline.py

scrape-11880:
	python scripts/examples/scrape_11880_test.py

# Monitoring
logs-api:
	tail -f logs/scraper.log

logs-docker:
	docker-compose logs -f app

# Health checks
health:
	curl http://localhost:8000/health

health-detailed:
	curl http://localhost:8000/health/detailed

# Backup
backup-db:
	@echo "Creating database backup..."
	docker exec kr-postgres pg_dump -U kr_user kr_leads > backup_$$(date +%Y%m%d_%H%M%S).sql
	@echo "✅ Backup created"

# Production deployment
deploy:
	@echo "🚀 Deploying to production..."
	git pull origin main
	docker-compose -f docker-compose.prod.yml up -d --build
	@echo "✅ Deployment completed"

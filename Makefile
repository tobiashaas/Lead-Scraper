.PHONY: help install dev-install setup docker-up docker-down docker-logs docker-build docker-restart db-init db-migrate db-upgrade test lint format clean run worker worker-dev worker-prod worker-logs worker-stats test-smart-scraper smart-scraper-demo monitoring-up monitoring-down monitoring-logs alertmanager alertmanager-up alertmanager-down test-alerts validate-alert-rules benchmark-models benchmark-prompts benchmark-report test-benchmarks load-test load-test-ui load-test-mixed load-test-bulk load-test-export load-test-analyze load-test-seed

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
	@echo "  make monitoring-up  - Start Prometheus, Grafana & Alertmanager"
	@echo "  make monitoring-down- Stop Prometheus, Grafana & Alertmanager"
	@echo "  make monitoring-logs- Tail monitoring service logs"
	@echo "  make alertmanager-up - Start Alertmanager"
	@echo "  make alertmanager-down- Stop Alertmanager"
	@echo "  make alertmanager   - Tail Alertmanager logs"
	@echo "  make worker         - Start local RQ worker"
	@echo "  make worker-dev     - Start worker via docker-compose"
	@echo "  make worker-prod    - Start production workers (compose prod)"
	@echo "  make worker-logs    - Tail worker logs"
	@echo "  make worker-stats   - Show queue statistics"
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
	@echo "  make test-alerts    - Run alerting-focused tests"
	@echo "  make validate-alert-rules - Validate Prometheus alert rules"
	@echo "  make lint           - Check code quality (Black + Ruff)"
	@echo "  make format         - Format code (Black + Ruff)"
	@echo "  make fix            - Auto-fix all code issues"
	@echo "  make lint-ci        - Lint for CI/CD (GitHub Actions)"
	@echo "  make clean          - Clean temporary files"
	@echo ""
	@echo "Load Testing:"
	@echo "  make load-test          - Run mixed scenario via helper script (headless)"
	@echo "  make load-test-ui       - Start Locust web UI"
	@echo "  make load-test-mixed    - Headless mixed workload with HTML/CSV reports"
	@echo "  make load-test-bulk     - Headless bulk-operations scenario"
	@echo "  make load-test-export   - Headless export-heavy scenario"
	@echo "  make load-test-analyze  - Analyze latest mixed load-test stats"
	@echo "  make load-test-seed     - Seed 10k companies for load testing"
	@echo ""
	@echo "Database Backup & Restore:"
	@echo "  make backup-db           - Create manual backup"
	@echo "  make backup-daily        - Create daily backup with cleanup"
	@echo "  make backup-weekly       - Create weekly backup (encrypted)"
	@echo "  make backup-list         - List available backups"
	@echo "  make backup-verify       - Verify latest backup"
	@echo "  make restore-db          - Restore database (interactive)"
	@echo "  make restore-test        - Test restore (non-destructive)"
	@echo "  make test-backup-restore - Run backup/restore tests"
	@echo ""
	@echo "Deployment:"
	@echo "  make deploy-staging     - Deploy to staging (push to develop)"
	@echo "  make deploy-production  - Deploy to production (create and push tag)"
	@echo "  make deploy-check       - Check deployment status"
	@echo "  make deploy-logs        - Show deployment logs"
	@echo "  make deploy-rollback    - Trigger manual rollback"
	@echo "  make deploy-health      - Run health checks"
	@echo ""
	@echo "Ollama:"
	@echo "  make ollama-setup   - Setup Ollama models"
	@echo "  make ollama-list    - List installed models"
	@echo ""
	@echo "Smart Scraper:"
	@echo "  make test-smart-scraper  - Test smart scraper integration"
	@echo "  make smart-scraper-demo  - Run smart scraper demo"
	@echo ""
	@echo "AI Model Benchmarking:"
	@echo "  make benchmark-models   - Run the full model benchmarking suite"
	@echo "  make benchmark-prompts  - Generate optimized prompt benchmarks"
	@echo "  make benchmark-report   - Print the latest benchmark report (if available)"
	@echo "  make test-benchmarks    - Run benchmark-focused pytest suite"
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
	@echo "Starting API, Redis, Postgres, Ollama, and worker services..."
	docker-compose up -d
	@echo "✅ Services started. Worker queue is available."

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f

docker-build:
	docker-compose build

docker-restart:
	docker-compose restart

# Worker management
worker:
	./scripts/start_worker.sh

worker-dev:
	docker-compose up worker

worker-prod:
	docker-compose -f docker-compose.prod.yml up worker-1 worker-2

worker-logs:
	docker-compose logs -f worker

worker-stats:
	python -c "from app.workers.queue import get_queue_stats; import json; print(json.dumps(get_queue_stats(), indent=2))"

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

test-alerts:
	pytest tests/unit/test_notifications.py tests/integration/test_alerting.py -v

test-fast:
	pytest tests/ -v -m "not slow"

# Code quality
lint:
	@echo "🔍 Running Black check..."
	black --check .
	@echo "🔍 Running Ruff check..."
	ruff check .
	@echo "✅ All linting checks passed!"

format:
	@echo "🎨 Formatting code with Black..."
	black .
	@echo "🔧 Fixing issues with Ruff..."
	ruff check --fix .
	@echo "✅ Code formatted successfully!"

fix: format
	@echo "🚀 All code quality issues fixed!"

lint-ci:
	black --check --diff .
	ruff check --output-format=github .

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

# Smart Scraper
test-smart-scraper:
	@echo "Testing smart scraper integration..."
	pytest tests/unit/test_smart_scraper.py tests/e2e/test_smart_scraper_integration.py -v

smart-scraper-demo:
	@echo "Running smart scraper demo..."
	python scripts/examples/test_smart_scraper_integration.py

# Benchmarking
benchmark-models:
	python scripts/benchmarks/benchmark_ollama_models.py --models llama3.2,llama3.2:1b,mistral,qwen2.5 --output both

benchmark-prompts:
	python scripts/benchmarks/optimize_prompts.py --model llama3.2 --use-case company_basic --output markdown

benchmark-report:
	@if [ -f data/benchmarks/benchmark_report.md ]; then \
		cat data/benchmarks/benchmark_report.md; \
	else \
		echo "Benchmark report not found. Run 'make benchmark-models' first."; \
	fi

test-benchmarks:
	pytest tests/benchmarks/ -v -m benchmark

# Load Testing
load-test:
	./scripts/load_testing/run_load_test.sh mixed 100 10 5m

load-test-ui:
	locust -f tests/load/locustfile.py --host http://localhost:8000

load-test-mixed:
	locust -f tests/load/locustfile.py --headless -u 100 -r 10 --run-time 5m \
		--html data/load_tests/mixed_report.html --csv data/load_tests/mixed --loglevel INFO

load-test-bulk:
	locust -f tests/load/scenarios/bulk_operations.py --headless -u 75 -r 10 --run-time 5m \
		--html data/load_tests/bulk_report.html --csv data/load_tests/bulk --loglevel INFO

load-test-export:
	locust -f tests/load/scenarios/export_heavy.py --headless -u 50 -r 8 --run-time 5m \
		--html data/load_tests/export_report.html --csv data/load_tests/export --loglevel INFO

load-test-analyze:
	python scripts/load_testing/analyze_results.py --stats-csv data/load_tests/mixed_stats.csv --output both

load-test-seed:
	python -c "from tests.load.config import create_http_client, get_auth_token, build_auth_headers, ensure_seed_data; client=create_http_client(); token=get_auth_token(client); headers=build_auth_headers(token); ensure_seed_data(client, headers, count=10000)"

# Monitoring
monitoring-up:
	@echo "Starting Prometheus, Grafana, and Alertmanager..."
	docker-compose up -d prometheus grafana alertmanager
	@echo "✅ Monitoring stack running at grafana:3000 / prometheus:9090 / alertmanager:9093"

monitoring-down:
	@echo "Stopping Prometheus, Grafana, and Alertmanager..."
	docker-compose stop prometheus grafana alertmanager
	@echo "✅ Monitoring stack stopped"

monitoring-logs:
	@echo "Tailing Prometheus, Grafana, and Alertmanager logs..."
	docker-compose logs -f prometheus grafana alertmanager

alertmanager-up:
	@echo "Starting Alertmanager..."
	docker-compose up -d alertmanager
	@echo "✅ Alertmanager available at http://localhost:9093"

alertmanager-down:
	@echo "Stopping Alertmanager..."
	docker-compose stop alertmanager
	@echo "✅ Alertmanager stopped"

alertmanager:
	@echo "Tailing Alertmanager logs..."
	docker-compose logs -f alertmanager

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
	python scripts/maintenance/backup_database.py --type manual --compress --verify
	@echo "✅ Backup created and verified"

backup-daily:
	@echo "Running daily backup with cleanup..."
	python scripts/maintenance/backup_database.py --type daily --compress --verify --cleanup

backup-weekly:
	@echo "Running weekly backup with encryption and cleanup..."
	python scripts/maintenance/backup_database.py --type weekly --compress --encrypt --verify --cleanup

backup-list:
	@echo "Listing latest backups..."
	ls -lh backups/*.sql*

backup-verify:
	@echo "Verifying latest backup..."
	python scripts/maintenance/backup_database.py --verify-only

restore-db:
	@echo "Starting interactive database restore..."
	python scripts/maintenance/restore_database.py

restore-test:
	@echo "Running non-destructive restore test..."
	python scripts/maintenance/restore_database.py --test-only

test-backup-restore:
	@echo "Running automated backup/restore tests..."
	python scripts/maintenance/test_backup_restore.py --verbose

# Deployment commands
deploy-staging:
	@echo "🚀 Deploying to staging..."
	git push origin develop
	@echo "✅ Pushed to develop, GitHub Actions will deploy to staging"
	@echo "Monitor: https://github.com/tobiashaas/Lead-Scraper/actions"

deploy-production:
	@read -p "Enter version (e.g., 1.2.3): " version; \
	echo "Creating tag v$$version..."; \
	git tag v$$version -m "Release v$$version"; \
	git push origin v$$version; \
	echo "✅ Tag v$$version pushed, GitHub Actions will deploy to production"; \
	echo "Monitor: https://github.com/tobiashaas/Lead-Scraper/actions"

deploy-check:
	@echo "Checking deployment status..."
	@echo "Production:" && curl -f https://api.your-domain.com/health || echo "❌ Production health check failed"
	@echo "Staging:" && curl -f https://staging.your-domain.com/health || echo "❌ Staging health check failed"

deploy-logs:
	@echo "Fetching deployment logs..."
	ssh $${DEPLOY_USER:-deploy}@${PRODUCTION_HOST:-production-host} "tail -n 100 /opt/kr-scraper/logs/deployment.log"

deploy-rollback:
	@read -p "Enter environment (production/staging): " env; \
	read -p "Enter target version: " version; \
	read -p "Enter reason: " reason; \
	gh workflow run rollback.yml -f environment=$$env -f target_version=$$version -f reason="$$reason"; \
	echo "✅ Rollback triggered, monitor: https://github.com/tobiashaas/Lead-Scraper/actions"

deploy-health:
	@echo "Running health checks..."
	@echo "Production:" && curl -s https://api.your-domain.com/health/detailed | jq .
	@echo "Staging:" && curl -s https://staging.your-domain.com/health/detailed | jq .

deploy: deploy-production
	@echo "Alias for deploy-production"

docker-prod-up:
	docker-compose -f docker-compose.prod.yml up -d

docker-prod-down:
	docker-compose -f docker-compose.prod.yml down

docker-staging-up:
	docker-compose -f docker-compose.staging.yml up -d

docker-staging-down:
	docker-compose -f docker-compose.staging.yml down

# API Documentation
.PHONY: api-docs api-docs-open api-schema api-validate

api-docs:
	@echo "API Documentation available at:"
	@echo "  Swagger UI: http://localhost:8000/docs"
	@echo "  ReDoc: http://localhost:8000/redoc"
	@echo "  OpenAPI JSON: http://localhost:8000/openapi.json"

api-docs-open:
	@echo "Opening API documentation..."
	@if command -v open > /dev/null; then \
		open http://localhost:8000/docs; \
	elif command -v xdg-open > /dev/null; then \
		xdg-open http://localhost:8000/docs; \
	elif command -v start > /dev/null; then \
		start http://localhost:8000/docs; \
	else \
		echo "Please open http://localhost:8000/docs in your browser"; \
	fi

api-schema:
	@echo "Downloading OpenAPI schema..."
	@mkdir -p data
	@curl -s http://localhost:8000/openapi.json | python -m json.tool > data/openapi.json
	@echo "✅ Schema saved to data/openapi.json"

api-validate:
	@echo "Validating OpenAPI schema..."
	@pip show openapi-spec-validator > /dev/null 2>&1 || pip install openapi-spec-validator
	@openapi-spec-validator data/openapi.json
	@echo "✅ OpenAPI schema is valid"

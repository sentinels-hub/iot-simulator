.PHONY: dev build up down logs test lint clean

# Development — start backend with uvicorn + frontend with vite dev
dev:
	@echo "Starting development environment..."
	@trap 'kill 0' INT; \
	(cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload) & \
	(cd frontend && npm run dev) & \
	wait

# Docker build
build:
	docker compose build

# Docker up
up:
	docker compose up -d

# Docker down
down:
	docker compose down

# Docker logs
logs:
	docker compose logs -f

# Run backend tests
test:
	cd backend && python -m pytest tests/ -v --tb=short

# Lint backend code
lint:
	cd backend && python -m ruff check app/ tests/

# Clean build artifacts
clean:
	rm -rf frontend/dist frontend/node_modules backend/__pycache__
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

# Deploy to Wakanda
deploy:
	bash scripts/deploy-wakanda.sh

# Test MQTT connectivity
test-connection:
	bash scripts/test-connection.sh
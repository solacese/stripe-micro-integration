.PHONY: install lint typecheck coverage test test-unit test-integration test-e2e \
        up up-cloud up-local down down-cloud down-local provision validate \
        e2e e2e-local logs clean

ifneq (,$(wildcard .env))
include .env
export
endif

install:
	python3 -m pip install -r requirements.txt -r requirements-dev.txt

lint:
	python3 -m ruff check app/ tests/ scripts/

format:
	python3 -m ruff format app/ tests/ scripts/

typecheck:
	python3 -m mypy --strict app/

test-unit:
	python3 -m pytest tests/unit/ -v --tb=short

test-integration:
	python3 -m pytest tests/integration/ -v --tb=short

test-e2e:
	RUN_E2E=1 python3 -m pytest tests/e2e/ -v --tb=short -s

coverage:
	python3 -m pytest tests/unit tests/integration --cov=app --cov-fail-under=85 -v --tb=short

test:
	$(MAKE) coverage

up:
	docker compose -f docker/docker-compose.yml up -d --build
	@echo "Waiting for services..."
	@sleep 20
	docker compose -f docker/docker-compose.yml logs provision

up-cloud:
	docker compose -f docker/docker-compose.yml up -d --build app redis
	@echo "Waiting for cloud-mode services..."
	@sleep 10

up-local:
	SOLACE_HOST=tcp://solace:55555 \
	SOLACE_SEMP_HOST=http://solace:8080 \
	SOLACE_SEMP_USERNAME=admin \
	SOLACE_SEMP_PASSWORD=admin \
	SOLACE_VPN=default \
	docker compose -f docker/docker-compose.yml up -d --build
	@echo "Waiting for local services..."
	@sleep 20
	docker compose -f docker/docker-compose.yml logs provision

down:
	docker compose -f docker/docker-compose.yml down -v

down-cloud:
	docker compose -f docker/docker-compose.yml down -v

down-local:
	docker compose -f docker/docker-compose.yml down -v

provision:
	python scripts/provision_solace.py

validate:
	python scripts/validate_pipeline.py \
	  --app-url http://localhost:${APP_PORT} \
	  --stripe-key ${STRIPE_API_KEY} \
	  --webhook-secret ${STRIPE_WEBHOOK_SECRET} \
	  --solace-host ${SOLACE_HOST} \
	  --solace-vpn ${SOLACE_VPN} \
	  --solace-user ${SOLACE_USERNAME} \
	  --solace-password ${SOLACE_PASSWORD} \
	  --account-id ${E2E_STRIPE_ACCOUNT_ID} \
	  --semp-host ${SOLACE_SEMP_HOST} \
	  --semp-username ${SOLACE_SEMP_USERNAME} \
	  --semp-password ${SOLACE_SEMP_PASSWORD}

validate-local:
	SOLACE_HOST=tcp://localhost:55555 \
	SOLACE_SEMP_HOST=http://localhost:8080 \
	SOLACE_SEMP_USERNAME=admin \
	SOLACE_SEMP_PASSWORD=admin \
	SOLACE_VPN=default \
	E2E_STRIPE_ACCOUNT_ID=${E2E_STRIPE_ACCOUNT_ID} \
	python scripts/validate_pipeline.py \
	  --app-url http://localhost:${APP_PORT} \
	  --stripe-key ${STRIPE_API_KEY} \
	  --webhook-secret ${STRIPE_WEBHOOK_SECRET} \
	  --solace-host tcp://localhost:55555 \
	  --solace-vpn default \
	  --solace-user ${SOLACE_USERNAME} \
	  --solace-password ${SOLACE_PASSWORD} \
	  --account-id ${E2E_STRIPE_ACCOUNT_ID} \
	  --semp-host http://localhost:8080 \
	  --semp-username admin \
	  --semp-password admin

e2e:
	$(MAKE) up-cloud
	$(MAKE) test-e2e
	$(MAKE) validate
	$(MAKE) down-cloud

e2e-local:
	$(MAKE) up-local
	RUN_E2E=1 RUN_E2E_LOCAL=1 python3 -m pytest tests/e2e/ -v --tb=short -s
	$(MAKE) validate-local
	$(MAKE) down-local

logs:
	docker compose -f docker/docker-compose.yml logs -f app

clean:
	docker compose -f docker/docker-compose.yml down -v
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -name "*.pyc" -delete

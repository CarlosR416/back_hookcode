SETTINGS ?= config.settings.development
DJANGO_MANAGE = python manage.py --settings=$(SETTINGS)

.PHONY: help install run migrate makemigrations superuser shell test lint format

help:  ## Show available commands
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install:  ## Install development dependencies
	pip install -r requirements/development.txt

run:  ## Start the development server
	$(DJANGO_MANAGE) runserver

migrate:  ## Apply database migrations
	$(DJANGO_MANAGE) migrate

makemigrations:  ## Create new migration files
	$(DJANGO_MANAGE) makemigrations

superuser:  ## Create a Django superuser
	$(DJANGO_MANAGE) createsuperuser

shell:  ## Open the Django shell (requires ipython)
	$(DJANGO_MANAGE) shell_plus --ipython

test:  ## Run test suite
	$(DJANGO_MANAGE) test apps/ --keepdb --verbosity=2

check:  ## Validate Django configuration
	$(DJANGO_MANAGE) check

lint:  ## Run ruff linter
	ruff check .

format:  ## Auto-format code with ruff
	ruff format .

docker-up:  ## Start all services with Docker Compose
	docker compose up -d

docker-down:  ## Stop all services
	docker compose down

docker-logs:  ## Tail API service logs
	docker compose logs -f api

docker-migrate:  ## Run migrations inside Docker
	docker compose exec api python manage.py migrate

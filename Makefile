.PHONY: up down logs ps build seed test clean

up:
	docker compose up -d --build

down:
	docker compose --profile tools down

logs:
	docker compose logs -f app

ps:
	docker compose ps

build:
	docker compose build

seed:
	docker compose exec app python -m app.seed_cli

test:
	bash tests/smoke.sh

clean:
	docker compose --profile tools down -v

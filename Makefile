# One command: make fight
# Windows without make: run the three commands under `fight` by hand.

.PHONY: fight clean gen check-card up down keys dashboard test reset

fight: .env up
	uv run fight.py

# Run your team on any CSV: make clean FILE=path/to/your.csv -> path/to/your.clean.csv
clean: .env
	@test -n "$(FILE)" || (echo "usage: make clean FILE=path/to/your.csv" && exit 1)
	$(MAKE) up
	uv run fight.py clean "$(FILE)"

gen: .env
	uv run fight.py gen

# Organizers: verify a submitted card against this repo's main before rerunning it.
check-card:
	@test -n "$(CARD)" || (echo "usage: make check-card CARD=path/to/fight-card.json" && exit 1)
	uv run fight.py check-card "$(CARD)"

.env:
	uv run fight.py init-env

up: .env
	docker compose up -d
	uv run fight.py wait-otari

down:
	docker compose down

keys: .env
	uv run fight.py keys

dashboard:
	@echo "$$(sed -n 's/^OTARI_URL=//p' .env 2>/dev/null | grep . || echo http://localhost:8000)  (sign in with the admin key: make keys)"

test:
	uv run --group dev pytest -q

reset: down
	docker compose down -v
	rm -f fight-card.md fight-card.json fight-log.jsonl data/golden.csv data/messy.csv data/*.clean.csv

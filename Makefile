.PHONY: help setup db-user db-create db-schema db-setup-all build-list test-parse clean

help:
	@echo "EDGAR Parser - Available Commands"
	@echo "=================================="
	@echo "make setup        - Install dependencies and setup environment"
	@echo "make db-user      - Create PostgreSQL user (one-time setup)"
	@echo "make db-create    - Create PostgreSQL database"
	@echo "make db-schema    - Load database schema"
	@echo "make build-list   - Download S&P 500 company list"
	@echo "make test-parse   - Test parser with embedded Apple data"
	@echo "make test-db      - Test database connection"
	@echo "make test-edgar   - Test EDGAR API fetch"
	@echo "make clean        - Remove generated files"

setup:
	python3 -m venv venv
	. venv/bin/activate && pip install -r requirements.txt
	cp .env.example .env
	@echo "✓ Setup complete. Edit .env with your credentials."

db-create:
	@if [ ! -f .env ]; then echo "Error: .env file not found. Run 'make setup' first."; exit 1; fi
	@DB_NAME=$$(grep '^DB_NAME=' .env | cut -d '=' -f2-) && \
		createdb $$DB_NAME && \
		echo "✓ Database '$$DB_NAME' created"

db-user:
	@if [ ! -f .env ]; then echo "Error: .env file not found. Run 'make setup' first."; exit 1; fi
	@DB_USER=$$(grep '^DB_USER=' .env | cut -d '=' -f2-) && \
		DB_PASSWORD=$$(grep '^DB_PASSWORD=' .env | cut -d '=' -f2-) && \
		DB_NAME=$$(grep '^DB_NAME=' .env | cut -d '=' -f2-) && \
		echo "Creating PostgreSQL user '$$DB_USER'..." && \
		(psql postgres -c "CREATE USER $$DB_USER WITH PASSWORD '$$DB_PASSWORD';" 2>/dev/null || \
		(psql postgres -c "ALTER USER $$DB_USER WITH PASSWORD '$$DB_PASSWORD';" && \
		echo "✓ User password updated (user already existed)")) && \
		psql postgres -c "GRANT ALL PRIVILEGES ON DATABASE $$DB_NAME TO $$DB_USER;" && \
		echo "✓ Database user '$$DB_USER' created and granted privileges"

db-schema:
	@if [ ! -f .env ]; then echo "Error: .env file not found. Run 'make setup' first."; exit 1; fi
	@DB_USER=$$(grep '^DB_USER=' .env | cut -d '=' -f2-) && \
		DB_NAME=$$(grep '^DB_NAME=' .env | cut -d '=' -f2-) && \
		psql $$DB_NAME < database/schema.sql && \
		psql $$DB_NAME -c "GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO $$DB_USER;" && \
		psql $$DB_NAME -c "GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO $$DB_USER;" && \
		echo "✓ Schema loaded and permissions granted to '$$DB_USER'"

db-setup-all: db-user db-create db-schema
	@DB_USER=$$(grep '^DB_USER=' .env | cut -d '=' -f2-) && \
		DB_NAME=$$(grep '^DB_NAME=' .env | cut -d '=' -f2-) && \
		echo "" && \
		echo "✓ Complete database setup finished!" && \
		echo "✓ User: $$DB_USER" && \
		echo "✓ Database: $$DB_NAME" && \
		echo "✓ Ready to run: make test-db"

build-list:
	python scripts/build_company_list.py
	@echo "✓ Company list downloaded to data/target_companies.csv"

test-parse:
	python src/edgar_parser/parser.py
	@echo "✓ Parser test complete"

test-db:
	python scripts/test_db_connection.py
	@echo "✓ Database connection test complete"

test-edgar:
	python scripts/test_edgar_fetch.py
	@echo "✓ EDGAR API test complete"

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf data/parsed/* data/*.json 2>/dev/null || true
	@echo "✓ Cleaned"

.PHONY: pipeline site build deploy test copy-data clean

PYTHON ?= python3.12

pipeline:
	$(PYTHON) -m pipeline.run_all

site:
	npm run dev

build:
	$(PYTHON) -m pipeline.run_all
	$(MAKE) copy-data
	npm run build

copy-data:
	mkdir -p src/data
	cp data/dist/*.parquet src/data/ 2>/dev/null || true

test:
	$(PYTHON) -m pytest tests/ -v

deploy: build
	npm run deploy

clean:
	rm -f data/nz_health.duckdb
	rm -rf data/dist/*
	rm -rf data/raw/*

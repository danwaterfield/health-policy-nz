.PHONY: pipeline site build deploy test copy-data clean

pipeline:
	python pipeline/run_all.py

site:
	npm run dev

build:
	python pipeline/run_all.py
	$(MAKE) copy-data
	npm run build

copy-data:
	mkdir -p src/data
	cp data/dist/*.parquet src/data/ 2>/dev/null || true

test:
	pytest tests/ -v

deploy: build
	npm run deploy

clean:
	rm -f data/nz_health.duckdb
	rm -rf data/dist/*
	rm -rf data/raw/*

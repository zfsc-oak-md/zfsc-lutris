LUTRIS_REF ?= eace36e97bd0e4d65bcb361b0d785d75433c65e9
LUTRIS_DIR ?= build/lutris
export LUTRIS_REF

.PHONY: fetch apply check run clean

fetch:
	./scripts/fetch-lutris.sh $(LUTRIS_DIR)

apply: fetch
	./scripts/apply.sh $(LUTRIS_DIR)

check:
	python3 -m compileall -q lutris scripts tests
	python3 -m unittest discover -s tests
	@if command -v ruff >/dev/null 2>&1; then \
		ruff check . && ruff format --check .; \
	else \
		echo "ruff not installed; skipping lint"; \
	fi

run: apply
	cd $(LUTRIS_DIR) && ./bin/lutris

clean:
	rm -rf build

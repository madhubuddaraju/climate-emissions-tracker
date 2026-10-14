PYTHON ?= python
export PYTHONPATH := src

.PHONY: install pipeline refresh report dashboard test lint all fixtures clean

install:     ## install runtime + dev dependencies
	$(PYTHON) -m pip install -r requirements-dev.txt

pipeline:    ## download (cached 12h) -> stage -> build models -> quality checks
	$(PYTHON) -m climate

refresh:     ## force a fresh download of all sources, then rebuild
	$(PYTHON) -m climate --refresh

report:      ## regenerate charts and reports/insights.md
	$(PYTHON) analysis/report.py

dashboard:   ## launch the Streamlit dashboard
	streamlit run dashboard/app.py

test:
	$(PYTHON) -m pytest -q

lint:
	ruff check .

fixtures:    ## rebuild offline test fixtures from data/raw
	$(PYTHON) tests/fixtures/make_fixtures.py

all: pipeline report test

clean:
	rm -rf data/ .pytest_cache .ruff_cache

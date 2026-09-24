# Prefer the project venv so the demo does not depend on whatever python3
# happens to be first on PATH. `make deps` creates it.
PYTHON := $(shell [ -x .venv/bin/python ] && echo .venv/bin/python || echo python3)
PY := $(PYTHON) -m src.governance

.PHONY: help deps validate bootstrap seed deploy show whoami gate-on gate-off conflict teardown reset demo role-analyst role-consumer role-full role-none

help:
	@echo "  make deps        create .venv and install requirements"
	@echo "  make validate    contracts gate - run this before anything reaches the workspace"
	@echo "  make bootstrap   account setup  - governed tags and groups, once"
	@echo "  make seed        demo data      - schema, table, rows"
	@echo "  make deploy      the mechanism  - functions, column tags, policies"
	@echo "  make show        read the table as you are"
	@echo "  make whoami      which groups resolve for you"
	@echo "  make gate-on     mark tables unverified - readers get zero rows"
	@echo "  make gate-off    mark tables verified   - masking takes over"
	@echo "  make conflict    two masks on one column - deploys clean, fails at read"
	@echo "  make role-analyst / role-consumer / role-full / role-none"
	@echo "                   put yourself in one role and wait until it takes effect"
	@echo "  make demo        the whole narrative, in order, with headings"
	@echo "  make teardown    remove the demo schemas and policies"

deps:
	@python3 -m venv .venv
	@.venv/bin/pip install -q -r requirements.txt
	@echo "  .venv ready: $$(.venv/bin/python --version)"

validate:  ; @$(PY).validate
bootstrap: ; @$(PY).bootstrap
seed:      ; @$(PY).apply seed
deploy:    ; @$(PY).apply deploy
show:      ; @$(PY).apply show
whoami:    ; @$(PY).apply whoami
gate-on:   ; @$(PY).apply gate-on
gate-off:  ; @$(PY).apply gate-off
conflict:  ; @$(PY).apply conflict
teardown:  ; @$(PY).apply teardown
role-analyst:  ; @$(PY).roles analyst
role-consumer: ; @$(PY).roles consumer
role-full:     ; @$(PY).roles full_access
role-none:     ; @$(PY).roles none

demo:      ; @$(PY).demo
reset: teardown seed deploy

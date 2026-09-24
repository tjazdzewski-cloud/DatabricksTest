PY := python3 -m src.governance

.PHONY: help validate bootstrap seed deploy show whoami gate-on gate-off conflict teardown reset

help:
	@echo "  make validate    contracts gate - run this before anything reaches the workspace"
	@echo "  make bootstrap   account setup  - governed tags and groups, once"
	@echo "  make seed        demo data      - schema, table, rows"
	@echo "  make deploy      the mechanism  - functions, column tags, policies"
	@echo "  make show        read the table as you are"
	@echo "  make whoami      which groups resolve for you"
	@echo "  make gate-on     mark tables unverified - readers get zero rows"
	@echo "  make gate-off    mark tables verified   - masking takes over"
	@echo "  make conflict    two masks on one column - deploys clean, fails at read"
	@echo "  make teardown    remove the demo schemas and policies"

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
reset: teardown seed deploy

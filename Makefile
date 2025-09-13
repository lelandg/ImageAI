PY ?= python3

.PHONY: codemap
codemap:
	$(PY) tools/generate_code_map.py


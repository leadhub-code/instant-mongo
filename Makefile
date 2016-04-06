
check:
	make check34

check34: local/venv34
	PYTHONDONTWRITEBYTECODE=1 local/venv34/bin/py.test -v tests

local/venv34: setup.py Makefile
	test -d local/venv34 || pyvenv-3.4 local/venv34
	local/venv34/bin/pip install -U pip
	local/venv34/bin/pip install -U pytest
	local/venv34/bin/pip install -U -e .
	touch local/venv34

.PHONY: check check34

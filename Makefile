python3=python3
venv_dir=venv
pytest_args=-v

check: $(venv_dir)/packages-installed
	PYTHONDONTWRITEBYTECODE=1 \
		$(venv_dir)/bin/pytest $(pytest_args) tests

venv: $(venv_dir)/packages-installed

$(venv_dir)/packages-installed: setup.py
	test -d $(venv_dir) || $(python3) -m venv $(venv_dir)
	$(venv_dir)/bin/pip install -U pip wheel
	$(venv_dir)/bin/pip install -e .
	$(venv_dir)/bin/pip install -e .[test]
	touch $@

check-py3.6:
	make check python3=python3.6 venv_dir=$(venv_dir)-py3.6

.PHONY: venv

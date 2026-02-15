python3=python3
venv_dir=venv
pytest_args=-vv --tb=short --log-cli-level=INFO

check: $(venv_dir)/packages-installed
	PYTHONDONTWRITEBYTECODE=1 \
		$(venv_dir)/bin/python3 -m pytest $(pytest_args) tests

lint: $(venv_dir)/packages-installed
	test -x $(venv_dir)/bin/flake8 || $(venv_dir)/bin/pip install flake8
	$(venv_dir)/bin/flake8 . --show-source --statistics

venv: $(venv_dir)/packages-installed

$(venv_dir)/packages-installed: pyproject.toml
	test -d $(venv_dir) || $(python3) -m venv $(venv_dir)
	$(venv_dir)/bin/pip install -U pip wheel
	$(venv_dir)/bin/pip install -e .
	$(venv_dir)/bin/pip install -e .[test]
	touch $@

.PHONY: venv

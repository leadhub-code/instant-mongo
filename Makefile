uv=uv
pytest_args=-vv --tb=short --log-cli-level=INFO
python3=python3

check:
	$(uv) run pytest $(pytest_args) tests

lint:
	$(uv) run flake8 . --show-source --statistics

venv:
	$(uv) sync --dev

dist:
	rm -rf dist
	$(uv) build
	test -f dist/instant_mongo-*.whl

check-dist:
	test -f dist/instant_mongo-*.whl
	rm -rf venv-check-dist
	$(python3) -m venv venv-check-dist
	venv-check-dist/bin/pip install dist/instant_mongo-*.whl
	venv-check-dist/bin/python -c 'import instant_mongo; print("ok:", instant_mongo.__version__)'
	rm -rf venv-check-dist

.PHONY: check lint venv dist

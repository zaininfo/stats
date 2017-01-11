NAME = stats
VERSION = 0.0.1

.PHONY: all
all: clean bootstrap lint test

.PHONY: bootstrap
bootstrap: venv

.PHONY: venv
venv:
	virtualenv venv -p python3.4
	/usr/bin/env bash -c "source venv/bin/activate && \
		pip install -r requirements.txt"

.PHONY: lint
lint:
	/usr/bin/env bash -c "source venv/bin/activate && find stats/ -name '*.py' | xargs ./venv/bin/pylint --rcfile pylintrc"
	/usr/bin/env bash -c "source venv/bin/activate && find test/ -name '*.py' | xargs ./venv/bin/pylint --rcfile pylintrc"

.PHONY: test
test:
	/usr/bin/env bash -c "source venv/bin/activate && python3 -m unittest"

.PHONY: clean
clean:
	find . -name *.pyc | xargs rm -rf
	find . -name __pycache__ | xargs rm -rf
	rm -rf venv

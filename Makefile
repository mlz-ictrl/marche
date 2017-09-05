PYTHON = /usr/bin/env python

all: build

build:
	$(PYTHON) setup.py build

install: build
	$(PYTHON) setup.py install

clean:
	rm -rf build

rcc:
	pyrcc4  -py3 marche/gui/res/marche-gui.qrc  > marche/gui/res.py

test:
	$(PYTHON) $(shell which pytest) -v test

test-verbose:
	$(PYTHON) $(shell which pytest) -v test -s

test-coverage:
	$(PYTHON) $(shell which pytest) -v test --cov=marche

doc:
	$(MAKE) -C doc html

help:
	@echo "Available make targets:"
	@echo "    install           - install marche"
	@echo "    test              - run the test suite"
	@echo "    test-coverage     - run the test suite"
	@echo "    doc               - build the html version of the documentation"


.PHONY: test test-coverage doc help



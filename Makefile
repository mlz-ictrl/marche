PYTHON = /usr/bin/env python

RCC4 = pyrcc4
RCC5 = pyrcc5

all: build

build:
	$(PYTHON) setup.py build

install: build
	$(PYTHON) setup.py install

clean:
	rm -rf build

res: marche/gui/res/marche-gui.qrc
	$(RCC4) -py3 -o marche/gui/res_qt4.py $<
	$(RCC5)      -o marche/gui/res_qt5.py $<

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

.PHONY: all build install clean res test test-verbose test-coverage doc help


release-patch:
	MODE="patch" $(MAKE) release

release-minor:
	MODE="minor" $(MAKE) release

release:
	ssh jenkinsng.admin.frm2 -p 29417 build -v -s -p GERRIT_PROJECT=$(shell git config --get remote.origin.url | rev | cut -d '/' -f -3 | rev) -p ARCH=all -p MODE=$(MODE) ReleasePipeline

.PHONY: release release-patch release-minor

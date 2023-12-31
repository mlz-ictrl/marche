PYTHON = /usr/bin/env python

RCC5 = pyrcc5
RCC6 = /usr/lib64/qt6/libexec/rcc

all:

clean:
	rm -rf build

res: marche/gui/res/marche.qrc
	$(RCC5) -o marche/gui/res_qt5.py $<
	$(RCC6) -g python $< | sed '0,/PySide6/s//PyQt6/' > marche/gui/res_qt6.py

T = test

test:
	$(PYTHON) $(shell which pytest) -v $(T)

test-verbose:
	$(PYTHON) $(shell which pytest) -v $(T) -s

test-coverage:
	$(PYTHON) $(shell which pytest) -v $(T) --cov=marche

lint:
	pylint -r n --rcfile=pylintrc marche test

doc:
	$(MAKE) -C doc html

help:
	@echo "Available make targets:"
	@echo "    install           - install marche"
	@echo "    test              - run the test suite"
	@echo "    test-coverage     - run the test suite"
	@echo "    doc               - build the html version of the documentation"

.PHONY: all clean res test test-verbose test-coverage doc help


release-patch:
	MODE="patch" $(MAKE) release

release-minor:
	MODE="minor" $(MAKE) release

release:
	ssh jenkins.admin.frm2 -p 29417 build -v -s -p GERRIT_PROJECT=$(shell git config --get remote.origin.url | rev | cut -d '/' -f -3 | rev) -p ARCH=all -p MODE=$(MODE) ReleasePipeline

.PHONY: release release-patch release-minor

VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

.PHONY: setup setup-dev run test clean build-sudoku

# create the virtualenv and install runtime dependencies (isolated from the
# system Python, which is externally managed and rejects pip installs)
$(VENV)/.stamp: requirements.txt
	python3 -m venv $(VENV)
	$(PIP) install -r requirements.txt
	touch $@

setup: $(VENV)/.stamp

# additionally install dev/test dependencies
$(VENV)/.stamp-dev: requirements-dev.txt requirements.txt
	python3 -m venv $(VENV)
	$(PIP) install -r requirements-dev.txt
	touch $@

setup-dev: $(VENV)/.stamp-dev

run: setup build-sudoku
	$(PYTHON) src/main.py

test: setup-dev build-sudoku
	$(PYTHON) -m pytest

clean:
	rm -rf __pycache__
	rm -rf src/solvers/sudoku/*.so

build-sudoku: src/solvers/sudoku/DancingLinks.cpp src/solvers/sudoku/Grid.cpp src/solvers/sudoku/Grid.h src/solvers/sudoku/Box.cpp src/solvers/sudoku/Box.h src/solvers/sudoku/Node.cpp src/solvers/sudoku/Node.h
	g++ -std=c++11 -fPIC -shared -o src/solvers/sudoku/DancingLinks.so src/solvers/sudoku/DancingLinks.cpp src/solvers/sudoku/Grid.cpp src/solvers/sudoku/Box.cpp src/solvers/sudoku/Node.cpp

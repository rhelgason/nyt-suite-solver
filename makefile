VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

.PHONY: setup setup-dev run test stats clean build build-sudoku build-strands

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

# build the C/C++ solver extensions
build: build-sudoku build-strands

run: setup build
	$(PYTHON) src/main.py

test: setup-dev build
	$(PYTHON) -m pytest

# regenerate the auto-updated stats section of the README from solutions/
stats:
	$(PYTHON) src/stats.py

clean:
	rm -rf __pycache__
	rm -rf src/solvers/sudoku/*.so src/solvers/strands/*.so

build-sudoku: src/solvers/sudoku/DancingLinks.cpp src/solvers/sudoku/Grid.cpp src/solvers/sudoku/Grid.h src/solvers/sudoku/Box.cpp src/solvers/sudoku/Box.h src/solvers/sudoku/Node.cpp src/solvers/sudoku/Node.h
	g++ -std=c++11 -fPIC -shared -o src/solvers/sudoku/DancingLinks.so src/solvers/sudoku/DancingLinks.cpp src/solvers/sudoku/Grid.cpp src/solvers/sudoku/Box.cpp src/solvers/sudoku/Node.cpp

build-strands: src/solvers/strands/StrandsSearch.cpp
	g++ -std=c++17 -O2 -fPIC -shared -o src/solvers/strands/StrandsSearch.so src/solvers/strands/StrandsSearch.cpp

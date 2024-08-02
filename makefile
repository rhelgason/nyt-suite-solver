setup: requirements.txt
	pip3 install -r requirements.txt

run: build-sudoku
	python3 src/main.py

clean:
	rm -rf __pycache__
	rm -rf src/solvers/sudoku/*.so

build-sudoku: src/solvers/sudoku/DancingLinks.cpp src/solvers/sudoku/Grid.cpp src/solvers/sudoku/Grid.h src/solvers/sudoku/Box.cpp src/solvers/sudoku/Box.h src/solvers/sudoku/Node.cpp src/solvers/sudoku/Node.h
	g++ -std=c++11 -fPIC -shared -o src/solvers/sudoku/DancingLinks.so src/solvers/sudoku/DancingLinks.cpp src/solvers/sudoku/Grid.cpp src/solvers/sudoku/Box.cpp src/solvers/sudoku/Node.cpp

#include <iostream>
#include <fstream>
#include <chrono>
#include "Grid.h"
#include "Box.h"

Grid* grid;

void dancing_links_init(int** inBoard, int dim, int subHeight, int subWidth) {
    cout << "Initializing board..." << endl;
    // initialize game board
    try {
        grid = new Grid(inBoard, dim, subHeight, subWidth);
        cout << "blalkdfas" << grid->toString() << endl;
        grid->dancingLinks(inBoard);
    } catch (invalid_argument const &e) {
        cout << endl << e.what() << endl;
        return;
    }
}

void dancing_links_solve() {
    // solve the board
    chrono::steady_clock::time_point begin = chrono::steady_clock::now();
    cout << endl << grid->toString() << endl << endl;

    if (grid->solveDancingLinks()) {
        chrono::steady_clock::time_point end = chrono::steady_clock::now();
        auto duration = (chrono::duration_cast<chrono::nanoseconds>(end - begin).count() / 1000000.0);
        double milliseconds = static_cast<double>(duration);
        cout << "Puzzle has been solved in " << setprecision(3) << milliseconds << " milliseconds:\n\n" << grid->toString() << endl;
    } else {
        cout << "\nThe puzzle could not be solved." << endl << endl;
    }
    grid->destructDancingLinks();
    delete grid;
    grid = NULL;
}

extern "C" {
    void _dancing_links_init(int** inBoard, int dim, int subHeight, int subWidth) {
        return dancing_links_init(inBoard, dim, subHeight, subWidth);
    }

    void _dancing_links_solve() {
        return dancing_links_solve();
    }
}

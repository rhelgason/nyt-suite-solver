#include <iostream>
#include <fstream>
#include <chrono>
#include "Grid.h"
#include "Box.h"

void dancing_links_init(int** inBoard, int dim, int subHeight, int subWidth) {
    // initialize game board
    Grid* grid;
    try {
        grid = new Grid(inBoard, dim, subHeight, subWidth);
        grid->dancingLinks(inBoard);
    } catch (invalid_argument const &e) {
        cout << endl << e.what() << endl;
        return;
    }
/*
    // solve the board
    chrono::steady_clock::time_point begin = chrono::steady_clock::now();
    cout << "\nSolving this board:\n\n" << grid->toString() << "\n\nWorking..." << endl;
    if (grid->solveDancingLinks()) {
        chrono::steady_clock::time_point end = chrono::steady_clock::now();
        auto duration = (chrono::duration_cast<chrono::milliseconds>(end - begin).count() / 1000.0);
        double seconds = static_cast<double>(duration);
        if (seconds < 60) {
            cout << "Board has been solved in " << seconds << " seconds:\n\n" << grid->toString() << endl;
        } else  {
            int minutes = seconds / 60;
            seconds = seconds - (minutes * 60);
            cout << "Board has been solved in " << minutes << " minute" << (minutes == 1 ? "" : "s") <<
                " and " << seconds << " seconds:\n\n" << grid->toString() << endl << endl;
        }
    } else {
        cout << "\nThe board could not be solved." << endl << endl;
    }
    grid->destructDancingLinks();
    delete grid;
    grid = NULL;
*/
}

bool dancing_links_solve() {
    return true;
}

extern "C" {
    void _dancing_links_init(int** inBoard, int dim, int subHeight, int subWidth) {
        return dancing_links_init(inBoard, dim, subHeight, subWidth);
    }

    bool _dancing_links_solve() {
        return dancing_links_solve();
    }
}

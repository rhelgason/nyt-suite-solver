#include <iostream>
#include <fstream>
#include <chrono>
#include "Grid.h"
#include "Box.h"

Grid* grid;

void dancing_links_init(int** inBoard, int dim, int subHeight, int subWidth) {
    // initialize game board
    try {
        grid = new Grid(inBoard, dim, subHeight, subWidth);
        grid->dancingLinks(inBoard);
    } catch (invalid_argument const &e) {
        cout << endl << e.what() << endl;
        return;
    }
}

void dancing_links_solve(char* solvedBoard) {
    grid->solveDancingLinks();
    grid->toString(solvedBoard);
    grid->destructDancingLinks();
    delete grid;
    grid = NULL;
}

extern "C" {
    void _dancing_links_init(int** inBoard, int dim, int subHeight, int subWidth) {
        return dancing_links_init(inBoard, dim, subHeight, subWidth);
    }

    void _dancing_links_solve(char* solvedBoard) {
        return dancing_links_solve(solvedBoard);
    }
}

#include <iostream>
#include <fstream>
#include <chrono>
#include "Grid.h"
#include "Box.h"

Grid* grid;

// initialize the game board; returns false (and leaves grid NULL) if the
// scraped input board is invalid so the caller can fail cleanly
bool dancing_links_init(int** inBoard, int dim, int subHeight, int subWidth) {
    try {
        grid = new Grid(inBoard, dim, subHeight, subWidth);
        grid->dancingLinks(inBoard);
    } catch (invalid_argument const &e) {
        cout << endl << e.what() << endl;
        grid = NULL;
        return false;
    }
    return true;
}

// solve the board; returns whether a solution was found. Even on failure the
// output buffer is populated (with sentinels for unsolved cells) so the caller
// always receives a well-formed string.
bool dancing_links_solve(char* solvedBoard) {
    if (grid == NULL) return false;
    bool solved = grid->solveDancingLinks();
    grid->toString(solvedBoard);
    grid->destructDancingLinks();
    delete grid;
    grid = NULL;
    return solved;
}

extern "C" {
    bool _dancing_links_init(int** inBoard, int dim, int subHeight, int subWidth) {
        return dancing_links_init(inBoard, dim, subHeight, subWidth);
    }

    bool _dancing_links_solve(char* solvedBoard) {
        return dancing_links_solve(solvedBoard);
    }
}

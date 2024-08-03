#ifndef GRID_H
#define GRID_H

#include <iostream>
#include <fstream>
#include <string>
#include <set>
#include <vector>
#include "Box.h"
#include "Node.h"
using namespace std;

// class representing the entire board for the Sudoku puzzle.
class Grid {
    private:
        int dim;
        int subHeight;
        int subWidth;
        bool** rows;
        bool** cols;
        bool*** divs;
        Box*** board;

        // dancing links data structures
        Node* head;
        Node** colHeads;

    public:
        // basic constructor for the Grid
        Grid(int**& inBoard, int dim, int subHeight, int subWidth);
        
        // determine if a number is valid in a position
        bool valid(int row, int col, int num);

        // place a number in the tracking sets
        void track(int row, int col, int num);

        // remove a number from the tracking sets
        void untrack(int row, int col, int num);

        // constructor helper for dancing links method
        void dancingLinks(int** inBoard);

        // add a row to the dancing links matrix
        void linksRow(int row, int col, int num, int r);

        // recursive function for solving with dancing links
        bool solveDancingLinks();

        // returns a string version of the Grid for output
        string toString();

        // destructor for Grid class
        ~Grid();

        // destructor helper for dancing links
        void destructDancingLinks();
};

#endif

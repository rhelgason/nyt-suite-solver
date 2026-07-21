#ifndef BOX_H
#define BOX_H

#include <iostream>
using namespace std;

// class representing a single square of the Sudoku puzzle
class Box {
    private:
        int value;

    public:
        // basic constructor for initializing an unknown Box
        Box(int dim);

        // constructor for initializing a known Box
        Box(int dim, int val);

        // get the value of the Box
        int getValue();

        // set the value of the Box
        void setValue(int val);
};

#endif

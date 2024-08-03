#include <iostream>
#include <fstream>
#include <chrono>
#include "Grid.h"
#include "Box.h"

bool dancing_links_main(int** input_board, int dim) {
    // initialize game board
    Grid* grid;
    for (int i = 0; i < 9; i++) {
        for (int j = 0; j < 9; j++) {
            cout << input_board[i][j] << " ";
        }
        cout << endl;
    }
    return true;
    /*
    int** inBoard = NULL;
    int dim = 0;
    try {
        grid = new Grid(inFile, inBoard, dim);
        grid->dancingLinks(inBoard);
    } catch (invalid_argument const &e) {
        cout << endl << e.what() << endl;
        return 1;
    }
    inFile.close();
    for (int i = 0; i < dim; i++) {
        delete[] inBoard[i];
    }
    delete[] inBoard;
    inBoard = NULL;

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

extern "C" {
    bool _dancing_links_main(int** input_board, int dim) {
        return dancing_links_main(input_board, dim);
    }
}

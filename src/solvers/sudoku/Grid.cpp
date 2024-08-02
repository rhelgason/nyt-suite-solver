#include "Grid.h"

Grid::Grid(ifstream& inFile, int**& inBoard, int& dim) {
    string curr;
    try {
        inFile >> curr;
        dim = stoi(curr);
        if (dim > 16) throw out_of_range("");
        this->dim = dim;
        inFile >> curr;
        subHeight = stoi(curr);
        inFile >> curr;
        subWidth = stoi(curr);
        inFile >> curr;
        if (curr != "---") throw invalid_argument("");
        if (dim < 1 || subHeight < 1 || subWidth < 1 || subHeight * subWidth != dim) throw out_of_range("");
    } catch (invalid_argument const &e) {
        throw invalid_argument("Error: there was a mistake in the dimension input.");
    } catch (out_of_range const &e) {
        throw invalid_argument("Error: the input dimensions are not valid.");
    }

    // read the board contents
    inBoard = new int*[dim];
    for (int i = 0; i < dim; i++) inBoard[i] = new int[dim];
    for (int i = 0; i < dim; i++) {
        for (int j = 0; j < dim; j++) {
            // error checking for single input
            if (!(inFile >> curr)) throw invalid_argument("Error: the input board did not contain enough information.");
            if (curr == ".") {
                inBoard[i][j] = -1;
            }
            else {
                int temp;
                try {
                    temp = stoi(curr, 0, 16);
                } catch (out_of_range const &e) {
                    throw invalid_argument("Error: inputs must be between 1 and " + to_string(dim) + ", inclusive.");
                } catch (invalid_argument const &e) {
                    throw invalid_argument("Error: some input in the board was invalid.");
                }
                if (dim == 16) {
                    if (temp > dim || temp < 0) throw invalid_argument("Error: inputs must be between 0 and " + to_string(dim) + ", inclusive.");
                } else {
                    if (temp > dim || temp < 1) throw invalid_argument("Error: inputs must be between 1 and " + to_string(dim) + ", inclusive.");
                }
                if (temp == 0) temp = 16;
                inBoard[i][j] = temp;
            }
        }
    }
    if (inFile >> curr) throw invalid_argument("Error: the input file contained too much information.");

    // initialize tracking sets
    rows = new bool*[dim];
    cols = new bool*[dim];
    divs = new bool**[subWidth];
    for (int i = 0; i < dim; i++) {
        rows[i] = new bool[dim];
        cols[i] = new bool[dim];
        for (int j = 0; j < dim; j++) {
            rows[i][j] = false;
            cols[i][j] = false;
        }
    }
    for (int i = 0; i < subWidth; i++) {
        divs[i] = new bool*[subHeight];
        for (int j = 0; j < subHeight; j++) {
            divs[i][j] = new bool[dim];
            for (int k = 0; k < dim; k++) {
                divs[i][j][k] = false;
            }
        }
    }

    // initialize game board
    board = new Box**[dim];
    for (int i = 0; i < dim; i++) {
        board[i] = new Box*[dim];

        for (int j = 0; j < dim; j++) {
            if (inBoard[i][j] == -1) {
                board[i][j] = new Box(dim);
            } else {
                if (valid(i, j, inBoard[i][j])) {
                    board[i][j] = new Box(dim, inBoard[i][j]);
                    track(i, j, inBoard[i][j]);
                } else {
                    throw invalid_argument("Error: the input board was not valid at row " + to_string(i) + " and column " + to_string(j) + ".");
                }
            }
        }
    }

    // empty tracking sets
    for (int i = 0; i < dim; i++) {
        for (int j = 0; j < dim; j++) {
            rows[i][j] = false;
            cols[i][j] = false;
        }
    }
    for (int i = 0; i < subWidth; i++) {
        for (int j = 0; j < subHeight; j++) {
            for (int k = 0; k < dim; k++) {
                divs[i][j][k] = false;
            }
        }
    }
}

bool Grid::valid(int row, int col, int num) {
    // check if already used
    if (rows[row][num - 1]) return false;
    if (cols[col][num - 1]) return false;
    if (divs[row / subHeight][col / subWidth][num - 1]) return false;
    return true;
}

void Grid::track(int row, int col, int num) {
    rows[row][num - 1] = true;
    cols[col][num - 1] = true;
    divs[row / subHeight][col / subWidth][num - 1] = true;
}

void Grid::untrack(int row, int col, int num) {
    rows[row][num - 1] = false;
    cols[col][num - 1] = false;
    divs[row / subHeight][col / subWidth][num - 1] = false;
}

void Grid::dancingLinks(int** inBoard) {
    // initialize header row
    colHeads = new Node*[dim * dim * 4];
    head = new Node();
    Node* curr = head;
    for (int i = 0; i < (dim * dim * 4); i++) {
        curr->setRight(new Node(curr, head));
        curr = curr->getRight();
        head->setLeft(curr);
        colHeads[i] = curr;
    }

    // initialize matrix
    curr = head->getRight();
    for (int i = 0; i < (dim * dim * dim); i++) {
        // determine if value is known
        int row = i / (dim * dim);
        int col = (i % (dim * dim)) / dim;
        int num = ((i % (dim * dim)) % dim) + 1;
        if (inBoard[row][col] == -1 || inBoard[row][col] == num) {
            linksRow(row, col, num, i);
        }
    }
}

void Grid::linksRow(int row, int col, int num, int r) {
    // cell constraint
    int val = (row * dim) + col;
    Node* colHead = colHeads[val];
    colHead->setUp(new Node(NULL, NULL, colHead->getUp(), colHead, colHead, r));
    Node* curr = colHead->getUp();
    curr->getUp()->setDown(curr);
    Node* first = curr;

    // row constraint
    val = (dim * dim) + (row * dim) + (num - 1);
    colHead = colHeads[val];
    colHead->setUp(new Node(curr, NULL, colHead->getUp(), colHead, colHead, r));
    curr = colHead->getUp();
    curr->getLeft()->setRight(curr);
    curr->getUp()->setDown(curr);

    // column constraint
    val = (dim * dim * 2) + (col * dim) + (num - 1);
    colHead = colHeads[val];
    colHead->setUp(new Node(curr, NULL, colHead->getUp(), colHead, colHead, r));
    curr = colHead->getUp();
    curr->getLeft()->setRight(curr);
    curr->getUp()->setDown(curr);

    // subgrid constraint
    int box = (col / subWidth) + (row / subHeight) * subHeight;
    val = (dim * dim * 3) + (box * dim) + (num - 1);
    colHead = colHeads[val];
    colHead->setUp(new Node(curr, first, colHead->getUp(), colHead, colHead, r));
    curr = colHead->getUp();
    curr->getLeft()->setRight(curr);
    curr->getUp()->setDown(curr);
    first->setLeft(curr);
}

bool Grid::solveDancingLinks() {
    // check for solution
    if (head->getRight() == head) return true;

    // deterministically select column
    Node* low = head->getRight();
    Node* curr = low->getRight();
    while (curr != head) {
        if (curr->getCand() < low->getCand()) low = curr;
        curr = curr->getRight();
    }
    low->cover();

    // nondeterministically try rows
    curr = low->getDown();
    while (curr != low) {
        // cover columns for partial solution
        Node* rowCurr = curr->getRight();
        while (rowCurr != curr) {
            rowCurr->getColHead()->cover();
            rowCurr = rowCurr->getRight();
        }

        if (solveDancingLinks()) {
            // uncover for destruction
            rowCurr = curr->getLeft();
            while (rowCurr != curr) {
                rowCurr->getColHead()->uncover();
                rowCurr = rowCurr->getLeft();
            }
            low->uncover();

            // add valid solution to grid
            int r = curr->getRow();
            int row = r / (dim * dim);
            int col = (r % (dim * dim)) / dim;
            int num = ((r % (dim * dim)) % dim) + 1;
            board[row][col]->setValue(num);
            return true;
        } else {
            // uncover and continue search
            rowCurr = curr->getLeft();
            while (rowCurr != curr) {
                rowCurr->getColHead()->uncover();
                rowCurr = rowCurr->getLeft();
            }
        }

        curr = curr->getDown();
    }

    // no solution was found
    low->uncover();
    return false;
}

string Grid::toString() {
    char hex[16] = {'1', '2', '3', '4', '5', '6', '7', '8', '9', 'A', 'B', 'C', 'D', 'E', 'F', '0'};
    string out = "";
    for (int i = 0; i < dim; i++) {
        for (int j = 0; j < dim; j++) {
            int val = board[i][j]->getValue();
            out += (val == -1) ? '.' : hex[val - 1];
            if (j != dim - 1) out += " ";
            else break;
            if ((j + 1) % subWidth == 0) out += "| ";
        }
        if (i != dim - 1) out += "\n";
        if ((i + 1) % subHeight == 0 && i + 1 != dim) {
            for (int j = 0; j < dim; j++) {
                out += '-';
                if (j != dim - 1) out += "-";
                else break;
                if ((j + 1) % subWidth == 0) out += "+-";
            }
            out += "\n";
        }
    }
    return out;
}

Grid::~Grid() {
    // destruct tracking sets
    for (int i = 0; i < dim; i++) {
        delete[] rows[i];
        delete[] cols[i];
    }
    delete[] rows;
    delete[] cols;
    for (int i = 0; i < subWidth; i++) {
        for (int j = 0; j < subHeight; j++) {
            delete[] divs[i][j];
        }
        delete[] divs[i];
    }
    delete[] divs;

    // destruct game board
    for (int i = 0; i < dim; i++) {
        for (int j = 0; j < dim; j++) {
            delete board[i][j];
        }
        delete[] board[i];
    }
    delete[] board;
}

void Grid::destructDancingLinks() {
    // destruct matrix
    Node* curr = head->getRight();
    while (curr != head) {
        Node* currMat = curr->getDown();
        while (currMat != curr) {
            currMat = currMat->getDown();
            delete currMat->getUp();
        }
        curr = curr->getRight();
    }

    // destruct column headers
    curr = head->getRight();
    while (curr != head) {
        curr = curr->getRight();
        delete curr->getLeft();
    }
    delete[] colHeads;
    delete head;
}

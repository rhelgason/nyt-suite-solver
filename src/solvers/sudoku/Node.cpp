#include "Node.h"

Node::Node() {
    left = right = up = down = colHead = this;
    cand = -1;
}

Node::Node(Node* l, Node *r) {
    left = l;
    right = r;
    up = down = colHead = this;
    cand = 0;
}

Node::Node(Node* l, Node* r, Node* u, Node* d, Node* c, int row) {
    left = l;
    right = r;
    up = u;
    down = d;
    colHead = c;
    c->addCand();
    this->row = row;
}

void Node::setRight(Node * n) {
    right = n;
}

void Node::setLeft(Node * n) {
    left = n;
}

void Node::setUp(Node * n) {
    up = n;
}

void Node::setDown(Node * n) {
    down = n;
}

Node* Node::getRight() {
    return right;
}

Node* Node::getLeft() {
    return left;
}

Node* Node::getUp() {
    return up;
}

Node* Node::getDown() {
    return down;
}

Node* Node::getColHead() {
    return colHead;
}

void Node::addCand() {
    cand++;
}

void Node::removeCand() {
    cand--;
}

int Node::getCand() {
    return cand;
}

int Node::getRow() {
    return row;
}

void Node::cover() {
    // cover header node
    left->setRight(right);
    right->setLeft(left);

    // cover related nodes in matrix
    Node* colCurr = down;
    while (colCurr != this) {
        Node* rowCurr = colCurr->getRight();
        while (rowCurr != colCurr) {
            rowCurr->getUp()->setDown(rowCurr->getDown());
            rowCurr->getDown()->setUp(rowCurr->getUp());
            rowCurr->getColHead()->removeCand();
            rowCurr = rowCurr->getRight();
        }
        colCurr = colCurr->getDown();
    }
}

void Node::uncover() {
    // uncover related nodes in matrix
    Node* colCurr = up;
    while (colCurr != this) {
        Node* rowCurr = colCurr->getLeft();
        while (rowCurr != colCurr) {
            rowCurr->getColHead()->addCand();
            rowCurr->getUp()->setDown(rowCurr);
            rowCurr->getDown()->setUp(rowCurr);
            rowCurr = rowCurr->getLeft();
        }
        colCurr = colCurr->getUp();
    }

    // uncover header node
    left->setRight(this);
    right->setLeft(this);
}

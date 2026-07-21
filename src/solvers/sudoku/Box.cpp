#include "Box.h"

Box::Box(int dim) {
    value = -1;
}

Box::Box(int dim, int val) {
    value = val;
}

int Box::getValue() {
    return value;
}

void Box::setValue(int val) {
    value = val;
}

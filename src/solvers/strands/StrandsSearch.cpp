// Exact-cover search for NYT Strands, in C++ for speed.
//
// The board (<= 64 cells) is a single uint64 bitmask, so cover/uncover and
// disjointness are O(1). Two passes, mirroring the Python hybrid but ~20-50x
// faster (so the budget explores far deeper):
//   1) Fast exact cover: tile every cell with valid words, at least one spanning
//      opposite sides (the spangram is one dictionary word or a chain of them).
//   2) Leftover pass: place exactly NUM_WORDS theme words and require the
//      remaining cells to form one connected king-path spanning opposite sides
//      (the spangram, never dictionary-matched -> phrase spangrams work).
// Both branch on the most-constrained cells first (corners -> edges -> interior),
// a cheap static approximation of MRV.
#include <algorithm>
#include <cstdint>
#include <ctime>
#include <vector>

using namespace std;
typedef unsigned long long u64;

namespace {

const int MAX_WORDS_TOTAL = 9;
const long HAM_STEP_BUDGET = 200000;

int N_CELLS, ROWS, COLS, NUM_WORDS, MAX_SPANGRAM, N_THEME;
long NODE_BUDGET;
double CUR_TIME_BUDGET;
const u64* MASKS;
const int* WORD_IDS;
int THEME[32];
u64 FULL;

vector<vector<int>> CELL_TO_PL;  // cell -> placement indices (longest word first)
vector<vector<int>> ADJ;         // cell -> king-move neighbours
vector<char> IS_SPAN;            // placement -> spans opposite sides?
vector<int> CELL_ORDER;          // corner/edge-first cell ordering

long nodes, ham_steps;
clock_t start_clk;
bool exhausted, solved_flag;
int best_overlap;
long candidate_count;
int chosen_ids[MAX_WORDS_TOTAL + 1];

void reset_budget(double time_budget) {
    nodes = 0;
    start_clk = clock();
    CUR_TIME_BUDGET = time_budget;
    exhausted = false;
}

bool budget_ok() {
    if (++nodes > NODE_BUDGET) { exhausted = true; return false; }
    if ((nodes & 4095) == 0 &&
        (double)(clock() - start_clk) / CLOCKS_PER_SEC > CUR_TIME_BUDGET) {
        exhausted = true;
        return false;
    }
    return true;
}

int first_unassigned(u64 assigned) {
    for (int c : CELL_ORDER) {
        if (!((assigned >> c) & 1)) return c;
    }
    return -1;
}

bool span_bits(u64 mask) {
    bool top = false, bot = false, lft = false, rgt = false;
    for (int c = 0; c < N_CELLS; c++) {
        if (!((mask >> c) & 1)) continue;
        int r = c / COLS, col = c % COLS;
        if (r == 0) top = true;
        if (r == ROWS - 1) bot = true;
        if (col == 0) lft = true;
        if (col == COLS - 1) rgt = true;
    }
    return (top && bot) || (lft && rgt);
}

bool ham_extend(int cell, u64 target, u64 seen, int remaining) {
    if (remaining == 0) return true;
    if (++ham_steps > HAM_STEP_BUDGET) return false;
    for (int nb : ADJ[cell]) {
        u64 bit = 1ULL << nb;
        if ((target & bit) && !(seen & bit)) {
            if (ham_extend(nb, target, seen | bit, remaining - 1)) return true;
            if (ham_steps > HAM_STEP_BUDGET) return false;
        }
    }
    return false;
}

bool spangram_valid(u64 mask) {
    int cnt = __builtin_popcountll(mask);
    if (cnt < 1 || cnt > MAX_SPANGRAM) return false;
    if (!span_bits(mask)) return false;
    ham_steps = 0;
    for (int c = 0; c < N_CELLS; c++) {
        if (!((mask >> c) & 1)) continue;
        if (ham_extend(c, mask, 1ULL << c, cnt - 1)) return true;
        if (ham_steps > HAM_STEP_BUDGET) return false;
    }
    return false;
}

int theme_overlap(int depth) {
    int overlap = 0;
    for (int j = 0; j < N_THEME; j++) {
        for (int i = 0; i < depth; i++) {
            if (chosen_ids[i] == THEME[j]) { overlap++; break; }
        }
    }
    return overlap;
}

// Pass 1: full word cover with at least one spanning word.
void dfs_words(u64 covered, int depth, int spanning_count) {
    if (solved_flag || exhausted) return;
    if (!budget_ok()) return;
    if (covered == FULL) {
        if (spanning_count >= 1) {
            candidate_count++;
            int overlap = theme_overlap(depth);
            if (overlap > best_overlap) best_overlap = overlap;
            if (overlap == N_THEME) solved_flag = true;
        }
        return;
    }
    if (depth >= MAX_WORDS_TOTAL) return;
    int cell = first_unassigned(covered);
    for (int idx : CELL_TO_PL[cell]) {
        if (MASKS[idx] & covered) continue;
        chosen_ids[depth] = WORD_IDS[idx];
        dfs_words(covered | MASKS[idx], depth + 1, spanning_count + IS_SPAN[idx]);
        if (solved_flag || exhausted) return;
    }
}

// Pass 2: exactly NUM_WORDS theme words plus a leftover spangram strand.
void dfs_leftover(u64 covered, u64 reserved, int depth) {
    if (solved_flag || exhausted) return;
    if (!budget_ok()) return;
    if (depth == NUM_WORDS) {
        if (spangram_valid(FULL & ~covered)) {
            candidate_count++;
            int overlap = theme_overlap(depth);
            if (overlap > best_overlap) best_overlap = overlap;
            if (overlap == N_THEME) solved_flag = true;
        }
        return;
    }
    u64 assigned = covered | reserved;
    if (assigned == FULL) return;
    int cell = first_unassigned(assigned);
    for (int idx : CELL_TO_PL[cell]) {
        if (MASKS[idx] & assigned) continue;
        chosen_ids[depth] = WORD_IDS[idx];
        dfs_leftover(covered | MASKS[idx], reserved, depth + 1);
        if (solved_flag || exhausted) return;
    }
    if (__builtin_popcountll(reserved) < MAX_SPANGRAM) {
        dfs_leftover(covered, reserved | (1ULL << cell), depth);
    }
}

}  // namespace

extern "C" int strands_solve(const u64* masks, const int* word_ids, int n_placements,
                             int n_cells, int rows, int cols, int num_words,
                             const int* theme_ids, int n_theme, int max_spangram,
                             long node_budget, double words_time, double leftover_time,
                             int* out_best_overlap, long* out_candidates) {
    MASKS = masks;
    WORD_IDS = word_ids;
    N_CELLS = n_cells;
    ROWS = rows;
    COLS = cols;
    NUM_WORDS = num_words;
    MAX_SPANGRAM = max_spangram;
    NODE_BUDGET = node_budget;
    N_THEME = n_theme;
    for (int i = 0; i < n_theme && i < 32; i++) THEME[i] = theme_ids[i];
    FULL = (n_cells >= 64) ? ~0ULL : ((1ULL << n_cells) - 1);

    CELL_TO_PL.assign(n_cells, {});
    for (int i = 0; i < n_placements; i++) {
        for (int c = 0; c < n_cells; c++) {
            if ((masks[i] >> c) & 1) CELL_TO_PL[c].push_back(i);
        }
    }
    IS_SPAN.assign(n_placements, 0);
    for (int i = 0; i < n_placements; i++) IS_SPAN[i] = span_bits(masks[i]) ? 1 : 0;

    ADJ.assign(n_cells, {});
    int dr[8] = {-1, -1, -1, 0, 0, 1, 1, 1};
    int dc[8] = {-1, 0, 1, -1, 1, -1, 0, 1};
    for (int c = 0; c < n_cells; c++) {
        int r = c / cols, col = c % cols;
        for (int k = 0; k < 8; k++) {
            int nr = r + dr[k], nc = col + dc[k];
            if (nr >= 0 && nr < rows && nc >= 0 && nc < cols) ADJ[c].push_back(nr * cols + nc);
        }
    }
    CELL_ORDER.resize(n_cells);
    for (int c = 0; c < n_cells; c++) CELL_ORDER[c] = c;
    stable_sort(CELL_ORDER.begin(), CELL_ORDER.end(),
                [](int a, int b) { return ADJ[a].size() < ADJ[b].size(); });

    best_overlap = 0;
    candidate_count = 0;
    solved_flag = false;

    reset_budget(words_time);
    dfs_words(0, 0, 0);
    if (!solved_flag) {
        reset_budget(leftover_time);
        dfs_leftover(0, 0, 0);
    }

    *out_best_overlap = best_overlap;
    *out_candidates = candidate_count;
    return solved_flag ? 1 : 0;
}

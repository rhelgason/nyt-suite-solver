# nyt-suite-solver

Algorithms that solve the daily New York Times puzzle suite and log how
effectively each puzzle was solved. Solvers are algorithmic wherever possible
(no AI); the two games with no clean algorithm, Connections and the Mini
crossword, use an LLM, and even the Mini keeps its grid fill deterministic. It
runs every day on its own via GitHub Actions, with no server required, and can
also be used interactively or headlessly.

<!-- STATS:START -->
## Lifetime results

_Auto-generated from `solutions/` · **3929** puzzles solved across 7 games (through 2026-07-22)._

<div align="center">
<table>
<tr><th>Game</th><th>Puzzles</th><th>Avg score</th><th>p90 runtime</th></tr>
<tr><td>Spelling Bee</td><td>10</td><td>99.3%</td><td>105 ms</td></tr>
<tr><td>Letter Boxed</td><td>2</td><td>2.0 words</td><td>116 ms</td></tr>
<tr><td>Sudoku</td><td>6</td><td>100%</td><td>0.23 ms</td></tr>
<tr><td>Wordle (easy)</td><td>1860</td><td>3.8 guesses</td><td>7.10 s</td></tr>
<tr><td>Wordle (hard)</td><td>1860</td><td>3.9 guesses</td><td>492 ms</td></tr>
<tr><td>Strands</td><td>189</td><td>76% words</td><td>65.37 s</td></tr>
<tr><td>Connections</td><td>1</td><td>0%</td><td>11.53 s</td></tr>
<tr><td>Mini Crossword</td><td>1</td><td>58% cells</td><td>3.31 s</td></tr>
</table>
</div>
<!-- STATS:END -->

The results above refresh automatically: a scheduled GitHub Actions workflow
solves every game each morning and commits the new results, so this page stays
up to date with no hosted service.

## How the solvers work

### Spelling Bee

Spelling Bee shows seven letters, one of them required, and asks for every word
that uses only those letters and includes the required one. The solver loads a
human wordlist into a trie and walks it to collect the valid words and pangrams,
scoring each by length with a bonus for pangrams. That score is compared against
the puzzle's official answer list to produce a percentage and a rank from
Beginner up to Queen Bee. Because it searches a realistic vocabulary rather than
the official answers, the result reflects how well that vocabulary covers each
day's puzzle.

<p align="center"><img src="stats/spelling_bee_scores.svg" alt="Spelling Bee score distribution" width="520"></p>

### Letter Boxed

Letter Boxed puts twelve letters on the four sides of a square and asks you to
spell a chain of words that uses every letter, where each word begins with the
previous word's last letter and no two consecutive letters share a side. The
solver builds a trie of board-legal words from a human wordlist and runs a
depth-first search for the shortest chain, capped at two words, that covers all
twelve letters. Candidate solutions are then checked against NYT's accepted
dictionary. The chart below shows how often the puzzle is solvable in a single
word versus two.

<p align="center"><img src="stats/letter_boxed_words.svg" alt="Letter Boxed words per solution" width="520"></p>

### Sudoku

Sudoku is treated as an exact-cover problem and solved with Donald Knuth's
Algorithm X using the Dancing Links technique, written as a C++ extension. Every
cell, row, column, and box rule becomes a column in a sparse matrix of
doubly-linked nodes, and the algorithm repeatedly covers the most-constrained
column and backtracks until each rule is satisfied exactly once. It finds the
unique solution in well under a millisecond on every difficulty, so there is no
chart here; the p90 runtime above tells the whole story.

### Wordle

Wordle gives six tries to guess a hidden five-letter word. The solver treats each
turn as an information-theory question: it scores every candidate by the expected
information (Shannon entropy) its feedback would reveal and plays the guess that,
on average, eliminates the most remaining words. The opening guess is therefore
the same every day (`tares`, the highest-entropy word in the vocabulary), after
which it recomputes the best next guess from the feedback so far. Two modes are
tracked: **hard** may only guess words still consistent with every clue, while
**easy** may play any word (even one it knows cannot be the answer) purely to
extract more information, so it tends to solve in fewer guesses. Like the other
games it plays from a human vocabulary, not the official answer list, and the
chart compares how many guesses each mode needs (X marks a miss).

<p align="center"><img src="stats/wordle_guesses.svg" alt="Wordle guess distribution by mode" width="720"></p>

### Strands

Strands hides a set of theme words plus a spanning "spangram" in a 6x8 grid,
where the answers tile the board so every letter is used exactly once. There is
no theme understanding here at all: the solver treats it as a pure exact-cover
puzzle, finding every valid word-path (king moves) from a human wordlist and
searching for ways to partition all 48 cells into a few long words with one path
spanning opposite sides. It keeps every candidate partition and counts a puzzle
as solved when one of them recovers all the theme words. It will not crack every
board (English offers many valid tilings, and spangrams are usually multi-word
phrases we cannot match as a single word), but getting some without any AI is the
fun of it.

<p align="center"><img src="stats/strands_outcomes.svg" alt="Strands outcomes" width="520"></p>

### Connections

Connections splits 16 words into 4 hidden groups joined by wordplay, trivia, or a
shared prefix, which has no clean algorithm, so this is a deliberate LLM solver.
It never sees the answer key while solving: each turn the model reasons over the
whole remaining board, proposes the full split ordered by confidence, and the
solver guesses the surest group first, replanning with the real "one away" and
wrong-guess feedback until it wins or spends its four mistakes. The LLM runs on
GitHub Models using the daily workflow's built-in token, so it stays free with no
API key to manage; if the model is unavailable the game is simply recorded as
unsolved. The score reflects realistic play rather than a trivial win, since a
wrong group costs a mistake just as it would for a person.

<p align="center"><img src="stats/connections_groups.svg" alt="Connections groups found" width="520"></p>

### Mini crossword

The Mini is the project's clearest hybrid: an LLM answers the clues, but a
deterministic search fills the grid. In one batched call the model proposes a few
candidate answers per clue at the exact required length; a backtracking
constraint solver then tiles the 5x5 so every crossing letter agrees, using a
human wordlist as backup, so a wrong clue answer is corrected by its crossings
instead of poisoning the grid. Any slot it still cannot place is re-queried once
with the known letters shown, then the search runs again. Only the Mini is free
to fetch; the full-size Daily and Sunday crosswords are locked behind a NYT
subscription, so they are intentionally left out.

<p align="center"><img src="stats/crossword_passfail.svg" alt="Mini crossword pass/fail" width="520"></p>

## Running it yourself

The `make` targets create an isolated virtualenv on first run, so nothing
touches your system Python.

Interactive terminal UI:
```
make run
```

Solve headlessly (all games today, a specific date, or a backfill):
```
.venv/bin/python src/cli.py
.venv/bin/python src/cli.py --game spelling-bee --date 2026-07-20
.venv/bin/python src/cli.py --game spelling-bee --backfill
```

Connections and the Mini crossword call an LLM. In GitHub Actions this is free
via GitHub Models (the workflow's `GITHUB_TOKEN` with `models: read`). To run
them locally, export a provider credential first, otherwise they record an
unsolved result:
```
export GITHUB_TOKEN=...   # a PAT with the Models permission
# or: export GEMINI_API_KEY=...   # free-tier fallback
.venv/bin/python src/cli.py --game connections
.venv/bin/python src/cli.py --game crossword
```

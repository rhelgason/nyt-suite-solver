# nyt-suite-solver

Algorithms that solve the daily New York Times puzzle suite and log how
effectively each puzzle was solved. It runs every day on its own via GitHub
Actions — no server required — and can also be used interactively or headlessly.

## Games & solvers

| Game | Approach | Word source |
|------|----------|-------------|
| Letter Boxed | Trie-backed search for 1–2 word solutions covering all sides | `wordlist_small.txt` |
| Spelling Bee | Trie word search, scored to a rank (Beginner → Queen Bee) | `wordlist.txt` |
| Sudoku | Donald Knuth's Dancing Links / Algorithm X exact cover (C++) | scraped board |

All solvers are **fully algorithmic — no AI/LLM calls.** Puzzles are scraped from
the NYT site (`window.gameData`) and results are written to `solutions/<game>/`.

<!-- STATS:START -->
## Latest results

_Auto-generated from `solutions/` (latest puzzle 2026-07-21)._

### Spelling Bee

- Puzzles solved: **33** (2024-07-22 → 2026-07-21)
- Score: avg **98.0%** · best **100%** · latest **100%** (QUEEN_BEE)

```mermaid
xychart-beta
    title "Spelling Bee score % by date"
    x-axis ["24-07-25", "24-08-03", "24-08-04", "24-08-05", "24-08-12", "24-08-13", "24-08-14", "24-08-15", "24-08-16", "24-08-19", "24-08-20", "24-08-21", "24-08-23", "26-07-13", "26-07-14", "26-07-15", "26-07-16", "26-07-17", "26-07-18", "26-07-19", "26-07-20", "26-07-21"]
    y-axis "Score %" 0 --> 100
    bar [100, 99, 94, 98, 90, 99, 99, 100, 99, 87, 100, 99, 97, 99, 100, 97, 100, 100, 100, 100, 100, 100]
```

### Letter Boxed

- Puzzles solved: **3** (2024-08-22 → 2026-07-21)
- Valid solutions/day: avg **24.7** · latest **2** · avg shortest solution **2.0** words

### Sudoku

- Puzzles solved: **7** (2024-08-20 → 2026-07-21) — easy: 2, hard: 3, medium: 2
- Solved successfully: **7/7** · avg solve time **0.24 ms**
<!-- STATS:END -->

## Design philosophy

See [`CLAUDE.md`](CLAUDE.md) for the full rationale. In short:

1. **Assess realistic human solving.** Solvers use a local human-realistic
   wordlist and use NYT's official answer/dictionary lists only to score and
   validate — never to solve. (Solving from the answer list would trivially win
   and measure nothing.)
2. **Prefer deterministic algorithms over AI.** Reach for an LLM only for a
   puzzle that genuinely can't be solved otherwise (e.g. a future Crossword).
3. **Solvers stay pure and headless**, decoupled from the interactive TUI.

## Usage

The `make` targets create and use an isolated virtualenv (`.venv`) on first run
and install dependencies there, so nothing touches your system Python.

Interactive terminal UI (arrow-key menus):
```
make run
```

Run the offline test suite:
```
make test
```

Headless — used by the daily automation, and for backfilling. Run through the
venv (created by `make setup`):
```
.venv/bin/python src/cli.py                                # all games, today
.venv/bin/python src/cli.py --game spelling-bee --date 2026-07-20
.venv/bin/python src/cli.py --game sudoku --difficulty hard
.venv/bin/python src/cli.py --game spelling-bee --backfill # every archived date
```

> On macOS the interactive TUI needs Accessibility permission for your terminal
> (pynput's global key listener). The headless CLI has no such requirement.

## Output & stats

Each solved puzzle writes a JSON file under `solutions/<game>/` capturing the
puzzle, the solution(s), and performance metrics:

- **Spelling Bee**: `score`, `percentage`, `rank`, `pangrams`, `missed_answers`, `solve_time`
- **Letter Boxed**: `valid_answers`, `invalid_answers`, `shortest_answer_length`, `solve_time`
- **Sudoku**: `input_puzzle`, `solved_puzzle`, `solve_time`

Historical results are surfaced in the **[Latest results](#latest-results)**
section above, which `src/stats.py` regenerates from these JSON files. The daily
workflow refreshes it on every run, so the repo's front page stays up to date
with no hosted service. Regenerate locally with `make stats`.

## Automation

- **`.github/workflows/daily.yml`** — solves every game each morning and commits
  the results, so puzzles are solved and logged daily with no server.
- **`.github/workflows/tests.yml`** — runs the unit tests on every push and PR.

## Data availability

NYT only serves today's puzzle for Letter Boxed and Sudoku, so those accumulate
going forward. Spelling Bee exposes a ~1-week public archive (captured by
`--backfill`); deeper history requires a logged-in subscription session.

## Project layout

- `src/solvers/<game>/` — solver classes (pure logic + scraping)
- `src/solvers/scraping.py`, `src/solvers/BaseSolver.py` — shared helpers
- `src/cli.py` — headless entrypoint
- `src/main.py`, `src/menus.py`, `src/game_runner.py` — interactive TUI
- `tests/` — offline pytest suite

## Milestones

- [X] Letter Boxed — solver + daily upload
- [X] Spelling Bee — solver + daily upload + archive backfill
- [X] Sudoku — solver + daily upload
- [X] Stat tracking (per-puzzle)
- [X] Daily automation (GitHub Actions cron)
- [X] Auto-updating stats in the README (no hosted UI)

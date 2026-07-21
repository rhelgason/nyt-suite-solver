# nyt-suite-solver — project context

Algorithms that solve the daily New York Times puzzle suite (Letter Boxed,
Spelling Bee, Sudoku) and log how effectively each was solved. Runs daily via
GitHub Actions with no server required; also usable interactively or headlessly.

## Design principles

### 1. Assess realistic human solving — don't cheat with the answer list
Each solver searches a **local, human-realistic wordlist**, never NYT's official
answer data:
- Letter Boxed solves from `wordlist_small.txt`; Spelling Bee from `wordlist.txt`.
- NYT's supplied lists (Spelling Bee `answers`, Letter Boxed `dictionary`) are
  used **only to score and validate** results — rank, percentage, missed answers,
  valid vs. invalid solutions — and are **never** the source of solutions.
- Solving from the official list would trivially "win" every puzzle and measure
  nothing. To find *more* solutions, improve the wordlist; do not borrow answers.

### 2. Prefer deterministic algorithms over AI/LLMs
Solve with real algorithms wherever possible; avoid LLM calls unless a puzzle
genuinely cannot be solved otherwise.
- Current solvers are fully algorithmic: trie-backed word search (Letter Boxed,
  Spelling Bee) and a Dancing Links / Algorithm X exact-cover solver in C++
  (Sudoku). No AI is involved, and that is the goal.
- A future puzzle such as the **Crossword** would likely require an LLM (clue
  semantics have no clean algorithm). That is an acceptable exception — but reach
  for an LLM only when there is no reasonable deterministic approach, and
  document why in that solver.

### 3. Solvers are pure and headless
Solver classes contain solving + scraping only. All interactive/terminal
(`pynput`) code lives in `menus.py` / `game_runner.py`, so solvers import and run
headlessly (CI, cron) with no display. Keep it that way — never import the menu
layer from a solver.

### 4. Surface results without a hosted service
Historical results live in the committed `solutions/*.json` and are rendered into
an auto-generated `## Latest results` section of the README (between
`<!-- STATS:START -->` / `<!-- STATS:END -->` markers) by `src/stats.py`, using
GitHub-native Mermaid charts (no committed images). The daily workflow
regenerates it on every run. Deliberately **no hosted Web UI** — the README is
the dashboard. If you add metrics, extend `stats.py` and keep it dependency-free
(standard library only) so it runs anywhere.

## Layout
- `src/solvers/<game>/` — one solver class per game (pure logic + scraping)
- `src/solvers/BaseSolver.py` — shared date/id state + solution writing
- `src/solvers/scraping.py` — the single NYT `window.gameData` fetch/parse helper
- `src/cli.py` — headless entrypoint (daily run + backfill)
- `src/main.py`, `src/menus.py`, `src/game_runner.py` — interactive TUI
- `solutions/<game>/*.json` — logged results (one file per puzzle/day)
- `tests/` — offline pytest suite (no network; uses fixtures)
- `.github/workflows/` — `daily.yml` (scheduled solve) + `tests.yml` (CI)

## Working on this repo
- `make` targets create/use an isolated `.venv` (system Python is externally
  managed and rejects `pip install`). `make run`, `make test`, `make setup`.
- Run tests: `make test` (builds the Sudoku extension, then pytest)
- Solve headlessly: `.venv/bin/python src/cli.py --game all`
- Data availability: NYT serves only today's puzzle for Letter Boxed & Sudoku;
  a ~1-week public archive for Spelling Bee. Deeper backfill needs a subscriber
  login.

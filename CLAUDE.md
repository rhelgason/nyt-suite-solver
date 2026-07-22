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
- The algorithmic solvers use no AI, and that is the goal: trie-backed word
  search (Letter Boxed, Spelling Bee), a Dancing Links / Algorithm X exact-cover
  solver in C++ (Sudoku), a constraint-filtering / information-gain solver
  (Wordle), and an exact-cover grid-partition search (Strands, with a C++
  extension `StrandsSearch.so` for speed and a pure-Python fallback). Strands
  notably has no theme understanding at all — it relies purely on the
  combinatorial rigidity of tiling the grid, so it only solves a fraction of
  puzzles, which is expected and acceptable.
- Both C/C++ extensions are built by `make build` (which the CI and daily
  workflows run); the `.so` files are gitignored and rebuilt per environment.
- **Connections** and the **Mini crossword** are the sanctioned LLM exceptions:
  grouping 16 trivia/wordplay words and answering natural-language clues have no
  reasonable deterministic algorithm. Even so, the algorithmic half stays
  algorithmic — the Mini's LLM only supplies candidate answers and a
  deterministic backtracking CSP fills the grid with crossing constraints; and
  both solve from the model's reasoning, using NYT's answer data only to score.
  All LLM calls go through the single client in `src/solvers/llm.py`.
- The LLM client defaults to **GitHub Models** (authenticated by the workflow's
  built-in `GITHUB_TOKEN`, so there is no external API key to create, rotate, or
  expire), with an optional `GEMINI_API_KEY` free-tier fallback. `daily.yml`
  grants `permissions: models: read`. If no provider is configured or all fail,
  the solver records an unsolved result rather than crashing the daily run.
- **Data availability caveat:** only the Mini is freely fetchable. The full-size
  **Daily and Sunday crosswords are gated behind a NYT Games subscription** — the
  content endpoint returns metadata with the clues/grid stripped out — so no free
  solver can run them; they are intentionally out of scope.

### 3. Solvers are pure and headless
Solver classes contain solving + scraping only. All interactive/terminal
(`pynput`) code lives in `menus.py` / `game_runner.py`, so solvers import and run
headlessly (CI, cron) with no display. Keep it that way — never import the menu
layer from a solver.

### 4. Surface results without a hosted service
Historical results live in the committed `solutions/*.json` and are rendered by
`src/stats.py` into an auto-generated `## Lifetime results` section of the README
(between `<!-- STATS:START -->` / `<!-- STATS:END -->` markers). It emphasizes
**lifetime aggregates** (totals/averages across all runs), not recent trends: an
at-a-glance per-game table (puzzles, avg score, p90 runtime) plus charts rendered
as committed SVGs (`stats/*.svg`) via the dependency-free `src/svg_charts.py`
(there is no Mermaid). Charts are centered with `<p align="center">` and the
per-game write-ups in "How the solvers work" reference them. The daily workflow
regenerates everything on every run. Deliberately **no hosted Web UI** — the
README is the dashboard. If you add metrics, extend `stats.py` and keep both it
and `svg_charts.py` standard-library only.

## Layout
- `src/solvers/<game>/` — one solver class per game (pure logic + scraping)
- `src/solvers/BaseSolver.py` — shared date/id state + solution writing
- `src/solvers/scraping.py` — the single NYT fetch/parse helper (`window.gameData`
  HTML plus the JSON `svc/*` endpoints)
- `src/solvers/llm.py` — the single LLM client (Connections + Mini crossword only)
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
  a ~1-week public archive for Spelling Bee; and full date-addressable history
  for Wordle, Strands, Connections, and the Mini crossword (`--backfill` covers
  Spelling Bee, Wordle, and Strands — the LLM games are left out to stay within
  free rate limits). The full-size Daily/Sunday crosswords need a subscriber
  login and are out of scope.
- LLM games (Connections, Mini) need a provider configured: in CI the workflow's
  `GITHUB_TOKEN` + `models: read` covers it for free; locally, export
  `GITHUB_TOKEN` (a PAT with the Models permission) or `GEMINI_API_KEY`, else
  those two record unsolved results.

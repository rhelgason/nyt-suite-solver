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
- The LLM client tries providers in order and skips any without a credential:
  **Groq** (`GROQ_API_KEY`, generous free tier + strong model, so it leads when
  set), then **GitHub Models** (authenticated by the workflow's built-in
  `GITHUB_TOKEN`, so there is no external key to rotate or expire), then **Gemini**
  (`GEMINI_API_KEY`). `daily.yml` grants `permissions: models: read`. If no
  provider is configured or all fail, the solver records an unsolved result rather
  than crashing the daily run.
- **No single-model lock-in (dynamic model discovery).** At run time each provider's
  live catalog is queried (`_discover_*` -> `_rank_models`), filtered to real chat
  model families, and ranked best-first (reasoning-capable, then larger parameter
  count, then newer version); `_try_models` then tries them in that order. So as
  models are added, deprecated, or downgraded, the solver automatically uses the
  current best available one with no code change -- built to keep working for years.
  Discovery is best-effort and cached per run: if a catalog can't be reached it
  falls back to a small static list (`*_STATIC_MODELS`), so it is never worse than a
  fixed model. Pinning an env var (`GROQ_MODEL` / `GITHUB_MODELS_MODEL` /
  `GEMINI_MODEL`, comma-separated) overrides discovery. Combined with the provider
  fallback, the LLM only fully fails if every model of every configured provider is
  down.
- These puzzles are lateral/wordplay reasoning, so chains lead with a **reasoning
  model** for quality (GitHub Models' `openai/o4-mini`) and fall back to a
  **standard-tier model** (`openai/gpt-4o-mini`) whose free daily quota is far
  larger, since the o-series free allowance on GitHub Models is only single
  digits/day. Model tiers have independent quotas, so a rate-limit on one falls
  through to the next. Reasoning models need a larger token budget (hidden reasoning
  tokens) and reject a custom temperature, both handled in `llm.py`; their
  `<think>` output is stripped before JSON parsing. Gemini's free tier is
  region-gated (some accounts get `limit: 0`), so it is only viable where eligible
  or with billing enabled.
- **Data availability caveat:** for crosswords, only **today's Mini** is freely
  fetchable — every past Mini's content is subscriber-gated (the content endpoint
  returns metadata with the clues/grid stripped), and the full-size Daily/Sunday
  are gated on every date. So the Mini is today-only (no backfill) and Daily/Sunday
  are out of scope. Connections, by contrast, has free full history.

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
- `.github/workflows/` — `daily.yml` (scheduled solve), `backfill.yml` (manual
  dispatch), + `tests.yml` (CI)

## Unattended operation
This is designed to run untended for long stretches:
- The daily job commits results every day, which keeps the scheduled workflow from
  being auto-disabled (GitHub pauses cron workflows after ~60 days with no repo
  commits). If it ever pauses, re-enable it from the Actions tab.
- Real breakage surfaces by email: a genuine solve error (e.g. an NYT endpoint
  change) makes `cli.py` exit non-zero, the daily run goes red, and GitHub notifies
  the repo owner. An LLM simply not solving a puzzle is recorded, not an error, so
  it does not raise false alarms.
- Dependencies are upper-bounded in `requirements.txt`, and LLM model chains fall
  through on deprecation, so a routine upstream change should not break the run.

## Working on this repo
- `make` targets create/use an isolated `.venv` (system Python is externally
  managed and rejects `pip install`). `make run`, `make test`, `make setup`.
- Run tests: `make test` (builds the Sudoku extension, then pytest)
- Solve headlessly: `.venv/bin/python src/cli.py --game all`
- Data availability: NYT serves only today's puzzle for Sudoku and the Mini
  crossword; a ~1-week public archive for Spelling Bee; and full date-addressable
  history for Wordle, Strands, Connections, and Letter Boxed. `--backfill` covers
  Spelling Bee, Wordle, Strands, Connections, and Letter Boxed; Connections is
  capped (`--limit`, default 30) since it calls an LLM. The full-size Daily/Sunday
  crosswords need a subscriber login and are out of scope.
  - Letter Boxed history lives at `svc/letter-boxed/v1/<YYYY-MM-DD>.json` (back to
    the `ARCHIVE_EPOCH` of 2019-01-06, puzzle #16), each day carrying its own
    board-specific `dictionary`, so past days can be scored as well as solved.
    Today still comes from the HTML page, so the daily path is unchanged. Note
    the HTML page 404s for past dates — when checking whether a game is
    backfillable, probe the `svc/*` JSON endpoint, not just the HTML.
  - A full Letter Boxed backfill is ~2,750 dates and CPU-bound, not quota-bound:
    most days solve in well under a second, but a board with no 2-word solution
    falls through to a depth-3 search that can take a minute or more. Use
    `--limit` to work through it in chunks.
- LLM games (Connections, Mini) need a provider configured: in CI the workflow's
  `GITHUB_TOKEN` + `models: read` covers it for free; locally, export
  `GITHUB_TOKEN` (a PAT with the Models permission) or `GEMINI_API_KEY`, else
  those two record unsolved results.

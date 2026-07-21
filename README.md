# nyt-suite-solver
Provides a number of algorithms to solve each of the New York Times games every day.

## Usage

Interactive terminal UI:
```
make run
```

Headless (no menu — used by the daily automation and for backfilling):
```
python3 src/cli.py                              # all games, today
python3 src/cli.py --game spelling-bee --date 2024-08-20
python3 src/cli.py --game sudoku --difficulty hard
python3 src/cli.py --game spelling-bee --backfill   # every archived date
```

Run the tests:
```
make test
```

## Automation
A scheduled GitHub Actions workflow (`.github/workflows/daily.yml`) solves every
game each morning and commits the results under `solutions/`, so puzzles are
solved and logged daily without a running server. Unit tests run on every push
via `.github/workflows/tests.yml`.

## Data availability
The NYT only exposes today's puzzle for Letter Boxed and Sudoku, so those
accumulate going forward. Spelling Bee serves a short (~1 week) public archive,
which `--backfill` captures; deeper Spelling Bee history requires a logged-in
subscription session.

## Upcoming Milestones
- [X] Letter Boxed
  - [X] Functional algorithm
  - [X] Upload solved puzzles
- [X] Spelling Bee
  - [X] Functional algorithm
  - [X] Upload solved puzzles
  - [X] Solve archived puzzles
- [X] Sudoku
  - [X] Functional algorithm
  - [X] Upload solved puzzles
- [X] Stat tracking
- [X] Cron job for automatically solving puzzles every day
- [ ] Web UI

import json
import os

from solvers.BaseSolver import BaseSolver


def test_default_output_file_name():
    class S(BaseSolver):
        OUTPUT_DIRECTORY_PATH = "unused"

    assert S("2026-05-05").output_file_name() == "2026-05-05.json"


def test_write_solution_creates_dir_and_file(tmp_path):
    out_dir = str(tmp_path / "solutions" / "demo")

    class S(BaseSolver):
        OUTPUT_DIRECTORY_PATH = out_dir

    solver = S("2026-05-05")
    solver.write_solution({"ds": solver.ds, "value": 42})

    path = os.path.join(out_dir, "2026-05-05.json")
    assert os.path.exists(path)
    assert json.load(open(path)) == {"ds": "2026-05-05", "value": 42}


def test_ds_defaults_to_today():
    from datetime import datetime

    class S(BaseSolver):
        OUTPUT_DIRECTORY_PATH = "unused"

    assert S().ds == datetime.today().date().strftime("%Y-%m-%d")

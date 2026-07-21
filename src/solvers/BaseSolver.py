from datetime import datetime
from typing import Any, Dict, Optional

import json
import os


class BaseSolver:
    """Shared scaffolding for every NYT puzzle solver.

    Handles the concerns that were previously duplicated across the three
    solvers: tracking the puzzle date/id and writing the solution JSON to disk.
    Subclasses set ``OUTPUT_DIRECTORY_PATH`` and implement the actual solving.
    """

    # relative directory (under the repo root) where solutions are written
    OUTPUT_DIRECTORY_PATH: str = ""

    def __init__(self, ds: Optional[str] = None) -> None:
        self.puzzle_id: Optional[int] = None
        self.ds: str = ds or datetime.today().date().strftime("%Y-%m-%d")

    def output_file_name(self) -> str:
        """Name of the solution file for this puzzle. Override when a puzzle has
        more than one variant per day (e.g. Sudoku difficulties)."""
        return f"{self.ds}.json"

    def write_solution(self, data: Dict[str, Any]) -> None:
        """Write a solution dict to ``OUTPUT_DIRECTORY_PATH``, creating it if
        necessary."""
        output_path = os.path.join("./", self.OUTPUT_DIRECTORY_PATH)
        if not os.path.exists(output_path):
            os.makedirs(output_path)
        output_file_path = os.path.join(output_path, self.output_file_name())

        with open(output_file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

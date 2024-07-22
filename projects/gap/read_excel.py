from pathlib import Path

import pandas as pd

from crawler.config import settings


def read_excel(file_path: Path) -> pd.DataFrame:
    spring_24 = pd.read_excel(file_path, sheet_name="SP24")
    summer_24 = pd.read_excel(file_path, sheet_name="SUM24")
    spring_24.


if __name__ == "__main__":
    gap_file = settings.project_dir.joinpath("data", "GAP款号.xlsx")
    next_file = settings.project_dir.joinpath("data", "next款号.xlsx")
    print(gap_file)

    read_excel(gap_file)
    print(gap_df.values.all())

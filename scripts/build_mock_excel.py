#!/usr/bin/env python3
"""Build data/mock_data.xlsx from a cleaned SalphaPredict CSV.

Mock unit costs are prototype estimates only — see logic/mock_costs.py.

Run from the project root:
    python scripts/build_mock_excel.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd

from logic.mock_costs import MOCK_COST_DISCLAIMER, build_mock_excel_dataframe

DEFAULT_SOURCE = Path("data/mock_data_upload_cleaned.csv")
DEFAULT_OUTPUT = Path("data/mock_data.xlsx")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build SalphaPredict mock Excel dataset.")
    parser.add_argument(
        "--source",
        type=Path,
        default=DEFAULT_SOURCE,
        help=f"Cleaned CSV input (default: {DEFAULT_SOURCE})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Excel output path (default: {DEFAULT_OUTPUT})",
    )
    args = parser.parse_args()

    if not args.source.exists():
        raise SystemExit(f"Source file not found: {args.source}")

    cleaned = pd.read_csv(args.source, parse_dates=["sale_date"])
    excel_df = build_mock_excel_dataframe(cleaned)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    excel_df.to_excel(args.output, index=False, sheet_name="Sales")

    print(MOCK_COST_DISCLAIMER)
    print(f"Wrote {len(excel_df)} rows to {args.output}")


if __name__ == "__main__":
    main()

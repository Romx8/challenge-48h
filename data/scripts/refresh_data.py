import argparse
from datetime import date
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.core.config import get_settings
from app.services.pipeline import ConsolidationService


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh consolidated index data")
    parser.add_argument("--days", type=int, default=None)
    parser.add_argument("--start-date", type=date.fromisoformat, default=None)
    parser.add_argument("--end-date", type=date.fromisoformat, default=None)
    args = parser.parse_args()

    service = ConsolidationService(get_settings())
    result = service.refresh(start_date=args.start_date, end_date=args.end_date, days=args.days)
    print(f"refresh_ok rows={result.rows} generated_at={result.generated_at.isoformat()}")


if __name__ == "__main__":
    main()

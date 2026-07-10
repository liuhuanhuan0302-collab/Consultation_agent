import asyncio
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.database import init_db
from app.service.report_queue import run_report_delivery_worker


def main() -> None:
    init_db()
    asyncio.run(run_report_delivery_worker())


if __name__ == "__main__":
    main()

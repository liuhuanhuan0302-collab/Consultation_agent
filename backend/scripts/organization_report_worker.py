"""Independent worker for organization diagnosis analysis and PDF reports."""

import asyncio
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.database import init_db
from app.service.organization_report_service import run_organization_report_worker


def main() -> None:
    init_db()
    asyncio.run(run_organization_report_worker())


if __name__ == "__main__":
    main()

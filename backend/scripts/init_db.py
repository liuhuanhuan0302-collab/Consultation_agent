import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.database import get_db, init_db
from app.seed import seed_initial_data


def main() -> None:
    init_db()
    db = next(get_db())
    try:
        seed_initial_data(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()

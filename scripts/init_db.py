"""Create all tables. Run: .venv/bin/python -m scripts.init_db"""

from app import models  # noqa: F401  (registers models on Base)
from app.database import Base, engine


def main() -> None:
    Base.metadata.create_all(engine)
    print("Tables created.")


if __name__ == "__main__":
    main()

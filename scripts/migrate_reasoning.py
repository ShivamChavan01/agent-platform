"""Step 7 (live thinking) migration: add messages.reasoning.

Run: /opt/agentplatform-venv/bin/python -m scripts.migrate_reasoning
Safe to re-run. Tests don't need this (they use drop_all/create_all).
"""

from sqlalchemy import text

from app.database import engine

STATEMENTS = [
    "ALTER TABLE messages ADD COLUMN IF NOT EXISTS reasoning TEXT",
]


def main() -> None:
    with engine.begin() as conn:
        for statement in STATEMENTS:
            conn.execute(text(statement))
    print("Reasoning migration applied.")


if __name__ == "__main__":
    main()

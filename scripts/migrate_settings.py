"""Step 6 (settings) live migration: idempotent ALTERs + usage_events table.

Run: /opt/agentplatform-venv/bin/python -m scripts.migrate_settings
Safe to re-run. Tests don't need this (they use drop_all/create_all).
"""

from sqlalchemy import text

from app.database import engine

STATEMENTS = [
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS name VARCHAR(255)",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS preferences JSON NOT NULL DEFAULT '{}'",
    "ALTER TABLE conversations ADD COLUMN IF NOT EXISTS pinned BOOLEAN NOT NULL DEFAULT FALSE",
    """
    CREATE TABLE IF NOT EXISTS usage_events (
        id UUID PRIMARY KEY,
        user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
        conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE,
        model VARCHAR(255) NOT NULL,
        prompt_tokens INTEGER NOT NULL,
        completion_tokens INTEGER NOT NULL,
        total_tokens INTEGER NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_usage_events_user_id ON usage_events(user_id)",
    "CREATE INDEX IF NOT EXISTS ix_usage_events_project_id ON usage_events(project_id)",
    "CREATE INDEX IF NOT EXISTS ix_usage_events_conversation_id ON usage_events(conversation_id)",
]


def main() -> None:
    with engine.begin() as conn:
        for statement in STATEMENTS:
            conn.execute(text(statement))
    print("Settings migration applied.")


if __name__ == "__main__":
    main()

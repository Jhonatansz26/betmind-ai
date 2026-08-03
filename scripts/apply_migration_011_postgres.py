"""Apply migration 011 to Supabase PostgreSQL: add match_type column."""
import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from apps.api.config import settings

MIGRATION_SQL = """
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'matches' AND column_name = 'match_type'
    ) THEN
        ALTER TABLE matches ADD COLUMN match_type VARCHAR(20) NOT NULL DEFAULT 'LEAGUE';
        RAISE NOTICE 'Column match_type added.';
    ELSE
        RAISE NOTICE 'Column match_type already exists, skipping.';
    END IF;
END;
$$;

UPDATE matches
SET match_type = 'KNOCKOUT_CUP'
WHERE league_id IN (
    SELECT id FROM leagues
    WHERE external_id IN (241, 130, 73, 254, 13, 11, 2, 3, 848)
);

CREATE INDEX IF NOT EXISTS idx_matches_match_type ON matches(match_type);
"""


async def apply():
    import asyncpg

    url = settings.DATABASE_URL
    # Convert asyncpg URL format
    pg_url = (
        url
        .replace("postgresql+asyncpg://", "postgresql://")
        .replace("postgres+asyncpg://", "postgresql://")
    )

    # asyncpg uses its own URL format
    conn = await asyncpg.connect(pg_url)
    try:
        result = await conn.execute(MIGRATION_SQL)
        print(f"Migration applied successfully: {result}")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(apply())

"""
DB Cleanup script:
1. Delete garbage matches from fake leagues (9001, 9003, 9004, 9005, 9011)
2. Delete fake leagues
3. Fix league names and deduplicate
4. Update Liga 1 external_id from 294 to 281
"""
import asyncio, sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import text
from apps.api.config import settings

engine = create_async_engine(settings.DATABASE_URL)
factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def cleanup():
    async with factory() as session:
        # 1. Delete predictions referencing garbage matches first
        print("Deleting predictions for garbage matches...")
        r = await session.execute(text("""
            DELETE FROM predictions WHERE match_id IN (
                SELECT id FROM matches WHERE league_id IN (
                    SELECT id FROM leagues WHERE external_id IN (9001, 9003, 9004, 9005, 9011)
                )
            )
        """))
        print(f"  Predictions deleted: {r.rowcount}")

        # 2. Delete odds for garbage matches
        print("\nDeleting odds for garbage matches...")
        r = await session.execute(text("""
            DELETE FROM bookmaker_odds WHERE match_id IN (
                SELECT id FROM matches WHERE league_id IN (
                    SELECT id FROM leagues WHERE external_id IN (9001, 9003, 9004, 9005, 9011)
                )
            )
        """))
        print(f"  Odds deleted: {r.rowcount}")

        # 3. Delete tactical analyses for garbage matches
        print("\nDeleting tactical analyses for garbage matches...")
        r = await session.execute(text("""
            DELETE FROM tactical_analyses WHERE match_id IN (
                SELECT id FROM matches WHERE league_id IN (
                    SELECT id FROM leagues WHERE external_id IN (9001, 9003, 9004, 9005, 9011)
                )
            )
        """))
        print(f"  Analyses deleted: {r.rowcount}")

        # 4. Now safe to delete garbage matches
        print("\nDeleting matches in fake leagues...")
        r = await session.execute(text("""
            DELETE FROM matches WHERE league_id IN (
                SELECT id FROM leagues WHERE external_id IN (9001, 9003, 9004, 9005, 9011)
            )
        """))
        print(f"  Matches deleted: {r.rowcount}")

        # 2. Delete fake leagues
        print("\nDeleting fake leagues...")
        r = await session.execute(text("""
            DELETE FROM leagues WHERE external_id IN (9001, 9003, 9004, 9005, 9011)
        """))
        print(f"  Leagues deleted: {r.rowcount}")

        # 3. Move Sudamericana matches from old (9011) to new (11)
        print("\nMerging CONMEBOL Sudamericana duplicates...")
        old_sud = await session.execute(text("SELECT id FROM leagues WHERE external_id = 9011"))
        new_sud = await session.execute(text("SELECT id FROM leagues WHERE external_id = 11"))
        old_id = old_sud.scalar()
        if old_id:
            r = await session.execute(text("""
                UPDATE matches SET league_id = (SELECT id FROM leagues WHERE external_id = 11)
                WHERE league_id = :old_id
            """), {"old_id": old_id})
            print(f"  Matches moved: {r.rowcount}")
            await session.execute(text("DELETE FROM leagues WHERE id = :old_id"), {"old_id": old_id})
            print("  Old league deleted.")

        # 4. Fix league names
        print("\nFixing league names...")
        renames = {
            239: "Liga BetPlay Dimayor",
            11: "CONMEBOL Sudamericana",
            241: "Copa Colombia",
            294: "Liga 1 Perú",
        }
        for ext_id, name in renames.items():
            r = await session.execute(text(
                "UPDATE leagues SET name = :name WHERE external_id = :ext_id AND name != :name"
            ), {"name": name, "ext_id": ext_id})
            if r.rowcount:
                print(f"  Renamed ext_id={ext_id} to '{name}'")

        # 5. Update Liga 1 external_id from 294 to 281
        print("\nUpdating Liga 1 external_id: 294 -> 281...")
        r = await session.execute(text(
            "UPDATE leagues SET external_id = 281 WHERE external_id = 294"
        ))
        print(f"  Updated: {r.rowcount} rows")

        await session.commit()
        print("\n=== Cleanup complete ===")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(cleanup())

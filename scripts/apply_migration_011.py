"""Apply migration 011: add match_type column to SQLite betmind.db"""
import sqlite3
import pathlib

db = pathlib.Path("apps/api/betmind.db")
if not db.exists():
    print("betmind.db not found — skipping (SQLAlchemy will create on next startup)")
else:
    con = sqlite3.connect(str(db))
    cur = con.cursor()
    cur.execute("PRAGMA table_info(matches)")
    cols = [row[1] for row in cur.fetchall()]
    if "match_type" not in cols:
        cur.execute(
            "ALTER TABLE matches ADD COLUMN match_type VARCHAR(20) NOT NULL DEFAULT 'LEAGUE'"
        )
        cup_ids = (241, 130, 73, 254, 13, 11, 2, 3, 848)
        placeholders = ",".join("?" for _ in cup_ids)
        cur.execute(
            f"UPDATE matches SET match_type = 'KNOCKOUT_CUP' WHERE league_id IN "
            f"(SELECT id FROM leagues WHERE external_id IN ({placeholders}))",
            cup_ids,
        )
        con.commit()
        print(f"Migration applied: match_type column added.")
        print(f"Rows backfilled as KNOCKOUT_CUP: {cur.rowcount}")
    else:
        print("match_type column already exists — skipping")
    con.close()

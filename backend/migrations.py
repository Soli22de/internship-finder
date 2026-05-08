"""Migration: add salary and publish_time columns."""
from backend.db import get_db
from typing import List, Tuple

MIGRATIONS: List[Tuple[str, str]] = [
    # B2: salary columns
    ("salary_min_kday", "REAL"),
    ("salary_max_kday", "REAL"),
    ("salary_unit", "TEXT DEFAULT 'unknown'"),
    # B3: publish_time column
    ("publish_time_iso", "TEXT"),
    # B4: dedup key
    ("dedup_key", "TEXT"),
]


def run():
    conn = get_db()
    for col, col_type in MIGRATIONS:
        try:
            conn.execute(f"ALTER TABLE jobs ADD COLUMN {col} {col_type}")
        except Exception as e:
            if "duplicate" not in str(e).lower():
                raise
    conn.commit()
    conn.close()
    print("Migrations applied successfully")


if __name__ == "__main__":
    run()

"""Diagnose JD quality per Brain's spec."""
import sys, re
sys.path.insert(0, r"C:\jz_code\internship_finding")
from backend.db import get_db

db = get_db()
total = db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
all_jd = db.execute("SELECT jd_raw FROM jobs WHERE jd_raw IS NOT NULL AND jd_raw != ''").fetchall()

# 1. PUA chars check
def has_pua(s):
    return any("\ue000" <= c <= "\uf8ff" for c in str(s or ""))
pua_count = sum(1 for r in all_jd if has_pua(str(r[0])))
print(f"PUA chars in JD: {pua_count} / {total}")

# 2. Salary patterns in JD (Python-level)
salary_re = re.compile(r"\d+[-~至到]\d+\s*[元KkK]|\d+[-~至到]\d+\s*元/\w+|\d+\s*元/\w+")
hit = sum(1 for r in all_jd if salary_re.search(str(r[0] or "")))
print(f"Salary pattern in JD: {hit} / {total} ({hit/total*100:.2f}%)")

# 2. Salary patterns in JD (Python-level)
salary_re = re.compile(r"\d+[-~至到]\d+\s*[元KkK]|\d+[-~至到]\d+\s*元/\w+|\d+\s*元/\w+")
all_jd = db.execute("SELECT jd_raw FROM jobs WHERE jd_raw IS NOT NULL AND jd_raw != ''").fetchall()
hit = sum(1 for r in all_jd if salary_re.search(str(r[0] or "")))
print(f"Salary pattern in JD: {hit} / {total} ({hit/total*100:.2f}%)")

# 3. Existing salary field
existing = db.execute(
    "SELECT COUNT(*) FROM jobs WHERE salary != '' AND salary IS NOT NULL"
).fetchone()[0]
print(f"Salary field filled: {existing} / {total}")

# 4. Empty JD
empty = db.execute(
    "SELECT COUNT(*) FROM jobs WHERE jd_raw IS NULL OR jd_raw = ''"
).fetchone()[0]
print(f"Empty JD: {empty} / {total}")

db.close()

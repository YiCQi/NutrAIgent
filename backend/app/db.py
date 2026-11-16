import os
import sqlite3
from pathlib import Path

SCHEMA = Path(__file__).with_name("schema.sql")
DEFAULT_DB = Path(os.environ.get("NUTRAIGENT_DB", Path.home() / ".nutraigent" / "nutraigent.db"))

CORE_NUTRIENTS = [
    ("energy_kcal", "Energy", "kcal", "energy"),
    ("protein_g", "Protein", "g", "macro"),
    ("carbohydrate_g", "Carbohydrate", "g", "macro"),
    ("fat_g", "Fat", "g", "macro"),
    ("fibre_g", "Fibre", "g", "macro"),
    ("sugars_g", "Total sugars", "g", "macro"),
    ("sat_fat_g", "Saturated fat", "g", "macro"),
    ("sodium_mg", "Sodium", "mg", "mineral"),
    ("calcium_mg", "Calcium", "mg", "mineral"),
    ("iron_mg", "Iron", "mg", "mineral"),
    ("vitamin_c_mg", "Vitamin C", "mg", "vitamin"),
    ("vitamin_b12_ug", "Vitamin B12", "ug", "vitamin"),
]


def connect(path: Path | str = DEFAULT_DB) -> sqlite3.Connection:
    if str(path) != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    init_db(conn)
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA.read_text(encoding="utf-8"))
    # migration v1 -> v2: qualifier column on food_nutrients
    cols = [r[1] for r in conn.execute("PRAGMA table_info(food_nutrients)")]
    if "qualifier" not in cols:
        conn.execute("ALTER TABLE food_nutrients ADD COLUMN qualifier TEXT "
                     "CHECK (qualifier IS NULL OR qualifier IN ('trace','N'))")
    # migration v7 -> v8: estimated flag (AI-estimated value, shown as such)
    if "estimated" not in cols:
        conn.execute("ALTER TABLE food_nutrients ADD COLUMN estimated INTEGER NOT NULL DEFAULT 0 "
                     "CHECK (estimated IN (0, 1))")
    conn.execute("UPDATE schema_meta SET value = '8' WHERE key = 'schema_version'")
    conn.executemany(
        "INSERT OR IGNORE INTO nutrients (code, name, unit, category) VALUES (?,?,?,?)",
        CORE_NUTRIENTS,
    )
    conn.commit()

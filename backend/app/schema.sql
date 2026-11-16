-- Schema v2. NULL value in food_nutrients = MISSING data; 0 = measured zero.
CREATE TABLE IF NOT EXISTS schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
INSERT OR IGNORE INTO schema_meta VALUES ('schema_version', '2');

CREATE TABLE IF NOT EXISTS sources (
  id INTEGER PRIMARY KEY,
  code TEXT NOT NULL UNIQUE,        -- e.g. 'cofid', 'usda_fdc'
  name TEXT NOT NULL,
  version TEXT,
  url TEXT,
  licence TEXT
);

CREATE TABLE IF NOT EXISTS nutrients (
  id INTEGER PRIMARY KEY,
  code TEXT NOT NULL UNIQUE,        -- canonical code, e.g. 'energy_kcal', 'protein_g'
  name TEXT NOT NULL,
  unit TEXT NOT NULL,               -- 'kcal','g','mg','ug'
  category TEXT NOT NULL            -- 'energy','macro','vitamin','mineral','other'
);

CREATE TABLE IF NOT EXISTS foods (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  source_id INTEGER NOT NULL REFERENCES sources(id),
  source_food_id TEXT,              -- id in the originating dataset
  food_group TEXT,
  state TEXT CHECK (state IN ('raw','cooked','processed','unknown')) DEFAULT 'unknown',
  edible_portion_pct REAL CHECK (edible_portion_pct IS NULL OR (edible_portion_pct >= 0 AND edible_portion_pct <= 100)),
  UNIQUE (source_id, source_food_id)
);
CREATE INDEX IF NOT EXISTS idx_foods_name ON foods(name);

-- Values are per 100 g (some CoFID alcoholic drinks: per 100 ml).
-- qualifier: NULL = plain value; 'trace' = source says trace (value stored as 0.0, true amount > 0
-- but unquantified); 'N' = present in significant amount but no reliable figure (value NULL).
CREATE TABLE IF NOT EXISTS food_nutrients (
  food_id INTEGER NOT NULL REFERENCES foods(id) ON DELETE CASCADE,
  nutrient_id INTEGER NOT NULL REFERENCES nutrients(id),
  value_per_100g REAL CHECK (value_per_100g IS NULL OR value_per_100g >= 0),
  qualifier TEXT CHECK (qualifier IS NULL OR qualifier IN ('trace','N')),
  PRIMARY KEY (food_id, nutrient_id)
);

CREATE TABLE IF NOT EXISTS portions (
  id INTEGER PRIMARY KEY,
  food_id INTEGER NOT NULL REFERENCES foods(id) ON DELETE CASCADE,
  description TEXT NOT NULL,        -- e.g. '1 medium'
  grams REAL NOT NULL CHECK (grams > 0)
);

CREATE TABLE IF NOT EXISTS profile (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  age INTEGER NOT NULL,
  sex TEXT NOT NULL CHECK (sex IN ('male','female')),
  height_cm REAL NOT NULL,
  weight_kg REAL NOT NULL,
  activity_level TEXT NOT NULL,
  goal TEXT NOT NULL CHECK (goal IN ('muscle_gain','fat_loss','maintenance')),
  dietary_preferences TEXT NOT NULL DEFAULT '[]',  -- JSON array
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS intake_log (
  id INTEGER PRIMARY KEY,
  log_date TEXT NOT NULL,           -- ISO date
  meal TEXT NOT NULL DEFAULT 'other',
  food_id INTEGER NOT NULL REFERENCES foods(id),
  grams REAL NOT NULL CHECK (grams > 0),
  logged_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_intake_date ON intake_log(log_date);

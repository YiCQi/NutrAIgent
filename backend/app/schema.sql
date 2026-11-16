-- Schema v6. NULL value in food_nutrients = MISSING data; 0 = measured zero.
CREATE TABLE IF NOT EXISTS schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
INSERT OR IGNORE INTO schema_meta VALUES ('schema_version', '6');

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

-- Local app settings (AI provider config). api_key is stored in plaintext in this local DB.
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);

-- AI assistant chat sessions. meta (JSON) on assistant messages: {proposals:[...], status:'pending'|'saved'|'discarded'}
CREATE TABLE IF NOT EXISTS conversations (
  id INTEGER PRIMARY KEY,
  title TEXT NOT NULL DEFAULT 'New chat',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS messages (
  id INTEGER PRIMARY KEY,
  conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  role TEXT NOT NULL CHECK (role IN ('user','assistant')),
  content TEXT NOT NULL,
  meta TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id, id);

-- User recipes: the recipe is also a row in foods (source 'user_recipe'); nutrients are computed from ingredients.
CREATE TABLE IF NOT EXISTS recipes (
  food_id INTEGER PRIMARY KEY REFERENCES foods(id) ON DELETE CASCADE,
  yield_g REAL NOT NULL CHECK (yield_g > 0),   -- cooked weight of the whole batch
  notes TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS recipe_ingredients (
  id INTEGER PRIMARY KEY,
  recipe_food_id INTEGER NOT NULL REFERENCES recipes(food_id) ON DELETE CASCADE,
  food_id INTEGER NOT NULL REFERENCES foods(id),
  grams REAL NOT NULL CHECK (grams > 0),
  position INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_recipe_ing ON recipe_ingredients(recipe_food_id);

-- Meal plans (AI proposes dishes; matching, scaling and nutrients are deterministic).
CREATE TABLE IF NOT EXISTS meal_plans (
  id INTEGER PRIMARY KEY,
  title TEXT NOT NULL,
  start_date TEXT NOT NULL,
  notes TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS plan_items (
  id INTEGER PRIMARY KEY,
  plan_id INTEGER NOT NULL REFERENCES meal_plans(id) ON DELETE CASCADE,
  plan_date TEXT NOT NULL,
  meal TEXT NOT NULL CHECK (meal IN ('breakfast','lunch','dinner','snack')),
  position INTEGER NOT NULL DEFAULT 0,
  label TEXT NOT NULL,
  food_id INTEGER NOT NULL REFERENCES foods(id),
  grams REAL NOT NULL CHECK (grams > 0)
);
CREATE INDEX IF NOT EXISTS idx_plan_items ON plan_items(plan_id, plan_date);

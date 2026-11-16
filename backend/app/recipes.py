"""User recipes: a recipe is a food (source 'user_recipe') whose per-100 g nutrients are computed
deterministically from its ingredients: sum(ingredient_g * value / 100) / yield_g * 100.

Rule for missing data: if ANY ingredient lacks a value for a nutrient, the recipe has NO value for
it (missing, never silently 0). 'trace' ingredient values count as 0.
"""
import sqlite3

SOURCE_CODE = "user_recipe"


class RecipeError(ValueError):
    pass


def _source_id(conn) -> int:
    conn.execute("INSERT OR IGNORE INTO sources (code, name, licence) VALUES (?,?,?)",
                 (SOURCE_CODE, "My recipes", "user data"))
    return conn.execute("SELECT id FROM sources WHERE code = ?", (SOURCE_CODE,)).fetchone()["id"]


def _validate(conn, name, ingredients, yield_g, exclude_id=None):
    name = (name or "").strip()
    if not 1 <= len(name) <= 80:
        raise RecipeError("name must be 1-80 characters")
    if not ingredients:
        raise RecipeError("at least one ingredient is required")
    if yield_g is not None and not yield_g > 0:
        raise RecipeError("yield must be positive")
    sid = _source_id(conn)
    dup = conn.execute("SELECT food_id FROM recipes r JOIN foods f ON f.id = r.food_id "
                       "WHERE f.name = ? AND f.source_id = ?", (name, sid)).fetchone()
    if dup and dup["food_id"] != exclude_id:
        raise RecipeError("a recipe with this name already exists")
    for ing in ingredients:
        if not ing["grams"] > 0:
            raise RecipeError("ingredient grams must be positive")
        row = conn.execute("SELECT f.id, s.code FROM foods f JOIN sources s ON s.id = f.source_id "
                           "WHERE f.id = ?", (ing["food_id"],)).fetchone()
        if row is None:
            raise RecipeError(f"food {ing['food_id']} not found")
        if row["code"] == SOURCE_CODE:
            raise RecipeError("a recipe cannot contain another recipe")
    return name


def recompute(conn, recipe_id: int) -> None:
    r = conn.execute("SELECT yield_g FROM recipes WHERE food_id = ?", (recipe_id,)).fetchone()
    ings = conn.execute("SELECT food_id, grams FROM recipe_ingredients WHERE recipe_food_id = ?",
                        (recipe_id,)).fetchall()
    conn.execute("DELETE FROM food_nutrients WHERE food_id = ?", (recipe_id,))
    for n in conn.execute("SELECT id FROM nutrients").fetchall():
        total, complete = 0.0, True
        for ing in ings:
            v = conn.execute("SELECT value_per_100g FROM food_nutrients WHERE food_id = ? AND nutrient_id = ?",
                             (ing["food_id"], n["id"])).fetchone()
            if v is None or v["value_per_100g"] is None:
                complete = False
                break
            total += v["value_per_100g"] * ing["grams"] / 100.0
        if complete:
            conn.execute("INSERT INTO food_nutrients (food_id, nutrient_id, value_per_100g) VALUES (?,?,?)",
                         (recipe_id, n["id"], round(total / r["yield_g"] * 100.0, 4)))


def _write_ingredients(conn, recipe_id, ingredients):
    conn.execute("DELETE FROM recipe_ingredients WHERE recipe_food_id = ?", (recipe_id,))
    conn.executemany(
        "INSERT INTO recipe_ingredients (recipe_food_id, food_id, grams, position) VALUES (?,?,?,?)",
        [(recipe_id, i["food_id"], float(i["grams"]), pos) for pos, i in enumerate(ingredients)])


def create(conn: sqlite3.Connection, name, ingredients, yield_g=None, notes="") -> int:
    name = _validate(conn, name, ingredients, yield_g)
    raw = sum(float(i["grams"]) for i in ingredients)
    cur = conn.execute("INSERT INTO foods (name, source_id, source_food_id, food_group, state) "
                       "VALUES (?,?,?,?,'cooked')", (name, _source_id(conn), None, "My recipes"))
    rid = cur.lastrowid
    conn.execute("INSERT INTO recipes (food_id, yield_g, notes) VALUES (?,?,?)", (rid, yield_g or raw, notes))
    _write_ingredients(conn, rid, ingredients)
    recompute(conn, rid)
    conn.commit()
    return rid


def update(conn: sqlite3.Connection, rid: int, name, ingredients, yield_g=None, notes="") -> None:
    if conn.execute("SELECT 1 FROM recipes WHERE food_id = ?", (rid,)).fetchone() is None:
        raise KeyError(rid)
    name = _validate(conn, name, ingredients, yield_g, exclude_id=rid)
    raw = sum(float(i["grams"]) for i in ingredients)
    conn.execute("UPDATE foods SET name = ? WHERE id = ?", (name, rid))
    conn.execute("UPDATE recipes SET yield_g = ?, notes = ?, updated_at = CURRENT_TIMESTAMP WHERE food_id = ?",
                 (yield_g or raw, notes, rid))
    _write_ingredients(conn, rid, ingredients)
    recompute(conn, rid)
    conn.commit()


def delete(conn: sqlite3.Connection, rid: int) -> None:
    if conn.execute("SELECT 1 FROM recipes WHERE food_id = ?", (rid,)).fetchone() is None:
        raise KeyError(rid)
    if conn.execute("SELECT 1 FROM intake_log WHERE food_id = ? LIMIT 1", (rid,)).fetchone():
        raise RecipeError("this recipe appears in your food log and cannot be deleted")
    conn.execute("DELETE FROM foods WHERE id = ?", (rid,))  # cascades recipes + ingredients + nutrients
    conn.commit()


def get(conn: sqlite3.Connection, rid: int) -> dict:
    r = conn.execute("SELECT r.*, f.name FROM recipes r JOIN foods f ON f.id = r.food_id WHERE r.food_id = ?",
                     (rid,)).fetchone()
    if r is None:
        raise KeyError(rid)
    ings = conn.execute(
        """SELECT i.food_id, f.name AS food_name, s.code AS source, i.grams
           FROM recipe_ingredients i JOIN foods f ON f.id = i.food_id JOIN sources s ON s.id = f.source_id
           WHERE i.recipe_food_id = ? ORDER BY i.position""", (rid,)).fetchall()
    nuts = conn.execute(
        """SELECT n.code, n.name, n.unit, fn.value_per_100g AS value
           FROM nutrients n LEFT JOIN food_nutrients fn ON fn.nutrient_id = n.id AND fn.food_id = ?
           ORDER BY n.id""", (rid,)).fetchall()
    ing_list = [dict(i) for i in ings]
    return {"id": rid, "name": r["name"], "yield_g": r["yield_g"], "notes": r["notes"],
            "raw_total_g": round(sum(i["grams"] for i in ing_list), 1),
            "ingredients": ing_list, "nutrients_per_100g": [dict(n) for n in nuts]}


def list_all(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """SELECT r.food_id AS id, f.name, r.yield_g,
                  (SELECT COUNT(*) FROM recipe_ingredients i WHERE i.recipe_food_id = r.food_id) AS n_ingredients,
                  (SELECT fn.value_per_100g FROM food_nutrients fn JOIN nutrients n ON n.id = fn.nutrient_id
                    WHERE fn.food_id = r.food_id AND n.code = 'energy_kcal') AS kcal_per_100g
           FROM recipes r JOIN foods f ON f.id = r.food_id ORDER BY f.name""").fetchall()
    return [dict(r) for r in rows]


def names(conn: sqlite3.Connection, limit: int = 60) -> list[str]:
    return [r["name"] for r in conn.execute(
        "SELECT f.name FROM recipes r JOIN foods f ON f.id = r.food_id ORDER BY r.updated_at DESC LIMIT ?",
        (limit,))]

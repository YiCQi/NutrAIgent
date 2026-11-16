"""Curated 'common foods' table for the Foods page (shown when no search is typed).

Each entry resolves through the same alias + ranking path the AI uses, so the demo shows exactly
what the assistant would pick. Values are read from the database per 100 g; None = missing (never 0).
"""
from .ai import aliases, matching

COLS = ("energy_kcal", "protein_g", "carbohydrate_g", "fat_g", "fibre_g", "sodium_mg")

# (category, alias key, 中文, English)
ITEMS = [
    ("staple", "米饭", "米饭(熟)", "White rice, cooked"),
    ("staple", "糙米饭", "糙米饭(熟)", "Brown rice, cooked"),
    ("staple", "燕麦", "燕麦片", "Rolled oats"),
    ("staple", "面条", "面条(熟)", "Pasta/noodles, cooked"),
    ("staple", "全麦面包", "全麦面包", "Whole-wheat bread"),
    ("staple", "红薯", "红薯(烤)", "Sweet potato, baked"),
    ("staple", "土豆", "土豆(煮)", "Potato, boiled"),
    ("protein", "鸡蛋", "水煮蛋", "Egg, hard-boiled"),
    ("protein", "鸡胸肉", "鸡胸肉(熟)", "Chicken breast, cooked"),
    ("protein", "猪里脊", "猪里脊(熟)", "Pork loin, cooked"),
    ("protein", "牛肉", "牛肉(熟)", "Beef round, cooked"),
    ("protein", "三文鱼", "三文鱼(熟)", "Salmon, cooked"),
    ("protein", "虾", "虾(熟)", "Shrimp, cooked"),
    ("protein", "豆腐", "豆腐", "Tofu, firm"),
    ("dairy", "牛奶", "全脂牛奶", "Whole milk"),
    ("dairy", "酸奶", "原味酸奶", "Plain yogurt"),
    ("dairy", "豆浆", "豆浆(无糖)", "Soy milk, unsweetened"),
    ("dairy", "豆奶", "豆奶(加糖)", "Soy milk, sweetened"),
    ("veg", "西兰花", "西兰花(煮)", "Broccoli, boiled"),
    ("veg", "菠菜", "菠菜(煮)", "Spinach, boiled"),
    ("veg", "西红柿", "西红柿", "Tomato, raw"),
    ("veg", "胡萝卜", "胡萝卜(煮)", "Carrot, boiled"),
    ("veg", "秋葵", "秋葵(煮)", "Okra, boiled"),
    ("fruit", "苹果", "苹果", "Apple"),
    ("fruit", "香蕉", "香蕉", "Banana"),
    ("fruit", "橙子", "橙子", "Orange"),
    ("fruit", "蓝莓", "蓝莓", "Blueberries"),
    ("fat", "花生", "花生(烤)", "Peanuts, dry-roasted"),
    ("fat", "杏仁", "杏仁", "Almonds"),
    ("fat", "橄榄油", "橄榄油", "Olive oil"),
    ("fat", "黄油", "黄油", "Butter"),
]


def featured(conn) -> list[dict]:
    out = []
    for cat, key, zh, en in ITEMS:
        q = aliases.ALIASES.get(key.lower())
        c = matching.candidates(conn, key, [q] if q else [], None, 1)
        if not c:
            continue
        f = c[0]
        vals = {r["code"]: r["value_per_100g"] for r in conn.execute(
            "SELECT n.code, fn.value_per_100g FROM food_nutrients fn JOIN nutrients n ON n.id = fn.nutrient_id "
            "WHERE fn.food_id = ?", (f["id"],))}
        out.append({"category": cat, "label_zh": zh, "label_en": en, "food_id": f["id"], "food_name": f["name"],
                    "source": f["source"], **{k: vals.get(k) for k in COLS}})
    return out

import pytest

from app import db
from app.ai import aliases, matching

NAMES = [
    ("Rice, white, glutinous, unenriched, cooked", "cooked"),
    ("Rice, white, long-grain, regular, enriched, cooked", "cooked"),
    ("Rice, white, long-grain, regular, raw, enriched", "raw"),
    ("Broccoli raab, cooked", "cooked"),
    ("Broccoli, cooked, boiled, drained, with salt", "cooked"),
    ("Broccoli, cooked, boiled, drained, without salt", "cooked"),
    ("Sweet potato leaves, cooked, steamed, without salt", "cooked"),
    ("Sweet potato, cooked, baked in skin, flesh, without salt", "cooked"),
    ("Oil, peanut, salad or cooking", "unknown"),
    ("Peanuts, all types, oil-roasted, with salt", "unknown"),
    ("Lambsquarters, raw", "raw"),
    ("Lamb, leg, whole (shank and sirloin), separable lean only, cooked, roasted", "cooked"),
]


@pytest.fixture
def conn():
    c = db.connect(":memory:")
    c.execute("INSERT INTO sources (code, name) VALUES ('usda_sr_legacy','x')")
    for n, s in NAMES:
        c.execute("INSERT INTO foods (name, source_id, state) VALUES (?, 1, ?)", (n, s))
    c.commit()
    return c


def top(conn, label, terms=(), state=None):
    return matching.candidates(conn, label, list(terms), state)[0]["name"]


def test_alias_beats_plain_name_length(conn):
    assert top(conn, "米饭") == "Rice, white, long-grain, regular, enriched, cooked"
    assert top(conn, "西兰花") == "Broccoli, cooked, boiled, drained, without salt"
    assert top(conn, "红薯") == "Sweet potato, cooked, baked in skin, flesh, without salt"
    assert top(conn, "花生油") == "Oil, peanut, salad or cooking"
    assert top(conn, "一碗大米饭") == "Rice, white, long-grain, regular, enriched, cooked"  # longest Chinese key inside label


def test_ranker_without_alias(conn):
    assert top(conn, "x", ["rice white cooked"], "cooked") == "Rice, white, long-grain, regular, enriched, cooked"
    assert top(conn, "x", ["broccoli cooked"]) == "Broccoli, cooked, boiled, drained, without salt"
    assert top(conn, "x", ["oil peanut"]) == "Oil, peanut, salad or cooking"
    assert top(conn, "x", ["sweet potato cooked"]) == "Sweet potato, cooked, baked in skin, flesh, without salt"


def test_plural_stem_only_not_longer_words(conn):
    assert top(conn, "羊肉").startswith("Lamb, leg")


def test_state_preference(conn):
    assert "raw" in top(conn, "x", ["rice white long-grain"], "raw")


def test_alias_lookup_rules():
    assert matching.alias_query("豆奶", []) != matching.alias_query("豆浆", [])  # sweetened vs unsweetened is deliberate
    assert matching.alias_query("some unknown dish", ["foo"]) is None
    assert matching.alias_query("x", ["Rice"]) == aliases.ALIASES["rice"]

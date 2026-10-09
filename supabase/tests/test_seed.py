from pathlib import Path
import re


SEED = Path(__file__).parents[1].joinpath("seed.sql").read_text()


def seed_rows() -> list[str]:
    return re.findall(r"^\s+\('[^\n]+\),?$", SEED, flags=re.MULTILINE)


def test_seed_contains_at_least_thirty_unique_ingredients() -> None:
    rows = seed_rows()
    names = [re.match(r"\s+\('([^']+)'", row).group(1) for row in rows]

    assert len(rows) >= 30
    assert len(names) == len(set(names))


def test_seed_uses_stable_category_codes_and_raw_nutrition_basis() -> None:
    allowed_categories = {
        "meat",
        "seafood",
        "dairy",
        "vegetable",
        "fruit",
        "carb",
        "seasoning",
        "other",
    }

    for row in seed_rows():
        match = re.match(
            r"\s+\('([^']+)', '([^']+)', '([^']+)',.*'([^']+)'\),?$",
            row,
        )
        assert match
        assert match.group(2) in allowed_categories
        assert match.group(3) == "raw"
        assert match.group(4) == "mvp_seed"
    assert "肉禽" not in SEED
    assert "水产" not in SEED


def test_seed_is_idempotent_by_name_and_reactivates_existing_rows() -> None:
    assert "on conflict (name) do update set" in SEED
    assert "is_active = true" in SEED
    for column in (
        "category",
        "nutrition_basis",
        "kcal_per_100g",
        "protein_per_100g",
        "carbs_per_100g",
        "fat_per_100g",
        "data_source",
    ):
        assert f"{column} = excluded.{column}" in SEED

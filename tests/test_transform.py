from mealiectl import sync as mrs


def _food(name, aliases=None, **extra):
    item = {"id": name, "name": name, "aliases": [{"name": a} for a in aliases or []]}
    item.update(extra)
    return item


def test_normalise_strips_and_lowercases():
    assert mrs.normalise("  Aubergine ") == "aubergine"
    assert mrs.normalise(None) == ""


def test_build_lookup_indexes_names_and_aliases():
    lookup = mrs.build_lookup([_food("Eierfrucht", ["Aubergine", "Melanzani"])])
    assert lookup["eierfrucht"]["name"] == "Eierfrucht"
    assert lookup["aubergine"]["name"] == "Eierfrucht"


def test_build_lookup_name_wins_over_alias():
    lookup = mrs.build_lookup([_food("Aubergine"), _food("Eierfrucht", ["Aubergine"])])
    assert lookup["aubergine"]["name"] == "Aubergine"


def test_resolve_matches_via_alias():
    lookup = mrs.build_lookup([_food("Eierfrucht", ["Aubergine"])])
    assert mrs.resolve(_food("Aubergine"), lookup)["name"] == "Eierfrucht"
    assert mrs.resolve(_food("Unknown"), lookup) is None


def test_alias_union_returns_additions_only():
    dest = _food("Eierfrucht", ["Aubergine"])
    src = _food("Eierfrucht", ["Aubergine", "Melanzani"])
    merged = mrs.alias_union(dest, src)
    assert {a["name"] for a in merged} == {"Aubergine", "Melanzani"}


def test_alias_union_none_when_no_additions():
    dest = _food("Eierfrucht", ["Aubergine", "Melanzani"])
    src = _food("Eierfrucht", ["Aubergine"])
    assert mrs.alias_union(dest, src) is None


def test_build_food_payload_copies_aliases_and_remaps_label():
    src = {
        "name": "Onion",
        "pluralName": "Onions",
        "description": "",
        "aliases": [{"name": "Zwiebel"}],
        "label": {"name": "Produce"},
    }
    label_map = {"produce": {"id": "dest-label", "name": "Produce"}}
    payload = mrs.build_food_payload(src, label_map)
    assert payload["name"] == "Onion"
    assert payload["aliases"] == [{"name": "Zwiebel"}]
    assert payload["labelId"] == "dest-label"


def test_build_food_payload_drops_unmapped_label():
    src = {"name": "Onion", "aliases": [], "label": {"name": "Unknown"}}
    assert "labelId" not in mrs.build_food_payload(src, {})


def test_build_unit_payload_carries_abbreviation_and_aliases():
    src = {
        "name": "gram",
        "abbreviation": "g",
        "fraction": False,
        "aliases": [{"name": "gramme"}],
        "useAbbreviation": True,
    }
    payload = mrs.build_unit_payload(src)
    assert payload["abbreviation"] == "g"
    assert payload["aliases"] == [{"name": "gramme"}]


def test_remap_ingredient_substitutes_and_preserves():
    src = {
        "quantity": 2,
        "note": "diced",
        "originalText": "2 onions",
        "title": None,
        "display": "2 onions",
        "referenceId": "ref-1",
        "food": {"id": "src-food", "name": "Onion"},
        "unit": {"id": "src-unit", "name": "piece"},
    }
    food_map = {"src-food": {"id": "dest-food", "name": "Onion"}}
    unit_map = {"src-unit": {"id": "dest-unit", "name": "piece"}}
    out = mrs.remap_ingredient(src, food_map, unit_map)
    assert out["food"]["id"] == "dest-food"
    assert out["unit"]["id"] == "dest-unit"
    assert out["quantity"] == 2
    assert out["originalText"] == "2 onions"
    assert out["referenceId"] == "ref-1"


def test_remap_ingredient_handles_freetext_without_food():
    src = {
        "quantity": None,
        "note": "salt to taste",
        "food": None,
        "unit": None,
        "originalText": "salt",
        "referenceId": "ref-2",
    }
    out = mrs.remap_ingredient(src, {}, {})
    assert out["food"] is None and out["unit"] is None
    assert out["note"] == "salt to taste"


def test_transform_recipe_strips_instance_fields_and_remaps():
    recipe = {
        "id": "rid",
        "userId": "u",
        "groupId": "g",
        "householdId": "h",
        "dateAdded": "2020",
        "name": "Soup",
        "slug": "soup",
        "recipeIngredient": [
            {
                "food": {"id": "sf", "name": "Onion"},
                "unit": None,
                "quantity": 1,
                "referenceId": "r",
            }
        ],
        "tags": [{"id": "st", "name": "Vegan", "slug": "vegan"}],
        "recipeCategory": [{"id": "sc", "name": "Dinner", "slug": "dinner"}],
        "tools": [],
        "recipeInstructions": [{"text": "Boil"}],
    }
    payload = mrs.transform_recipe(
        recipe,
        food_map={"sf": {"id": "df", "name": "Onion"}},
        unit_map={},
        tag_map={"vegan": {"id": "dt", "name": "Vegan", "slug": "vegan"}},
        category_map={"dinner": {"id": "dc", "name": "Dinner", "slug": "dinner"}},
        tool_map={},
    )
    assert "id" not in payload and "groupId" not in payload
    assert payload["name"] == "Soup"
    assert payload["recipeIngredient"][0]["food"]["id"] == "df"
    assert payload["tags"][0]["id"] == "dt"
    assert payload["recipeCategory"][0]["id"] == "dc"
    assert payload["recipeInstructions"] == [{"text": "Boil"}]

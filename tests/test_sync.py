import copy

import pytest

from mealiectl.sync import RecipeSync


class FakeMealieClient:
    def __init__(
        self,
        recipes=None,
        foods=None,
        units=None,
        labels=None,
        tags=None,
        categories=None,
        tools=None,
        images=None,
    ):
        self._recipes = {r["slug"]: r for r in recipes or []}
        self.foods = list(foods or [])
        self.units = list(units or [])
        self.labels = list(labels or [])
        self.tags = list(tags or [])
        self.categories = list(categories or [])
        self.tools = list(tools or [])
        self._images = images or {}
        self.updated = {}
        self.created = []
        self.uploaded_images = []
        self.food_updates = []

    def list_recipes(self):
        return [{"slug": r["slug"], "id": r["id"]} for r in self._recipes.values()]

    def get_recipe(self, slug):
        return copy.deepcopy(self._recipes[slug])

    def create_recipe(self, name):
        slug = name.lower().replace(" ", "-")
        self.created.append(slug)
        self._recipes.setdefault(slug, {"slug": slug, "id": "new-" + slug})
        return slug

    def update_recipe(self, slug, payload):
        self.updated[slug] = payload

    def get_image(self, recipe_id):
        return self._images.get(recipe_id)

    def update_image(self, slug, data, extension):
        self.uploaded_images.append((slug, data, extension))

    def list_foods(self):
        return self.foods

    def create_food(self, payload):
        created = dict(payload, id=f"dest-food-{len(self.foods)}")
        self.foods.append(created)
        return created

    def update_food(self, item_id, payload):
        self.food_updates.append((item_id, payload))

    def list_units(self):
        return self.units

    def create_unit(self, payload):
        created = dict(payload, id=f"dest-unit-{len(self.units)}")
        self.units.append(created)
        return created

    def update_unit(self, item_id, payload):
        pass

    def list_labels(self):
        return self.labels

    def create_label(self, payload):
        created = dict(payload, id="dest-label")
        self.labels.append(created)
        return created

    def _create_organizer(self, store, name):
        created = {
            "id": f"{store}-{len(getattr(self, store))}",
            "name": name,
            "slug": name.lower(),
        }
        getattr(self, store).append(created)
        return created

    def list_tags(self):
        return self.tags

    def create_tag(self, name):
        return self._create_organizer("tags", name)

    def list_categories(self):
        return self.categories

    def create_category(self, name):
        return self._create_organizer("categories", name)

    def list_tools(self):
        return self.tools

    def create_tool(self, name):
        return self._create_organizer("tools", name)


def _src_recipe(slug, **extra):
    base = {
        "slug": slug,
        "id": "src-" + slug,
        "name": slug.capitalize(),
        "image": "x",
        "recipeIngredient": [],
        "tags": [],
        "recipeCategory": [],
        "tools": [],
        "recipeInstructions": [],
    }
    base.update(extra)
    return base


def test_run_creates_missing_recipe_with_remapped_food_and_image():
    src_recipe = _src_recipe(
        "soup",
        recipeIngredient=[
            {
                "food": {"id": "sf", "name": "Onion", "aliases": [{"name": "Zwiebel"}]},
                "unit": None,
                "quantity": 1,
                "referenceId": "r",
            }
        ],
    )
    source = FakeMealieClient(
        recipes=[src_recipe],
        foods=[{"id": "sf", "name": "Onion", "aliases": [{"name": "Zwiebel"}]}],
        images={"src-soup": b"img"},
    )
    dest = FakeMealieClient()
    counts = RecipeSync(source, dest).run()
    assert counts["created"] == 1 and counts["updated"] == 0
    assert "soup" in dest.updated
    assert dest.updated["soup"]["recipeIngredient"][0]["food"]["name"] == "Onion"
    assert dest.uploaded_images and dest.uploaded_images[0][0] == "soup"


def test_run_updates_existing_recipe():
    source = FakeMealieClient(recipes=[_src_recipe("soup")])
    dest = FakeMealieClient(recipes=[{"slug": "soup", "id": "d"}])
    counts = RecipeSync(source, dest, copy_images=False).run()
    assert counts["updated"] == 1 and counts["created"] == 0
    assert dest.created == []


def test_run_merges_aliases_on_existing_food():
    source = FakeMealieClient(
        recipes=[_src_recipe("soup")],
        foods=[
            {
                "id": "sf",
                "name": "Onion",
                "aliases": [{"name": "Zwiebel"}, {"name": "Bulb"}],
            }
        ],
    )
    dest = FakeMealieClient(
        foods=[{"id": "df", "name": "Onion", "aliases": [{"name": "Zwiebel"}]}]
    )
    RecipeSync(source, dest, copy_images=False, merge_aliases=True).run()
    assert dest.food_updates and dest.food_updates[0][0] == "df"
    assert {a["name"] for a in dest.food_updates[0][1]["aliases"]} == {
        "Zwiebel",
        "Bulb",
    }


def test_dry_run_writes_nothing():
    source = FakeMealieClient(recipes=[_src_recipe("soup")])
    dest = FakeMealieClient()
    counts = RecipeSync(source, dest, dry_run=True).run()
    assert counts["created"] == 1
    assert dest.updated == {} and dest.created == [] and dest.foods == []


def test_nameless_source_food_raises_clear_error():
    source = FakeMealieClient(
        foods=[{"id": "f1", "name": "", "pluralName": "Felsengebirgshühner"}]
    )
    dest = FakeMealieClient()
    with pytest.raises(ValueError, match="Felsengebirgshühner"):
        RecipeSync(source, dest, dry_run=True).run()
    assert dest.foods == []


def test_run_counts_failure_and_continues():
    source = FakeMealieClient(recipes=[_src_recipe("good"), _src_recipe("bad")])

    class Boom(FakeMealieClient):
        def update_recipe(self, slug, payload):
            if slug == "bad":
                raise RuntimeError("boom")
            super().update_recipe(slug, payload)

    dest = Boom()
    counts = RecipeSync(source, dest, copy_images=False).run()
    assert counts["failed"] == 1 and counts["created"] == 1

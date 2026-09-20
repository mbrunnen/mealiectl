"""One-way Mealie recipe synchronisation (additive + update)."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Protocol

log = logging.getLogger("mealiectl")

_INSTANCE_FIELDS = (
    "id",
    "userId",
    "groupId",
    "householdId",
    "dateAdded",
    "dateUpdated",
    "createdAt",
    "update_at",
    "updatedAt",
)


def normalise(name: str | None) -> str:
    """Lower-case and strip a name for case-insensitive matching."""
    return (name or "").strip().lower()


def build_lookup(items: list[dict]) -> dict[str, dict]:
    """Index foods/units by normalised name and alias; names win over aliases."""
    lookup: dict[str, dict] = {}
    for item in items:
        key = normalise(item.get("name"))
        if key:
            lookup[key] = item
    for item in items:
        for alias in item.get("aliases") or []:
            key = normalise(alias.get("name"))
            if key and key not in lookup:
                lookup[key] = item
    return lookup


def resolve(src_item: dict, lookup: dict[str, dict]) -> dict | None:
    """Find a destination item by name, then by any alias."""
    key = normalise(src_item.get("name"))
    if key in lookup:
        return lookup[key]
    for alias in src_item.get("aliases") or []:
        akey = normalise(alias.get("name"))
        if akey in lookup:
            return lookup[akey]
    return None


def alias_union(dest_item: dict, src_item: dict) -> list[dict] | None:
    """Return the union of aliases if the source adds any, else None."""
    existing = {normalise(dest_item.get("name"))}
    for alias in dest_item.get("aliases") or []:
        existing.add(normalise(alias.get("name")))
    additions = []
    for alias in src_item.get("aliases") or []:
        key = normalise(alias.get("name"))
        if key and key not in existing:
            existing.add(key)
            additions.append({"name": alias["name"]})
    if not additions:
        return None
    merged = [{"name": a["name"]} for a in dest_item.get("aliases") or []]
    merged.extend(additions)
    return merged


def build_food_payload(src_food: dict, label_map: dict[str, dict]) -> dict:
    """Build a destination food payload, remapping the label by name."""
    payload = {
        "name": src_food.get("name"),
        "pluralName": src_food.get("pluralName"),
        "description": src_food.get("description") or "",
        "aliases": [{"name": a["name"]} for a in src_food.get("aliases") or []],
    }
    label = src_food.get("label")
    if label:
        dest = label_map.get(normalise(label.get("name")))
        if dest:
            payload["labelId"] = dest.get("id")
    return payload


def build_unit_payload(src_unit: dict) -> dict:
    """Build a destination unit payload carrying abbreviation and aliases."""
    return {
        "name": src_unit.get("name"),
        "pluralName": src_unit.get("pluralName"),
        "description": src_unit.get("description") or "",
        "abbreviation": src_unit.get("abbreviation") or "",
        "pluralAbbreviation": src_unit.get("pluralAbbreviation"),
        "useAbbreviation": bool(src_unit.get("useAbbreviation")),
        "fraction": bool(src_unit.get("fraction")),
        "aliases": [{"name": a["name"]} for a in src_unit.get("aliases") or []],
    }


def remap_ingredient(
    ingredient: dict, food_map: dict[str, dict], unit_map: dict[str, dict]
) -> dict:
    """Replace food/unit with destination objects, preserving text fields."""
    food = ingredient.get("food")
    unit = ingredient.get("unit")
    return {
        "quantity": ingredient.get("quantity"),
        "note": ingredient.get("note"),
        "title": ingredient.get("title"),
        "originalText": ingredient.get("originalText"),
        "display": ingredient.get("display"),
        "referenceId": ingredient.get("referenceId"),
        "food": food_map.get(food.get("id")) if food else None,
        "unit": unit_map.get(unit.get("id")) if unit else None,
    }


def _map_organizers(items: list[dict] | None, name_map: dict[str, dict]) -> list[dict]:
    mapped = []
    for item in items or []:
        dest = name_map.get(normalise(item.get("name")))
        if dest:
            mapped.append(dest)
    return mapped


def transform_recipe(
    recipe: dict,
    *,
    food_map: dict[str, dict],
    unit_map: dict[str, dict],
    tag_map: dict[str, dict],
    category_map: dict[str, dict],
    tool_map: dict[str, dict],
) -> dict:
    """Build a Recipe-Input payload with instance data stripped and remapped."""
    payload = dict(recipe)
    for field in _INSTANCE_FIELDS:
        payload.pop(field, None)
    payload["recipeIngredient"] = [
        remap_ingredient(ing, food_map, unit_map)
        for ing in recipe.get("recipeIngredient") or []
    ]
    payload["tags"] = _map_organizers(recipe.get("tags"), tag_map)
    payload["recipeCategory"] = _map_organizers(
        recipe.get("recipeCategory"), category_map
    )
    payload["tools"] = _map_organizers(recipe.get("tools"), tool_map)
    return payload


class MealieAPI(Protocol):
    """The subset of the Mealie API used by the synchroniser."""

    def list_recipes(self) -> list[dict]: ...
    def get_recipe(self, slug: str) -> dict: ...
    def create_recipe(self, name: str) -> str: ...
    def update_recipe(self, slug: str, payload: dict) -> None: ...
    def get_image(self, recipe_id: str) -> bytes | None: ...
    def update_image(self, slug: str, data: bytes, extension: str) -> None: ...
    def list_foods(self) -> list[dict]: ...
    def create_food(self, payload: dict) -> dict: ...
    def update_food(self, item_id: str, payload: dict) -> None: ...
    def list_units(self) -> list[dict]: ...
    def create_unit(self, payload: dict) -> dict: ...
    def update_unit(self, item_id: str, payload: dict) -> None: ...
    def list_labels(self) -> list[dict]: ...
    def create_label(self, payload: dict) -> dict: ...
    def list_tags(self) -> list[dict]: ...
    def create_tag(self, name: str) -> dict: ...
    def list_categories(self) -> list[dict]: ...
    def create_category(self, name: str) -> dict: ...
    def list_tools(self) -> list[dict]: ...
    def create_tool(self, name: str) -> dict: ...


class RecipeSync:
    """Copy recipes one-way from a source to a destination Mealie instance."""

    def __init__(
        self,
        source: MealieAPI,
        dest: MealieAPI,
        *,
        copy_images: bool = True,
        merge_aliases: bool = True,
        dry_run: bool = False,
    ) -> None:
        self.source = source
        self.dest = dest
        self.copy_images = copy_images
        self.merge_aliases = merge_aliases
        self.dry_run = dry_run
        self.counts = {"created": 0, "updated": 0, "skipped": 0, "failed": 0}
        self.food_map: dict[str, dict] = {}
        self.unit_map: dict[str, dict] = {}
        self.tag_map: dict[str, dict] = {}
        self.category_map: dict[str, dict] = {}
        self.tool_map: dict[str, dict] = {}

    def run(self) -> dict[str, int]:
        self._sync_labels_foods_units()
        self._sync_organizers()
        self._sync_recipes()
        return self.counts

    def _sync_labels_foods_units(self) -> None:
        label_map = {normalise(item["name"]): item for item in self.dest.list_labels()}
        for src_label in self.source.list_labels():
            key = normalise(src_label["name"])
            if key not in label_map and not self.dry_run:
                label_map[key] = self.dest.create_label(
                    {
                        "name": src_label["name"],
                        "color": src_label.get("color") or "#959595",
                    }
                )
        self.food_map = self._sync_master(
            self.source.list_foods(),
            self.dest.list_foods(),
            create=self.dest.create_food,
            update=self.dest.update_food,
            build=lambda item: build_food_payload(item, label_map),
        )
        self.unit_map = self._sync_master(
            self.source.list_units(),
            self.dest.list_units(),
            create=self.dest.create_unit,
            update=self.dest.update_unit,
            build=build_unit_payload,
        )

    def _sync_master(
        self,
        src_items: list[dict],
        dest_items: list[dict],
        *,
        create: Callable[[dict], dict],
        update: Callable[[str, dict], None],
        build: Callable[[dict], dict],
    ) -> dict[str, dict]:
        lookup = build_lookup(dest_items)
        mapping: dict[str, dict] = {}
        for src in src_items:
            if not normalise(src.get("name")):
                raise ValueError(
                    f"source item {src.get('id')} has no name "
                    f"(pluralName={src.get('pluralName')!r}); "
                    "give it a name or delete it on the source instance"
                )
            dest = resolve(src, lookup)
            if dest is None:
                if self.dry_run:
                    continue
                dest = create(build(src))
            elif self.merge_aliases:
                merged = alias_union(dest, src)
                if merged is not None and not self.dry_run:
                    update(dest["id"], {**dest, "aliases": merged})
                    dest = {**dest, "aliases": merged}
            mapping[src["id"]] = dest
        return mapping

    def _sync_organizers(self) -> None:
        self.tag_map = self._sync_organizer(
            self.source.list_tags(), self.dest.list_tags(), self.dest.create_tag
        )
        self.category_map = self._sync_organizer(
            self.source.list_categories(),
            self.dest.list_categories(),
            self.dest.create_category,
        )
        self.tool_map = self._sync_organizer(
            self.source.list_tools(), self.dest.list_tools(), self.dest.create_tool
        )

    def _sync_organizer(
        self,
        src_items: list[dict],
        dest_items: list[dict],
        create: Callable[[str], dict],
    ) -> dict[str, dict]:
        mapping = {normalise(item["name"]): item for item in dest_items}
        for src in src_items:
            key = normalise(src["name"])
            if key not in mapping:
                if self.dry_run:
                    continue
                mapping[key] = create(src["name"])
        return mapping

    def _sync_recipes(self) -> None:
        dest_slugs = {r["slug"] for r in self.dest.list_recipes()}
        for summary in self.source.list_recipes():
            slug = summary["slug"]
            try:
                self._sync_one(slug, slug in dest_slugs)
            except Exception as exc:  # noqa: BLE001
                self.counts["failed"] += 1
                log.warning("recipe %s failed: %s", slug, exc)

    def _sync_one(self, slug: str, exists: bool) -> None:
        src = self.source.get_recipe(slug)
        payload = transform_recipe(
            src,
            food_map=self.food_map,
            unit_map=self.unit_map,
            tag_map=self.tag_map,
            category_map=self.category_map,
            tool_map=self.tool_map,
        )
        outcome = "updated" if exists else "created"
        if self.dry_run:
            self.counts[outcome] += 1
            return
        if not exists:
            self.dest.create_recipe(src["name"])
        dest_recipe = self.dest.get_recipe(slug)
        payload.update(
            {f: dest_recipe[f] for f in _INSTANCE_FIELDS if f in dest_recipe}
        )
        self.dest.update_recipe(slug, payload)
        self._sync_image(src, slug)
        self.counts[outcome] += 1

    def _sync_image(self, src: dict, slug: str) -> None:
        if not self.copy_images or not src.get("image"):
            return
        data = self.source.get_image(src["id"])
        if data:
            self.dest.update_image(slug, data, "webp")

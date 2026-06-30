# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
uv sync                       # install deps (incl. dev group)
uv run pytest                 # run the test suite
uv run pytest tests/test_sync.py::test_dry_run_writes_nothing  # single test
uv run ruff check .           # lint
uv run ruff format --check .  # format check (drop --check to apply)
uv build                      # build sdist + wheel into dist/
uv run mealiectl sync --source-url ... --dest-url ... --dry-run  # run the CLI
```

CI (`.github/workflows/ci.yml`) runs lint, format check, and pytest on Python 3.11/3.12/3.13. Pushing a `v*` tag publishes to TestPyPI via `publish.yml`.

## Architecture

Three layers, source under `src/mealiectl/`:

- **`cli.py`** — Typer app (entry point `mealiectl.cli:app`). The single `sync` command reads tokens from `MEALIECTL_SOURCE_TOKEN` / `MEALIECTL_DEST_TOKEN` (never flags), constructs two `MealieClient`s, and runs `RecipeSync`. Exit code 1 if any recipe failed.
- **`client.py`** — `MealieClient`, a thin authenticated wrapper over the Mealie v3 REST API (`requests.Session` + Bearer token). All list endpoints go through `_paginate`. This is the only layer that does I/O.
- **`sync.py`** — the engine. `RecipeSync` orchestrates; the module-level pure functions (`normalise`, `build_lookup`, `resolve`, `alias_union`, `build_*_payload`, `remap_ingredient`, `transform_recipe`) hold all the remapping logic and are unit-tested directly.

### The `MealieAPI` Protocol seam

`sync.py` depends on a `MealieAPI` `Protocol`, not on `MealieClient`. Tests pass a `FakeMealieClient` (in `test_sync.py`) implementing the same surface, so the engine is exercised with zero HTTP. **When adding an API call: add it to the `MealieAPI` Protocol, implement it in `MealieClient`, and add it to `FakeMealieClient`** — all three must stay in sync.

### Sync semantics (one-way, additive)

`RecipeSync.run()` executes three phases in order, because recipes reference the IDs produced earlier:

1. `_sync_labels_foods_units` — labels first (foods reference label IDs), then foods/units via `_sync_master`. Master data is matched on the destination by normalised name then alias (`build_lookup`/`resolve`); missing items are created, and with `merge_aliases` existing items get the union of aliases. Builds `food_map`/`unit_map` keyed by **source** id → destination object.
2. `_sync_organizers` — tags, categories, tools; matched by normalised name, created if missing.
3. `_sync_recipes` — for each source recipe (matched by `slug`): create if missing, then PUT the transformed payload, then copy the image. `transform_recipe` strips instance-specific fields (`_INSTANCE_FIELDS`: ids, timestamps, etc.) and rewrites ingredients/organizers through the maps.

Never deletes; destination-only items are left untouched. `dry_run` makes every phase count actions without writing. Per-recipe exceptions are caught, counted as `failed`, and logged — the run continues.

## Conventions

- Matching across instances is always case-insensitive via `normalise` (strip + lower). Use it for any new name/alias comparison.
- Keep `client.py` as the sole I/O boundary; put logic in pure functions in `sync.py` so it stays testable without HTTP.

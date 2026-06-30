# mealiectl

Command-line control for [Mealie](https://mealie.io/) recipe-manager instances.

The first command, `mealiectl sync`, copies recipes **one way** from a source
Mealie instance to a destination instance: it creates recipes that are missing
and updates those that already exist (matched by slug), never deleting anything.
Foods, units, tags, categories, tools and their labels are remapped by
name/alias on the destination, food/unit aliases are unioned, and images are
copied. Recipes that exist only on the destination are left untouched.

## Install

```bash
pipx install --index-url https://test.pypi.org/simple/ \
  --pip-args='--extra-index-url https://pypi.org/simple/' mealiectl
```

(While the package is published to TestPyPI, the extra index pulls runtime
dependencies from the real PyPI.)

## Usage

```bash
export MEALIECTL_SOURCE_TOKEN=<source-api-token>
export MEALIECTL_DEST_TOKEN=<destination-api-token>

mealiectl sync \
  --source-url https://mealie.example.org \
  --dest-url https://mealie.example.net

# Preview without writing:
mealiectl sync --source-url ... --dest-url ... --dry-run

# Skip images or alias merging:
mealiectl sync --source-url ... --dest-url ... --no-images --no-merge-aliases
```

API tokens are read only from the environment, never passed as flags. Create a
token in each Mealie instance under *User Settings → API Tokens*; the source
token needs read access, the destination token needs write access.

## Development

```bash
uv sync
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

## Licence

MIT. See [LICENSE](LICENSE).

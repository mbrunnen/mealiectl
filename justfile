default: install

install:
    uv tool install --reinstall .

test:
    uv run pytest

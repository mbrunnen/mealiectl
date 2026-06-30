from typer.testing import CliRunner

from mealiectl import __version__
from mealiectl.cli import app

runner = CliRunner()


def test_version_flag():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_sync_requires_tokens(monkeypatch):
    monkeypatch.delenv("MEALIECTL_SOURCE_TOKEN", raising=False)
    monkeypatch.delenv("MEALIECTL_DEST_TOKEN", raising=False)
    result = runner.invoke(
        app, ["sync", "--source-url", "https://s", "--dest-url", "https://d"]
    )
    assert result.exit_code == 2


def test_sync_dry_run_reports_counts(monkeypatch):
    monkeypatch.setenv("MEALIECTL_SOURCE_TOKEN", "s")
    monkeypatch.setenv("MEALIECTL_DEST_TOKEN", "d")

    captured = {}

    class FakeSync:
        def __init__(self, *args, **kwargs):
            captured["kwargs"] = kwargs

        def run(self):
            return {"created": 3, "updated": 0, "skipped": 0, "failed": 0}

    monkeypatch.setattr("mealiectl.cli.RecipeSync", FakeSync)
    monkeypatch.setattr("mealiectl.cli.MealieClient", lambda *a, **k: object())
    result = runner.invoke(
        app,
        ["sync", "--source-url", "https://s", "--dest-url", "https://d", "--dry-run"],
    )
    assert result.exit_code == 0
    assert "created=3" in result.stdout
    assert captured["kwargs"]["dry_run"] is True

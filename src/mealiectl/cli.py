"""Command-line interface for mealiectl."""

from __future__ import annotations

import logging
import os

import typer

from . import __version__
from .client import MealieClient
from .sync import RecipeSync

app = typer.Typer(help="Control Mealie instances.", no_args_is_help=True)

SOURCE_TOKEN_ENV = "MEALIECTL_SOURCE_TOKEN"
DEST_TOKEN_ENV = "MEALIECTL_DEST_TOKEN"


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit


@app.callback()
def main(
    _version: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show the version and exit.",
    ),
) -> None:
    """mealiectl: command-line control for Mealie instances."""


@app.command()
def sync(
    source_url: str = typer.Option(..., help="Base URL of the source Mealie."),
    dest_url: str = typer.Option(..., help="Base URL of the destination Mealie."),
    images: bool = typer.Option(True, help="Copy recipe images."),
    merge_aliases: bool = typer.Option(True, help="Union food/unit aliases."),
    dry_run: bool = typer.Option(False, help="Report actions without writing."),
) -> None:
    """Sync recipes one-way from the source to the destination Mealie.

    Reads the API tokens from the MEALIECTL_SOURCE_TOKEN and
    MEALIECTL_DEST_TOKEN environment variables.
    """
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    source_token = os.environ.get(SOURCE_TOKEN_ENV)
    dest_token = os.environ.get(DEST_TOKEN_ENV)
    if not source_token or not dest_token:
        typer.echo(f"{SOURCE_TOKEN_ENV} and {DEST_TOKEN_ENV} must be set.", err=True)
        raise typer.Exit(code=2)
    source = MealieClient(source_url, source_token)
    dest = MealieClient(dest_url, dest_token)
    counts = RecipeSync(
        source,
        dest,
        copy_images=images,
        merge_aliases=merge_aliases,
        dry_run=dry_run,
    ).run()
    typer.echo(
        "sync done: created={created} updated={updated} "
        "skipped={skipped} failed={failed}".format(**counts)
    )
    raise typer.Exit(code=1 if counts["failed"] else 0)

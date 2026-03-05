"""Main CLI application using Typer."""

from __future__ import annotations

import typer

from gcp_robo_cloud._version import __version__

app = typer.Typer(
    name="gcp-robo-cloud",
    help="One command to train your robot on cloud GPUs.",
    no_args_is_help=True,
    add_completion=False,
)


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"gcp-robo-cloud {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False, "--version", "-v", help="Show version.", callback=version_callback, is_eager=True
    ),
) -> None:
    """gcp-robo-cloud: One command to train your robot on cloud GPUs."""


# Import and register subcommands
from gcp_robo_cloud.cli.launch import launch  # noqa: E402
from gcp_robo_cloud.cli.status import status  # noqa: E402
from gcp_robo_cloud.cli.stop import stop  # noqa: E402
from gcp_robo_cloud.cli.estimate import estimate  # noqa: E402
from gcp_robo_cloud.cli.config import config  # noqa: E402

app.command()(launch)
app.command()(status)
app.command()(stop)
app.command()(estimate)
app.command()(config)

"""The `gcp-robo-cloud estimate` command."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from gcp_robo_cloud.core.gpu_map import GPU_MAP, VALID_GPU_ALIASES
from gcp_robo_cloud.gcp.pricing import estimate_cost, format_estimate

console = Console()


def estimate(
    gpu: str = typer.Option("t4", "--gpu", "-g", help=f"GPU type: {', '.join(VALID_GPU_ALIASES)}"),
    duration: str = typer.Option(
        "1h",
        "--duration",
        "-d",
        help="Estimated duration (e.g., 2h, 30m).",
    ),
    spot: bool = typer.Option(True, "--spot/--no-spot", help="Use spot pricing."),
    all_gpus: bool = typer.Option(False, "--all", help="Show estimates for all GPU types."),
) -> None:
    """Estimate the cost of a training run."""

    if all_gpus:
        _show_all_estimates(duration, spot)
    else:
        try:
            est = estimate_cost(gpu, duration, spot)
        except ValueError as e:
            console.print(f"[red]Error:[/red] {e}")
            raise typer.Exit(1)
        console.print(Panel(format_estimate(est), title="Cost Estimate"))


def _show_all_estimates(duration: str, spot: bool) -> None:
    """Show cost estimates for all GPU types."""
    table = Table(title=f"Cost Estimates ({duration}, {'spot' if spot else 'on-demand'})")
    table.add_column("GPU", style="cyan")
    table.add_column("VRAM", style="yellow")
    table.add_column("$/hr", justify="right")
    table.add_column("Total", justify="right", style="green")

    for alias in VALID_GPU_ALIASES:
        spec = GPU_MAP[alias]
        est = estimate_cost(alias, duration, spot)
        table.add_row(
            alias,
            f"{spec.vram_gb} GB",
            f"${est.hourly_rate:.2f}",
            f"${est.total_usd:.2f}",
        )

    console.print(table)

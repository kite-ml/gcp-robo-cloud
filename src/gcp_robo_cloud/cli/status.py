"""The `gcp-robo-cloud status` command."""

from __future__ import annotations

from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from gcp_robo_cloud.core.job import Job, JobState

console = Console()

STATE_COLORS = {
    JobState.CREATED: "dim",
    JobState.BUILDING_IMAGE: "yellow",
    JobState.UPLOADING: "yellow",
    JobState.PROVISIONING: "yellow",
    JobState.RUNNING: "blue",
    JobState.DOWNLOADING: "cyan",
    JobState.COMPLETED: "green",
    JobState.FAILED: "red",
    JobState.STOPPED: "dim",
}


def status(
    job_id: Optional[str] = typer.Argument(None, help="Job ID to check (omit to list all)."),
) -> None:
    """Show status of training jobs."""

    if job_id:
        # Show single job details
        try:
            job = Job.load(job_id)
        except FileNotFoundError:
            console.print(f"[red]Job '{job_id}' not found.[/red]")
            raise typer.Exit(1)

        _print_job_detail(job)
    else:
        # List all jobs
        jobs = Job.list_all()
        if not jobs:
            console.print("No jobs found. Launch one with: gcp-robo-cloud launch train.py --gpu t4")
            return

        _print_job_table(jobs)


def _print_job_detail(job: Job) -> None:
    """Print detailed info for a single job."""
    color = STATE_COLORS.get(job.state, "white")
    console.print(f"\n[bold]Job:[/bold] {job.id}")
    console.print(f"  Name:       {job.name}")
    console.print(f"  State:      [{color}]{job.state.value}[/{color}]")
    console.print(f"  GPU:        {job.gpu}")
    console.print(f"  Script:     {job.script}")
    console.print(f"  Spot:       {job.spot}")
    console.print(f"  Project:    {job.project_id}")
    console.print(f"  Zone:       {job.zone}")
    console.print(f"  Instance:   {job.instance_name}")
    console.print(f"  Created:    {job.created_at}")
    if job.started_at:
        console.print(f"  Started:    {job.started_at}")
    if job.completed_at:
        console.print(f"  Completed:  {job.completed_at}")
    if job.cost_usd is not None:
        console.print(f"  Cost:       ${job.cost_usd:.2f}")
    if job.output_dir:
        console.print(f"  Output:     {job.output_dir}")
    if job.error:
        console.print(f"  [red]Error:[/red]     {job.error}")
    console.print()


def _print_job_table(jobs: list[Job]) -> None:
    """Print a table of all jobs."""
    table = Table(title="Training Jobs")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="white")
    table.add_column("GPU", style="yellow")
    table.add_column("State")
    table.add_column("Created")
    table.add_column("Cost")

    for job in jobs[:20]:  # Show last 20
        color = STATE_COLORS.get(job.state, "white")
        cost = f"${job.cost_usd:.2f}" if job.cost_usd is not None else "-"
        created = job.created_at[:19] if job.created_at else "-"
        table.add_row(
            job.id,
            job.name[:30],
            job.gpu,
            f"[{color}]{job.state.value}[/{color}]",
            created,
            cost,
        )

    console.print(table)

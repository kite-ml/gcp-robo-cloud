"""The `gcp-robocloud stop` command."""

from __future__ import annotations

import typer
from rich.console import Console

from gcp_robocloud.core.job import Job, JobState
from gcp_robocloud.gcp.auth import resolve_project
from gcp_robocloud.monitor.watchdog import cleanup_job

console = Console()


def stop(
    job_id: str = typer.Argument(..., help="Job ID to stop."),
) -> None:
    """Stop a running training job and delete the VM."""

    try:
        job = Job.load(job_id)
    except FileNotFoundError:
        console.print(f"[red]Job '{job_id}' not found.[/red]")
        raise typer.Exit(1)

    if job.is_terminal:
        console.print(f"Job {job_id} is already {job.state.value}.")
        return

    console.print(f"Stopping job {job_id}...")
    credentials, _ = resolve_project(job.project_id)

    cleanup_job(credentials, job)

    try:
        job.transition(JobState.STOPPED)
    except ValueError:
        job.state = JobState.STOPPED
    job.save()

    console.print(f"[green]Job {job_id} stopped.[/green] VM deleted.")

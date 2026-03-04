"""Job monitoring and auto-cleanup.

Monitors running jobs and handles:
- Detecting when training completes (VM self-terminates)
- Cleaning up resources if a job fails
- Tracking elapsed time for cost estimation
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from rich.console import Console
from rich.live import Live
from rich.table import Table

from gcp_robocloud.core.job import Job, JobState
from gcp_robocloud.gcp.compute import delete_instance, get_instance_status

if TYPE_CHECKING:
    from google.auth.credentials import Credentials

console = Console()


def monitor_job(
    credentials: Credentials,
    job: Job,
    poll_interval: float = 10.0,
) -> JobState:
    """Monitor a running job until it completes or fails.

    Polls the VM status and updates the job state accordingly.
    The VM self-terminates after training, so we watch for that.

    Args:
        credentials: GCP credentials.
        job: The job to monitor.
        poll_interval: Seconds between status checks.

    Returns:
        Final job state.
    """
    start_time = time.time()

    try:
        while True:
            status = get_instance_status(
                credentials=credentials,
                project_id=job.project_id,
                zone=job.zone,
                instance_name=job.instance_name,
            )

            elapsed = time.time() - start_time

            if status is None or status in ("TERMINATED", "STOPPED"):
                # VM is gone - training finished (self-terminated) or failed
                return JobState.DOWNLOADING

            if status == "STAGING" or status == "PROVISIONING":
                _print_status(job, "Provisioning...", elapsed)
            elif status == "RUNNING":
                _print_status(job, "Training in progress...", elapsed)

            time.sleep(poll_interval)

    except KeyboardInterrupt:
        console.print("\n  Detached. Job continues running in the cloud.")
        console.print(f"  Check status: gcp-robocloud status {job.id}")
        return job.state


def cleanup_job(
    credentials: Credentials,
    job: Job,
) -> None:
    """Force cleanup a job's GCP resources."""
    console.print(f"  Cleaning up VM: {job.instance_name}")
    delete_instance(
        credentials=credentials,
        project_id=job.project_id,
        zone=job.zone,
        instance_name=job.instance_name,
    )


def _print_status(job: Job, message: str, elapsed: float) -> None:
    """Print a compact status line."""
    hours = int(elapsed // 3600)
    minutes = int((elapsed % 3600) // 60)
    seconds = int(elapsed % 60)
    time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    console.print(
        f"\r  [{time_str}] {message}",
        end="",
        highlight=False,
    )

"""Log streaming from GCP VM serial port output."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from rich.console import Console

from gcp_robo_cloud.gcp.compute import get_serial_output

if TYPE_CHECKING:
    from google.auth.credentials import Credentials

console = Console()


def stream_logs(
    credentials: Credentials,
    project_id: str,
    zone: str,
    instance_name: str,
    poll_interval: float = 3.0,
    stop_marker: str = "=== gcp-robo-cloud complete ===",
) -> None:
    """Stream serial port logs from a running VM.

    Polls the serial port output and prints new lines to the console.
    Stops when the stop marker is detected or the instance terminates.

    Args:
        credentials: GCP credentials.
        project_id: GCP project ID.
        zone: GCP zone.
        instance_name: VM instance name.
        poll_interval: Seconds between polls.
        stop_marker: String that signals training completion.
    """
    offset = 0
    console.print("  Streaming logs (Ctrl+C to detach)...\n")

    try:
        while True:
            output, new_offset = get_serial_output(
                credentials=credentials,
                project_id=project_id,
                zone=zone,
                instance_name=instance_name,
                start=offset,
            )

            if output:
                # Print new output, filtering out boot noise
                for line in output.splitlines():
                    if _is_relevant_log(line):
                        console.print(f"  {line}")

                if stop_marker in output:
                    console.print("\n  Training complete.")
                    break

            offset = new_offset
            time.sleep(poll_interval)

    except KeyboardInterrupt:
        console.print("\n  Detached from logs. Job continues running.")
        console.print(f"  Re-attach with: gcp-robo-cloud logs <job_id>")


def _is_relevant_log(line: str) -> bool:
    """Filter out noisy boot/system logs, keeping training-relevant output."""
    # Skip common boot noise
    skip_prefixes = [
        "systemd[",
        "kernel:",
        "audit:",
        "dhclient",
        "sshd[",
        "google_",
        "Starting ",
        "Started ",
        "Reached target",
        "Listening on",
        "Mounted ",
    ]
    for prefix in skip_prefixes:
        if prefix in line:
            return False
    return True

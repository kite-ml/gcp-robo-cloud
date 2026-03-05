"""Download training artifacts from GCS."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from rich.console import Console

from gcp_robo_cloud.gcp.storage import download_artifacts

if TYPE_CHECKING:
    from google.auth.credentials import Credentials

console = Console()


def download_results(
    credentials: Credentials,
    project_id: str,
    bucket_name: str,
    job_id: str,
    output_dir: Path | None = None,
) -> tuple[Path, int]:
    """Download training results from GCS.

    Args:
        credentials: GCP credentials.
        project_id: GCP project ID.
        bucket_name: GCS bucket name.
        job_id: Job ID.
        output_dir: Local directory for results. Defaults to ./gcp-robo-cloud-output/<job_id>/.

    Returns:
        Tuple of (output_path, file_count).
    """
    if output_dir is None:
        output_dir = Path.cwd() / "gcp-robo-cloud-output" / job_id

    gcs_prefix = f"jobs/{job_id}/output"

    count = download_artifacts(
        credentials=credentials,
        project_id=project_id,
        bucket_name=bucket_name,
        gcs_prefix=gcs_prefix,
        local_dir=output_dir,
    )

    return output_dir, count

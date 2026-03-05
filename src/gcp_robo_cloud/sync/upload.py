"""Upload project files to GCS."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from rich.console import Console

from gcp_robo_cloud.gcp.storage import upload_directory
from gcp_robo_cloud.sync.ignore import load_ignore_patterns

if TYPE_CHECKING:
    from google.auth.credentials import Credentials

console = Console()


def upload_project(
    credentials: Credentials,
    project_id: str,
    bucket_name: str,
    job_id: str,
    project_dir: Path,
    extra_excludes: list[str] | None = None,
) -> tuple[str, int]:
    """Upload project files to GCS for a job.

    Args:
        credentials: GCP credentials.
        project_id: GCP project ID.
        bucket_name: GCS bucket name.
        job_id: Job ID for namespacing.
        project_dir: Local project directory.
        extra_excludes: Additional exclusion patterns.

    Returns:
        Tuple of (gcs_prefix, file_count).
    """
    gcs_prefix = f"jobs/{job_id}/input"
    patterns = load_ignore_patterns(project_dir)
    if extra_excludes:
        patterns.extend(extra_excludes)

    count = upload_directory(
        credentials=credentials,
        project_id=project_id,
        bucket_name=bucket_name,
        local_dir=project_dir,
        gcs_prefix=gcs_prefix,
        exclude_patterns=patterns,
    )

    return gcs_prefix, count

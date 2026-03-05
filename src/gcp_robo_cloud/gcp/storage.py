"""GCS file upload and download for job data.

Handles uploading project files and downloading training artifacts.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import google.cloud.storage as storage
from rich.console import Console
from rich.progress import Progress

if TYPE_CHECKING:
    from google.auth.credentials import Credentials

console = Console()

DEFAULT_BUCKET_PREFIX = "gcp-robo-cloud"


def get_or_create_bucket(
    credentials: Credentials,
    project_id: str,
    bucket_name: str = "",
    region: str = "us-central1",
) -> str:
    """Get or create a GCS bucket for robocloud data.

    Args:
        credentials: GCP credentials.
        project_id: GCP project ID.
        bucket_name: Explicit bucket name, or auto-generate from project ID.
        region: GCP region for the bucket.

    Returns:
        The bucket name.
    """
    client = storage.Client(credentials=credentials, project=project_id)

    if not bucket_name:
        bucket_name = f"{DEFAULT_BUCKET_PREFIX}-{project_id}"

    bucket = client.bucket(bucket_name)
    if not bucket.exists():
        bucket = client.create_bucket(bucket_name, location=region)
        console.print(f"  Created GCS bucket: gs://{bucket_name}")

    return bucket_name


def upload_directory(
    credentials: Credentials,
    project_id: str,
    bucket_name: str,
    local_dir: Path,
    gcs_prefix: str,
    exclude_patterns: list[str] | None = None,
) -> int:
    """Upload a local directory to GCS.

    Args:
        credentials: GCP credentials.
        project_id: GCP project ID.
        bucket_name: GCS bucket name.
        local_dir: Local directory to upload.
        gcs_prefix: GCS prefix (e.g., 'jobs/abc123/input').
        exclude_patterns: Glob patterns to exclude.

    Returns:
        Number of files uploaded.
    """
    client = storage.Client(credentials=credentials, project=project_id)
    bucket = client.bucket(bucket_name)

    # Collect files, applying exclusions
    files = []
    for path in local_dir.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(local_dir)
        if _should_exclude(str(rel), exclude_patterns or []):
            continue
        files.append((path, rel))

    if not files:
        return 0

    with Progress(console=console) as progress:
        task = progress.add_task("Uploading...", total=len(files))
        for local_path, rel_path in files:
            blob_name = f"{gcs_prefix}/{rel_path}"
            blob = bucket.blob(blob_name)
            blob.upload_from_filename(str(local_path))
            progress.advance(task)

    return len(files)


def download_artifacts(
    credentials: Credentials,
    project_id: str,
    bucket_name: str,
    gcs_prefix: str,
    local_dir: Path,
) -> int:
    """Download job artifacts from GCS to a local directory.

    Args:
        credentials: GCP credentials.
        project_id: GCP project ID.
        bucket_name: GCS bucket name.
        gcs_prefix: GCS prefix (e.g., 'jobs/abc123/output').
        local_dir: Local directory to download to.

    Returns:
        Number of files downloaded.
    """
    client = storage.Client(credentials=credentials, project=project_id)
    bucket = client.bucket(bucket_name)

    blobs = list(bucket.list_blobs(prefix=gcs_prefix))
    if not blobs:
        return 0

    local_dir.mkdir(parents=True, exist_ok=True)
    count = 0

    with Progress(console=console) as progress:
        task = progress.add_task("Downloading...", total=len(blobs))
        for blob in blobs:
            rel_path = blob.name.removeprefix(gcs_prefix).lstrip("/")
            if not rel_path:
                progress.advance(task)
                continue
            local_path = local_dir / rel_path
            local_path.parent.mkdir(parents=True, exist_ok=True)
            blob.download_to_filename(str(local_path))
            count += 1
            progress.advance(task)

    return count


def _should_exclude(rel_path: str, patterns: list[str]) -> bool:
    """Check if a relative path matches any exclusion pattern."""
    from fnmatch import fnmatch

    for pattern in patterns:
        if fnmatch(rel_path, pattern) or fnmatch(rel_path, f"**/{pattern}"):
            return True
        # Check directory-level patterns
        parts = rel_path.split("/")
        for part in parts:
            if fnmatch(part, pattern):
                return True
    return False

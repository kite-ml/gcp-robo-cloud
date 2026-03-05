"""Artifact Registry integration for Docker image storage.

Pushes locally-built Docker images to GCP Artifact Registry
so VMs can pull them during training.
"""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

from rich.console import Console

if TYPE_CHECKING:
    from google.auth.credentials import Credentials

console = Console()

DEFAULT_REPO_NAME = "gcp-robo-cloud"


def ensure_repository(
    project_id: str,
    region: str,
    repo_name: str = DEFAULT_REPO_NAME,
) -> str:
    """Ensure an Artifact Registry Docker repository exists.

    Returns:
        The full repository path (e.g., 'us-central1-docker.pkg.dev/project/repo').
    """
    registry_host = f"{region}-docker.pkg.dev"
    repo_path = f"{registry_host}/{project_id}/{repo_name}"

    # Check if repo exists, create if not
    result = subprocess.run(
        [
            "gcloud", "artifacts", "repositories", "describe",
            repo_name,
            f"--project={project_id}",
            f"--location={region}",
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        console.print(f"  Creating Artifact Registry repo: {repo_path}")
        subprocess.run(
            [
                "gcloud", "artifacts", "repositories", "create",
                repo_name,
                f"--project={project_id}",
                f"--location={region}",
                "--repository-format=docker",
                "--description=gcp-robo-cloud training images",
            ],
            check=True,
            capture_output=True,
            text=True,
        )

    return repo_path


def configure_docker_auth(region: str) -> None:
    """Configure Docker to authenticate with Artifact Registry."""
    registry_host = f"{region}-docker.pkg.dev"
    subprocess.run(
        ["gcloud", "auth", "configure-docker", registry_host, "--quiet"],
        check=True,
        capture_output=True,
        text=True,
    )


def push_image(local_tag: str, remote_uri: str) -> None:
    """Tag and push a Docker image to Artifact Registry.

    Args:
        local_tag: Local Docker image tag.
        remote_uri: Full Artifact Registry URI to push to.
    """
    import docker as docker_sdk

    client = docker_sdk.from_env()

    # Tag for remote registry
    image = client.images.get(local_tag)
    image.tag(remote_uri)

    # Push
    console.print(f"  Pushing image to {remote_uri}...")
    for line in client.images.push(remote_uri, stream=True, decode=True):
        if "error" in line:
            raise RuntimeError(f"Docker push failed: {line['error']}")

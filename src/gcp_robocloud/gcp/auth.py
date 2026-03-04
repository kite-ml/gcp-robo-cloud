"""GCP authentication and project resolution.

Uses Application Default Credentials (ADC) for authentication.
Users authenticate via `gcloud auth application-default login`.
"""

from __future__ import annotations

import google.auth
from google.auth.credentials import Credentials
from rich.console import Console

console = Console()


class AuthError(Exception):
    """Raised when GCP authentication fails."""


def get_credentials() -> tuple[Credentials, str]:
    """Get ADC credentials and default project ID.

    Returns:
        Tuple of (credentials, project_id).

    Raises:
        AuthError: If credentials cannot be found.
    """
    try:
        credentials, project_id = google.auth.default()
    except google.auth.exceptions.DefaultCredentialsError:
        raise AuthError(
            "GCP credentials not found. Run:\n"
            "  gcloud auth application-default login\n"
            "  gcloud config set project YOUR_PROJECT_ID"
        )

    if not project_id:
        raise AuthError(
            "GCP project ID not found. Set it with:\n"
            "  gcloud config set project YOUR_PROJECT_ID\n"
            "Or add 'project: YOUR_PROJECT_ID' to gcp-robocloud.yaml"
        )

    return credentials, project_id


def resolve_project(config_project: str = "") -> tuple[Credentials, str]:
    """Resolve the GCP project to use.

    Args:
        config_project: Project ID from config (takes priority over ADC default).

    Returns:
        Tuple of (credentials, project_id).
    """
    credentials, default_project = get_credentials()
    project_id = config_project or default_project
    return credentials, project_id

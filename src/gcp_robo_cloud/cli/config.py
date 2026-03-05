"""The `gcp-robo-cloud config` command."""

from __future__ import annotations

import subprocess

import typer
import yaml
from rich.console import Console
from rich.panel import Panel

from gcp_robo_cloud.core.config import USER_CONFIG_PATH, load_config

console = Console()

REQUIRED_APIS = [
    "compute.googleapis.com",
    "storage.googleapis.com",
    "artifactregistry.googleapis.com",
]


def config(
    init: bool = typer.Option(False, "--init", help="Run first-time setup."),
    show: bool = typer.Option(False, "--show", help="Show current config."),
    set_key: str = typer.Option("", "--set", help="Set a config value (format: key=value)."),
) -> None:
    """Manage gcp-robo-cloud configuration."""

    if init:
        _run_init()
    elif show:
        _show_config()
    elif set_key:
        _set_value(set_key)
    else:
        _show_config()


def _run_init() -> None:
    """First-time setup: check auth, enable APIs."""
    console.print("[bold]gcp-robo-cloud setup[/bold]\n")

    # Check gcloud auth
    console.print("Checking GCP authentication...")
    result = subprocess.run(
        ["gcloud", "auth", "application-default", "print-access-token"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        console.print("[yellow]Not authenticated.[/yellow] Running gcloud auth...")
        subprocess.run(["gcloud", "auth", "application-default", "login"], check=True)
    else:
        console.print("  [green]Authenticated[/green]")

    # Get project
    result = subprocess.run(
        ["gcloud", "config", "get-value", "project"],
        capture_output=True,
        text=True,
    )
    project_id = result.stdout.strip()
    if not project_id:
        console.print("[red]No project set.[/red] Run: gcloud config set project YOUR_PROJECT")
        raise typer.Exit(1)
    console.print(f"  Project: {project_id}")

    # Enable APIs
    console.print("\nEnabling required GCP APIs...")
    for api in REQUIRED_APIS:
        console.print(f"  Enabling {api}...")
        subprocess.run(
            ["gcloud", "services", "enable", api, f"--project={project_id}"],
            capture_output=True,
            text=True,
        )
    console.print("  [green]APIs enabled[/green]")

    # Check Docker
    console.print("\nChecking Docker...")
    result = subprocess.run(["docker", "info"], capture_output=True, text=True)
    if result.returncode != 0:
        console.print("[yellow]Docker not running.[/yellow] Please start Docker Desktop.")
    else:
        console.print("  [green]Docker running[/green]")

    # Create user config dir
    USER_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not USER_CONFIG_PATH.exists():
        USER_CONFIG_PATH.write_text(
            yaml.dump({"default_project": project_id, "default_region": "us-central1"})
        )
        console.print(f"\n  Config written to {USER_CONFIG_PATH}")

    console.print("\n[green]Setup complete![/green] Try: gcp-robo-cloud launch train.py --gpu t4")


def _show_config() -> None:
    """Show current config from all sources."""
    cfg = load_config()
    lines = [
        f"project:      {cfg.project or '(from gcloud)'}",
        f"region:       {cfg.region}",
        f"gpu:          {cfg.gpu}",
        f"spot:         {cfg.spot}",
        f"max_duration: {cfg.max_duration}",
    ]
    console.print(Panel("\n".join(lines), title="Current Config"))


def _set_value(key_value: str) -> None:
    """Set a user-level config value."""
    if "=" not in key_value:
        console.print("[red]Format:[/red] --set key=value")
        raise typer.Exit(1)

    key, value = key_value.split("=", 1)
    key = key.strip()
    value = value.strip()

    # Load existing config
    USER_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    data: dict[str, object] = {}
    if USER_CONFIG_PATH.exists():
        data = yaml.safe_load(USER_CONFIG_PATH.read_text()) or {}

    # Handle booleans
    if value.lower() in ("true", "yes"):
        data[f"default_{key}"] = True
    elif value.lower() in ("false", "no"):
        data[f"default_{key}"] = False
    else:
        data[f"default_{key}"] = value

    USER_CONFIG_PATH.write_text(yaml.dump(data))
    console.print(f"Set {key} = {value}")

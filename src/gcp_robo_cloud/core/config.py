"""Configuration loading and merging.

Config priority (highest wins):
1. CLI flags / Python API arguments
2. Project-level gcp-robo-cloud.yaml
3. User-level ~/.gcp-robo-cloud/config.yaml
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

USER_CONFIG_PATH = Path.home() / ".gcp-robo-cloud" / "config.yaml"
PROJECT_CONFIG_NAME = "gcp-robo-cloud.yaml"


@dataclass
class DockerConfig:
    base_image: str = ""
    python_version: str = "3.11"
    system_packages: list[str] = field(default_factory=list)
    pip_extra_index: list[str] = field(default_factory=list)
    dockerfile: str = ""


@dataclass
class SyncConfig:
    include: list[str] = field(default_factory=list)
    exclude: list[str] = field(default_factory=list)
    output_patterns: list[str] = field(default_factory=lambda: ["outputs/**"])


@dataclass
class Config:
    project: str = ""
    region: str = "us-central1"
    gpu: str = "t4"
    gpu_count: int = 1
    spot: bool = True
    max_duration: str = "4h"
    budget: float | None = None
    script: str = ""
    args: str = ""
    gcs_bucket: str = ""
    docker: DockerConfig = field(default_factory=DockerConfig)
    sync: SyncConfig = field(default_factory=SyncConfig)


def _load_yaml(path: Path) -> dict:
    """Load a YAML file, returning empty dict if it doesn't exist."""
    if not path.exists():
        return {}
    try:
        with open(path) as f:
            data = yaml.safe_load(f)
        return data if isinstance(data, dict) else {}
    except yaml.YAMLError:
        return {}


def _merge_into_config(config: Config, data: dict) -> None:
    """Merge a dict of values into a Config, only overwriting non-empty values."""
    for key, value in data.items():
        if key == "docker" and isinstance(value, dict):
            for dk, dv in value.items():
                if dv is not None and hasattr(config.docker, dk):
                    setattr(config.docker, dk, dv)
        elif key == "sync" and isinstance(value, dict):
            for sk, sv in value.items():
                if sv is not None and hasattr(config.sync, sk):
                    setattr(config.sync, sk, sv)
        elif hasattr(config, key) and value is not None:
            setattr(config, key, value)


def load_config(
    project_dir: Path | None = None,
    overrides: dict | None = None,
) -> Config:
    """Load and merge config from all sources.

    Args:
        project_dir: Directory to look for gcp-robo-cloud.yaml. Defaults to cwd.
        overrides: CLI/API overrides (highest priority).
    """
    config = Config()

    # Layer 1: User-level config
    user_data = _load_yaml(USER_CONFIG_PATH)
    # Remap default_* keys to standard keys
    for key in list(user_data.keys()):
        if key.startswith("default_"):
            user_data[key.removeprefix("default_")] = user_data.pop(key)
    _merge_into_config(config, user_data)

    # Layer 2: Project-level config
    if project_dir is None:
        project_dir = Path.cwd()
    project_data = _load_yaml(project_dir / PROJECT_CONFIG_NAME)
    _merge_into_config(config, project_data)

    # Layer 3: CLI/API overrides
    if overrides:
        _merge_into_config(config, overrides)

    return config

"""Dependency and framework detection for auto-containerization.

Scans a project directory to determine:
- How to install dependencies (requirements.txt, pyproject.toml, etc.)
- Which base Docker image to use
- Any special system packages needed
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ProjectInfo:
    """Detected project information."""

    # Dependency source
    has_requirements_txt: bool = False
    has_pyproject_toml: bool = False
    has_environment_yml: bool = False
    has_dockerfile: bool = False

    # Framework hints
    frameworks: list[str] = field(default_factory=list)

    # System packages needed
    system_packages: list[str] = field(default_factory=list)


# Keywords in requirements that hint at specific frameworks
_FRAMEWORK_HINTS: dict[str, list[str]] = {
    "isaaclab": ["isaac-lab", "isaaclab", "omni.isaac"],
    "ros2": ["rclpy", "ros2", "ament"],
    "mujoco": ["mujoco", "dm_control"],
    "pybullet": ["pybullet"],
    "gymnasium": ["gymnasium", "gym"],
    "stable-baselines3": ["stable-baselines3", "sb3"],
    "pytorch": ["torch", "pytorch"],
    "tensorflow": ["tensorflow"],
    "jax": ["jax", "jaxlib"],
}

# System packages commonly needed by robotics/ML projects
_FRAMEWORK_SYSTEM_PACKAGES: dict[str, list[str]] = {
    "mujoco": ["libgl1-mesa-glx", "libosmesa6", "libglew-dev"],
    "pybullet": ["libgl1-mesa-glx", "libegl1"],
    "gymnasium": ["libgl1-mesa-glx"],
}


def detect_project(project_dir: Path) -> ProjectInfo:
    """Scan a project directory and detect its configuration.

    Args:
        project_dir: Path to the project root.

    Returns:
        ProjectInfo with detected settings.
    """
    info = ProjectInfo()

    # Check for dependency files
    info.has_requirements_txt = (project_dir / "requirements.txt").exists()
    info.has_pyproject_toml = (project_dir / "pyproject.toml").exists()
    info.has_environment_yml = (
        (project_dir / "environment.yml").exists()
        or (project_dir / "environment.yaml").exists()
    )
    info.has_dockerfile = (project_dir / "Dockerfile").exists()

    # Scan requirements for framework hints
    deps_text = ""
    if info.has_requirements_txt:
        deps_text += (project_dir / "requirements.txt").read_text()
    if info.has_pyproject_toml:
        deps_text += (project_dir / "pyproject.toml").read_text()

    deps_lower = deps_text.lower()
    for framework, keywords in _FRAMEWORK_HINTS.items():
        if any(kw in deps_lower for kw in keywords):
            info.frameworks.append(framework)

    # Determine system packages needed
    seen = set()
    for framework in info.frameworks:
        for pkg in _FRAMEWORK_SYSTEM_PACKAGES.get(framework, []):
            if pkg not in seen:
                info.system_packages.append(pkg)
                seen.add(pkg)

    return info


def select_base_image(gpu: str, frameworks: list[str]) -> str:
    """Select the best Docker base image for the project.

    Args:
        gpu: GPU alias (e.g., 'a100', 'h100').
        frameworks: Detected framework names.

    Returns:
        Docker image string.
    """
    # Framework-specific images
    if "ros2" in frameworks:
        return "ros:jazzy-perception"

    # Default to CUDA images based on GPU
    needs_newer_cuda = gpu in ("h100", "b200")
    cuda_version = "12.6.0" if needs_newer_cuda else "12.4.1"
    return f"nvidia/cuda:{cuda_version}-runtime-ubuntu22.04"


def get_install_method(info: ProjectInfo) -> str:
    """Determine the package installation method.

    Returns:
        One of: 'requirements', 'pyproject', 'conda', 'none'
    """
    if info.has_requirements_txt:
        return "requirements"
    if info.has_pyproject_toml:
        return "pyproject"
    if info.has_environment_yml:
        return "conda"
    return "none"

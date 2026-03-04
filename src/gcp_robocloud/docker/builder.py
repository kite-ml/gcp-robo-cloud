"""Docker image building and management.

Generates Dockerfiles from templates, builds images locally,
and prepares them for pushing to Artifact Registry.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import docker as docker_sdk
import jinja2
from rich.console import Console

from gcp_robocloud.docker.detect import ProjectInfo, get_install_method, select_base_image
from gcp_robocloud.docker.templates import CUDA_TEMPLATE, ROS2_TEMPLATE

console = Console()


def generate_dockerfile(
    project_dir: Path,
    info: ProjectInfo,
    gpu: str,
    base_image: str = "",
    python_version: str = "3.11",
    extra_system_packages: list[str] | None = None,
) -> str:
    """Generate a Dockerfile for the project.

    Args:
        project_dir: Path to the project root.
        info: Detected project information.
        gpu: GPU alias for base image selection.
        base_image: Override base image (empty = auto-detect).
        python_version: Python version to install.
        extra_system_packages: Additional apt packages.

    Returns:
        Generated Dockerfile contents as a string.
    """
    if not base_image:
        base_image = select_base_image(gpu, info.frameworks)

    install_method = get_install_method(info)
    system_packages = list(info.system_packages)
    if extra_system_packages:
        system_packages.extend(extra_system_packages)

    # Select template
    template_str = ROS2_TEMPLATE if "ros2" in info.frameworks else CUDA_TEMPLATE

    template = jinja2.Template(template_str)
    return template.render(
        base_image=base_image,
        python_version=python_version,
        system_packages=system_packages,
        install_method=install_method,
        has_src_dir=(project_dir / "src").is_dir(),
    )


def build_image(
    project_dir: Path,
    info: ProjectInfo,
    gpu: str,
    tag: str,
    base_image: str = "",
    python_version: str = "3.11",
    extra_system_packages: list[str] | None = None,
) -> str:
    """Build a Docker image for the project.

    If the project has its own Dockerfile, uses that directly.
    Otherwise, generates one from templates.

    Args:
        project_dir: Path to the project root.
        info: Detected project information.
        gpu: GPU alias.
        tag: Docker image tag.
        base_image: Override base image.
        python_version: Python version.
        extra_system_packages: Additional apt packages.

    Returns:
        The image tag.
    """
    client = docker_sdk.from_env()

    if info.has_dockerfile:
        # Use the project's own Dockerfile
        console.print("  Using existing Dockerfile")
        image, logs = client.images.build(
            path=str(project_dir),
            tag=tag,
            rm=True,
        )
    else:
        # Generate a Dockerfile
        dockerfile_content = generate_dockerfile(
            project_dir=project_dir,
            info=info,
            gpu=gpu,
            base_image=base_image,
            python_version=python_version,
            extra_system_packages=extra_system_packages,
        )

        # Write to a temp file and build with project context
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".Dockerfile", dir=str(project_dir), delete=False
        ) as f:
            f.write(dockerfile_content)
            temp_dockerfile = f.name

        try:
            image, logs = client.images.build(
                path=str(project_dir),
                dockerfile=temp_dockerfile,
                tag=tag,
                rm=True,
            )
        finally:
            Path(temp_dockerfile).unlink(missing_ok=True)

    return tag

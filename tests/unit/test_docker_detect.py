"""Tests for project dependency detection."""

import tempfile
from pathlib import Path

from gcp_robocloud.docker.detect import (
    detect_project,
    get_install_method,
    select_base_image,
)


class TestDetectProject:
    def test_empty_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            info = detect_project(Path(tmpdir))
            assert not info.has_requirements_txt
            assert not info.has_pyproject_toml
            assert not info.has_dockerfile
            assert info.frameworks == []

    def test_detects_requirements_txt(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "requirements.txt").write_text("torch>=2.0\n")
            info = detect_project(Path(tmpdir))
            assert info.has_requirements_txt
            assert "pytorch" in info.frameworks

    def test_detects_mujoco(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "requirements.txt").write_text("mujoco>=3.0\ngymnasium\n")
            info = detect_project(Path(tmpdir))
            assert "mujoco" in info.frameworks
            assert "gymnasium" in info.frameworks
            assert "libgl1-mesa-glx" in info.system_packages

    def test_detects_pybullet(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "requirements.txt").write_text("pybullet\n")
            info = detect_project(Path(tmpdir))
            assert "pybullet" in info.frameworks

    def test_detects_stable_baselines3(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "requirements.txt").write_text("stable-baselines3\n")
            info = detect_project(Path(tmpdir))
            assert "stable-baselines3" in info.frameworks

    def test_detects_dockerfile(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "Dockerfile").write_text("FROM python:3.11\n")
            info = detect_project(Path(tmpdir))
            assert info.has_dockerfile

    def test_detects_pyproject_toml(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "pyproject.toml").write_text('[project]\nname = "test"\n')
            info = detect_project(Path(tmpdir))
            assert info.has_pyproject_toml


class TestSelectBaseImage:
    def test_default_cuda_for_a100(self):
        image = select_base_image("a100", [])
        assert "cuda" in image
        assert "12.4" in image

    def test_newer_cuda_for_h100(self):
        image = select_base_image("h100", [])
        assert "12.6" in image

    def test_ros2_image(self):
        image = select_base_image("a100", ["ros2"])
        assert "ros" in image


class TestGetInstallMethod:
    def test_requirements_priority(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "requirements.txt").write_text("torch\n")
            (Path(tmpdir) / "pyproject.toml").write_text("[project]\n")
            info = detect_project(Path(tmpdir))
            assert get_install_method(info) == "requirements"

    def test_pyproject_fallback(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "pyproject.toml").write_text("[project]\n")
            info = detect_project(Path(tmpdir))
            assert get_install_method(info) == "pyproject"

    def test_none_for_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            info = detect_project(Path(tmpdir))
            assert get_install_method(info) == "none"

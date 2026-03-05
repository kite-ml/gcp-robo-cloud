"""Tests for configuration loading and merging."""

import tempfile
from pathlib import Path

import yaml

from gcp_robo_cloud.core.config import Config, DockerConfig, SyncConfig, load_config


class TestConfigDefaults:
    def test_default_values(self):
        cfg = Config()
        assert cfg.gpu == "t4"
        assert cfg.region == "us-central1"
        assert cfg.spot is True
        assert cfg.max_duration == "4h"
        assert cfg.gpu_count == 1

    def test_docker_defaults(self):
        cfg = Config()
        assert cfg.docker.python_version == "3.11"
        assert cfg.docker.base_image == ""
        assert cfg.docker.system_packages == []

    def test_sync_defaults(self):
        cfg = Config()
        assert cfg.sync.output_patterns == ["outputs/**"]
        assert cfg.sync.exclude == []


class TestLoadConfig:
    def test_loads_from_empty_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = load_config(project_dir=Path(tmpdir))
            assert cfg.gpu == "t4"

    def test_project_config_overrides(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_data = {"gpu": "a100", "spot": False}
            (Path(tmpdir) / "gcp-robo-cloud.yaml").write_text(yaml.dump(config_data))
            cfg = load_config(project_dir=Path(tmpdir))
            assert cfg.gpu == "a100"
            assert cfg.spot is False

    def test_cli_overrides_project(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_data = {"gpu": "a100", "max_duration": "2h"}
            (Path(tmpdir) / "gcp-robo-cloud.yaml").write_text(yaml.dump(config_data))
            cfg = load_config(project_dir=Path(tmpdir), overrides={"gpu": "h100"})
            assert cfg.gpu == "h100"
            assert cfg.max_duration == "2h"  # Not overridden

    def test_docker_config_from_yaml(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_data = {
                "docker": {
                    "base_image": "custom:latest",
                    "python_version": "3.12",
                    "system_packages": ["libfoo"],
                }
            }
            (Path(tmpdir) / "gcp-robo-cloud.yaml").write_text(yaml.dump(config_data))
            cfg = load_config(project_dir=Path(tmpdir))
            assert cfg.docker.base_image == "custom:latest"
            assert cfg.docker.python_version == "3.12"
            assert cfg.docker.system_packages == ["libfoo"]

    def test_sync_config_from_yaml(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_data = {
                "sync": {
                    "exclude": ["data/", "*.bin"],
                    "output_patterns": ["results/**"],
                }
            }
            (Path(tmpdir) / "gcp-robo-cloud.yaml").write_text(yaml.dump(config_data))
            cfg = load_config(project_dir=Path(tmpdir))
            assert cfg.sync.exclude == ["data/", "*.bin"]
            assert cfg.sync.output_patterns == ["results/**"]

    def test_invalid_yaml_returns_defaults(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "gcp-robo-cloud.yaml").write_text("not: [valid: yaml: {{")
            # Should not crash, just use defaults
            cfg = load_config(project_dir=Path(tmpdir))
            assert cfg.gpu == "t4"

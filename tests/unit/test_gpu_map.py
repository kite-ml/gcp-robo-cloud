"""Tests for GPU alias resolution."""

import pytest

from gcp_robo_cloud.core.gpu_map import GPU_MAP, VALID_GPU_ALIASES, GPUSpec, resolve_gpu


class TestResolveGpu:
    def test_all_aliases_resolve(self):
        for alias in VALID_GPU_ALIASES:
            spec = resolve_gpu(alias)
            assert isinstance(spec, GPUSpec)

    def test_case_insensitive(self):
        assert resolve_gpu("A100") == resolve_gpu("a100")
        assert resolve_gpu("T4") == resolve_gpu("t4")

    def test_strips_whitespace(self):
        assert resolve_gpu("  a100  ") == resolve_gpu("a100")

    def test_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown GPU type"):
            resolve_gpu("nonexistent")

    def test_error_shows_valid_options(self):
        with pytest.raises(ValueError, match="t4"):
            resolve_gpu("bad")


class TestGPUSpec:
    def test_all_specs_have_zones(self):
        for alias, spec in GPU_MAP.items():
            assert len(spec.zones) > 0, f"{alias} has no zones"

    def test_all_specs_have_pricing(self):
        for alias, spec in GPU_MAP.items():
            assert spec.spot_hourly_usd > 0, f"{alias} missing spot price"
            assert spec.ondemand_hourly_usd > 0, f"{alias} missing on-demand price"
            assert spec.spot_hourly_usd < spec.ondemand_hourly_usd, f"{alias} spot >= on-demand"

    def test_all_specs_have_vram(self):
        for alias, spec in GPU_MAP.items():
            assert spec.vram_gb > 0, f"{alias} missing VRAM"

    def test_machine_types_valid(self):
        for alias, spec in GPU_MAP.items():
            assert spec.machine_type, f"{alias} missing machine_type"
            assert spec.accelerator_type, f"{alias} missing accelerator_type"

    def test_frozen(self):
        spec = resolve_gpu("t4")
        with pytest.raises(AttributeError):
            spec.vram_gb = 999

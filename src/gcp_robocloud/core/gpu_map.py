"""GPU alias -> GCP resource mapping.

Maps user-friendly GPU names (e.g. 'a100') to the exact GCP machine type,
accelerator type, and preferred zones needed to provision them.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GPUSpec:
    """Specification for a GCP GPU instance."""

    machine_type: str
    accelerator_type: str
    accelerator_count: int
    zones: tuple[str, ...]
    vram_gb: int
    spot_hourly_usd: float
    ondemand_hourly_usd: float


GPU_MAP: dict[str, GPUSpec] = {
    "t4": GPUSpec(
        machine_type="n1-standard-8",
        accelerator_type="nvidia-tesla-t4",
        accelerator_count=1,
        zones=("us-central1-a", "us-central1-b", "us-central1-f", "us-west1-b"),
        vram_gb=16,
        spot_hourly_usd=0.11,
        ondemand_hourly_usd=0.35,
    ),
    "v100": GPUSpec(
        machine_type="n1-standard-8",
        accelerator_type="nvidia-tesla-v100",
        accelerator_count=1,
        zones=("us-central1-c", "us-central1-f", "us-west1-b", "europe-west4-a"),
        vram_gb=16,
        spot_hourly_usd=0.74,
        ondemand_hourly_usd=2.48,
    ),
    "a100": GPUSpec(
        machine_type="a2-highgpu-1g",
        accelerator_type="nvidia-tesla-a100",
        accelerator_count=1,
        zones=("us-central1-a", "us-central1-c", "us-east1-c", "europe-west4-a"),
        vram_gb=40,
        spot_hourly_usd=1.10,
        ondemand_hourly_usd=3.67,
    ),
    "a100-80gb": GPUSpec(
        machine_type="a2-ultragpu-1g",
        accelerator_type="nvidia-a100-80gb",
        accelerator_count=1,
        zones=("us-central1-a", "us-central1-c", "us-east1-c"),
        vram_gb=80,
        spot_hourly_usd=1.47,
        ondemand_hourly_usd=4.90,
    ),
    "l4": GPUSpec(
        machine_type="g2-standard-8",
        accelerator_type="nvidia-l4",
        accelerator_count=1,
        zones=("us-central1-a", "us-central1-b", "us-east1-d", "us-west1-a"),
        vram_gb=24,
        spot_hourly_usd=0.22,
        ondemand_hourly_usd=0.72,
    ),
    "h100": GPUSpec(
        machine_type="a3-highgpu-1g",
        accelerator_type="nvidia-h100-80gb",
        accelerator_count=1,
        zones=("us-central1-a", "us-central1-c", "us-east4-a"),
        vram_gb=80,
        spot_hourly_usd=3.54,
        ondemand_hourly_usd=11.81,
    ),
}

VALID_GPU_ALIASES = sorted(GPU_MAP.keys())


def resolve_gpu(alias: str) -> GPUSpec:
    """Resolve a user-friendly GPU alias to a full GPUSpec.

    Raises:
        ValueError: If the alias is not recognized.
    """
    alias = alias.lower().strip()
    if alias not in GPU_MAP:
        valid = ", ".join(VALID_GPU_ALIASES)
        raise ValueError(f"Unknown GPU type '{alias}'. Valid options: {valid}")
    return GPU_MAP[alias]

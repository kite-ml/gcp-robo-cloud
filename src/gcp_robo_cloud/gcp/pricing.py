"""Cost estimation for GCP GPU instances.

Provides estimated costs based on GPU type, duration, and spot vs on-demand.
Prices are approximate and based on public GCP pricing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from gcp_robo_cloud.core.gpu_map import GPUSpec, resolve_gpu


@dataclass
class CostEstimate:
    """Estimated cost for a training run."""

    gpu: str
    duration_hours: float
    spot: bool
    hourly_rate: float
    total_usd: float


def parse_duration(duration: str) -> float:
    """Parse a duration string (e.g., '2h', '30m', '1h30m') to hours."""
    total_seconds = 0
    for value, unit in re.findall(r"(\d+)([hms])", duration.lower()):
        val = int(value)
        if unit == "h":
            total_seconds += val * 3600
        elif unit == "m":
            total_seconds += val * 60
        elif unit == "s":
            total_seconds += val
    if total_seconds == 0:
        # Try parsing as plain hours
        try:
            return float(duration)
        except ValueError:
            raise ValueError(f"Cannot parse duration: '{duration}'. Use format like '2h', '30m', '1h30m'")
    return total_seconds / 3600


def estimate_cost(
    gpu: str,
    duration: str = "1h",
    spot: bool = True,
) -> CostEstimate:
    """Estimate the cost of a training run.

    Args:
        gpu: GPU alias (e.g., 'a100').
        duration: Duration string (e.g., '2h', '30m').
        spot: Whether to use spot pricing.

    Returns:
        CostEstimate with pricing details.
    """
    spec = resolve_gpu(gpu)
    hours = parse_duration(duration)
    hourly = spec.spot_hourly_usd if spot else spec.ondemand_hourly_usd
    total = hourly * hours

    return CostEstimate(
        gpu=gpu,
        duration_hours=hours,
        spot=spot,
        hourly_rate=hourly,
        total_usd=round(total, 2),
    )


def format_estimate(estimate: CostEstimate) -> str:
    """Format a cost estimate for display."""
    pricing_type = "spot" if estimate.spot else "on-demand"
    return (
        f"GPU: {estimate.gpu} ({pricing_type})\n"
        f"Duration: {estimate.duration_hours:.1f}h\n"
        f"Rate: ${estimate.hourly_rate:.2f}/hr\n"
        f"Estimated total: ${estimate.total_usd:.2f}"
    )

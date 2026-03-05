"""Tests for cost estimation."""

import pytest

from gcp_robo_cloud.gcp.pricing import CostEstimate, estimate_cost, format_estimate, parse_duration


class TestParseDuration:
    def test_hours(self):
        assert parse_duration("2h") == 2.0

    def test_minutes(self):
        assert parse_duration("30m") == 0.5

    def test_combined(self):
        assert parse_duration("1h30m") == 1.5

    def test_seconds(self):
        assert parse_duration("3600s") == 1.0

    def test_invalid_raises(self):
        with pytest.raises(ValueError, match="Cannot parse"):
            parse_duration("invalid")


class TestEstimateCost:
    def test_spot_cheaper_than_ondemand(self):
        spot = estimate_cost("a100", "1h", spot=True)
        ondemand = estimate_cost("a100", "1h", spot=False)
        assert spot.total_usd < ondemand.total_usd

    def test_scales_with_duration(self):
        one_hour = estimate_cost("t4", "1h", spot=True)
        two_hours = estimate_cost("t4", "2h", spot=True)
        assert abs(two_hours.total_usd - 2 * one_hour.total_usd) < 0.01

    def test_invalid_gpu_raises(self):
        with pytest.raises(ValueError):
            estimate_cost("nonexistent", "1h")

    def test_returns_cost_estimate(self):
        est = estimate_cost("t4", "1h", spot=True)
        assert isinstance(est, CostEstimate)
        assert est.gpu == "t4"
        assert est.spot is True
        assert est.duration_hours == 1.0
        assert est.total_usd > 0


class TestFormatEstimate:
    def test_contains_key_info(self):
        est = estimate_cost("a100", "2h", spot=True)
        output = format_estimate(est)
        assert "a100" in output
        assert "spot" in output
        assert "$" in output
        assert "2.0h" in output

"""Shared test fixtures."""


def pytest_configure(config):
    config.addinivalue_line("markers", "integration: requires GCP credentials")

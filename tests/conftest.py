"""Fixtures for HAEO Device Forecast tests."""

import pytest

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(request: pytest.FixtureRequest):
    """Enable custom integrations for all tests, required by HA test harness.

    Skipped for tests using ``recorder_mock``: that fixture must set up the
    recorder database before ``hass`` is first instantiated, and eagerly
    depending on ``enable_custom_integrations`` (which requires ``hass``)
    here would instantiate ``hass`` too early and break that ordering.
    """
    if "recorder_mock" not in request.fixturenames:
        request.getfixturevalue("enable_custom_integrations")

"""Drive the real hub config flow and the "Add device" subentry flow in a browser.

tests/test_translations.py locks down the *source* JSON. This file locks down
the *result*: what a user sees after Home Assistant parses that JSON - the
translated labels of the device form, a working power-sensor picker, and a
device that actually gets created. A broken ICU string surfaces only as a JS
console error, not a Python exception, so page errors fail the tests too.

The tests share one HA instance and run in file order: the hub is created
first, devices are added to it afterwards.
"""

from __future__ import annotations

import re

from playwright.sync_api import Page, expect

from conftest import E2E_POWER_SENSOR_NAME, SCREENSHOT_DIR

INTEGRATION_NAME = "HAEO Device Forecast"
DEVICE_NAME = "E2E Washer"
DEVICE_FORM_LABELS = (
    "Name",
    "Power sensor",
    "Start threshold (W)",
    "Band bucket width (s)",
)
CREATED = "Created configuration for"


def _is_real_error(exc) -> bool:
    """Filter out benign browser noise unrelated to our flows (see ResizeObserver)."""
    message = str(exc)
    return bool(message) and message != "Object" and "ResizeObserver" not in message


def _collect_page_errors(page: Page) -> list[str]:
    errors: list[str] = []
    page.on("pageerror", lambda exc: errors.append(str(exc)) if _is_real_error(exc) else None)
    return errors


def test_hub_config_flow_creates_single_entry(page: Page) -> None:
    """Adding the integration creates the hub entry right away (no form)."""
    page_errors = _collect_page_errors(page)

    page.goto("/config/integrations/dashboard", wait_until="networkidle")
    page.get_by_role("button", name="Add integration").click()
    search = page.get_by_placeholder("Search for a brand name")
    search.wait_for(state="visible")
    search.fill(INTEGRATION_NAME)
    page.get_by_text(INTEGRATION_NAME, exact=True).click()

    # the flow content is slotted light DOM of dialog-data-entry-flow, not inside role=dialog
    dialog = page.locator("dialog-data-entry-flow")
    expect(dialog.get_by_text(CREATED)).to_be_visible(timeout=30000)
    page.screenshot(path=str(SCREENSHOT_DIR / "hub_created.png"), full_page=True)
    dialog.get_by_role("button", name="Finish").click()
    assert not page_errors, page_errors


def test_add_device_form_renders_and_creates_device(page: Page) -> None:
    """The "Add device" subentry form shows translated labels and creates a device."""
    page_errors = _collect_page_errors(page)

    page.goto("/config/integrations/integration/haeo_device_forecast", wait_until="networkidle")
    page.get_by_role("button", name="Add device").click()

    # the flow content is slotted light DOM of dialog-data-entry-flow, not inside role=dialog
    dialog = page.locator("dialog-data-entry-flow")
    expect(dialog.get_by_text("Add device").first).to_be_visible(timeout=15000)
    for label in DEVICE_FORM_LABELS:
        # required fields get a trailing "*"
        expect(dialog.get_by_text(re.compile(rf"^{re.escape(label)}\*?$")).first).to_be_visible()
    page.screenshot(path=str(SCREENSHOT_DIR / "add_device_form.png"), full_page=True)

    dialog.get_by_role("textbox", name=re.compile("^Name")).fill(DEVICE_NAME)
    dialog.get_by_text("Select an entity").click()
    page.get_by_text(E2E_POWER_SENSOR_NAME).last.click()
    expect(dialog.get_by_text(E2E_POWER_SENSOR_NAME).first).to_be_visible()
    dialog.get_by_role("button", name="Submit").click()

    expect(dialog.get_by_text(CREATED)).to_be_visible(timeout=30000)
    page.screenshot(path=str(SCREENSHOT_DIR / "device_created.png"), full_page=True)
    dialog.get_by_role("button", name="Finish").click()

    page.goto("/config/integrations/integration/haeo_device_forecast", wait_until="networkidle")
    expect(page.get_by_text(DEVICE_NAME).first).to_be_visible(timeout=15000)
    assert not page_errors, page_errors

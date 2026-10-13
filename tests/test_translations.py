"""Guards against the class of UI bugs that only show up when HA renders text.

These bugs (unescaped literal braces breaking the frontend's ICU placeholder
substitution, markdown syntax showing up as literal asterisks/backticks where
the frontend renders plain text, translation files drifting out of sync, a
translation key used in code but missing from the JSON) otherwise only show up
by installing the integration into a running Home Assistant and looking at it.
They don't need a browser: HA's own translation loader renders the same
flattened strings the frontend receives, and static checks on the JSON catch
the rest.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Any

import pytest
import voluptuous as vol
import yaml
from homeassistant.core import HomeAssistant
from homeassistant.helpers import translation

from custom_components.haeo_device_forecast import button, sensor
from custom_components.haeo_device_forecast.config_flow import (
    _DEVICE_SCHEMA,
    HaeoDeviceForecastConfigFlow,
)
from custom_components.haeo_device_forecast.const import DOMAIN

COMPONENT_DIR = Path("custom_components/haeo_device_forecast")
TRANSLATION_FILES = ["strings.json", "translations/en.json", "translations/de.json"]

# Placeholders the config flow substitutes into strings (description_placeholders=...).
# None today - any {argument} in the JSON would render as a broken placeholder.
KNOWN_PLACEHOLDERS: set[str] = set()

# Markdown that HA's frontend does NOT render in a section's own name/description - it shows
# these characters literally instead of formatting them.
_MARKDOWN_PATTERNS = [
    re.compile(r"\*\*[^*]+\*\*"),  # **bold**
    re.compile(r"`[^`]+`"),  # `code`
    re.compile(r"\[[^\]]+\]\([^)]+\)"),  # [text](link)
    re.compile(r"^#{1,6}\s", re.MULTILINE),  # # heading
    re.compile(r"^[-*]\s", re.MULTILINE),  # - bullet / * bullet
]
_SECTION_HEADER_PATH = re.compile(r"\.sections\.[^.]+\.(name|description)$")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _walk_strings(data: Any, path: str = "") -> list[tuple[str, str]]:
    """Flatten a strings/translations JSON tree to (path, value) for every leaf string."""
    results: list[tuple[str, str]] = []
    if isinstance(data, dict):
        for key, value in data.items():
            results.extend(_walk_strings(value, f"{path}.{key}" if path else key))
    elif isinstance(data, str):
        results.append((path, data))
    return results


def _icu_argument_names(text: str) -> list[str]:
    """Parse ``text`` as ICU MessageFormat and return the argument names found.

    Raises AssertionError with a descriptive message on malformed syntax.
    '{' and '}' are argument syntax unless inside a quoted literal span. A
    quoted span is opened by an apostrophe immediately followed by '{', '}',
    '#' or another apostrophe, and runs until the next apostrophe; a doubled
    apostrophe ('') is a literal apostrophe. A bare apostrophe not followed by
    a special character (e.g. "integration's") is just literal text.
    """
    names: list[str] = []
    in_quote = False
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == "'":
            if i + 1 < n and text[i + 1] == "'":
                i += 2
                continue
            if in_quote:
                in_quote = False
                i += 1
                continue
            if i + 1 < n and text[i + 1] in "{}#":
                in_quote = True
            i += 1
            continue
        if in_quote:
            i += 1
            continue
        if ch == "{":
            end = text.find("}", i + 1)
            nested = text.find("{", i + 1)
            if end == -1:
                raise AssertionError(f"unterminated '{{' (no matching '}}') in {text!r}")
            if nested != -1 and nested < end:
                raise AssertionError(
                    f"unescaped '{{' inside an argument at position {nested} in {text!r} - "
                    f"wrap literal braces in a quoted span (e.g. \"'{{...}}'\")"
                )
            arg_name = text[i + 1 : end].strip()
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", arg_name):
                raise AssertionError(f"malformed argument '{{{arg_name}}}' in {text!r}")
            names.append(arg_name)
            i = end + 1
            continue
        if ch == "}":
            raise AssertionError(f"stray '}}' with no matching '{{' in {text!r}")
        i += 1
    if in_quote:
        raise AssertionError(f"unterminated quoted literal (missing closing ') in {text!r}")
    return names


@pytest.fixture(scope="module")
def strings_json() -> dict[str, Any]:
    return _load_json(COMPONENT_DIR / "strings.json")


@pytest.fixture(scope="module")
def en_json() -> dict[str, Any]:
    return _load_json(COMPONENT_DIR / "translations" / "en.json")


@pytest.fixture(scope="module")
def de_json() -> dict[str, Any]:
    return _load_json(COMPONENT_DIR / "translations" / "de.json")


def test_en_translation_mirrors_strings_json(
    strings_json: dict[str, Any], en_json: dict[str, Any]
) -> None:
    """translations/en.json must stay identical to strings.json (the source of truth)."""
    assert en_json == strings_json


def test_de_translation_has_same_keys_as_en(
    en_json: dict[str, Any], de_json: dict[str, Any]
) -> None:
    """de.json must define exactly the keys of en.json - otherwise HA falls back to English."""
    en_keys = {path for path, _ in _walk_strings(en_json)}
    de_keys = {path for path, _ in _walk_strings(de_json)}
    assert en_keys == de_keys, (
        f"missing in de.json: {en_keys - de_keys}\nextra in de.json: {de_keys - en_keys}"
    )


@pytest.mark.parametrize("filename", TRANSLATION_FILES)
def test_icu_message_syntax_is_valid(filename: str) -> None:
    """Every string must be well-formed ICU MessageFormat and use only known placeholders.

    A literal '{'/'}' that isn't wrapped in a quoted span makes the whole string fail to
    parse on the frontend ("malformed argument"), whether or not it ever gets placeholders.
    """
    for path, text in _walk_strings(_load_json(COMPONENT_DIR / filename)):
        try:
            names = _icu_argument_names(text)
        except AssertionError as err:
            pytest.fail(f"{filename}:{path}: {err}")
        for name in names:
            assert name in KNOWN_PLACEHOLDERS, (
                f"{filename}:{path}: argument {{{name}}} is never supplied by the code "
                f"(known: {KNOWN_PLACEHOLDERS})"
            )


@pytest.mark.parametrize("filename", TRANSLATION_FILES)
def test_no_markdown_in_section_headers(filename: str) -> None:
    """A section's own name/description renders as plain text - markdown shows up literally."""
    for path, text in _walk_strings(_load_json(COMPONENT_DIR / filename)):
        if _SECTION_HEADER_PATH.search(path):
            for pattern in _MARKDOWN_PATTERNS:
                assert not pattern.search(text), (
                    f"{filename}:{path}: looks like markdown ({pattern.pattern}), but section "
                    f"headers render as plain text. Value: {text!r}"
                )


def test_subentry_flow_fields_have_labels(strings_json: dict[str, Any]) -> None:
    """Every field of the device form needs a label in both subentry steps."""
    subentry_types = HaeoDeviceForecastConfigFlow.async_get_supported_subentry_types(None)
    fields = {str(key) for key in _DEVICE_SCHEMA.schema if isinstance(key, vol.Marker)}
    for subentry_type in subentry_types:
        subentry = strings_json["config_subentries"][subentry_type]
        assert subentry.get("entry_type")
        for step_id in ("user", "reconfigure"):
            assert subentry["initiate_flow"].get(step_id), f"initiate_flow.{step_id} missing"
            step = subentry["step"][step_id]
            assert step.get("title")
            assert set(step["data"]) == fields, (
                f"config_subentries.{subentry_type}.step.{step_id}.data: "
                f"missing {fields - set(step['data'])}, extra {set(step['data']) - fields}"
            )


def _entity_translation_keys(module: Any) -> dict[str, list[str]]:
    """Map each entity class's ``_attr_translation_key`` to its ``_attr_options`` (enum states).

    Read from the source: HA's entity metaclass turns ``_attr_*`` class attributes into
    cached properties, so their values are not available on the class object itself.
    """
    tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
    keys: dict[str, list[str]] = {}
    for cls in (node for node in tree.body if isinstance(node, ast.ClassDef)):
        attrs: dict[str, Any] = {}
        for stmt in cls.body:
            if isinstance(stmt, ast.Assign) and isinstance(stmt.targets[0], ast.Name):
                attrs[stmt.targets[0].id] = stmt.value
            elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                attrs[stmt.target.id] = stmt.value
        if "_attr_translation_key" in attrs:
            options = attrs.get("_attr_options")
            keys[ast.literal_eval(attrs["_attr_translation_key"])] = (
                ast.literal_eval(options) if options is not None else []
            )
    return keys


def test_entity_translation_keys_exist(strings_json: dict[str, Any]) -> None:
    """Every entity translation_key (and enum state) used in code has a name in strings.json."""
    for platform, module in (("sensor", sensor), ("button", button)):
        keys = _entity_translation_keys(module)
        assert keys, f"no {platform} entities with a translation_key found"
        assert set(keys) == set(strings_json["entity"][platform]), platform
        for key, options in keys.items():
            entry = strings_json["entity"][platform][key]
            assert entry.get("name"), f"entity.{platform}.{key}.name missing"
            for option in options:
                assert entry.get("state", {}).get(option), (
                    f"entity.{platform}.{key}.state.{option} missing"
                )


def test_services_have_translations(strings_json: dict[str, Any]) -> None:
    """Every service and field in services.yaml has a name/description in strings.json."""
    services = yaml.safe_load((COMPONENT_DIR / "services.yaml").read_text(encoding="utf-8"))
    assert set(services) == set(strings_json["services"])
    for service, definition in services.items():
        texts = strings_json["services"][service]
        assert texts.get("name") and texts.get("description"), service
        for field in definition.get("fields", {}):
            assert texts["fields"][field].get("name"), f"{service}.{field}.name missing"
            assert texts["fields"][field].get("description"), (
                f"{service}.{field}.description missing"
            )


async def test_ha_translation_loader_renders_strings(hass: HomeAssistant) -> None:
    """Load translations exactly the way HA's frontend does, in both languages."""
    prefix = f"component.{DOMAIN}"
    expected = {
        "en": {
            ("config", "config.step.user.title"): "Set up HAEO Device Forecast",
            ("config_subentries", "config_subentries.device.initiate_flow.user"): "Add device",
            ("entity", "entity.sensor.status.state.running"): "Running",
            ("services", "services.search_profiles.name"): "Search for new profiles",
        },
        "de": {
            ("config", "config.step.user.title"): "HAEO Device Forecast einrichten",
            ("config_subentries", "config_subentries.device.initiate_flow.user"): (
                "Gerät hinzufügen"
            ),
            ("entity", "entity.sensor.status.state.running"): "Läuft",
            ("services", "services.search_profiles.name"): "Nach neuen Profilen suchen",
        },
    }
    for language, cases in expected.items():
        for (category, key), value in cases.items():
            translations = await translation.async_get_translations(
                hass, language, category, integrations={DOMAIN}
            )
            assert translations.get(f"{prefix}.{key}") == value, (language, key, translations)

# HAEO Device Forecast

Home Assistant custom integration (`custom_components/haeo_device_forecast`), distributed via HACS.
Learns load profiles of rarely used appliances from a power sensor and publishes a 5-minute
forecast (`forecast` attribute) for HAEO.

## Rules

- **Docs are bilingual.** README, `examples/`, and other user-facing docs are always updated in
  German and English in the same change. Root README: English first, German section at the end.
  Examples: `examples/en/` and `examples/de/`. Exceptions: the README developer section and
  `docs/REQUIREMENTS.md` (German only).
- **`docs/REQUIREMENTS.md` is the spec.** Read it before behavior changes; update it together
  with the code. Keep functional requirements (what) separate from technical aspects (how).
  Code docstrings cite its sections by heading (e.g. "Analyse von Lastprofilen") - keep the
  headings stable or update the citations. Mark unimplemented items "Status: noch nicht umgesetzt".
- **Conventional Commits** (`feat`, `fix`, `docs`, `chore`, `ci`, `test`; `feat!` for breaking).
  They drive semantic-release. Never hand-edit the version, `CHANGELOG.md`, or make
  `chore(release)` commits - CI does that. Do not commit/push unless asked.
- **Tests:** run `python -m pytest` (never bare `pytest`). UI changes to the config/subentry flow
  also need a case in `tests_e2e/` (real browser); run with `pip install -r requirements_e2e.txt`,
  `python -m playwright install --with-deps chromium`, `python -m pytest tests_e2e`.
  The Windows host has no Python - run tests in the devcontainer or a `python:3.14` container.
- **Translations:** `strings.json`, `translations/en.json`, `translations/de.json` stay in sync
  (`tests/test_translations.py` enforces it). They are ICU MessageFormat - escape literal `{`/`}`
  with `'...'` quoting, not doubling.
- **Robustness:** errors in user input are validated in the flow with localized field errors
  and must never crash the integration or HA (log, keep the last good state).
- Pinned `homeassistant` version in `requirements_test.txt` dictates the minimum Python version
  (CI + devcontainer); `requirements_e2e.txt` pins must match it. `hacs.json` holds the minimum
  HA version users need (config subentries).

## Layout

- `custom_components/haeo_device_forecast/` - integration: one hub config entry, one config
  subentry per device (`config_flow.py`); `coordinator.py` live tracking; `analysis/`
  segmentation/banding/clustering/DTW/forecast; `storage/` per-device `.storage` files;
  `history/` recorder access; `services.py` profile management
- `tests/` - mocked unit/flow tests; `tests_e2e/` - real HA + Playwright
- `docs/REQUIREMENTS.md` - requirements spec
- `examples/{en,de}/` - documented examples
- `.github/` - workflows (test, test-e2e, release with test gate), PR template (bilingual)
- `.devcontainer/` + `scripts/develop` - dev container with a local HA instance on port 8123

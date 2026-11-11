# Contributing

This page is for people who work on the IronLogic integration itself.
If you only want to use it, start with the README.

## Where things live

- `custom_components/ironlogic/`: the integration.
- `tests/`: Python tests for the key logic. They do not need Home Assistant.
- `.github/workflows/`: CI (tests, version check, release).
- `CHANGELOG.md`: the source of truth for release notes.

## Branches

- `main` is the release branch. It only takes merges from `dev`.
- `dev` is where work happens. Push here, let CI run, test on a real controller, then open a PR to `main`.
- Never delete `dev`.

## Before you open a PR

Run locally:

```bash
pytest tests/ -v
```


Check that `version` in `manifest.json`, `hacs.json`, and the section in `CHANGELOG.md` all match. CI runs the same checks, plus `hassfest` and HACS validation.

## Versioning

This project follows Semantic Versioning, with one addition for this repository:

- **PATCH** (`1.3.x`): bug fixes, and improvements to an existing feature that do not add a new entity, service, or options step. Example: key number normalization, short key display, name in a sensor.
- **MINOR** (`1.x.0`): a new entity, a new service, a new step in options flow, or a behaviour change users can notice. Example: allowed keys management, key synchronization.
- **MAJOR** (`x.0.0`): a breaking change. Example: removing an entity, changing the storage format, renaming a service.

If a release has both `Added` and `Fixed` in `CHANGELOG.md`, and the `Added` entries are improvements to an existing feature, PATCH is acceptable. If they are genuinely new features, use MINOR.

## Releases

1. In `dev`, update `CHANGELOG.md`: turn `## [Unreleased]` into `## [X.Y.Z] - YYYY-MM-DD`, and add a new empty `## [Unreleased]` above it.
2. Bump `version` in `custom_components/ironlogic/manifest.json` and `hacs.json` to the same `X.Y.Z`.
3. Push `dev`, let CI pass.
4. Open a PR from `dev` to `main`, merge it.
5. Go to **Actions → Release → Run workflow**, enter `X.Y.Z`.
6. The workflow creates the tag, extracts the `CHANGELOG.md` section, and opens a draft release. Review it and publish.

## Local testing on a real controller

CI cannot check how the controller behaves. Before you merge `dev` into `main`, copy the integration to your Home Assistant instance, reload it, and check at least:

- A key added in Home Assistant reaches the controller.
- A key removed in Home Assistant disappears from the controller.
- The controller still opens the door after Home Assistant is stopped (autonomous mode).
- Events (key granted, door open/close) appear in Home Assistant.

If you use a script to copy files, put it in `.gitignore` and document the path in this file.

## Language

Code, comments, commit messages, and documentation are in English.
Russian is allowed only in `README_ru.md`, `ru.json`, and user-facing translations.
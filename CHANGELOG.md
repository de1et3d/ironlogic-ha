# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.4.0] - 2026-11-11

### Added

- Key number normalization: input up to 12 hex characters is padded with leading zeros (Wiegand short form), input longer than 12 characters is rejected with a clear error
- Short key display in sensors and options flow (last 6 hex characters), full key number is kept internally and in CSV export
- Key name shown instead of key number in `Last key` and `Last event` sensors when available

### Fixed

- Key add/remove commands not reaching the controller when sent from options flow and services (`ws_server` → `ws_handler`)
- `NameError` in `power_on` handling for `CONF_SN`/`CONF_MODEL` in WebSocket mode
- Missing `increment_keys_version()` call after CSV import, so the controller didn't re-sync
- Missing `import json` in sensor module causing failure on string-formatted keys

## [1.3.1] - 2026-11-10

### Changed

- Key input normalization: leading zeros added automatically
- Short key display (last 6 hex characters) in sensors and options flow
- Key name shown instead of key number in `Last key` and `Last event` sensors when available

## [1.3.0] - 2026-11-09

### Added

- Support for allowed keys with access control via `check_access`
- Key synchronization to controller on `power_on`
- Instant key sync when adding or removing keys through options flow
- Master key type in allowed keys with iButton-only warning
- `Allowed keys` sensor with full key list in attributes
- Automatic keys backup to `/config/ironlogic_keys_backup.json` on unload and removal
- Options flow wizard for managing allowed keys

### Changed

- Export keys file operations moved to executor to avoid blocking the event loop

### Fixed

- `check_access` not handled in WebSocket mode
- `ClientConnectionResetError` on closed WebSocket
- Door sensor availability and reload behavior

## [1.2.1] - 2026-10-06

### Fixed

- Patch release (details not recorded)

## [1.2.0] - 2026-10-06

### Added

- Support for WebSocket
- Option to export keys
- Updated README
- Added HACS metadata

## [1.0.1] - 2026-03-27

### Fixed

- Patch release (details not recorded)

## [1.0.0] - 2026-03-27

### Added

- Initial release
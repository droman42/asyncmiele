# Changelog

## [0.2.0] – YYYY-MM-DD
### Added
* Encrypted PUT capability and generic `_put_request()`.
* `wake_up`, `remote_start`, `can_remote_start` helpers.
* Global config flag `enable_remote_start` with safety gate.
* Minimal `asyncmiele.enums` module and automatic Enum casting in `DeviceState`.
* Convenience examples `examples/wake_up.py` and `examples/remote_start.py`.
* Expanded README with wake-up and remote-start documentation.

### Changed
* Refactored shared auth header generation (`build_auth_header`).

### Removed
* N/A 
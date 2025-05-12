# AsyncMiele – Implementation Plan

## Goal
Add **optional** local‐network device-control features (wake-up & remote-start) and the plumbing (signed AES-encrypted PUT requests) they rely on, while preserving the library's core principles:

* 100 % asynchronous, type-annotated API
* MIT-licensed (clean-room re-implementation of GPL sources)
* Fail-safe by default – remote-start only when the user explicitly opts-in
* Extensible foundation for future DOP2 read/write support

The work is broken into self-contained phases so we can pause/resume in future sessions with minimal context loss.

---

## Phase 0 – Preparation & Scaffolding
1.  Create feature branch `feat/put-requests-remote-start`.
2.  Add `docs/` entry (this file) to track progress & decisions.
3.  Define **coding-style** rules for new crypto helpers (same Black/ruff settings).

Outcome: planning artefacts committed; no functional change.

---

## Phase 1 – Refactor Crypto Helpers (GET & PUT shared) ✅ Completed
**Motivation:**  Current `_get_request()` reproduces the signing logic inline; we need it reusable.

Steps
1.  Move signature & IV derivation to `asyncmiele.utils.crypto`:
    * `build_auth_header(method, host, resource, date, body, group_id, group_key) -> str, iv:bytes`.
2.  Add unit tests with known vectors (use captured traffic or golden values).
3.  Refactor `_get_request()` to call new helper (should be no behaviour change).

Outcome: deterministic helper covering GET & future PUT.

---

## Phase 2 – Implement `_put_request()` ✅ Completed
1.  Private async method mirroring `_get_request()` but accepting `body: bytes | dict | None`.
2.  Steps performed:
    * Serialize body (JSON) **before** signing.
    * Pad & encrypt with AES-CBC (blocksize 16) using IV from auth header.
    * Send via `aiohttp` with identical headers / timeout handling.
    * Accept 200 or 204 as success; decrypt response if non-empty.
3.  Unit tests using `aresponses` mocking to validate header format & encryption length.

Outcome: generic signed/encrypted PUT capability.

---

## Phase 3 – Public Wake-Up Helper ✅ Completed
1.  Add `async def wake_up(self, device_id: str) -> None` to `MieleClient`.
2.  Implementation: `_put_request(f"/Devices/{quote(device_id)}/State", {"DeviceAction": 2})`.
3.  Raises `ResponseError` on non-2xx.
4.  Update README with simple example.

Outcome: Users can wake sleeping appliances.

---

## Phase 4 – Remote-Start Helper (OPT-IN) ✅ Completed
1.  Add library-level feature flag:
    ```python
    from asyncmiele.config import settings  # simple dataclass w/ global flags
    settings.enable_remote_start = False  # default
    ```
    (or pass `allow_remote_start=True` per call – TBD during implementation)
2.  Add `async def remote_start(self, device_id: str) -> None`.
3.  Guard clause: if flag disabled → raise `PermissionError("Remote start disabled – see docs")`.
4.  PUT to `/Devices/<id>/State` with body `{ "ProcessAction": 1 }`.
5.  Provide helper `async def can_remote_start(self, device_id) -> bool` (GET summary, check `Status==0x04` & `15 in RemoteEnable`).
6.  Unit tests covering both enabled/disabled scenarios.

Outcome: Remote-start available only when explicitly enabled.

---

## Phase 5 – Minimal Enum Module ✅ Completed
1.  Introduce `asyncmiele.enums` with small sets: `Status`, `ProgramPhase`, `ProgramId`, `DeviceType`.
2.  Auto-convert when building `DeviceState` but keep raw int fallback.
3.  Document mapping completeness & contribution guideline.

Outcome: Human-readable status without magic numbers.

---

## Phase 6 – Documentation & Examples ✅ Completed
1.  README:
    * **Activation** instructions (code snippet to enable flag or call kw-arg).
    * Warning box about safety & liability.
2.  New example scripts in `examples/remote_start.py` & `examples/wake_up.py`.
3.  API reference (doc-strings) updated.

Outcome: Clear, discoverable usage guidance.

---

## Phase 7 – Release Tasks
1.  Bump version `x.y.0 → x.(y+1).0`.
2.  Update `CHANGELOG.md`.
3.  Ensure all tests/pass.

---

## Phase 8 – DOP2 Foundation (Raw Access)
**Objective:** expose low-level DOP2 read/write without any heavy parsing so power-users and external tools can experiment immediately.

Steps
1.  Build helper `_build_dop2_path(device_id, unit, attribute, idx1, idx2)` → string.
2.  Add `async def dop2_read_leaf(self, device_id, unit, attribute, *, idx1: int = 0, idx2: int = 0) -> bytes`.
3.  Add `async def dop2_write_leaf(self, …, payload: bytes)` (returns `None`).
4.  Both use `_get_request()` / `_put_request()` **without** JSON body (payload is raw bytes).
5.  Provide padding utility `pad_payload(payload: bytes, blocksize=16)` in `utils.crypto`.
6.  Add doctest in doc-string and integration test with mocked response.
7.  Flag these APIs as *experimental* in docs.

Outcome: Users can poke any DOP2 leaf; foundation reused by higher-level decoders.

---

## Phase 9 – Structured DOP2 Decoder (Core Annotators)
**Objective:** parse a subset of frequently useful leaves into pydantic models for ergonomic consumption.

Steps
1.  Create `asyncmiele.dop2.parser` module containing:
    * `AttributeDecoder` registry (clean-room re-implementation).
    * Minimal value classes (Bool, Int, String, Array, Struct).
2.  Implement decoder for leaf `DeviceState` (`unit 2 / attribute 256`).
3.  Implement decoder for leaf `SF_Value` (`unit 2 / attribute 105`).
4.  Public API: `await client.dop2_get_parsed(device_id, unit, attribute, model_cls)` returning instance of supplied model.
5.  Unit tests with captured binary fixtures committed under `tests/fixtures`.
6.  Extend docs with mapping table (leaf → model).

Outcome: Consumers get Pythonic objects without touching bytes.

---

## Phase 10 – Device Settings Helper (SF Values)
**Objective:** expose high-level getters / setters for common settings (language, buzzer, water hardness, …).

Steps
1.  Add model `SFValue` (id, current, min, max, default, etc.).
2.  Helper methods:
    * `async def get_setting(self, device_id, sf_id: int | SfEnum) -> SFValue`.
    * `async def set_setting(self, …, new_value: Any)` (validates bounds).
3.  Requires writing correct payload – reuse Phase 9 struct encoder.
4.  Write extensive tests against emulator / dummy.

Outcome: Safe manipulation of settings through simple API.

---

## Phase 11 – Summary Helper & Progress Calculation
1.  Combine `/Devices/<id>/Ident` + `/State` + `dop2_get_parsed(DeviceState)`.
2.  Compute: elapsed / remaining minutes, progress %, remote-start capability, friendly enums.
3.  Expose as `async def get_summary(self, device_id) -> DeviceSummary` (pydantic).
4.  Use in README examples.

Outcome: One-stop high-level status snapshot for UI integrations.

---

## Phase 12 – Advanced DOP2 (Future Work)
* Firmware file upload (`FileWrite` leaves).
* SuperVision list management.
* OTA update monitoring.

These are out of current scope; revisit after real-world demand.

---

## Optional Phase 13 – Enum & Icon Import from *pymiele*
*Status: optional – requires re-confirming upstream repository state before execution.*

Context
:  The MIT-licensed `const.py` (or similar) tables in [pymiele](https://github.com/nordicopen/pymiele) already map raw numeric codes to human-readable names, icons, and units.  Re-using them (via JSON resources, **not** cloud calls) will enrich our `asyncmiele.enums` and improve UI integrations.

Steps
1.  **Pre-work:** re-scan the latest *pymiele* repository for changed file names/structure.
2.  Write a one-off converter script (`scripts/extract_pymiele_consts.py`) that parses the tables and emits `resources/enums.json` & `resources/icon_map.json`.
3.  Generate Enum classes automatically at build time or commit generated code (decision during phase start).
4.  Unit test round-trip (int ↔ enum ↔ int).
5.  Extend docs: contribution guideline for keeping mappings in sync.

Outcome: richer Enum coverage and icon meta-data, still offline.

---

## Optional Phase 14 – Static Program Catalogue & Option Builder
*Depends on Phase 13; again re-scan *pymiele* before starting.*

Context
:  *pymiele* bundles JSON catalogues describing every selectable program per device.  Locally we can ship the same catalogues and translate chosen program & options into the correct DOP2 `PS_SELECT` payload.

Steps
1.  Import/clean the `programs/*.json` directory; normalise schema (MIT licence).
2.  Add `Program`, `Option`, `ProgramCatalog` pydantic models.
3.  Implement `ProgramCatalog.for_device(device_ident)` → returns list of programs.
4.  Implement `build_dop2_selection(program, chosen_options)` → bytes for Phase 10 encoder.
5.  Provide example script `examples/select_program.py`.

Outcome: users can enumerate and prepare programs offline; execution still travels via local DOP2 write.

---

## Optional Phase 15 – Consumption & Statistics Models
*Requires Phases 9 & 14.*

Context
:  DOP2 leaves already expose hours-of-operation, cycle counters, energy/water totals.  *pymiele*’s models and calculations (cost estimate) are cloud-agnostic and can be reused.

Steps
1.  Decode leaves `2/119`, `2/138`, others into `ConsumptionStats` model.
2.  Mirror *pymiele*’s cost calculation helper but drive it with user-supplied tariff config.
3.  Unit tests with fixture binaries and golden outputs.

Outcome: feature parity with cloud integration for statistics dashboards.

---

## Optional Phase 16 – Event Dispatcher / Subscription API

Context
:  *pymiele* implements a callback dispatcher that minimises traffic and delivers per-property change events to Home-Assistant.  We can replicate that logic for local polling.

Steps
1.  Design `SubscriptionManager` (async task creating `asyncio.sleep(interval)` loop).
2.  Use diffs of `DeviceSummary` to fire events.
3.  Provide decorators / context-manager helpers.
4.  Document caveats (still polling; device sleep modes; recommend ≥30 s interval).

Outcome: cleaner integration for reactive frameworks (HA, FastAPI websockets, etc.).

---

> **Self-Reminder:** Before starting any optional phase, run a fresh scan of `https://github.com/nordicopen/pymiele` to capture new files or schema changes, and verify licence/ownership of any data being imported.

---

## References & Compatibility Notes
* Remote-start & wake-up message bodies observed in MieleRESTServer (`{"ProcessAction":1}` / `{ "DeviceAction":2 }`).
* Devices often answer **204 No Content**; caller should treat 200/204 same.
* GPL code served only as protocol reference – all implementations here are new.
* Remote-start may require device to be fully programmed and `RemoteEnable` flag present; helper `can_remote_start()` checks this.

---

*Last updated:* <!-- keep this line for quick diff --> 
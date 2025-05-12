# AsyncMiele – Code-base Improvement Roadmap

This document groups the post-v0.2.0 refactor & convenience work into **four self-contained phases**.  Each phase can be released on its own and should not change observable on-wire behaviour.

> Scope note: *The tasks below are limited to the core library.  Tests, examples and CI changes are implied but not listed repeatedly.*

---

## Phase 1 – HTTP Core Refactor & Persistent Session ✅ Completed

Goal: remove duplicated request plumbing while enabling connection reuse.

Tasks
1. **Consolidate request flow**  
   • Add private coroutine `MieleClient._request_bytes(method, resource, *, body: bytes = b"", content_type: str = "")` that performs signing, header assembly, (optionally) encryption/decryption and returns the raw **decrypted** bytes.  
   • Refactor `_get_request`, `_get_raw`, `_put_request` to delegate to the helper.
2. **Persistent `aiohttp.ClientSession`**  
   • Add `self._session: Optional[aiohttp.ClientSession]` and create it lazily.  
   • Implement `async def __aenter__/__aexit__` to open/close the session, leaving the existing constructor unchanged for backwards-compatibility.
3. **Header constants**  
   • Move duplicated literals (`Accept`, `User-Agent`, content-type) to `asyncmiele.utils.http_consts` and import them from a single place.

Outcome: single code path for all requests, reduced TCP overhead, easier future maintenance.

---

## Phase 2 – Code Clean-Up & Naming Consistency ✅ Completed

Goal: eliminate dead code, shadowing names and linter warnings.

Tasks
1. **Remove deprecated helpers**  
   • Delete `utils.crypto.create_signature` (superseded by `build_auth_header`).
2. **Exception renaming**  
   • Introduce `NetworkConnectionError`, `NetworkTimeoutError` in `exceptions.network` and re-export the old names with `DeprecationWarning` (grace period ≥ one minor release).
3. **Crypto helper symmetry**  
   • Add `decrypt_and_unpad()` complementing `encrypt_payload`/`pad_payload`; use in `utils.crypto.decrypt_response` & the new core request helper.
4. **Dependency specification**  
   • Add `pydantic>=2.0` to `pyproject.toml` / `requirements.txt` and ensure it is imported with version guard.
5. **Misc. lint**  
   • Remove unused `aiohttp` import in `utils.discovery`, ensure file/var names match Black & ruff rules.

Outcome: cleaner public surface, zero obvious duplications, green static-analysis.

---

## Phase 3 – Convenience API Layer ✅ Completed

Goal: make common user flows one-liners without sacrificing low-level power.

Tasks
1. **Hex-string constructor & context helper**  
   • `@classmethod MieleClient.from_hex(host, group_id_hex: str, group_key_hex: str, **kw)` returning a ready client.  
   • Include the async-context support from Phase 1.
2. **Device proxy object**  
   • `class Appliance` exposed via `await client.device(<id>)`.  
   • Methods: `wake_up()`, `remote_start()`, `set_setting()`, `start_program(program_name, **options)` etc., internally using existing helpers.
3. **Batch helpers**  
   • `get_all_summaries()` returning `Dict[id, DeviceSummary]` in one await.
4. **Enum friendly properties**  
   • Add `status_name`, `program_phase_name` properties to `DeviceState` using `enums.status_name()` etc.
5. **Discovery shortcut**  
   • `utils.discovery.auto_clients(group_id_hex, group_key_hex, *, timeout=…) -> List[MieleClient]`.

Outcome: scripts shrink to a handful of readable lines; no breaking changes for existing callers.

---

## Phase 4 – Consumption & Monitoring Enhancements ✅ Completed

Goal: extend statistics & monitoring ergonomics built on top of existing Phase 15 groundwork.

Tasks
1. **Monthly/weekly delta helpers**  
   • `get_consumption_delta(device_id, *, since: datetime) -> ConsumptionStats` using two reads + local diff.
2. **Tariff-aware cost utilities**  
   • `get_monthly_cost(device_id, tariff_cfg)` returning float & `Currency` enum placeholder.
3. **SubscriptionManager improvements**  
   • Add `on_error(callback)` or `logger` injection to surface callback exceptions.
4. **Prometheus exporter skeleton** (stretch)  
   • Provide an example `asyncmiele.exporters.prometheus` module demonstrating how to feed metrics—purely optional, no direct runtime dependency.

Outcome: richer data for dashboards and cost calculations while keeping this phase skippable for minimal installations.

---

## Phase 5 – Documentation Refresh (README & Examples) ✅ Completed

Goal: ensure first-time users immediately benefit from the new convenience layer and refactor.

Tasks
1. **README overhaul**  
   • Update architecture diagram to include *Persistent Session* and *Appliance proxy*.  
   • Replace legacy setup snippet with the new *hex-string constructor* + async-context example.  
   • Show one-liner remote-start using the appliance proxy (`await washer.start_program(...)`).
2. **Feature table**  
   • Add section listing high-level helpers (wake_up, remote_start, get_all_summaries, cost estimation).  
   • Mark experimental/optional APIs (Phase 4 exporters) accordingly.
3. **Examples synchronisation**  
   • Rewrite `examples/remote_start.py`, `examples/wake_up.py`, `examples/monitor.py` to use the convenience layer.  
   • Add `examples/prometheus_exporter.py` if Phase 4 stretch task is completed.
4. **Deprecation & migration notes**  
   • Describe how existing code using `await client.remote_start(...)` continues to work.  
   • Document the new `DeprecationWarning` for Network*Error renames.
5. **Badges & metadata**  
   • Update README badges (coverage, ruff) after refactor; link to *Code-base Improvement Roadmap*.

Outcome: sales-grade landing page that reflects the modernised API and smooth upgrade path.

---

### Dependency & compatibility notes
* All phases are additive or de-duplicating; no public API is removed outright before the usual deprecation cycle.
* Each phase should bump the minor version (`x.(y+1).0`), update CHANGELOG and docs.

*Last updated: <!-- keep for diff -->* 
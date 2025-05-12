"""High-level appliance proxy introduced in Phase-3.

Provides a device-centric façade wrapping around :class:`asyncmiele.api.client.MieleClient`.
"""

from __future__ import annotations

from typing import Dict, Iterable

from asyncmiele.api.client import MieleClient
from asyncmiele.models.summary import DeviceSummary
from asyncmiele.programs import ProgramCatalog, build_dop2_selection

__all__: Iterable[str] = ["Appliance"]


class Appliance:
    """Proxy bound to a single device ID for concise interactions."""

    def __init__(self, client: MieleClient, device_id: str) -> None:  # noqa: D401
        self._client = client
        self.id = device_id

    # ------------------------------------------------------------------
    # Delegating helpers

    async def wake_up(self) -> None:
        """Wake a sleeping appliance."""
        await self._client.wake_up(self.id)

    async def remote_start(self, *, allow_remote_start: bool | None = None) -> None:
        """Start the currently prepared program (delegates to client)."""
        await self._client.remote_start(self.id, allow_remote_start=allow_remote_start)

    async def set_setting(self, sf_id: int, value: int) -> None:
        """Write a *Simple Feature* value via leaf 2/105."""
        await self._client.set_setting(self.id, sf_id, value)

    async def start_program(self, program_name: str, options: Dict[int, int] | None = None) -> None:
        """Select *program_name* with *options* and start execution.

        Steps
        -----
        1. Resolve program info through `ProgramCatalog`.
        2. Build selection payload and write to PS_SELECT (unit 2/attr 300).
        3. Trigger `remote_start()`.
        """
        ident = await self._client.get_device_ident(self.id)
        catalog = ProgramCatalog.for_device(ident)

        try:
            program = catalog.programs_by_name[program_name]
        except KeyError as exc:
            raise ValueError(
                f"Unknown program '{program_name}' for device type '{catalog.device_type}'"
            ) from exc

        payload = build_dop2_selection(program, options)
        await self._client.dop2_write_leaf(self.id, 2, 300, payload)
        await self.remote_start(allow_remote_start=True)

    # ------------------------------------------------------------------
    # Introspection helpers

    async def summary(self) -> DeviceSummary:
        """Return a fresh :class:`DeviceSummary` snapshot for this appliance."""
        return await self._client.get_summary(self.id)

    # ------------------------------------------------------------------
    # Async context passthrough (does not manage connection itself)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):  # noqa: D401
        return False

    # ------------------------------------------------------------------
    # Status helpers

    async def can_remote_start(self) -> bool:
        """Return True if the appliance is ready & allows remote start."""
        return await self._client.can_remote_start(self.id) 
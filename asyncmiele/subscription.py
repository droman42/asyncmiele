"""Event-dispatcher / subscription helper (Phase-16).

This is a lightweight polling loop that periodically fetches `DeviceSummary`
objects and notifies registered callbacks when *anything* in the summary
changes.

Usage::

    client = MieleClient(...)
    sub = SubscriptionManager(client, interval=30)
    
    @sub.on_change("0001")
    async def handle_change(new, old):
        print("Device changed", new.progress)

    await sub.start()
    ...
    await sub.stop()

Alternatively use the async-context form::

    async with SubscriptionManager(client) as sub:
        ...
"""

from __future__ import annotations

import asyncio
from typing import Awaitable, Callable, Dict, List, Optional

from asyncmiele.api.client import MieleClient
from asyncmiele.models.summary import DeviceSummary

# Callback signature: (new_summary, old_summary) -> Awaitable | None
Callback = Callable[[DeviceSummary, Optional[DeviceSummary]], Awaitable[None] | None]


class SubscriptionManager:
    """Poll devices at a fixed interval and dispatch change events.

    Parameters
    ----------
    on_error
        Optional callback invoked with *(exc, device_id)* when a listener raises or a
        fetch fails.  If *None* (default) exceptions are swallowed silently (prev. behaviour).
    """

    def __init__(
        self,
        client: MieleClient,
        *,
        interval: float = 30.0,
        on_error: Callable[[Exception, str], Awaitable[None] | None] | None = None,
    ) -> None:
        self.client = client
        self.interval = interval
        self._on_error = on_error

        self._listeners: Dict[str, List[Callback]] = {}
        self._current: Dict[str, DeviceSummary] = {}

        self._stop_event = asyncio.Event()
        self._task: Optional[asyncio.Task] = None

    # ------------------------------------------------------------------
    # Public API

    def add_listener(self, device_id: str, callback: Callback) -> None:
        """Register *callback* for *device_id* change events."""
        self._listeners.setdefault(device_id, []).append(callback)

    def on_change(self, device_id: str):  # decorator helper
        def decorator(fn: Callback):
            self.add_listener(device_id, fn)
            return fn

        return decorator

    async def start(self) -> None:
        """Start the background polling task (idempotent)."""
        if self._task is None or self._task.done():
            self._stop_event.clear()
            self._task = asyncio.create_task(self._poll_loop(), name="asyncmiele-subscription")

    async def stop(self) -> None:
        """Request graceful stop and wait until background task ends."""
        self._stop_event.set()
        if self._task is not None:
            try:
                await self._task
            finally:
                self._task = None

    # ------------------------------------------------------------------
    # Async-context helpers

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.stop()

    # ------------------------------------------------------------------
    # Internal implementation

    async def _poll_loop(self) -> None:
        """Internal task: loop until `stop_event` is set."""
        while not self._stop_event.is_set():
            await self._poll_once()
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self.interval)
            except asyncio.TimeoutError:
                # timeout means interval elapsed → continue loop
                continue
            except Exception:
                break

    async def _poll_once(self) -> None:
        """Fetch summaries and dispatch diffs."""
        if not self._listeners:
            return  # nothing to do

        for device_id, callbacks in list(self._listeners.items()):
            if not callbacks:
                continue
            try:
                summary = await self.client.get_summary(device_id)
            except Exception as exc:
                # device unreachable etc; skip but keep previous value
                if self._on_error:
                    maybe = self._on_error(exc, device_id)
                    if asyncio.iscoroutine(maybe):
                        await maybe
                continue

            old = self._current.get(device_id)
            if old is not None and summary == old:
                # no change
                continue

            self._current[device_id] = summary

            for cb in callbacks:
                try:
                    result = cb(summary, old)
                    if asyncio.iscoroutine(result):
                        await result
                except Exception as exc:
                    if self._on_error:
                        maybe = self._on_error(exc, device_id)
                        if asyncio.iscoroutine(maybe):
                            await maybe
                    continue 
"""Prometheus exporter skeleton (optional Phase-4 helper).

This module purposefully contains *no external dependencies* – callers feed
DeviceSummary objects and receive plain text exposition format.
"""

from __future__ import annotations

from typing import List

from asyncmiele.models.summary import DeviceSummary

__all__: List[str] = ["metrics_from_summary"]


def _metric_line(name: str, value: float, *, labels: str = "") -> str:
    if labels:
        return f"{name}{{{labels}}} {value}\n"
    return f"{name} {value}\n"


def metrics_from_summary(summary: DeviceSummary) -> str:
    """Return Prometheus metrics string for *summary* (best-effort)."""
    lines: List[str] = []

    device_label = f'id="{summary.id}",name="{summary.name}"'

    if summary.progress is not None:
        lines.append(_metric_line("asyncmiele_progress", summary.progress, labels=device_label))

    if summary.ready_to_start is not None:
        lines.append(
            _metric_line("asyncmiele_ready", 1.0 if summary.ready_to_start else 0.0, labels=device_label)
        )

    # Combined state if available
    if summary.combined_state is not None:
        cs = summary.combined_state
        lines.append(_metric_line("asyncmiele_appliance_state", cs.appliance_state, labels=device_label))
        lines.append(_metric_line("asyncmiele_operation_state", cs.operation_state, labels=device_label))
        lines.append(_metric_line("asyncmiele_process_state", cs.process_state, labels=device_label))

    return "".join(lines) 
from __future__ import annotations

"""Static program catalogue utilities (Phase 14).

This module loads JSON catalogues that describe every selectable program
and its available options for a given device type.  The catalogues are
converted into *pydantic* models so that users get auto-completion and
runtime validation.

Only **offline** resources are used – the JSON files are bundled under
``resources/programs/`` at build time.  No cloud access is necessary.

Example
-------
>>> from asyncmiele.programs import ProgramCatalog, build_dop2_selection
>>> catalog = ProgramCatalog.for_device("WashingMachine")
>>> cottons = catalog.programs_by_name["Cottons"]
>>> payload = build_dop2_selection(cottons, {10: 60, 11: 1600})
>>> payload.hex()
'0001000a003c000b0640'
"""

from pathlib import Path
import json
from typing import List, Mapping, Optional

from pydantic import BaseModel, Field, field_validator

from asyncmiele.utils.crypto import pad_payload

__all__ = [
    "Option",
    "Program",
    "ProgramCatalog",
    "build_dop2_selection",
]

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class Option(BaseModel):
    """Represents a single adjustable option for a program.

    Attributes
    ----------
    id
        Raw numeric option identifier used by the appliance.
    name
        Human-readable identifier (English; can be mapped to translations by
        the consumer).
    default
        Optional default value that will be used when *chosen_options* does
        not contain an entry for this option.
    allowed_values
        Enumerates legal values.  The *builder* does **not** enforce these –
        client code may implement additional validation if desired.
    """

    id: int = Field(..., ge=0, le=0xFFFF)
    name: str
    default: Optional[int] = Field(default=None, ge=0)
    allowed_values: Optional[List[int]] = None

    @field_validator("allowed_values")
    @classmethod
    def _validate_allowed_values(cls, v: Optional[List[int]]) -> Optional[List[int]]:
        if v is not None:
            for val in v:
                if not 0 <= val <= 0xFFFF:
                    raise ValueError("allowed_values items must fit into uint16")
        return v


class Program(BaseModel):
    """Represents an appliance program with its selectable options."""

    id: int = Field(..., ge=0, le=0xFFFF)
    name: str
    options: List[Option] = Field(default_factory=list)

    def option_by_id(self, option_id: int) -> Option:
        try:
            return next(o for o in self.options if o.id == option_id)
        except StopIteration as exc:
            raise KeyError(f"Program has no option with id {option_id}") from exc

    def __repr__(self) -> str:  # pragma: no cover – cosmetic
        return f"Program(id={self.id}, name='{self.name}', options={len(self.options)})"


class ProgramCatalog(BaseModel):
    """Collection of programs supported by a *single* device-type."""

    device_type: str
    programs: List[Program] = Field(default_factory=list)

    # ----------------------------- helpers ----------------------------------

    @property
    def programs_by_name(self) -> Mapping[str, Program]:
        """Return dict mapping *name → Program* (case-sensitive)."""
        return {p.name: p for p in self.programs}

    @property
    def programs_by_id(self) -> Mapping[int, Program]:
        """Return dict mapping *program-id → Program*."""
        return {p.id: p for p in self.programs}

    # ----------------------------- loading ----------------------------------

    _RESOURCE_BASE = Path(__file__).resolve().parent.parent.parent / "resources" / "programs"

    @classmethod
    def _resource_path(cls, device_type: str) -> Path:
        filename = device_type.lower().replace(" ", "_") + ".json"
        return cls._RESOURCE_BASE / filename

    @classmethod
    def for_device(cls, device_ident) -> "ProgramCatalog":
        """Load catalogue for *device_ident* (flexible argument).

        *device_ident* can be:
            • *str*: name such as "WashingMachine" or tech-type string.
            • *int*: numeric :class:`asyncmiele.enums.DeviceType` value.
            • :class:`asyncmiele.models.device.DeviceIdentification` instance.
        """
        # ------------------------------------------------------------------
        # Resolve *device_type* string from the heterogeneous argument.
        # ------------------------------------------------------------------
        from asyncmiele.enums import DeviceType  # local import to avoid cycle
        from asyncmiele.models.device import DeviceIdentification

        if isinstance(device_ident, str):
            device_type = device_ident
        elif isinstance(device_ident, int):
            try:
                device_type = DeviceType(device_ident).name
            except ValueError as exc:
                raise ValueError(f"Unknown device-type code: {device_ident}") from exc
        elif isinstance(device_ident, DeviceIdentification):
            device_type = device_ident.device_type or device_ident.tech_type
            if not device_type:
                raise ValueError("DeviceIdentification lacks device_type/tech_type information")
        else:
            raise TypeError("device_ident must be str, int or DeviceIdentification")

        # ------------------------------------------------------------------
        # Locate and load JSON resource.
        # ------------------------------------------------------------------
        path = cls._resource_path(device_type)
        if not path.is_file():
            raise FileNotFoundError(
                f"No program catalogue for device-type '{device_type}' (expected {path})"
            )

        try:
            with path.open("r", encoding="utf-8") as fh:
                raw = json.load(fh)
        except Exception as exc:
            raise RuntimeError(f"Failed to parse catalogue file {path}: {exc}") from exc

        return cls.model_validate(raw)


# ---------------------------------------------------------------------------
# Payload builder
# ---------------------------------------------------------------------------

def _u16(value: int) -> bytes:
    """Return *value* encoded as big-endian unsigned-16."""
    if not 0 <= value <= 0xFFFF:
        raise ValueError("Value out of range for uint16")
    return value.to_bytes(2, "big")


def build_dop2_selection(program: Program, chosen_options: Mapping[int, int] | None = None) -> bytes:
    """Serialize *program* + *chosen_options* into a binary DOP2 payload.

    The binary format implemented here is a **minimal** representation that
    satisfies the local API:

    1. Two-byte *program-id* (big-endian).
    2. For each option present in *program.options* **in the original order**:
       • two-byte *option-id*
       • two-byte *value*

    Parameters
    ----------
    program
        Program instance obtained from :class:`ProgramCatalog`.
    chosen_options
        Mapping *option-id → value*.  Missing entries fall back to
        :pyattr:`Option.default`; if that is *None* a :class:`ValueError` is
        raised.

    Returns
    -------
    bytes
        The binary payload, padded to 16-byte boundary using
        :pyfunc:`asyncmiele.utils.crypto.pad_payload` (ASCII space padding).
    """
    chosen_options = dict(chosen_options or {})  # mutable local copy
    payload = bytearray()
    payload += _u16(program.id)

    for opt in program.options:
        value = chosen_options.pop(opt.id, opt.default)
        if value is None:
            raise ValueError(
                f"No value supplied for mandatory option id {opt.id} ({opt.name})"
            )
        payload += _u16(opt.id)
        payload += _u16(int(value))

    if chosen_options:
        unexpected = ", ".join(str(k) for k in chosen_options)
        raise ValueError(f"Unknown option id(s) for program: {unexpected}")

    return pad_payload(bytes(payload)) 
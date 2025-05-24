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
    def from_dict(cls, data: dict) -> "ProgramCatalog":
        """Create a program catalog directly from a dictionary.
        
        This method allows creating a catalog without needing to first write
        the data to a JSON file. The dictionary structure must match the expected
        schema used in the JSON catalog files.
        
        Parameters
        ----------
        data : dict
            Dictionary containing device_type and programs information
            
        Returns
        -------
        ProgramCatalog
            Initialized catalog instance
            
        Raises
        ------
        ValueError
            If the dictionary doesn't have the required structure
        
        Example
        -------
        >>> catalog_data = {
        ...     "device_type": "washing_machine",
        ...     "programs": [
        ...         {
        ...             "id": 1,
        ...             "name": "Cottons",
        ...             "options": [
        ...                 {
        ...                     "id": 10,
        ...                     "name": "Temperature",
        ...                     "default": 40,
        ...                     "allowed_values": [20, 30, 40, 60, 90]
        ...                 }
        ...             ]
        ...         }
        ...     ]
        ... }
        >>> catalog = ProgramCatalog.from_dict(catalog_data)
        """
        # Validate required fields
        if not isinstance(data, dict):
            raise ValueError("Data must be a dictionary")
            
        if "device_type" not in data:
            raise ValueError("Dictionary must contain 'device_type' field")
            
        if "programs" not in data:
            raise ValueError("Dictionary must contain 'programs' field")
        
        # Use Pydantic's built-in validation to validate the structure
        return cls.model_validate(data)

    @classmethod
    def for_device(cls, device_ident, custom_catalog: dict = None) -> "ProgramCatalog":
        """Load catalogue for *device_ident* (flexible argument).

        *device_ident* can be:
            • *str*: name such as "WashingMachine" or tech-type string.
            • *int*: numeric :class:`asyncmiele.enums.DeviceType` value.
            • :class:`asyncmiele.models.device.DeviceIdentification` instance.
            
        Parameters
        ----------
        device_ident : str, int, or DeviceIdentification
            Device identification to determine which catalog to load
        custom_catalog : dict, optional
            If provided, a custom catalog dictionary that will be used instead
            of loading from a file
            
        Returns
        -------
        ProgramCatalog
            Loaded catalog for the device
            
        Raises
        ------
        ValueError
            If device_ident is invalid or catalog file is not found
        """
        # If a custom catalog is provided, use it directly
        if custom_catalog is not None:
            # If the custom catalog has a device_type, make sure it matches
            if (isinstance(device_ident, str) and 
                "device_type" in custom_catalog and 
                custom_catalog["device_type"].lower() != device_ident.lower()):
                # Log a warning but still use the provided catalog
                import logging
                logging.getLogger(__name__).warning(
                    f"Custom catalog device_type '{custom_catalog['device_type']}' "
                    f"doesn't match requested device_type '{device_ident}'"
                )
                
            return cls.from_dict(custom_catalog)
            
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
    
    def to_dict(self) -> dict:
        """Convert the catalog to a dictionary for DeviceProfile storage.
        
        Returns
        -------
        dict
            Dictionary representation suitable for DeviceProfile.program_catalog
        """
        return self.model_dump()
    
    def get_all_programs(self) -> List[dict]:
        """Get all programs as a list of dictionaries.
        
        This method provides a simple interface for getting program information
        in a format suitable for API responses and DeviceProfile integration.
        
        Returns
        -------
        List[dict]
            List of program dictionaries with id, name, and options
        """
        programs = []
        for program in self.programs:
            program_dict = {
                "id": program.id,
                "name": program.name,
                "options": []
            }
            
            for option in program.options:
                option_dict = {
                    "id": option.id,
                    "name": option.name,
                    "default": option.default,
                    "allowed_values": option.allowed_values
                }
                program_dict["options"].append(option_dict)
                
            programs.append(program_dict)
            
        return programs


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
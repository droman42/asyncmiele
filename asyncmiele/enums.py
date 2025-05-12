from enum import IntEnum
import json
import importlib.resources


class Status(IntEnum):
    NoUse = 0
    Off = 1
    On = 2
    Programmed = 3
    WaitingToStart = 4
    Running = 5
    Paused = 6
    EndedSuccessfully = 7
    Failure = 8
    Abort = 9
    Idle = 10
    Rinse = 11
    Service = 12


class ProgramPhase(IntEnum):
    NotUsed = 0
    Progress = 1
    WashingMachineIdle = 256
    WashingMachinePreWash = 257
    WashingMachineSoak = 258
    WashingMachineWashing = 260
    WashingMachineRinse = 261
    WashingMachineFinished = 268


class ProgramId(IntEnum):
    NotSelected = 0
    Automatic = 1
    WhitesCottons = 2
    MinimumIron = 3
    Wool = 4


class DeviceType(IntEnum):
    NoUse = 0
    WashingMachine = 1
    TumbleDryer = 2
    Dishwasher = 7
    Oven = 12


# Dynamically extend enums from resources/enums.json (generated from pymiele)
try:
    data_path = importlib.resources.files("resources").joinpath("enums.json")
    with open(data_path, "r", encoding="utf-8") as fh:
        extra = json.load(fh)

    STATUS_NAMES = {int(k): v for k, v in extra.get("Status", {}).items()}
    PROGRAM_NAMES = {int(k): v for k, v in extra.get("ProgramId", {}).items()}
    ICON_MAP = extra.get("Icons", {})
except Exception:
    # Resource file missing or parsing failed – ignore silently.
    STATUS_NAMES = {}
    PROGRAM_NAMES = {}
    ICON_MAP = {}

# Expose helper functions

def status_name(code: int) -> str | None:
    """Return human-readable name for status code (or None)."""
    return STATUS_NAMES.get(code) or (Status(code).name if code in Status._value2member_map_ else None)


def program_name(code: int) -> str | None:
    """Return program name if known."""
    return PROGRAM_NAMES.get(code)


def icon_for(key: str) -> str | None:
    """Return mdi icon string for given key (e.g. 'Appliance.WASHING_MACHINE')."""
    return ICON_MAP.get(key) 
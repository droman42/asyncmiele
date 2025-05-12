import json
import pytest
from asyncmiele.models.response import MieleResponse
from asyncmiele.models.device import DeviceState
from asyncmiele.enums import Status as StatusEnum, ProgramPhase as ProgramPhaseEnum


def build_response(payload):
    return MieleResponse(data=payload, root_path="/Devices/1234/State")


def test_enum_conversion():
    payload = {
        "status": {"value_raw": 5, "value_localized": "Running"},
        "programPhase": {"value_raw": 260, "value_localized": "Washing"},
    }

    state = DeviceState.from_response(build_response(payload))

    assert state.status_enum == StatusEnum.Running
    assert state.program_phase_enum == ProgramPhaseEnum.WashingMachineWashing 
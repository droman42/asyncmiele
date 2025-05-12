from typing import Optional
from pydantic import BaseModel

from asyncmiele.models.device import DeviceIdentification, DeviceState
from asyncmiele.dop2.models import DeviceCombinedState


class DeviceSummary(BaseModel):
    id: str
    name: str

    ident: DeviceIdentification
    state: DeviceState
    combined_state: Optional[DeviceCombinedState] = None

    progress: Optional[float] = None  # 0.0–1.0
    ready_to_start: Optional[bool] = None 
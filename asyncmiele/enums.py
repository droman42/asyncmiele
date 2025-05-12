from enum import IntEnum


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
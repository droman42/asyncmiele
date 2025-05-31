"""
Enumerations for Miele device types, states, and constants.
Aligned with MieleRESTServer reference implementation.
"""

from enum import Enum, IntEnum
import json
import importlib.resources


class DeviceType(Enum):
    """Miele device types."""
    WASHING_MACHINE = "WashingMachine"
    DRYER = "Dryer"
    DISHWASHER = "Dishwasher"
    OVEN = "Oven"
    COFFEE_MAKER = "CoffeeMaker"
    HOOD = "Hood"
    FRIDGE = "Fridge"
    FREEZER = "Freezer"
    WASHER_DRYER = "WasherDryer"


# Complete enums from MieleRESTServer reference implementation

class DeviceId(IntEnum):
    """Device ID enumeration from MieleRESTServer."""
    NoDevice = 0
    WashingMachineEntryLevel = 1
    DryerEntryLevel = 2
    WashingMachineSemiPro = 3
    DryerSemiPro = 4
    WashingMachinePro = 5
    DryerPro = 6
    DishwasherEntryLevel = 7
    DishwasherSemiPro = 8
    DishwasherPro = 9
    Cooker = 10
    CookerWithMicrowave = 11
    Oven = 12
    OvenWithMicrowave = 13
    WasherDryer = 24


class ProtocolType(IntEnum):
    """Protocol type enumeration from MieleRESTServer."""
    Unknown = 0
    Uart = 1
    MeterbusDop1 = 2
    MeterbusDop2 = 3
    SenseWireDop2 = 4


class DetergentType(IntEnum):
    """Detergent type enumeration from MieleRESTServer."""
    NoDetergent = 0
    UltraPhase1 = 1
    UltraPhase2 = 2
    UltraWhite = 3
    UltraColor = 4


class UserRequest(IntEnum):
    """User request enumeration from MieleRESTServer."""
    NoRequest = 0
    Start = 1
    SetInteriorLightOn = 12141
    SetInteriorLightOff = 12142


class XkmRequest(IntEnum):
    """XKM request enumeration from MieleRESTServer."""
    NoRequest = 0
    Reset = 1
    FactorySettings = 2
    SoftApCustomer = 3
    SystemCreate = 4


class ApplianceState(IntEnum):
    """Appliance state enumeration from MieleRESTServer."""
    Unknown = 0
    Off = 1
    Synchronizing = 2
    Initializing = 3
    Normal = 4
    Demonstration = 5
    Service = 6
    Error = 7
    Check = 8
    Standby = 9
    Supervisory = 10
    ShowWindow = 11


class OperationState(IntEnum):
    """Operation state enumeration from MieleRESTServer."""
    Unknown = 0
    EndOfLine = 1
    Service = 2
    Settings = 3
    InitialSettings = 4
    SelectProgram = 5
    RunProgram = 6
    RunDelay = 7
    RunMaintenanceProcess = 8
    VoltageBrownout = 9
    WelcomeScreen = 10
    Locked = 11
    TimeSettingScreen = 12
    DisplayOff = 15
    ColdRising = 21
    NormalRinsing = 22
    EmergencyStop = 32


class ProcessState(IntEnum):
    """Process state enumeration from MieleRESTServer."""
    Unknown = 0
    NoProgram = 1
    ProgramSelected = 2
    ProgramStarted = 3
    ProgramRunning = 4
    ProgramStop = 5


class ProgramType(IntEnum):
    """Program type enumeration from MieleRESTServer."""
    BuiltInFunction = 1
    UserDefined = 2
    Automatic = 3
    CleaningProgram = 4
    CustomerService = 5
    Helper = 6


class RemoteControl(Enum):
    """Remote control enumeration from MieleRESTServer."""
    Disabled = 0
    EnabledButNotPossible = 7
    Full = 15
    Unknown = 2147483647


class DeviceTypeMiele(Enum):
    """Device type enumeration from MieleRESTServer (more comprehensive)."""
    NoUse = 0
    WashingMachine = 1
    TumbleDryer = 2
    WashingMachineSemiPro = 3
    TumbleDryerSemiPro = 4
    WashingMachinePro = 5
    TumbleDryerPro = 6
    Dishwasher = 7
    DishwasherSemiPro = 8
    DishwasherPro = 9
    Range = 10
    RangeWithMicrowave = 11
    Oven = 12
    OvenWithMicrowave = 13
    Cooktop = 14
    SteamOven = 15
    Microwave = 16
    CoffeeMaker = 17
    Hood = 18
    Fridge = 19
    Freezer = 20
    FridgeWithFreezer = 21
    ChestFreezer = 22
    RobotVacuum = 23
    WasherDryer = 24
    WarmingDrawer = 25
    BeverageMaker = 26


class DryingStep(Enum):
    """Drying step enumeration from MieleRESTServer."""
    ExtraDry = 0
    NormalPlus = 1
    Normal = 2
    SlightlyDry = 3
    HandIron1 = 4
    HandIron2 = 5
    MachineIron = 6
    HygieneDry = 7


class Light(Enum):
    """Light enumeration from MieleRESTServer."""
    NotSupported = 0
    Enabled = 1
    Disabled = 2


class Status(Enum):
    """Status enumeration from MieleRESTServer."""
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
    SuperFreeze = 13
    SuperCool = 14
    SuperHeat = 15
    Default = 144
    Lock = 145
    SuperCoolSuperFreeze = 146


class ProgramId(Enum):
    """Program ID enumeration from MieleRESTServer."""
    NotSelected = 0
    Automatic = 1
    WhitesCottons = 2
    MinimumIron = 3
    Wool = 4
    Delicate = 5
    HotAir = 6
    ColdAir = 7
    Express = 8
    Cotton = 9
    Gentle = 10
    CottonHygiene = 11
    Cottons40Celsius = 27
    Cottons25Celsius = 28
    MinimumIron25Celsius = 29
    SyntheticBedding = 30
    NaturalBedding = 31
    Microfiber = 32
    WetcareIntensive = 33
    WetcareSensitive = 34
    WetcareSilk = 35
    LargeItems = 36
    Reactivate = 37
    Smoothing = 38
    CottonsWhiteHygiene = 39
    ProgramFortyCelsius = 59


class ProgramPhase(Enum):
    """Program phase enumeration from MieleRESTServer."""
    NotUsed = 0
    Progress = 1
    BatteryCharging = 2
    WashingMachineIdle = 256
    WashingMachinePreWash = 257
    WashingMachineSoak = 258
    WashingMachinePreRinse = 259
    WashingMachineWashing = 260
    WashingMachineRinse = 261
    WashingMachineRinseHold = 262
    WashingMachineClean = 263
    WashingMachineCooldown = 264
    WashingMachineDrain = 265
    WashingMachineSpin = 266
    WashingMachineAntiCrease = 267
    WashingMachineFinished = 268
    WashingMachineVenting = 269
    WashingMachineStarch = 270
    WashingMachineMoisting = 271
    WashingMachineRemoisting = 272
    WashingMachineHygiene = 279
    WashingMachineDrying = 280
    WashingMachineDisinfection = 285
    WashingMachineSteamSmoothing = 295
    TumbleDryerIdle = 512
    TumbleDryerProgramStart = 513
    TumbleDryerDrying = 514
    TumbleDryerMachineIron = 515
    TumbleDryerHandIron2 = 516
    TumbleDryerNormal = 517
    TumbleDryerNormalPlus = 518
    TumbleDryerComfortCooldown = 519
    TumbleDryerHandIron1 = 520
    TumbleDryerAntiCreaseFinish = 521
    TumbleDryerFinished = 522
    TumbleDryerExtraDry = 523
    TumbleDryerHandIronWithoutDrop = 524
    TumbleDryerHygieneDrying = 525
    TumbleDryerWetting = 526
    TumbleDryerSpin = 527
    TumbleDryerFanActive = 528
    TumbleDryerHotAir = 529
    TumbleDryerSteamSmooth = 530
    TumbleDryerCooling = 531
    TumbleDryerFluff = 532
    TumbleDryerRinse = 533
    TumbleDryerSmooth = 534
    TumbleDryerUnknown1 = 535
    TumbleDryerRemoteStart = 536
    TumbleDryerDelayedRun = 537
    TumbleDryerSlightlyDry = 538
    TumbleDryerSafetyCooldown = 539
    DishwasherNoProgram = 1792
    DishwasherRegenerate = 1793
    DishwasherPreRinse = 1794
    DishwasherClean = 1795
    DishwasherRinse = 1796
    DishwasherRinseInterim = 1797
    DishwasherRinseClear = 1798
    DishwasherDrying = 1799
    DishwasherFinished = 1800
    DishwasherPreRinse2 = 1801
    OvenCooldown = 3072
    OvenHeating = 3073
    OvenTempHold = 3074
    OvenDoorOpen = 3075
    OvenPyrolyze = 3076
    OvenMicrowave = 3077
    OvenProgramDone = 3078
    OvenLight = 3079
    OvenSearing = 3080
    OvenRoasting = 3081
    OvenDefrost = 3082
    OvenCooldown2 = 3083
    OvenEnergySave = 3084
    OvenHoldWarm = 3094
    OvenDescale = 3098
    OvenPreheat = 3099


class SfValueId(IntEnum):
    """SF Value ID enumeration from MieleRESTServer (partial - most commonly used)."""
    NONE = 0
    Global_Language = 10000
    Global_DisplayBrightness = 10001
    Global_DisplayContrast = 10002
    Global_VolumeToneSignal = 10003
    Global_VolumeToneKey = 10004
    Global_DisplayTime = 10005
    Global_TimePresentation = 10006
    Global_WaterHardness = 10010
    Global_SuperVisionDisplay = 10011
    
    Washer_DetergentTypeContainerOne = 12005
    Washer_DetergentAmountContainerOne = 12006
    Washer_DetergentTypeContainerTwo = 12007
    Washer_DetergentAmountContainerTwo = 12008
    Washer_SoilingDefault = 12009
    Washer_Soiling = 12010
    Washer_TimeDisplayFormat = 12011
    Washer_SynchronizeTime = 12012
    Washer_BuzzerVolume = 12015
    Washer_KeypadTone = 12016
    Washer_PinCodeEnable = 12017
    Washer_TemperatureUnit = 12021
    Washer_DisplayBrightness = 12022
    Washer_RemoteControl = 12039
    Washer_NetworkRegistration = 12194
    Washer_Remote = 12195
    Washer_FactoryReset = 12196
    Washer_RemoteUpdate = 12143
    
    Dryer_FactoryDefault = 16001
    Dryer_Language = 16002
    Dryer_ClockFormat = 16003
    Dryer_TimeSynchronize = 16004
    Dryer_BuzzerOn = 16012
    Dryer_FinishToneVolume = 16013
    Dryer_KeypadTone = 16014
    Dryer_DisplayBrightness = 16021

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


# Add new enums after the existing UserRequest enum for protocol consistency

class ProcessAction(IntEnum):
    """Process action enumeration for program control."""
    NO_OPERATION = 0           # Default state
    START_RESUME = 1           # Start or resume program
    STOP = 2                   # Stop/cancel program
    PAUSE = 3                  # Pause program (device dependent)
    START_SUPERFREEZING = 4    # Start SuperFreeze (refrigeration)
    STOP_SUPERFREEZING = 5     # Stop SuperFreeze (refrigeration)
    START_SUPERCOOLING = 6     # Start SuperCool (refrigeration)
    STOP_SUPERCOOLING = 7      # Stop SuperCool (refrigeration)
    DISABLE_GAS = 8            # Disable gas supply (gas appliances)
    ENABLE_GAS = 9             # Enable gas supply (gas appliances)


class DeviceAction(IntEnum):
    """Device action enumeration for device state control."""
    NO_ACTION = 0              # Default state
    POWER_ON = 1               # Power on device
    WAKE_UP = 2                # Wake up device (already implemented)
    ENTER_STANDBY = 3          # Enter standby/deep sleep


# ... existing code ... 
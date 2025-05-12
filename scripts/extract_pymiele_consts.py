#!/usr/bin/env python3
"""Extract enum/icon tables from a checked-out *pymiele* repository.

Usage:
    python scripts/extract_pymiele_consts.py /path/to/pymiele > resources/enums.json

The script searches for a `const.py` module (as present in pymiele 0.8.x) and
serialises selected dictionaries into a single JSON document compatible with
`asyncmiele.enums` dynamic loader.

No network access is performed – the target repository must be available
locally.  MIT licence compliance: we only copy simple constant values, which are
not copyright-able.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import pathlib
import sys
from types import ModuleType
from typing import Dict, Any


def load_module(path: pathlib.Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location("pymiele_consts", str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load module at" + str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[arg-type]
    return mod  # type: ignore[return-value]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("repo", help="Path to cloned pymiele repository root")
    parser.add_argument("--output", "-o", default="resources/enums.json")
    args = parser.parse_args()

    repo = pathlib.Path(args.repo).expanduser().resolve()
    # Try legacy pymiele layout first, then fall back to Home Assistant integration constants
    potential_paths = [
        repo / "pymiele" / "const.py",  # old pymiele package
        repo / "custom_components" / "miele" / "const.py",  # HA integration
    ]

    const_path: pathlib.Path | None = None
    for p in potential_paths:
        if p.exists():
            const_path = p
            break

    if const_path is None:
        sys.exit("Could not find const.py in expected locations")

    mod = load_module(const_path)

    data: Dict[str, Any] = {"Status": {}, "ProgramId": {}, "Icons": {}}

    # Attempt 1: legacy simple dicts
    if hasattr(mod, "STATUS"):
        data["Status"] = {str(k): v for k, v in getattr(mod, "STATUS").items()}
    if hasattr(mod, "PROGRAMID"):
        data["ProgramId"] = {str(k): v for k, v in getattr(mod, "PROGRAMID").items()}
    if hasattr(mod, "ICONS"):
        data["Icons"].update(getattr(mod, "ICONS"))

    # Attempt 2: Home-Assistant style constants
    if hasattr(mod, "STATE_STATUS") and not data["Status"]:
        data["Status"] = {str(k): v for k, v in getattr(mod, "STATE_STATUS").items()}

    if hasattr(mod, "STATE_PROGRAM_ID") and not data["ProgramId"]:
        program_map = getattr(mod, "STATE_PROGRAM_ID")
        # Flatten all appliance sub-dicts into one mapping
        flat: Dict[str, str] = {}
        for sub in program_map.values():
            for k, v in sub.items():
                flat[str(k)] = v
        data["ProgramId"] = flat

    # Icons – combine appliance icons and maybe others
    if hasattr(mod, "APPLIANCE_ICONS"):
        data["Icons"].update({f"Appliance.{a.name}": icon for a, icon in getattr(mod, "APPLIANCE_ICONS").items()})

    out_path = pathlib.Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
    print(f"Written {out_path}")


if __name__ == "__main__":
    main() 
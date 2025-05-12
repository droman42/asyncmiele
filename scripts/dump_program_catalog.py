import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Mapping, Any, List, Dict

from asyncmiele.api.client import MieleClient
from asyncmiele.enums import DeviceType

# ---------------------------------------------------------------------------
# Minimal binary decoders for the two DOP2 leaves we need.
# These are deliberately conservative: the format has been observed to be
# stable across appliances but is *not* officially documented.
# ---------------------------------------------------------------------------
import struct

# Helpers -------------------------------------------------------------------

U16 = struct.Struct('>H')  # network-byte-order unsigned-16


def _u16(data: bytes, offset: int) -> int:
    """Read one uint16 from *data* starting at *offset*."""
    return U16.unpack_from(data, offset)[0]


# Leaf 14/1570 – Programme list ------------------------------------------------
# Each entry is 12 bytes in firmware captured so far:
#   0–1 : programme-id  (uint16)
#   2–3 : string-id     (uint16)  name in string table 14/2570
#   4–5 : option-group  (uint16)
#   6–11: reserved / flags
_ENTRY_SIZE = 12


def parse_program_list(payload: bytes) -> List[Dict[str, Any]]:
    if len(payload) % _ENTRY_SIZE:
        raise ValueError(f"Program list length {len(payload)} not a multiple of {_ENTRY_SIZE}")

    programs: List[Dict[str, Any]] = []
    for ofs in range(0, len(payload), _ENTRY_SIZE):
        pid = _u16(payload, ofs)
        str_id = _u16(payload, ofs + 2)
        opt_grp = _u16(payload, ofs + 4)
        programs.append({
            "id": pid,
            "name_id": str_id,
            "option_group": opt_grp,
            "options": [],  # filled later
        })
    return programs


# Leaf 14/1571 – option list per programme ----------------------------------
# Layout seen so far (8 bytes per entry):
#   0–1 : option-id   (uint16)
#   2–3 : string-id   (uint16)
#   4–5 : default     (uint16)
#   6–7 : reserved / flags
_OPT_SIZE = 8


def parse_option_list(payload: bytes) -> List[Dict[str, Any]]:
    if len(payload) % _OPT_SIZE:
        raise ValueError(f"Option list length {len(payload)} not a multiple of {_OPT_SIZE}")
    items: List[Dict[str, Any]] = []
    for ofs in range(0, len(payload), _OPT_SIZE):
        oid = _u16(payload, ofs)
        str_id = _u16(payload, ofs + 2)
        default = _u16(payload, ofs + 4)
        items.append({
            "id": oid,
            "name_id": str_id,
            "default": default,
        })
    return items


# Leaf 14/2570 – string table -------------------------------------------------
# Binary blob of UTF-8 null-terminated strings.  The *string-id* is an index
# into that table, counting only *completed strings* (id 0 = first string).


def build_string_map(blob: bytes) -> Mapping[int, str]:
    parts = blob.split(b"\x00")
    # Last entry after final NUL is empty – drop it
    strings = [s.decode("utf-8", errors="replace") for s in parts if s]
    return {idx: text for idx, text in enumerate(strings)}


# ---------------------------------------------------------------------------
# Catalogue builder
# ---------------------------------------------------------------------------

async def build_catalogue(client: MieleClient, device_id: str) -> Dict[str, Any]:
    # Read programme list ----------------------------------------------------
    leaf_1570 = await client.dop2_read_leaf(device_id, 14, 1570)
    programs = parse_program_list(leaf_1570)

    # Per-programme option lists --------------------------------------------
    for prog in programs:
        pid = prog["id"]
        leaf_1571 = await client.dop2_read_leaf(device_id, 14, 1571, idx1=pid)
        prog["options"] = parse_option_list(leaf_1571)

    # Resolve human-readable strings ----------------------------------------
    string_blob = await client.dop2_read_leaf(device_id, 14, 2570)
    str_map = build_string_map(string_blob)

    for p in programs:
        p["name"] = str_map.get(p.pop("name_id"), f"program_{p['id']}")
        for opt in p["options"]:
            opt["name"] = str_map.get(opt.pop("name_id"), f"opt_{opt['id']}")

    # Identify device-type ---------------------------------------------------
    ident = await client.get_device_ident(device_id)
    if isinstance(ident.device_type, int):
        device_type = DeviceType(ident.device_type).name
    else:
        device_type = ident.device_type or ident.tech_type or "unknown"

    return {
        "device_type": device_type,
        "programs": programs,
    }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _make_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Dump programme catalogue (DOP2 14/1570+1571) from a Miele appliance "
                    "and store it as JSON so that asyncmiele.programs.ProgramCatalog can load it.")
    p.add_argument("--host", required=True, help="IP or hostname of the appliance")
    p.add_argument("--device-id", required=True, help="Device identifier (12 digits)")
    p.add_argument("--group-id", required=True, metavar="HEX32",
                   help="GroupID in hex (32 characters / 16 bytes)")
    p.add_argument("--group-key", required=True, metavar="HEX32",
                   help="GroupKey in hex (32 characters / 16 bytes)")
    p.add_argument("--out", default=None, help="Output path (default: resources/programs/<device>.json)")
    p.add_argument("--wake", action="store_true", help="Send wake-up command before reading")
    return p


async def _async_main(args):
    client = MieleClient(
        host=args.host,
        group_id=bytes.fromhex(args.group_id),
        group_key=bytes.fromhex(args.group_key),
    )

    if args.wake:
        try:
            await client.wake_up(args.device_id)
        except Exception as exc:  # noqa: BLE001 – want to continue even if wake fails
            print(f"[WARN] wake_up failed: {exc}", file=sys.stderr)
            await asyncio.sleep(1)

    catalog = await build_catalogue(client, args.device_id)

    # Determine output path --------------------------------------------------
    if args.out:
        out_path = Path(args.out)
    else:
        base = Path(__file__).resolve().parent.parent / "resources" / "programs"
        base.mkdir(parents=True, exist_ok=True)
        fname = catalog["device_type"].lower().replace(" ", "_") + ".json"
        out_path = base / fname

    with out_path.open("w", encoding="utf-8") as fh:
        json.dump(catalog, fh, indent=2, ensure_ascii=False)

    print(f"Written catalogue for {catalog['device_type']} -> {out_path}")


def main():
    parser = _make_argparser()
    args = parser.parse_args()
    try:
        asyncio.run(_async_main(args))
    except KeyboardInterrupt:
        print("Aborted by user", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main() 
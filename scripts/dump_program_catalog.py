import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Dict, Any

from asyncmiele.api.client import MieleClient
from asyncmiele.enums import DeviceType
from asyncmiele.utils.program_parser import build_string_map

# ---------------------------------------------------------------------------
# Catalogue builder
# ---------------------------------------------------------------------------

async def build_catalogue(client: MieleClient, device_id: str) -> Dict[str, Any]:
    """Build a program catalog by extracting it from a device.
    
    This tries both the newer leaf method (2/1584) and the older method (14/1570)
    to maximize compatibility across different device models and firmware versions.
    """
    # Use the client's extract_program_catalog method which handles both approaches
    catalog = await client.extract_program_catalog(device_id)
    
    # If we got a successful result, return it
    if catalog and catalog.get("programs"):
        return catalog
        
    # If all approaches failed, raise an error
    raise ValueError(f"Failed to extract program catalog from device {device_id}")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _make_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Dump programme catalogue from a Miele appliance "
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
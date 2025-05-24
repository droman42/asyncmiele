"""Example: wake up and (optionally) remotely start a device.

Usage:
    python examples/remote_start.py --host 192.168.1.50 --device 000123456789 --start

The --start flag is opt-in and will fail unless you either:
  • pass --force, or
  • have set asyncmiele.config.settings.enable_remote_start = True elsewhere.
"""

import asyncio
import argparse

from asyncmiele import MieleClient, Appliance
from asyncmiele.config import settings


async def main():
    parser = argparse.ArgumentParser(description="Wake up / remote-start Miele device")
    parser.add_argument("--host", required=True, help="IP address of XKM / appliance")
    parser.add_argument("--group-id", required=True, help="GroupID in hex")
    parser.add_argument("--group-key", required=True, help="GroupKey in hex")
    parser.add_argument("--device", required=True, help="Device route / ID")
    parser.add_argument("--start", action="store_true", help="Actually trigger start")
    parser.add_argument("--force", action="store_true", help="Bypass safety flag for start")
    args = parser.parse_args()

    client = MieleClient.from_hex(args.host, args.group_id, args.group_key)

    async with client:
        # Create appliance with proper architecture - client as dependency
        appliance = Appliance(client, args.device)

        print("Waking up …")
        await appliance.wake_up()

        if args.start:
            print("Checking remote-start capability …")
            can_start = await appliance.can_remote_start()
            print("can_remote_start =", can_start)
            if not can_start:
                print("Device not ready – aborting")
                return

            if args.force:
                allow = True
            else:
                allow = settings.enable_remote_start
            if not allow:
                print("Remote-start disabled. Use --force or enable via settings.")
                return

            print("Starting program …")
            await appliance.remote_start(allow_remote_start=True)
            print("Remote start command sent")


if __name__ == "__main__":
    asyncio.run(main()) 
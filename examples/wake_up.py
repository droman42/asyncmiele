"""Wake up a sleeping Miele appliance.

Usage:
    python examples/wake_up.py --host 192.168.1.50 --device 000123456789 --group-id ... --group-key ...
"""

import asyncio
import argparse

from asyncmiele import MieleClient, Appliance


async def main():
    parser = argparse.ArgumentParser(description="Wake up Miele device")
    parser.add_argument("--host", required=True)
    parser.add_argument("--group-id", required=True)
    parser.add_argument("--group-key", required=True)
    parser.add_argument("--device", required=True)
    args = parser.parse_args()

    client = MieleClient.from_hex(args.host, args.group_id, args.group_key)

    async with client:
        # Create appliance with proper architecture - client as dependency
        appliance = Appliance(client, args.device)
        await appliance.wake_up()
        print("Wake-up command sent")


if __name__ == "__main__":
    asyncio.run(main()) 
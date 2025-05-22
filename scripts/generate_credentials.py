#!/usr/bin/env python3
"""
Generate random GroupID and GroupKey credentials for Miele device provisioning.

This script provides a command-line interface for generating secure random
credentials to use when configuring Miele devices.
"""

import argparse
import json
import sys
from typing import Dict, Any

from asyncmiele.models.credentials import MieleCredentials


def _make_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Generate random GroupID and GroupKey credentials for Miele device provisioning"
    )
    p.add_argument("--format", choices=["json", "hex"], default="json",
                   help="Output format (default: json)")
    p.add_argument("--out", default=None, 
                   help="Output file path (default: stdout)")
    p.add_argument("--pretty", action="store_true",
                   help="Pretty-print JSON output")
    return p


def generate_and_output(args: argparse.Namespace) -> None:
    """Generate credentials and output in the specified format."""
    # Generate random credentials
    credentials = MieleCredentials.generate_random()
    
    # Format the output
    if args.format == "json":
        if args.pretty:
            output = json.dumps(
                credentials.model_dump(),
                indent=2,
                ensure_ascii=False
            )
        else:
            output = credentials.model_dump_json()
    else:  # hex format
        output = f"GroupID: {credentials.get_id_hex()}\nGroupKey: {credentials.get_key_hex()}"
    
    # Write to file or stdout
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Credentials written to {args.out}")
    else:
        print(output)


def main():
    parser = _make_argparser()
    args = parser.parse_args()
    try:
        generate_and_output(args)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main() 
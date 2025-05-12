"""Example: build DOP2 payload to select a program with options.

Run with:
    python examples/select_program.py

This does **not** send the payload – it only shows how to obtain
program information offline and prepare the binary blob for
:pymeth:`asyncmiele.MieleClient.dop2_write_leaf` (unit 2 / attribute 300
PS_SELECT).
"""

from asyncmiele import ProgramCatalog, build_dop2_selection
from binascii import hexlify

# Pick a catalogue -----------------------------------------------------------------
cat = ProgramCatalog.for_device("WashingMachine")
print(f"Loaded catalogue for {cat.device_type}: {len(cat.programs)} programs\n")

# Choose a program ------------------------------------------------------------------
program = cat.programs_by_name["Cottons"]

# Use non-default option values -----------------------------------------------------
chosen = {10: 60, 11: 1600}  # °C and RPM
payload = build_dop2_selection(program, chosen)

print(f"Program '{program.name}' ({program.id}) -> payload {hexlify(payload).decode()}")
print(f"Length (padded): {len(payload)} bytes") 